import numpy as np
from ultralytics import YOLO
from config import MODEL_PATH, IMGSZ, DETECT_CONF

model = YOLO(MODEL_PATH, task="detect")
# Warm-up once at startup: the first inference is slow (seconds), later ones are fast
model(np.zeros((IMGSZ, IMGSZ, 3), dtype="uint8"), imgsz=IMGSZ, verbose=False)


def detect(frame):
    """Return a list of detections: name, confidence, centre x (0-1), height and width as a fraction of the frame."""
    H, W = frame.shape[:2]
    res = model(frame, imgsz=IMGSZ, conf=DETECT_CONF, verbose=False)[0]
    out = []
    for b in res.boxes:
        x1, y1, x2, y2 = b.xyxy[0].tolist()
        out.append({
            "name": model.names[int(b.cls)],
            "conf": float(b.conf),
            "cx": (x1 + x2) / 2 / W,
            "h": (y2 - y1) / H,
            "w": (x2 - x1) / W,
        })
    return out
