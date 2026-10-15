"""Top module: creates the camera, the speaker and the two workers, and connects the inputs.

  Camera stream --> Guardian worker (YOLO, always running) --> Speaker --> earphones
  Camera stream --> Ask worker (Gemini, on button press) ----> Speaker
"""
import threading, time
import ask, guardian, inputs
from camera import warm_up
from speech import Speaker, ANSWER

speaker = Speaker()
cam = warm_up()


def mode_handler(mode):
    def handler():
        threading.Thread(target=ask.run_mode, args=(mode, speaker), daemon=True).start()
    return handler


handlers = {
    "read": mode_handler("read"),
    "color": mode_handler("color"),
    "item": mode_handler("item"),
    "scene": mode_handler("scene"),
    "repeat": lambda: speaker.say(ask.state["last"] or "Nothing to repeat", ANSWER),
    "pack": lambda: ask.cycle_pack(speaker),
}

threading.Thread(target=guardian.run, args=(cam, speaker), daemon=True).start()
speaker.say("System ready. Guardian on.", ANSWER)

buttons = inputs.setup_gpio(handlers)   # on the Pi this always succeeds, even with no buttons wired
# The keyboard always works too, so you can test without buttons. Real buttons also work at the same time.
inputs.keyboard_loop(handlers)
if buttons:                              # keyboard closed (q or no terminal): keep running on the buttons
    while True:
        time.sleep(1)