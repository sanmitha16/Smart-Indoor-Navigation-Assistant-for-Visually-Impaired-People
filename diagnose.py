"""Runs Object mode one step at a time and prints what happens, with timings. Nothing is spoken.

    python diagnose.py            Object mode
    python diagnose.py read       Reading mode
Hold the object (or the text) in front of the camera before you press Enter.
"""
import sys, time, traceback

mode = sys.argv[1] if len(sys.argv) > 1 else "object"
input(f"Hold something in front of the camera for {mode} mode, then press Enter... ")

print("\nSTEP 1: camera")
from camera import warm_up, capture_best
t = time.time()
warm_up()
time.sleep(2)
print(f"  camera ready in {time.time() - t:.1f} s")
t = time.time()
path, score = capture_best(width=640 if mode == "object" else 1024)
print(f"  picture saved as {path}   sharpness {score:.0f} (needs at least 40)   took {time.time() - t:.2f} s")
print("  OPEN frame.jpg and check that it shows what you held up.")

print("\nSTEP 2: Gemini")
import ask
from prompts import PROMPTS, object_prompt
prompt = PROMPTS["read"] if mode == "read" else object_prompt()
ask.GEMINI_TIMEOUT = 90          # wait longer here than the app does, to see what really happens
print("  waiting for Gemini (up to 90 seconds)...")
t = time.time()
try:
    answer = ask._call_with_timeout(path, prompt, ask.MODES[mode]["tokens"])
    print(f"  answer in {time.time() - t:.1f} s: {answer!r}")
except ask.GeminiTimeout:
    print(f"  NO ANSWER after {time.time() - t:.0f} s. Gemini or the network is not responding.")
except Exception:
    print(f"  FAILED after {time.time() - t:.1f} s:")
    traceback.print_exc()

print("\nSTEP 3: the whole mode, exactly as the app runs it (words below are what would be spoken)")


class PrintSpeaker:
    def say(self, text, priority=None, max_age=None, done=None):
        print(f"  WOULD SAY: {text!r}")


ask.GEMINI_TIMEOUT = 20          # what the app really uses
t = time.time()
ask.run_mode(mode, PrintSpeaker())
print(f"  finished in {time.time() - t:.1f} s")