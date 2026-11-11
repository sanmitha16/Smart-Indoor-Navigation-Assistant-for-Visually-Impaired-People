"""Hands-free voice commands for the two modes. Offline: Vosk listening for a fixed list of phrases.

Say:   "activate read mode"      (or just "read mode")
       "activate object mode"    (or just "object mode")
       "find keys"               (also "find my keys", "find the keys"; the words are listed in TARGETS)
       "repeat"                  repeat the last answer
       "stop"                    stop talking

Needs:  pip install vosk sounddevice
        a Vosk model folder inside the project folder (see README.txt)

Test the microphone alone:   python voice.py
List the microphones:        python voice.py --devices
Choose a microphone:         set MIC_DEVICE=2   (Windows)   or   export MIC_DEVICE=2   (Pi)
"""
import glob, json, os, platform, queue, threading, time

SAMPLE_RATE = 16000
BLOCK = 4000          # 0.25 s of audio per chunk
# Seconds to ignore the microphone after the device stops talking. A Bluetooth speaker plays the
# last words a moment after the program has finished, so on the Pi the wait is longer.
# Change it without editing: export VOICE_TAIL=1.5   (Pi)   or   set VOICE_TAIL=1.5   (Windows)
TAIL = float(os.environ.get("VOICE_TAIL") or (1.2 if platform.system() == "Linux" else 0.7))
HELP_EVERY = 6        # at most one "I did not understand" message per this many seconds
MIC_DEVICE = os.environ.get("MIC_DEVICE")

# Objects the user can ask for with "find ...". The recogniser can only hear words in this list.
# Add your own (lower case). Any object NOT in the list is still named by "activate object mode".
TARGETS = [
    "keys", "door", "chair", "table", "phone", "bottle", "water bottle", "bag", "cup", "mug",
    "remote", "remote control", "switch", "light switch", "bed", "window", "laptop", "book",
    "wallet", "glasses", "stairs", "sofa", "fan", "plate", "pen", "charger", "umbrella",
    "toilet", "sink", "bucket",
]


def _build_commands():
    c = {}
    for p in ("activate read mode", "activate reading mode", "read mode", "reading mode"):
        c[p] = ("read", None)
    for p in ("activate object mode", "object mode"):
        c[p] = ("object", None)
    for p in ("repeat", "repeat that", "say that again"):
        c[p] = ("repeat", None)
    for p in ("stop", "stop talking"):
        c[p] = ("stop", None)
    for w in TARGETS:
        for pre in ("find ", "find my ", "find the "):
            c[pre + w] = ("object", w)
    return c


COMMANDS = _build_commands()          # exact phrase -> (action, target)


def parse(text):
    """Turn what the recogniser heard into (action, target), or None. Only exact known phrases count."""
    t = " ".join(w for w in (text or "").lower().split() if w != "[unk]")
    return COMMANDS.get(t)


def _looks_like_command(text):
    words = (text or "").lower().split()
    return bool(words) and words[0] in ("activate", "find")


def _to_16k(raw, src_rate):
    """Convert one chunk of 16-bit mono audio from src_rate to 16000 Hz (for microphones that cannot do 16000)."""
    import numpy as np
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if len(x) < 2:
        return b""
    n = int(round(len(x) * SAMPLE_RATE / src_rate))
    y = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
    return y.astype(np.int16).tobytes()


def _find_model():
    env = os.environ.get("VOSK_MODEL")
    if env and os.path.isdir(os.path.join(env, "am")):
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    for pat in ("vosk-model*", "model"):
        for p in sorted(glob.glob(os.path.join(here, pat))):
            if os.path.isdir(os.path.join(p, "am")):
                return p
    return None


def _run(action, target, handlers):
    kind = action
    print(f"VOICE: {kind}" + (f" ({target})" if target else ""), flush=True)
    try:
        if kind == "object":
            handlers["object"](target)
        else:
            handlers[kind]()
    except Exception as e:                # never let one bad command stop the listener
        print("Voice command error:", e, flush=True)


