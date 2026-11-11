"""YOLO guardian: watches the camera all the time and speaks short warnings by itself.

Ported from realtime_final.py (same model, thresholds and logic). What changed:
  - frames come from the shared camera in camera.py (the webcam cannot be opened twice)
  - warnings are spoken through speech.py, so they never overlap with answers or voice feedback
  - "stairs" is spoken at CRITICAL priority: it interrupts an answer that is being read
    (say "repeat" afterwards to hear the answer again). Other warnings wait for the current speech.
  - no pyttsx3, no preview window

Tune the numbers below. To use a faster exported model (for example NCNN or ONNX on the Pi), set
YOLO_MODEL to its path, for instance:   export YOLO_MODEL=best_final_ncnn_model
"""
import os, threading, time
from collections import deque, Counter
from speech import CRITICAL, GUARDIAN

_HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.environ.get("YOLO_MODEL") or os.path.join(_HERE, "best_final.pt")
IMGSZ = int(os.environ.get("YOLO_IMGSZ") or 416)   # 640 is too heavy for a Pi 4. Set YOLO_IMGSZ=320 to match a 320 NCNN export

# Per-class thresholds: strict on stairs (false positives), lenient on door (missed)
CLASS_CONF = {
    "door": 0.30,
    "stairs": 0.75,
    "person": 0.50,
    "window": 0.40,
    "wall": 0.60,
}
ANNOUNCE = {"door", "wall", "stairs", "person", "window"}
URGENT = {"stairs"}          # spoken at CRITICAL priority

# Temporal confirmation: a class must appear in CONFIRM_K of the last WINDOW_M frames
WINDOW_M = 6
CONFIRM_K = 3
CONFIRM_K_CLASS = {"stairs": 4}   # stairs interrupts everything, so it must be seen in more frames

# Stairs sanity check for a chest mounted camera
STAIRS_MIN_BOTTOM = 0.55     # box bottom edge must be in the lower 45% of the frame
STAIRS_MIN_AREA = 0.06       # box must cover at least 6% of the frame

COOLDOWN = 5                 # seconds before a moved object is announced again
ABSENCE_TIME = 2             # seconds of absence before an object counts as new
ALERT_MAX_AGE = 4            # a warning that waited longer than this is dropped (it is stale)

GLOBAL_GAP = 3               # seconds between any two non-urgent warnings (stops rapid-fire chatter)
MAX_FPS = 6                  # detections per second at most: leaves CPU for voice and Gemini
THREADS = int(os.environ.get("GUARDIAN_THREADS", "2"))   # CPU threads YOLO may use

MIN_CONF = min(CLASS_CONF.values())


def get_zone(x, width):
    r = x / width
    if r < 1 / 3:
        return "left"
    if r > 2 / 3:
        return "right"
    return "center"


def make_message(name, zone):
    return f"{name} ahead" if zone == "center" else f"{name} on your {zone}"


def passes_filters(name, conf, box, w, h):
    if conf < CLASS_CONF.get(name, 0.5):
        return False
    x1, y1, x2, y2 = box
    if name == "stairs":
        if y2 < STAIRS_MIN_BOTTOM * h:
            return False
        if (x2 - x1) * (y2 - y1) < STAIRS_MIN_AREA * w * h:
            return False
    return True


