import os, platform, queue, signal, subprocess, threading, time

CRITICAL, GUARDIAN, ANSWER = 0, 1, 2     # lower number = higher priority

# Where the voice comes out on the Pi. Normally leave this empty: the voice goes to the Pi's default
# output, which is the Bluetooth speaker once you have selected it (see README / setup steps).
# To force one output, set AUDIO_DEVICE to a name from `aplay -L`, for example:
#   export AUDIO_DEVICE=pipewire         (or pulse, or plughw:Headphones,0)
AUDIO_DEVICE = os.environ.get("AUDIO_DEVICE")
_LINUX = platform.system() == "Linux"


class Speaker:
    """One voice for the whole program. Everything that wants to talk goes through say()."""

    def __init__(self):
        self.q = queue.PriorityQueue()
        self.n = 0
        self.proc = None
        self.lock = threading.Lock()
        self.now_priority = 99
        threading.Thread(target=self._worker, daemon=True).start()

    def idle(self):
        """True when nothing is playing and nothing is waiting."""
        return self.q.empty() and self.now_priority == 99

    def stop(self):
        """Stop talking now and forget everything that is waiting.
        Urgent (CRITICAL) safety warnings are never cut off or thrown away."""
        keep = []
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] == CRITICAL:
                    keep.append(item)
        except queue.Empty:
            pass
        for item in keep:
            self.q.put(item)
        with self.lock:
            if self.now_priority > CRITICAL:
                self._kill()

    def _kill(self):
        """End the speech playing now. On the Pi the voice is a pipeline (espeak-ng | aplay) when
        AUDIO_DEVICE is set, so the whole process group is ended, not just the first program."""
        p = self.proc
        if p and p.poll() is None:
            try:
                if _LINUX:
                    os.killpg(p.pid, signal.SIGTERM)
                else:
                    p.terminate()
            except Exception:
                try:
                    p.terminate()
                except Exception:
                    pass

    def say(self, text, priority=ANSWER, max_age=None, done=None):
        """max_age: drop the message if it waited longer than this many seconds (stale alerts).
        done: optional function called when this message has finished playing."""
        self.n += 1
        self.q.put((priority, self.n, time.time(), max_age, text, done))
        if priority == CRITICAL:             # cut off lower-priority speech that is playing now
            with self.lock:
                if self.now_priority > CRITICAL:
                    self._kill()

    def _cmd(self, text):
        if _LINUX:
            if text.startswith("-"):             # never let the text look like an option
                text = " " + text
            if AUDIO_DEVICE:                     # send the voice to a chosen output
                return ["sh", "-c", 'espeak-ng -s 150 --stdout "$1" | aplay -q -D "$2"', "sh", text, AUDIO_DEVICE]
            return ["espeak-ng", "-s", "150", text]
        safe = text.replace("'", "")
        return ["powershell", "-NoProfile", "-Command",
                "Add-Type -AssemblyName System.Speech; "
                f"(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{safe}')"]

    def _worker(self):
        while True:
            priority, _, t, max_age, text, done = self.q.get()
            if max_age is not None and time.time() - t > max_age:
                continue                     # stale alert, skip it
            self.now_priority = priority
            print("SPEAK:", text, flush=True)
            try:
                with self.lock:
                    self.proc = subprocess.Popen(self._cmd(text), start_new_session=_LINUX)
                self.proc.wait()
            except Exception as e:           # e.g. espeak-ng not installed: keep running
                print("Speech error:", e, flush=True)
            self.now_priority = 99
            if done:
                try:
                    done()
                except Exception as e:
                    print("Speech callback error:", e, flush=True)