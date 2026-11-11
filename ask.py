"""The two Gemini modes.

  read    Reading mode: reads the text in front of the camera aloud.
  object  Object mode: says what the main object is and where it is (left / ahead / right, near / far).
          With a target ("find my keys") it SEARCHES: it keeps checking the camera while the user turns,
          until the object is found, the user says stop, or SEARCH_SECONDS pass.

Both modes: take a sharp picture, send it to Gemini through vision_ai.ask(), speak the answer.
"""
import inspect
import queue
import re
import threading
import time
from camera import capture_best
from vision_ai import ask as gemini_ask
try:
    from vision_ai import ask_stream      # speaks long readings while Gemini is still writing them
except ImportError:
    ask_stream = None
from prompts import PROMPTS, object_prompt
from speech import ANSWER

MODES = {
    "read":   {"say": "Reading", "width": 1024, "tokens": 400},
    "object": {"say": "Looking", "width": 640,  "tokens": 80},
}
GEMINI_TIMEOUT = 20        # seconds to wait for Gemini before telling the user "No answer"
BLUR_THRESHOLD = 40        # pictures below this sharpness are retaken
RETRY_WAIT = 0.6           # seconds before the second attempt at a sharp picture
SEARCH_SECONDS = 40        # how long "find ..." keeps searching before giving up
SEARCH_GAP = 0.5           # pause between search attempts
# Added to every object prompt so Gemini does not mirror left and right
ORIENTATION = ("Say left and right exactly as they appear in the picture: left means the left side "
               "of the picture, right means the right side of the picture. Never swap them.")
STREAM_READING = True      # reading mode: start speaking after the first sentence, not the whole page
FIRST_CHUNK_MIN = 25       # characters in the first spoken piece (low delay)
LATER_CHUNK_MIN = 150      # later pieces are longer, so there are fewer pauses between them
STREAM_IDLE_TIMEOUT = 12   # seconds without new text before a stream is given up
state = {"last": ""}
cancel = threading.Event()     # set by "stop" to end a search
_busy = threading.Lock()

# Works with either version of your vision_ai.py (with or without a max_tokens argument)
_HAS_TOKENS = "max_tokens" in inspect.signature(gemini_ask).parameters


def _call(path, prompt, tokens):
    if _HAS_TOKENS:
        return gemini_ask(path, prompt, max_tokens=tokens)
    return gemini_ask(path, prompt)


class GeminiTimeout(Exception):
    pass


def _call_with_timeout(path, prompt, tokens):
    """Ask Gemini, but never leave the user in silence: give up after GEMINI_TIMEOUT seconds."""
    box = {}

    def work():
        try:
            box["answer"] = _call(path, prompt, tokens)
        except Exception as e:
            box["error"] = e

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(GEMINI_TIMEOUT)
    if t.is_alive():
        raise GeminiTimeout(f"no answer from Gemini after {GEMINI_TIMEOUT} seconds")
    if "error" in box:
        raise box["error"]
    return box.get("answer")


def _error_message(e):
    if isinstance(e, GeminiTimeout):
        return "No answer, try again"
    s = str(e).lower()
    if any(w in s for w in ("429", "resource_exhausted", "quota", "rate limit")):
        return "Limit reached, try again in a minute"
    if any(w in s for w in ("api_key", "api key", "permission_denied", "403")):
        return "Key problem"
    if any(w in s for w in ("getaddrinfo", "connection", "timed out", "timeout", "network", "unreachable")):
        return "No internet"
    if any(w in s for w in ("503", "overloaded", "unavailable")):
        return "Service busy, try again"
    return "Sorry, try again"


def _sharp_picture(width):
    """Up to two tries at a sharp picture. Returns (path, score), or (None, score) if both were blurry."""
    score = 0
    for attempt in range(2):
        path, score = capture_best(width=width)
        print(f"sharpness {score:.0f}")
        if score >= BLUR_THRESHOLD:
            return path, score
        if attempt == 0:
            time.sleep(RETRY_WAIT)
    return None, score


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def _take(buf, min_len, use_last):
    """Cut a speakable piece off the front of buf at a sentence boundary. Returns (piece, rest)."""
    ends = [m.end() for m in _SENTENCE_END.finditer(buf)]
    for e in (ends[-1:] if use_last else ends):
        if len(buf[:e].strip()) >= min_len:
            return buf[:e].strip(), buf[e:]
    return "", buf


def _stream_and_speak(path, prompt, tokens, speaker, t0):
    """Speak a long answer piece by piece while Gemini is still writing it. Returns the full text.
    Raises only if nothing at all arrived (so the caller can tell the user or fall back)."""
    pieces = queue.Queue()

    def reader():
        try:
            for piece in ask_stream(path, prompt, max_tokens=tokens):
                pieces.put(("text", piece))
            pieces.put(("end", None))
        except Exception as e:
            pieces.put(("error", e))

    threading.Thread(target=reader, daemon=True).start()
    full, buf = "", ""
    got_text = spoken = False
    last_activity = time.time()
    while True:
        if cancel.is_set():
            return full
        try:
            kind, val = pieces.get(timeout=0.3)
        except queue.Empty:
            limit = STREAM_IDLE_TIMEOUT if got_text else GEMINI_TIMEOUT
            if time.time() - last_activity > limit:
                if not got_text:
                    raise GeminiTimeout(f"no answer from Gemini after {GEMINI_TIMEOUT} seconds")
                break
            continue
        last_activity = time.time()
        if kind == "error":
            if not got_text:
                raise val
            print("stream stopped early:", val)
            break
        if kind == "end":
            break
        if not val:
            continue
        got_text = True
        full += val
        buf += val
        piece, buf = _take(buf, LATER_CHUNK_MIN if spoken else FIRST_CHUNK_MIN, use_last=spoken)
        if piece:
            if not spoken:
                print(f"timing: first words after {time.time() - t0:.1f} s")
            spoken = True
            speaker.say(piece, ANSWER)
    if not cancel.is_set() and buf.strip():
        if not spoken:
            print(f"timing: first words after {time.time() - t0:.1f} s")
        speaker.say(buf.strip(), ANSWER)
    return full


