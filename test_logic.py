"""Simulated test of the two modes, the buttons and the speaker.
Needs no camera, no internet, no Gemini key and no Raspberry Pi:   python test_logic.py
"""
import contextlib, io, sys, threading, time, types

# ---- fake camera and fake Gemini, so ask.py can be imported and driven ----
CAM = {"scores": [150.0], "calls": [], "error": None}


def fake_capture_best(path="frame.jpg", width=1024, window=0.5):
    if CAM["error"]:
        raise RuntimeError(CAM["error"])
    CAM["calls"].append(width)
    score = CAM["scores"].pop(0) if len(CAM["scores"]) > 1 else CAM["scores"][0]
    return path, score


fake_camera = types.ModuleType("camera")
fake_camera.capture_best = fake_capture_best
sys.modules["camera"] = fake_camera

GEM = {"answer": "ok", "error": None, "calls": []}


def fake_gemini(image_path, prompt, max_tokens=150):
    GEM["calls"].append({"prompt": prompt, "tokens": max_tokens})
    if GEM["error"]:
        raise GEM["error"]
    return GEM["answer"]


fake_vision = types.ModuleType("vision_ai")
fake_vision.ask = fake_gemini
sys.modules["vision_ai"] = fake_vision

import ask
import inputs
import speech
from speech import Speaker, ANSWER

ask.RETRY_WAIT = 0.01
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name + (f"   {detail}" if detail else ""))


class FakeSpeaker:
    def __init__(self):
        self.said = []

    def say(self, text, priority=ANSWER, max_age=None, done=None):
        self.said.append(text)


def fresh(score=150.0, answer="ok", error=None, cam_error=None):
    CAM.update(scores=[score] if not isinstance(score, list) else score, calls=[], error=cam_error)
    GEM.update(answer=answer, error=error, calls=[])
    ask.state["last"] = ""
    return FakeSpeaker()


# ---- Reading mode ----
sp = fresh(answer="Exit. Ward 3.")
ask.run_mode("read", sp)
check("reading: says Reading, then the answer", sp.said == ["Reading", "Exit. Ward 3."], str(sp.said))
check("reading: uses the read prompt and a wide picture",
      "Read all visible text" in GEM["calls"][0]["prompt"] and CAM["calls"] == [1024], str(CAM["calls"]))
check("reading: allows a long answer", GEM["calls"][0]["tokens"] >= 300, str(GEM["calls"][0]["tokens"]))
check("reading: answer is remembered for repeat", ask.state["last"] == "Exit. Ward 3.")

# ---- Object mode ----
sp = fresh(answer="Bottle on your right, within reach.")
ask.run_mode("object", sp)
check("object: says Looking, then the answer", sp.said == ["Looking", "Bottle on your right, within reach."], str(sp.said))
p = GEM["calls"][0]["prompt"]
check("object: asks for name and position", "main object" in p and "left" in p and "ahead" in p and "right" in p)
check("object: smaller picture, short answer", CAM["calls"] == [640] and GEM["calls"][0]["tokens"] <= 120)

sp = fresh(answer="Keys ahead, near.")
ask.run_mode("object", sp, "my keys")
check("object with a target looks for that target", "my keys" in GEM["calls"][0]["prompt"] and sp.said[-1] == "Keys ahead, near.",
      GEM["calls"][0]["prompt"][-120:])

# ---- blurry pictures ----
sp = fresh(score=[10.0, 12.0])
ask.run_mode("object", sp)
check("two blurry pictures: Hold steady, Gemini not called", sp.said == ["Looking", "Hold steady and try again"] and GEM["calls"] == [], str(sp.said))

sp = fresh(score=[10.0, 120.0], answer="Cup ahead, near.")
ask.run_mode("object", sp)
check("blurry then sharp: retakes once and answers", sp.said == ["Looking", "Cup ahead, near."] and CAM["calls"] == [640, 640], str(sp.said))

# ---- errors ----
for text, want in [
    ("[Errno 11001] getaddrinfo failed", "No internet"),
    ("429 RESOURCE_EXHAUSTED quota exceeded", "Limit reached, try again in a minute"),
    ("400 API_KEY_INVALID", "Key problem"),
    ("503 UNAVAILABLE the model is overloaded", "Service busy, try again"),
    ("something odd", "Sorry, try again"),
]:
    sp = fresh(error=Exception(text))
    with contextlib.redirect_stdout(io.StringIO()):
        ask.run_mode("read", sp)
    check(f"error '{text[:28]}...' says '{want}'", sp.said[-1] == want, str(sp.said))

sp = fresh(cam_error="Camera not found")
with contextlib.redirect_stdout(io.StringIO()):
    ask.run_mode("read", sp)
check("camera failure says Camera problem", sp.said[-1] == "Camera problem", str(sp.said))

sp = fresh(answer="   ")
ask.run_mode("read", sp)
check("empty answer says not sure", sp.said[-1] == "not sure", str(sp.said))

# ---- busy lock ----
slow = threading.Event()
release = threading.Event()


def slow_gemini(image_path, prompt, max_tokens=150):
    slow.set()
    release.wait(2)
    return "late answer"


