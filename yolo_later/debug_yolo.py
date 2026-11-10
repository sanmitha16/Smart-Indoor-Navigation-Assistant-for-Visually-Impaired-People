import cv2
from ultralytics import YOLO
from camera import warm_up

model = YOLO("yolo11n.pt")
cap = warm_up()
IMGSZ = 640
CONF = 0.10        # very low on purpose, to see weak detections

while True:
    ok, frame = cap.read()
    if not ok:
        continue
    res = model(frame, imgsz=IMGSZ, conf=CONF, verbose=False)[0]
    cv2.imshow("debug (press q to quit)", res.plot())
    print([f"{model.names[int(b.cls)]} {float(b.conf):.2f}" for b in res.boxes])
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cv2.destroyAllWindows()