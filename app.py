"""Top module. Two modes, both using Gemini:

  Reading mode  -> reads the text in front of the camera
  Object mode   -> names the object in front of the camera and says where it is

Start:   python app.py            (type r, o, x, q   or use the two buttons on the Pi)
         python app.py --view     (also opens a live camera window, for testing)

The YOLO guardian is parked in the yolo_later folder until it is ready to be integrated.
"""
import sys, threading, time
import ask, inputs
from camera import warm_up
from speech import Speaker, ANSWER

speaker = Speaker()
cam = warm_up()


def mode_handler(mode):
    def handler(target=None):
        if not speaker.idle():           # pressing while it is talking just stops the talking
            speaker.stop()
            return
        threading.Thread(target=ask.run_mode, args=(mode, speaker, target), daemon=True).start()
    return handler


handlers = {
    "read": mode_handler("read"),
    "object": mode_handler("object"),
    "repeat": lambda: speaker.say(ask.state["last"] or "Nothing to repeat", ANSWER),
}

speaker.say("Ready. Left button reads. Right button finds objects.", ANSWER)
buttons = inputs.setup_gpio(handlers)    # on the Pi this works even with no buttons wired yet

if "--view" in sys.argv:
    import viewer
    threading.Thread(target=inputs.keyboard_loop, args=(handlers,), daemon=True).start()
    viewer.run(cam)                      # blocks until you press q in the window
else:
    inputs.keyboard_loop(handlers)       # returns on q, or at once when there is no terminal
    if buttons:                          # started automatically at boot: keep running on the buttons
        while True:
            time.sleep(1)