ask.gemini_ask = slow_gemini
sp1, sp2 = fresh(), FakeSpeaker()
CAM.update(scores=[150.0])
t = threading.Thread(target=ask.run_mode, args=("read", sp1))
t.start()
slow.wait(2)
ask.run_mode("object", sp2)
check("second press while Gemini is working says Please wait", sp2.said == ["Please wait"], str(sp2.said))
release.set()
t.join()
check("first request still finishes", sp1.said[-1] == "late answer", str(sp1.said))
ask.gemini_ask = fake_gemini

# ---- Gemini does not answer: the user is told, the app is not stuck ----
def hanging_gemini(image_path, prompt, max_tokens=150):
    time.sleep(2)
    return "far too late"


ask.gemini_ask = hanging_gemini
ask.GEMINI_TIMEOUT = 0.3
sp = fresh()
t0 = time.time()
ask.run_mode("object", sp)
check("no answer from Gemini: says 'No answer, try again' without waiting for it",
      sp.said == ["Looking", "No answer, try again"] and time.time() - t0 < 1.5, f"{sp.said} {time.time() - t0:.1f}s")
ask.gemini_ask = fake_gemini
ask.GEMINI_TIMEOUT = 20
sp = fresh(answer="Spoon ahead, near.")
ask.run_mode("object", sp)
check("works again right after a timeout", sp.said == ["Looking", "Spoon ahead, near."], str(sp.said))

# ---- unknown mode ignored ----
sp = fresh()
ask.run_mode("color", sp)
check("old modes are gone", sp.said == [] and GEM["calls"] == [])

# ---- buttons (fake gpiozero) ----
class FakeButton:
    made = {}

    def __init__(self, pin, pull_up=True, bounce_time=None, hold_time=1):
        self.pin, self.hold_time = pin, hold_time
        self.when_held = None
        self.when_released = None
        FakeButton.made[pin] = self

    def press_and_release(self, seconds):
        if seconds >= self.hold_time and self.when_held:
            self.when_held()
        if self.when_released:
            self.when_released()


fake_gpio = types.ModuleType("gpiozero")
fake_gpio.Button = FakeButton
sys.modules["gpiozero"] = fake_gpio

log = []
handlers = {"read": lambda: log.append("read"), "object": lambda *a: log.append("object"),
            "repeat": lambda: log.append("repeat")}
buttons = inputs.setup_gpio(handlers)
check("two buttons on GPIO 17 and 27", set(FakeButton.made) == {17, 27} and set(buttons) == {"read", "object"}, str(sorted(FakeButton.made)))
FakeButton.made[17].press_and_release(0.1)
FakeButton.made[27].press_and_release(0.1)
check("short press starts the matching mode", log == ["read", "object"], str(log))
log.clear()
FakeButton.made[17].press_and_release(2.0)
check("long press repeats and does not start the mode", log == ["repeat"], str(log))
FakeButton.made[17].press_and_release(0.1)
check("a short press after a long press works again", log == ["repeat", "read"], str(log))

import inspect
cbs = [FakeButton.made[17].when_held, FakeButton.made[17].when_released]
check("button callbacks take no arguments", all(len(inspect.signature(c).parameters) == 0 for c in cbs))

# ---- keyboard ----
log = []
h = {"read": lambda: log.append("read"), "object": lambda target=None: log.append(("object", target)),
     "repeat": lambda: log.append("repeat")}
sys.stdin = io.StringIO("r\no\no blue bottle\nfind keys\nx\nzzz\nq\nr\n")
with contextlib.redirect_stdout(io.StringIO()):
    inputs.keyboard_loop(h)
check("keyboard commands", log == ["read", ("object", None), ("object", "blue bottle"), ("object", "keys"), "repeat"], str(log))

sys.stdin = io.StringIO("")
with contextlib.redirect_stdout(io.StringIO()):
    inputs.keyboard_loop(h)
check("no terminal (boot): keyboard loop ends quietly", True)

# ---- speaker: stop ----
class FakeProc:
    def __init__(self, seconds):
        self.end = time.time() + seconds
        self.killed = threading.Event()

    def wait(self):
        while time.time() < self.end and not self.killed.is_set():
            time.sleep(0.01)

    def poll(self):
        return None if (time.time() < self.end and not self.killed.is_set()) else 0

    def terminate(self):
        self.killed.set()


procs = []
speech.subprocess.Popen = lambda cmd, *a, **k: procs.append(FakeProc(3)) or procs[-1]
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    s = Speaker()
    s.say("a long reading", ANSWER)
    s.say("waiting one", ANSWER)
    t0 = time.time()
    while not procs and time.time() - t0 < 3:        # wait until the first message really started playing
        time.sleep(0.01)
    busy = not s.idle()
    s.stop()
    time.sleep(0.5)
spoken = [l.split("SPEAK: ")[1] for l in buf.getvalue().splitlines() if l.startswith("SPEAK: ")]
detail = f"spoken={spoken} procs_started={len(procs)} killed={[p.killed.is_set() for p in procs]}"
check("speaker is busy while talking", busy)
check("stop cuts the speech and drops what was waiting",
      len(procs) == 1 and procs[0].killed.is_set() and spoken == ["a long reading"], detail)
check("speaker is idle again after stop", s.idle())

buf2 = io.StringIO()
with contextlib.redirect_stdout(buf2):
    s.say("after the stop", ANSWER)
    time.sleep(0.4)
check("new speech works after a stop", "SPEAK: after the stop" in buf2.getvalue(), buf2.getvalue().strip()[:80])

print()
print("ALL PASSED" if all(results) else "SOME FAILED")
sys.exit(0 if all(results) else 1)