def _listen(rec, audio, handlers, speaker, stream):
    tail_until = 0.0
    need_reset = False
    last_help = 0.0
    while True:
        data = audio.get()
        now = time.time()
        talking = not speaker.idle()
        if talking:
            tail_until = now + TAIL
            need_reset = True
        elif now < tail_until:
            continue                      # just stopped talking: skip the echo tail
        elif need_reset:
            try:
                rec.Reset()               # forget anything heard while the device was talking
            except Exception:
                pass
            need_reset = False
        done = rec.AcceptWaveform(data)
        if talking:
            # While the device talks there is no pause for the recogniser to finish a sentence,
            # so watch the partial result and accept only "stop".
            if done:
                text = json.loads(rec.Result()).get("text", "")
            else:
                text = json.loads(rec.PartialResult()).get("partial", "")
            action = parse(text)
            if action and action[0] == "stop":
                try:
                    rec.Reset()
                except Exception:
                    pass
                _run("stop", None, handlers)
            continue
        if not done:
            continue
        text = json.loads(rec.Result()).get("text", "")
        action = parse(text)
        if action:
            _run(action[0], action[1], handlers)
        elif _looks_like_command(text) and now - last_help > HELP_EVERY:
            last_help = now
            print("VOICE: not understood:", text, flush=True)
            speaker.say("Sorry. Say activate read mode, or activate object mode.")


def start(handlers, speaker):
    """Load the model, open the microphone and start listening in the background.
    Raises RuntimeError with a readable reason if voice cannot start."""
    try:
        import sounddevice as sd
        from vosk import Model, KaldiRecognizer, SetLogLevel
    except Exception as e:
        raise RuntimeError(f"packages missing ({e}). Run: pip install vosk sounddevice")
    path = _find_model()
    if not path:
        raise RuntimeError("no Vosk model folder found next to voice.py (see README.txt)")
    SetLogLevel(-1)
    model = Model(path)
    grammar = json.dumps(list(COMMANDS) + ["[unk]"])
    rec = KaldiRecognizer(model, SAMPLE_RATE, grammar)
    audio = queue.Queue(maxsize=40)

    device = int(MIC_DEVICE) if MIC_DEVICE and MIC_DEVICE.isdigit() else MIC_DEVICE
    src_rate = SAMPLE_RATE

    def on_audio(indata, frames, t, status):
        try:
            raw = bytes(indata)
            audio.put_nowait(raw if src_rate == SAMPLE_RATE else _to_16k(raw, src_rate))
        except queue.Full:
            pass

    try:
        stream = sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK, dtype="int16",
                                   channels=1, device=device, callback=on_audio)
        stream.start()
    except Exception as first:
        # Many USB microphones cannot record at 16000 Hz: open at their own rate and convert
        try:
            src_rate = int(sd.query_devices(device, "input")["default_samplerate"])
            stream = sd.RawInputStream(samplerate=src_rate, blocksize=int(BLOCK * src_rate / SAMPLE_RATE),
                                       dtype="int16", channels=1, device=device, callback=on_audio)
            stream.start()
            print(f"Microphone opened at {src_rate} Hz and converted to 16000 Hz", flush=True)
        except Exception as e:
            raise RuntimeError(f"cannot open the microphone ({first}; then {e}). Run: python voice.py --devices")
    t = threading.Thread(target=_listen, args=(rec, audio, handlers, speaker, stream), daemon=True)
    t.start()
    print("Voice listening, model:", os.path.basename(path), flush=True)
    return t


if __name__ == "__main__":
    import sys
    if "--devices" in sys.argv:
        import sounddevice as sd
        print(sd.query_devices())
        sys.exit()

    class _TestSpeaker:
        def idle(self): return True
        def say(self, text, *a, **k): print("WOULD SAY:", text)

    test_handlers = {
        "read": lambda: print("  -> READ MODE would start"),
        "object": lambda target=None: print("  -> OBJECT MODE would start", f"(looking for {target})" if target else ""),
        "repeat": lambda: print("  -> REPEAT"),
        "stop": lambda: print("  -> STOP"),
    }
    try:
        start(test_handlers, _TestSpeaker())
    except RuntimeError as e:
        print("Voice cannot start:", e)
        sys.exit(1)
    print("Say a command (for example: activate read mode). Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass