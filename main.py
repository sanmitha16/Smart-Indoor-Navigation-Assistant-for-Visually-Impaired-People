import time

from camera import capture_best, warm_up
from vision_ai import ask
from prompts import PROMPTS
from speech import speak


KEYS = {
    "r": "read",
    "c": "color",
    "i": "item",
    "g": "grocery",
    "s": "scene"
}


# Open the camera once when the program starts
warm_up()


while True:

    k = input(
        "r=read c=color i=item g=grocery s=scene q=quit: "
    ).strip().lower()

    if k == "q":
        break

    if k in KEYS:

        speak("Capturing")

        try:

            # -------------------------
            # CAMERA
            # -------------------------
            t0 = time.time()

            path, score = capture_best()

            t1 = time.time()

            print(f"sharpness {score:.0f}")
            print(f"camera {t1 - t0:.1f}s")

            # -------------------------
            # GEMINI AI
            # -------------------------
            answer = ask(
                path,
                PROMPTS[KEYS[k]]
            )

            t2 = time.time()

            print(f"AI {t2 - t1:.1f}s")

            print(f"TOTAL {t2 - t0:.1f}s")

            # -------------------------
            # SPEECH
            # -------------------------
            speak(answer)

        except Exception as e:

            speak("Sorry, something went wrong")

            print(e)