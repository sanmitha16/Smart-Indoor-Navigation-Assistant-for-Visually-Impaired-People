# Central settings. Change these when moving from the laptop to the Pi.

# Camera. A USB webcam on the Pi is usually index 0 (/dev/video0). If the app cannot find it,
# run 'v4l2-ctl --list-devices' and use the number of the webcam's first /dev/videoN.
USE_PICAMERA2 = False                  # False = USB webcam through OpenCV. Set True only for the ribbon Pi camera.
CAMERA_INDEX = 0
CAMERA_WIDTH = 1280                    # lower to 640 / 480 if the Pi struggles
CAMERA_HEIGHT = 720