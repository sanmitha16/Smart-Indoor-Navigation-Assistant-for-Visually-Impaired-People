"""Test of the text layer. Needs no camera, no model and no internet:  python test_reader.py"""
import sys, threading, time
import cv2
import numpy as np
from text_trigger import has_text, find_text
from reader import TextReader

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name + (f"   {detail}" if detail else ""))


# ---- synthetic pictures ----
rng = np.random.default_rng(0)


def page():
    img = np.full((480, 640, 3), 235, np.uint8)
    lines = ["EXIT  Ward 3  Pharmacy", "Reception  Open 9 to 5", "Lift  Stairs  Toilets",
             "Please keep silence", "Visiting hours 4 to 6", "Emergency  Ground floor"]
    for i, t in enumerate(lines):
        cv2.putText(img, t, (40, 70 + i * 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (20, 20, 20), 2)
    return img


def wall():
    img = np.full((480, 640, 3), 200, np.uint8)
    noise = rng.normal(0, 2, img.shape)
    return np.clip(img + noise, 0, 255).astype(np.uint8)


def gradient():
    ramp = np.tile(np.linspace(60, 220, 640, dtype=np.uint8), (480, 1))
    return cv2.merge([ramp, ramp, ramp])


def door():
    img = np.full((480, 640, 3), 180, np.uint8)
    cv2.rectangle(img, (220, 40), (420, 470), (60, 90, 140), -1)
    cv2.circle(img, (390, 260), 8, (200, 200, 200), -1)
    return img


def clutter():
    img = rng.integers(0, 255, (480, 640, 3), dtype=np.uint8)
    return cv2.GaussianBlur(img, (0, 0), 4)


check("page with text is detected", has_text(page()), str(len(find_text(page())[0])) + " blobs")
check("plain wall with sensor noise is not text", not has_text(wall()))
check("smooth gradient is not text", not has_text(gradient()))
check("door shape is not text", not has_text(door()))
check("blurred clutter is not text", not has_text(clutter()))
check("text in a dim picture still found", has_text((page() * 0.45).astype(np.uint8)))

# ---- question flow ----
class Cam:
    def __init__(self): self.frame = page()
    def read(self): return True, self.frame.copy()


class Speaker:
    """Fake voice: every message takes `speak_time` seconds to play, then its done() is called."""
    def __init__(self, speak_time=0.05):
        self.said, self.speak_time, self.busy_until = [], speak_time, 0
    def idle(self): return time.time() >= self.busy_until
    def say(self, text, priority=None, max_age=None, done=None):
        self.said.append(text)
        self.busy_until = time.time() + self.speak_time
        if done:
            threading.Timer(self.speak_time, done).start()


def make(speak_time=0.05, **kw):
    cam, sp, calls = Cam(), Speaker(speak_time), []
    r = TextReader(cam, sp, poll=0.05, stable_frames=3, answer_timeout=0.6,
                   cooldown_yes=0.5, cooldown_no=0.5, check_online=lambda: True,
                   run_read=lambda: calls.append("read"), **kw)
    r.start()
    return cam, sp, calls, r


# yes -> read
cam, sp, calls, r = make()
time.sleep(0.5)
check("asks once when text is steady", len(sp.said) == 1 and sp.said[0].startswith("Text detected"), str(sp.said))
r.yes()
time.sleep(0.2)
check("yes starts Gemini reading", calls == ["read"], str(calls))
time.sleep(0.3)
check("no second question during cooldown", len(sp.said) == 1, str(sp.said))

# no -> quiet, then asks again after the cooldown
cam, sp, calls, r = make()
time.sleep(0.5)
r.no()
time.sleep(0.2)
check("no says Okay and does not read", sp.said[-1] == "Okay" and calls == [], str(sp.said))
time.sleep(1.2)
check("asks again after the cooldown", sp.said.count("Text detected. Do you want me to read it? Say yes or no.") == 2, str(sp.said))

# silence -> treated as no
cam, sp, calls, r = make()
time.sleep(0.5)
time.sleep(0.9)
check("silence is treated as no (no reading)", calls == [], str(calls))
r.yes()
time.sleep(0.1)
check("a late yes after the timeout is ignored", calls == [], str(calls))

# yes with no question pending does nothing
cam, sp, calls, r = make()
cam.frame = wall()
time.sleep(0.4)
r.yes()
time.sleep(0.1)
check("yes with nothing pending is ignored", calls == [] and sp.said == [], str(sp.said))

# no text in view -> never asks
check("no text in view, no question", sp.said == [], str(sp.said))

# a slow question (1.2 s to speak, timeout 0.6 s): the timer must start AFTER it was spoken
cam, sp, calls, r = make(speak_time=1.2)
time.sleep(1.2)                         # question queued about 0.5 s in, still playing now
r.yes()
time.sleep(0.2)
check("yes works while the question is still playing", calls == ["read"], str(calls))

cam, sp, calls, r = make(speak_time=1.2)
time.sleep(0.5 + 1.2 + 0.3)             # question finished 0.3 s ago, timeout 0.6 s not reached
r.yes()
time.sleep(0.2)
check("yes just after a long question is not timed out", calls == ["read"], str(calls))

# no new question while the device is still talking
cam, sp, calls, r = make()
sp.busy_until = time.time() + 1.0       # pretend a long answer is being read out
time.sleep(0.8)
check("does not ask while the device is speaking", sp.said == [], str(sp.said))
time.sleep(0.9)
check("asks once the device is quiet", len(sp.said) == 1, str(sp.said))

# offline -> never asks
cam, sp, calls = Cam(), Speaker(), []
r = TextReader(cam, sp, poll=0.05, stable_frames=3, answer_timeout=0.6, check_online=lambda: False,
               run_read=lambda: calls.append("read"))
r.start()
time.sleep(0.6)
check("offline: does not ask", sp.said == [], str(sp.said))

print()
print("ALL PASSED" if all(results) else "SOME FAILED")
sys.exit(0 if all(results) else 1)