def run_mode(mode, speaker, target=None):
    if mode not in MODES:
        return
    if not _busy.acquire(blocking=False):
        speaker.say("Please wait", ANSWER)
        return
    cancel.clear()
    t0 = time.time()
    try:
        cfg = MODES[mode]
        speaker.say(cfg["say"], ANSWER)
        try:
            path, score = _sharp_picture(cfg["width"])
        except Exception as e:
            print("camera error:", e)
            speaker.say("Camera problem", ANSWER)
            return
        if path is None:
            speaker.say("Hold steady and try again", ANSWER)
            return
        if cancel.is_set():              # the user said stop while the picture was being taken
            return
        t_pic = time.time() - t0
        prompt = PROMPTS["read"] if mode == "read" else object_prompt(target) + " " + ORIENTATION
        if mode == "read" and STREAM_READING and ask_stream is not None:
            try:
                full = _stream_and_speak(path, prompt, cfg["tokens"], speaker, t0).strip()
                if full:
                    state["last"] = full
                elif not cancel.is_set():
                    speaker.say("not sure", ANSWER)
                print(f"timing: picture {t_pic:.1f} s, total {time.time() - t0:.1f} s")
                return
            except Exception as e:
                print(e)
                known = _error_message(e)
                if known != "Sorry, try again":      # a known problem: tell the user
                    speaker.say(known, ANSWER)
                    return
                # unknown streaming problem: fall back to the normal call below
        try:
            answer = _call_with_timeout(path, prompt, cfg["tokens"])
        except Exception as e:
            print(e)
            speaker.say(_error_message(e), ANSWER)
            return
        print(f"timing: picture {t_pic:.1f} s, answer after {time.time() - t0:.1f} s")
        if cancel.is_set():              # the user said stop while Gemini was thinking: stay silent
            return
        answer = (answer or "").strip() or "not sure"
        state["last"] = answer
        speaker.say(answer, ANSWER)
    finally:
        _busy.release()


# ---------------------------------------------------------------- search ("find bottle")

def _search_prompt(target):
    return (
        f"A blind person is searching for: {target}. Look at the picture. "
        f"If a {target} is clearly visible, reply exactly: FOUND: <short phrase saying where it is, "
        f"such as 'on your right, within reach'; use left, ahead or right, and within reach, near or far>. "
        f"If only part of a {target} is visible at the edge of the picture, reply exactly: PARTLY: <left or right>. "
        f"If there is no {target}, reply exactly: NOT FOUND. " + ORIENTATION + " Reply with nothing else."
    )


def _parse_search(answer):
    """Returns ('found', phrase), ('partly', 'left'|'right'|''), or ('none', '')."""
    a = (answer or "").strip()
    u = a.upper()
    rest = a.split(":", 1)[1].strip().rstrip(".").strip() if ":" in a else ""
    if u.startswith("FOUND"):
        return "found", rest
    if u.startswith("PARTLY"):
        side = rest.lower()
        return "partly", side if side in ("left", "right") else ""
    return "none", ""


def run_search(target, speaker):
    """Keep looking for `target` while the user turns, until found, stopped, or SEARCH_SECONDS pass."""
    target = (target or "").strip()
    if not target:
        return
    if not _busy.acquire(blocking=False):
        speaker.say("Please wait", ANSWER)
        return
    cancel.clear()
    try:
        speaker.say(f"Looking for {target}. Turn slowly.", ANSWER)
        start = time.time()
        misses = 0
        blurry = 0
        while time.time() - start < SEARCH_SECONDS:
            if cancel.is_set():
                return
            try:
                path, score = capture_best(width=MODES["object"]["width"])
            except Exception as e:
                print("camera error:", e)
                speaker.say("Camera problem", ANSWER)
                return
            if score < BLUR_THRESHOLD:           # turning too fast: skip, no Gemini call used
                blurry += 1
                print(f"sharpness {score:.0f} (too blurry, skipped)")
                if blurry == 3:
                    speaker.say("Turn more slowly", ANSWER)
                time.sleep(0.3)
                continue
            blurry = 0
            try:
                answer = _call_with_timeout(path, _search_prompt(target), 40)
            except Exception as e:
                print(e)
                speaker.say(_error_message(e), ANSWER)
                return
            if cancel.is_set():
                return
            kind, rest = _parse_search(answer)
            print(f"search: {kind} {rest}")
            if kind == "found":
                where = (rest[:1].upper() + rest[1:]) if rest else ""
                msg = f"Found {target}. {where}".strip()
                if where:
                    msg += "."
                state["last"] = msg
                speaker.say(msg, ANSWER)
                return
            misses += 1
            if kind == "partly":
                if rest:
                    speaker.say(f"Partly visible on your {rest}. Turn {rest}.", ANSWER)
                else:
                    speaker.say("Partly visible. Turn a little.", ANSWER)
            elif misses == 1:
                speaker.say("Not here yet. Keep turning slowly.", ANSWER)
            elif misses % 3 == 0:
                speaker.say("Still looking.", ANSWER)
            time.sleep(SEARCH_GAP)
        speaker.say(f"I could not find {target}. Say find {target} to try again.", ANSWER)
    finally:
        _busy.release()