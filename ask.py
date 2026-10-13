import inspect
import threading
from camera import capture_best
from vision_ai import ask as gemini_ask
from prompts import PROMPTS
from speech import ANSWER

MODES = {
    "read":  {"say": "Reading", "width": 1024, "tokens": 250},
    "color": {"say": "Color",   "width": 512,  "tokens": 20},
    "item":  {"say": "Item",    "width": 512,  "tokens": 30},
    "scene": {"say": "Scene",   "width": 640,  "tokens": 80},
}
BLUR_THRESHOLD = 40        # tune from your own sharpness numbers (you saw 95 to 183 when still)
PACKS = ["general", "home", "hospital", "mall"]
PACK_HINTS = {
    "general": "",
    "home": " Also look for: gas stove, stairs, steps at thresholds, wet floor, doors.",
    "hospital": " Also look for: lift, ward or room number signs, ramps, reception desk, glass doors.",
    "mall": " Also look for: escalator, lift, glass doors, store signboards, exit signs.",
}
state = {"pack": "general", "last": ""}
_busy = threading.Lock()

# Works with either version of your vision_ai.py (with or without a max_tokens argument)
_HAS_TOKENS = "max_tokens" in inspect.signature(gemini_ask).parameters


def _call(path, prompt, tokens):
    if _HAS_TOKENS:
        return gemini_ask(path, prompt, max_tokens=tokens)
    return gemini_ask(path, prompt)


def cycle_pack(speaker):
    i = (PACKS.index(state["pack"]) + 1) % len(PACKS)
    state["pack"] = PACKS[i]
    speaker.say(f"{state['pack']} pack", ANSWER)


def _is_network_error(e):
    s = str(e).lower()
    return any(w in s for w in ("getaddrinfo", "connection", "timed out", "timeout", "network"))


def run_mode(mode, speaker):
    if not _busy.acquire(blocking=False):
        speaker.say("Please wait", ANSWER)
        return
    try:
        cfg = MODES[mode]
        speaker.say(cfg["say"], ANSWER)
        path, score = capture_best(width=cfg["width"])
        print(f"sharpness {score:.0f}")
        if score < BLUR_THRESHOLD:
            speaker.say("Hold steady and try again", ANSWER)
            return
        prompt = PROMPTS[mode] + (PACK_HINTS[state["pack"]] if mode == "scene" else "")
        try:
            answer = _call(path, prompt, cfg["tokens"])
        except Exception as e:
            print(e)
            speaker.say("No internet" if _is_network_error(e) else "Sorry, try again", ANSWER)
            return
        answer = (answer or "").strip() or "not sure"
        state["last"] = answer
        speaker.say(answer, ANSWER)
    finally:
        _busy.release()
