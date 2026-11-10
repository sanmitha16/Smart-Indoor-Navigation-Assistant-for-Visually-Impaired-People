"""The two Gemini modes.

  read    Reading mode: reads the text in front of the camera aloud.
  object  Object mode: says what the main object is and where it is (left / ahead / right, near / far).
          With a target ("find my keys") it looks for that object instead.

Both modes: take a sharp picture, send it to Gemini through vision_ai.ask(), speak the answer.
"""
import inspect
import threading
import time
from camera import capture_best
from vision_ai import ask as gemini_ask
from prompts import PROMPTS, object_prompt
from speech import ANSWER

MODES = {
    "read":   {"say": "Reading", "width": 1024, "tokens": 400},
    "object": {"say": "Looking", "width": 640,  "tokens": 80},
}
GEMINI_TIMEOUT = 20        # seconds to wait for Gemini before telling the user "No answer"
BLUR_THRESHOLD = 40        # pictures below this sharpness are retaken
RETRY_WAIT = 0.6           # seconds before the second attempt at a sharp picture
state = {"last": ""}
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


def run_mode(mode, speaker, target=None):
    if mode not in MODES:
        return
    if not _busy.acquire(blocking=False):
        speaker.say("Please wait", ANSWER)
        return
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
        prompt = PROMPTS["read"] if mode == "read" else object_prompt(target)
        try:
            answer = _call_with_timeout(path, prompt, cfg["tokens"])
        except Exception as e:
            print(e)
            speaker.say(_error_message(e), ANSWER)
            return
        answer = (answer or "").strip() or "not sure"
        state["last"] = answer
        speaker.say(answer, ANSWER)
    finally:
        _busy.release()