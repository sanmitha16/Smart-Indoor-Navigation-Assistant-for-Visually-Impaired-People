import time
from detector import detect
from speech import GUARDIAN

# Classes in best_door_finetune.pt: wall, door, stairs, person, window.
# Dict order = priority order (most important first). One alert is spoken per cycle.
RULES = {
    "stairs": dict(say="Stairs", conf=0.35, cooldown=5,  min_h=0.0),
    "door":   dict(say="Door",   conf=0.35, cooldown=8,  min_h=0.0),
    "window": dict(say="Window", conf=0.35, cooldown=8,  min_h=0.0),
    "person": dict(say="Person", conf=0.50, cooldown=6,  min_h=0.0),
}

# Walls fill the frame almost everywhere indoors, so announcing them would be constant noise.
# Leave this False and let the distance sensor handle "wall close" later.
WALL_ALERT = False
if WALL_ALERT:
    RULES["wall"] = dict(say="Wall", conf=0.50, cooldown=10, min_h=0.85)

LOOP_SLEEP = 0.05      # seconds; raise to 0.1 on the Pi so YOLO leaves CPU for the camera and Gemini


def run(cam, speaker):
    last = {}
    while True:
        ok, frame = cam.read()
        if not ok:
            time.sleep(0.05)
            continue

        found = {}
        for d in detect(frame):
            r = RULES.get(d["name"])
            if r and d["conf"] >= r["conf"] and d["h"] >= r["min_h"]:
                if d["name"] not in found or d["h"] > found[d["name"]]["h"]:
                    found[d["name"]] = d

        now = time.time()
        for name, r in RULES.items():
            if name in found and now - last.get(name, 0) > r["cooldown"]:
                d = found[name]
                side = "on left" if d["cx"] < 0.35 else "on right" if d["cx"] > 0.65 else "ahead"
                near = ", close" if d["h"] > 0.6 else ""
                speaker.say(f"{r['say']} {side}{near}", GUARDIAN, max_age=2)
                last[name] = now
                break

        time.sleep(LOOP_SLEEP)
