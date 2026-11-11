"""Top module. The complete prototype.

  Guardian      YOLO watches the camera all the time and warns by itself (door, stairs, person, window, wall)
  Reading mode  -> reads the text in front of the camera            (Gemini)
  Object mode   -> names the object in front of the camera and says where it is   (Gemini)
                   "find keys" keeps searching while the user turns

Hands-free: say "activate read mode", "activate object mode", "find keys", "repeat" or "stop".
Keyboard (for testing): r, o, o keys, x, s, q.   Buttons on the Pi still work if they are wired.

Start:   python app.py            (guardian + voice + keyboard)
         python app.py --view     (also opens a live camera window, needs a screen)
         python app.py --web      (live camera view in a web browser, works over SSH: see webview.py)
"""
import sys, threading, time
import ask, inputs
from camera import warm_up
from speech import Speaker, ANSWER

speaker = Speaker()
cam = warm_up()


def mode_handler(mode):
    def handler(target=None):
        if not speaker.idle():           # asking while it is talking just stops the talking
            speaker.stop()
            return
        if mode == "object" and target:  # "find keys": keep searching while the user turns
            threading.Thread(target=ask.run_search, args=(target, speaker), daemon=True).start()
        else:
            threading.Thread(target=ask.run_mode, args=(mode, speaker, target), daemon=True).start()
    return handler


def stop_all():
    ask.cancel.set()                     # ends a running search or a pending answer
    speaker.stop()                       # urgent safety warnings are not cut off


handlers = {
    "read": mode_handler("read"),
    "object": mode_handler("object"),
    "repeat": lambda: speaker.say(ask.state["last"] or "Nothing to repeat", ANSWER),
    "stop": stop_all,
}

voice_on = False
try:
    import voice
    voice.start(handlers, speaker)
    voice_on = True
except Exception as e:                   # no microphone, no model, packages missing...
    print("Voice commands are off:", e)

guardian_on = False
try:
    import guardian
    guardian.start(cam, speaker)
    guardian_on = True
except Exception as e:                   # no model file, ultralytics missing...
    print("Obstacle warnings are off:", e)

buttons = inputs.setup_gpio(handlers)    # optional: works with no buttons wired

if "--web" in sys.argv:                  # live view in a browser, safe to start with no screen
    try:
        import webview
        webview.start(cam)
    except Exception as e:
        print("Web view is off:", e)

if voice_on:
    speaker.say("Ready. Say activate read mode, or activate object mode.", ANSWER)
else:
    speaker.say("Voice commands are not available.", ANSWER)
if not guardian_on:
    speaker.say("Obstacle warnings are not available.", ANSWER)

if "--view" in sys.argv:
    import viewer
    threading.Thread(target=inputs.keyboard_loop, args=(handlers,), daemon=True).start()
    viewer.run(cam)                      # blocks until you press q in the window
else:
    inputs.keyboard_loop(handlers)       # returns on q, or at once when there is no terminal
    if (voice_on or guardian_on or buttons) and not sys.stdin.isatty():
        while True:                      # started at boot with no terminal: keep running
            time.sleep(1)