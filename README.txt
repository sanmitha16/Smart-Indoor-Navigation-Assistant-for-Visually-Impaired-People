BLIND ASSIST - INTEGRATION FILES
================================

Copy these files into C:\blind_assist (replace camera.py and prompts.py and speech.py when asked).
Do NOT replace vision_ai.py: keep your working one. Keep best_door_finetune.pt in the same folder.

Files
  app.py        top module: run this instead of main.py
  config.py     MODEL_PATH and IMGSZ (the only things you change for the Pi)
  detector.py   wraps your friend's YOLO model behind detect(frame)
  guardian.py   always-on loop: stairs, door, window, person alerts (wall is off on purpose)
  ask.py        Gemini on button press: read, color, item, scene, repeat, pack
  inputs.py     GPIO buttons on the Pi, keyboard on the laptop
  speech.py     one speaker with priorities (works on Windows and Pi)
  prompts.py    prompts (item merged with grocery; scene also covers lift, escalator, wet floor, sharp objects)
  camera.py     threaded camera: laptop webcam now, Pi camera (picamera2) on the Pi
  test_logic.py simulated test for the guardian and speaker logic (no camera or model needed)

Run on the laptop
  cd C:\blind_assist
  venv\Scripts\activate
  python app.py
  keys: r read, c color, i item, s scene, x repeat, p pack, q quit

Check
  1. You hear "System ready. Guardian on."
  2. Stand in front of the camera: Guardian speaks "Person ahead" about every 6 seconds.
  3. Press i with an object in view: you hear "Item", then the answer, while Guardian keeps running.
  4. Press i twice quickly: the second press says "Please wait".
  5. Turn Wi-Fi off and press r: "No internet".

Classes in best_door_finetune.pt: wall, door, stairs, person, window.
Not covered by this model (Gemini scene mode covers them for now): lift, escalator, wet floor, knife, scissors.
