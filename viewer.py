"""Live camera window for testing: shows what the camera sees and how sharp it is.

  Sharpness is the number the app checks before sending a picture to Gemini.
  Green = good enough (at least ask.BLUR_THRESHOLD), red = the app would retake the picture.

Start the app with:  python app.py --view        Press q in the window to close it.
"""
import cv2
import ask
from camera import sharpness


def run(cam, title="Camera view (press q to close)"):
    try:
        while True:
            ok, frame = cam.read()
            if ok:
                img = frame.copy()
                score = sharpness(frame)
                good = score >= ask.BLUR_THRESHOLD
                cv2.putText(img, f"sharpness {score:.0f}  {'OK' if good else 'BLURRY, hold steady'}", (10, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 0) if good else (0, 0, 255), 2, cv2.LINE_AA)
                cv2.imshow(title, img)
            if cv2.waitKey(30) & 0xFF == ord("q"):
                break
    except cv2.error as e:
        print("Cannot open a camera window here (no screen?):", e)
    finally:
        cv2.destroyAllWindows()