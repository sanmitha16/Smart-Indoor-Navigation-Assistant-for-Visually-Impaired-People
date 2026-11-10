"""Speed test for the Pi: how many frames per second can YOLO process at different image sizes?

  python bench_pi.py                                  uses config.MODEL_PATH at 640, 416 and 320
  python bench_pi.py best_door_finetune_ncnn_model 320     a specific model and size(s)

An exported NCNN model only works at the size it was exported with.
"""
import subprocess, sys, time
from ultralytics import YOLO
from camera import warm_up
import config


def vc(arg):
    try:
        return subprocess.run(["vcgencmd", arg], capture_output=True, text=True).stdout.strip()
    except Exception:
        return "n/a"


cam = warm_up()
time.sleep(1.5)                          # let the camera settle
path = sys.argv[1] if len(sys.argv) > 1 else config.MODEL_PATH
sizes = [int(s) for s in sys.argv[2:]] or [640, 416, 320]

model = YOLO(path, task="detect")
print("model:", path)
print("before:", vc("measure_temp"), vc("get_throttled"))

for size in sizes:
    for _ in range(3):                   # warm-up, the first runs are slow
        model(cam.read()[1], imgsz=size, verbose=False)
    n = 20
    t = time.time()
    for _ in range(n):
        model(cam.read()[1], imgsz=size, verbose=False)
    dt = time.time() - t
    print(f"{size}px: {n / dt:.1f} fps  ({1000 * dt / n:.0f} ms per frame)")

print("after: ", vc("measure_temp"), vc("get_throttled"))