class Guardian:
    def __init__(self, cam, speaker, model=None):
        self.cam = cam
        self.speaker = speaker
        self.model = model
        self.history = deque(maxlen=WINDOW_M)    # set of class names seen per frame
        self.state = {}
        self.last_alert = -1e9
        self.running = True

    def update(self, detections, w, h, now):
        """detections: list of (name, conf, (x1, y1, x2, y2)). Speaks what is new. Returns the messages."""
        visible = {}
        for name, conf, box in detections:
            if not passes_filters(name, conf, box, w, h):
                continue
            if name not in visible or conf > visible[name]["conf"]:
                cx = (box[0] + box[2]) // 2
                visible[name] = {"conf": conf, "box": box, "zone": get_zone(cx, w)}

        self.history.append(set(visible))
        counts = Counter(n for s in self.history for n in s)
        confirmed = {n for n, c in counts.items() if c >= CONFIRM_K_CLASS.get(n, CONFIRM_K)}

        spoken = []
        for name, d in visible.items():
            if name not in confirmed or name not in ANNOUNCE:
                continue
            zone = d["zone"]
            prev = self.state.get(name)
            announce = (
                prev is None
                or now - prev["last_seen"] >= ABSENCE_TIME
                or (zone != prev["zone"] and now - prev["last_spoken"] >= COOLDOWN)
            )
            if announce and name not in URGENT and now - self.last_alert < GLOBAL_GAP:
                if prev:                         # too soon after another warning: try again on a later frame
                    prev["last_seen"] = now
                continue
            if announce:
                msg = make_message(name, zone)
                priority = CRITICAL if name in URGENT else GUARDIAN
                print(f"GUARDIAN: {name} {d['conf']:.2f} {zone}", flush=True)   # to tune CLASS_CONF
                self.speaker.say(msg, priority, max_age=ALERT_MAX_AGE)
                self.last_alert = now
                spoken.append(msg)
                self.state[name] = {"zone": zone, "last_seen": now, "last_spoken": now}
            else:
                self.state[name]["last_seen"] = now
                self.state[name]["zone"] = zone

        for name in list(self.state):
            if name not in confirmed and now - self.state[name]["last_seen"] >= ABSENCE_TIME:
                del self.state[name]
        return spoken

    def _detect(self, frame):
        result = self.model.predict(frame, imgsz=IMGSZ, conf=MIN_CONF, verbose=False)[0]
        return [(self.model.names[int(b.cls[0].item())],
                 float(b.conf[0].item()),
                 tuple(map(int, b.xyxy[0].tolist()))) for b in result.boxes]

    def _loop(self):
        failures = 0
        frames = 0
        t0 = time.time()
        while self.running:
            ok, frame = self.cam.read()
            if not ok or frame is None:
                time.sleep(0.1)
                continue
            started = time.time()
            h, w = frame.shape[:2]
            try:
                detections = self._detect(frame)
                failures = 0
            except Exception as e:
                failures += 1
                print("Guardian error:", e, flush=True)
                if failures >= 5:
                    print("Guardian stopped after repeated errors", flush=True)
                    self.speaker.say("Obstacle warnings stopped", CRITICAL)
                    return
                time.sleep(1)
                continue
            self.update(detections, w, h, time.time())
            frames += 1
            if frames % 60 == 0:                 # speed report, useful for the Pi
                print(f"Guardian: {frames / (time.time() - t0):.1f} frames per second", flush=True)
                frames, t0 = 0, time.time()
            time.sleep(max(0.02, 1.0 / MAX_FPS - (time.time() - started)))   # let the other threads breathe

    def stop(self):
        self.running = False


def start(cam, speaker):
    """Load the model and start watching in the background. Raises RuntimeError with a readable reason."""
    if not os.path.exists(MODEL_PATH):
        raise RuntimeError(f"model not found: {MODEL_PATH} (copy best_final.pt into the project folder)")
    try:
        from ultralytics import YOLO
    except Exception as e:
        raise RuntimeError(f"ultralytics is missing ({e}). Run: pip install ultralytics")
    try:
        import torch
        torch.set_num_threads(THREADS)
    except Exception:
        pass
    try:
        import numpy as np
        model = YOLO(MODEL_PATH)
        model.predict(np.zeros((480, 640, 3), dtype=np.uint8), imgsz=IMGSZ, verbose=False)   # warm-up
    except Exception as e:
        raise RuntimeError(f"the model could not run ({e})")
    g = Guardian(cam, speaker, model)
    threading.Thread(target=g._loop, daemon=True).start()
    print("Obstacle guardian running, model:", os.path.basename(MODEL_PATH), flush=True)
    return g