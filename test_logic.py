"""Simulated test of the guardian rules and the speaker priorities.
Needs no camera, no model and no internet:  python test_logic.py
"""
import sys, threading, time, types

# ---- fake detector so guardian.py can be imported and driven with scripted detections ----
SCRIPT = {"dets": []}
fake = types.ModuleType("detector")
fake.detect = lambda frame: list(SCRIPT["dets"])
sys.modules["detector"] = fake

import guardian
from speech import Speaker, CRITICAL, GUARDIAN, ANSWER


class FakeCam:
    def read(self):
        return True, object()


class FakeSpeaker:
    def __init__(self):
        self.said = []

    def say(self, text, priority=ANSWER, max_age=None):
        self.said.append(text)


def det(name, conf, cx=0.5, h=0.3, w=0.3):
    return {"name": name, "conf": conf, "cx": cx, "h": h, "w": w}


def run_guardian(dets, seconds):
    SCRIPT["dets"] = dets
    sp = FakeSpeaker()
    t = threading.Thread(target=guardian.run, args=(FakeCam(), sp), daemon=True)
    t.start()
    time.sleep(seconds)
    return sp.said


results = []

def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name + (f"   {detail}" if detail else ""))


# 1. Door on the left is spoken first (priority order), then person, one alert per cycle
guardian.run.__globals__["time"].sleep  # sanity: module has time
said = run_guardian([det("person", 0.9, 0.5, 0.7), det("door", 0.5, 0.2, 0.3)], 0.6)
check("door left then person ahead close", said[:2] == ["Door on left", "Person ahead, close"], str(said))

# 2. Cooldown: nothing repeats within the cooldown window
check("no repeat inside cooldown", len(said) == 2, str(said))

# 3. Below-threshold stairs and walls are silent
said = run_guardian([det("stairs", 0.2), det("wall", 0.95, 0.5, 0.95, 0.95)], 0.4)
check("weak stairs and wall stay silent", said == [], str(said))

# 4. Strong stairs on the right
said = run_guardian([det("stairs", 0.8, 0.8, 0.3)], 0.4)
check("stairs on right", said[:1] == ["Stairs on right"], str(said))

# 5. Person below 0.5 is ignored
said = run_guardian([det("person", 0.45)], 0.4)
check("person under 0.5 ignored", said == [], str(said))

# ---- speaker priorities ----
# A fake "voice process" replaces the real one, so this test does not depend on how fast
# Windows starts a subprocess or on whether espeak/PowerShell speech is installed.
import io, contextlib
import speech


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


DURATION = {"s": 0.3}
speech.subprocess.Popen = lambda cmd, *a, **k: FakeProc(DURATION["s"])


def spoken(buf):
    return [l.split("SPEAK: ")[1] for l in buf.getvalue().splitlines() if l.startswith("SPEAK: ")]


DURATION["s"] = 0.3
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    sp = Speaker()
    sp.say("a1", ANSWER)
    time.sleep(0.05)                       # a1 is now playing for 0.3 s
    sp.say("a2", ANSWER)
    sp.say("g1", GUARDIAN, max_age=2)
    sp.say("old", GUARDIAN, max_age=0.1)   # will be stale by the time it is reached
    time.sleep(1.5)
order = spoken(buf)
check("guardian jumps ahead of waiting answer, stale alert dropped", order == ["a1", "g1", "a2"], str(order))

DURATION["s"] = 2
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    sp2 = Speaker()
    sp2.say("long answer", ANSWER)
    time.sleep(0.1)
    sp2.say("danger", CRITICAL)
    time.sleep(0.6)
order = spoken(buf)
check("critical alert interrupts a long answer", order == ["long answer", "danger"], str(order))

print()
print("ALL PASSED" if all(results) else "SOME FAILED")
sys.exit(0 if all(results) else 1)