BLIND ASSIST - TWO MODES (Gemini only)
======================================

Reading mode : reads the text in front of the camera aloud.
Object mode  : says what the main object is and where it is (left / ahead / right, within reach / near / far).
               "o keys" (or "find keys") looks for keys instead.

The YOLO guardian (door, stairs, window, person) is parked in the folder yolo_later until your friend's
model is ready. Nothing was deleted.

Files
  app.py        start here:  python app.py        (python app.py --view also opens a live camera window)
  ask.py        the two modes: take a sharp picture, ask Gemini, speak the answer, handle errors
  prompts.py    what Gemini is asked in each mode
  inputs.py     two buttons on the Pi (GPIO 17 and 27), keyboard on the laptop; python inputs.py tests the wiring
  speech.py     one voice (espeak-ng on the Pi, Windows speech on the laptop), can be stopped
  camera.py     threaded camera that always has a fresh frame and picks the sharpest one (unchanged)
  config.py     camera settings only
  viewer.py     live camera window with the sharpness number (python app.py --view)
  vision_ai.py  YOUR file, unchanged
  test_logic.py simulated test of the modes, buttons and speaker (no camera, no internet needed)

Keys on the laptop
  r  read        o  object        o keys  look for keys        x  repeat the last answer        q  quit

Buttons on the Pi
  left button (GPIO 17)  Reading mode          right button (GPIO 27)  Object mode
  hold either one for 1.5 seconds = repeat the last answer
  press while it is talking = stop talking

Spoken messages
  Ready ...                            started
  Reading / Looking                    working on it
  Hold steady and try again            two blurry pictures in a row
  Please wait                          you pressed again while Gemini was still answering
  No internet                          cannot reach Gemini
  Limit reached, try again in a minute free Gemini limit
  Key problem                          the API key is wrong or missing
  Camera problem                       the camera did not give a picture

Start automatically when the Pi boots (run on the Pi, in the project folder, with the key in ~/.gemini_key)
  printf 'GEMINI_API_KEY=%s\n' "$(tr -d '[:space:]' < ~/.gemini_key)" > ~/.gemini.env
  chmod 600 ~/.gemini.env
  mkdir -p ~/.config/systemd/user
  cp blind_assist.service ~/.config/systemd/user/
  systemctl --user daemon-reload
  systemctl --user enable --now blind_assist.service
  sudo loginctl enable-linger $USER
  journalctl --user -u blind_assist -f        (watch what it prints; Ctrl+C to leave)
  Stop it while testing by hand:  systemctl --user stop blind_assist
  Turn auto-start off:            systemctl --user disable --now blind_assist