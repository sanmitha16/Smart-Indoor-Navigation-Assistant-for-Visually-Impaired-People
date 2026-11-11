"""Takes ONE picture from the camera and runs it through the guardian model in different ways,
so you can see whether the problem is the image size, the NCNN conversion, or the camera.

    python compare_models.py

Stand where the camera can see you (or point it at stairs / a door) before you press Enter.
Saves compare_frame.jpg (what the camera saw) and compare_<name>.jpg (the detections drawn on it).
"""
import os, sys, time
import cv2

CONF = 0.25          # low on purpose, so you see everything the model thinks it sees
CONFIGS = [          # (model, image size)
    ("best_final.pt", 640),
    ("best_final.pt", 416),
    ("best_final.pt", 320),
    ("best_final_ncnn_model", 320),
    ("best_final_ncnn_model", 416),     # only valid if you exported with imgsz=416
]

input("Get the camera pointing at what you want to test, then press Enter... ")
from camera import warm_up
cam = warm_up()
time.sleep(2)
frame = None
for _ in range(10):
    ok, f = cam.read()
    if ok:
        frame = f
    time.sleep(0.1)
if frame is None:
    sys.exit("No picture from the camera.")
cv2.imwrite("compare_frame.jpg", frame)
print(f"Picture saved: compare_frame.jpg  ({frame.shape[1]}x{frame.shape[0]})  <- OPEN IT and check it shows what you expect\n")

from ultralytics import YOLO
here = os.path.dirname(os.path.abspath(__file__))
for path, size in CONFIGS:
    full = os.path.join(here, path)
    if not os.path.exists(full):
        continue
    if "ncnn" in path:
        # an NCNN model only works at the size it was exported with; trying others is meaningless
        pass
    try:
        m = YOLO(full, task="detect")
        m.predict(frame, imgsz=size, conf=CONF, verbose=False)        # warm-up
        t = time.time()
        for _ in range(3):
            r = m.predict(frame, imgsz=size, conf=CONF, verbose=False)[0]
        ms = (time.time() - t) / 3 * 1000
    except Exception as e:
        print(f"{path} @ {size}: FAILED ({str(e)[:100]})\n")
        continue
    found = sorted(((m.names[int(b.cls[0])], float(b.conf[0])) for b in r.boxes), key=lambda x: -x[1])
    text = ", ".join(f"{n} {c:.2f}" for n, c in found) or "nothing"
    print(f"{path} @ {size}   {ms:.0f} ms/frame")
    print(f"    sees: {text}\n")
    cv2.imwrite(f"compare_{path.replace('.pt','').replace('_model','')}_{size}.jpg", r.plot())
print("Done. Compare the lists: if the .pt lines find the person and the NCNN lines do not,")
print("the NCNN conversion or small size is the problem. If all of them miss, it is the model or the camera view.")