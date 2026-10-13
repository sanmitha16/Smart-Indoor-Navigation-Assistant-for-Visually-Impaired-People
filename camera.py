import platform, threading, time
from collections import deque
import cv2

try:
    from picamera2 import Picamera2
    HAVE_PICAM = True
except Exception:
    HAVE_PICAM = False


class CameraStream:
    """Reads the camera continuously in a background thread so frames are never stale."""

    def __init__(self, index=0, size=(1024, 768)):
        self.frames = deque(maxlen=15)          # (timestamp, frame)
        self.lock = threading.Lock()
        self.running = True
        if HAVE_PICAM:                          # Pi camera on the CSI ribbon
            self.picam = Picamera2()
            self.picam.configure(self.picam.create_video_configuration(
                main={"size": size, "format": "RGB888"}))
            self.picam.start()
        else:                                   # USB webcam or laptop
            backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
            self.cap = cv2.VideoCapture(index, backend)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        threading.Thread(target=self._loop, daemon=True).start()
        t0 = time.time()
        while not self.frames and time.time() - t0 < 5:     # wait for the first frame
            time.sleep(0.05)

    def _loop(self):
        while self.running:
            if HAVE_PICAM:
                frame = self.picam.capture_array()   # "RGB888" arrives in BGR order, ready for OpenCV
                ok = frame is not None
            else:
                ok, frame = self.cap.read()
            if ok:
                with self.lock:
                    self.frames.append((time.time(), frame))
            else:
                time.sleep(0.01)

    def read(self):
        """Latest frame. Same interface as cv2.VideoCapture.read()."""
        with self.lock:
            if not self.frames:
                return False, None
            return True, self.frames[-1][1].copy()

    def recent(self, seconds=0.5):
        now = time.time()
        with self.lock:
            return [f.copy() for t, f in self.frames if now - t <= seconds]

    def isOpened(self):
        return True if HAVE_PICAM else self.cap.isOpened()


_stream = None


def warm_up():
    global _stream
    if _stream is None or not _stream.isOpened():
        _stream = CameraStream()
    return _stream


def sharpness(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def capture_best(path="frame.jpg", width=1024, window=0.5):
    """Pick the sharpest frame from the last half second, resize it and save it."""
    cam = warm_up()
    frames = cam.recent(window)
    if not frames:
        ok, f = cam.read()
        if not ok:
            raise RuntimeError("Camera not found")
        frames = [f]
    best = max(frames, key=sharpness)
    score = sharpness(best)
    h, w = best.shape[:2]
    best = cv2.resize(best, (width, int(h * width / w)))
    cv2.imwrite(path, best)
    return path, score


def capture(path="frame.jpg", width=1024):
    return capture_best(path, width)[0]
