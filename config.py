# Central settings. Change these when moving from the laptop to the Pi.
MODEL_PATH = "best_door_finetune.pt"   # later: the exported NCNN folder, e.g. "best_door_finetune_ncnn_model"
IMGSZ = 640                            # first test at 640 (matches your friend), then try 416 or 320 on the Pi
DETECT_CONF = 0.25                     # model-level threshold; per-class rules live in guardian.py
