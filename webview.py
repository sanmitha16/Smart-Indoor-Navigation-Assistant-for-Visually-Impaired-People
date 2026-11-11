"""Live camera view in a web browser. Works over SSH and on a Pi with no screen.

Start the app with:   python app.py --web
It prints an address like   http://192.168.1.23:8080   : open it in the browser of any laptop or phone
on the SAME Wi-Fi. You see what the camera sees, the sharpness score, and the guardian's boxes:
  green box = the guardian counts it, grey box = seen but filtered out (too weak or the wrong size).

Anyone on the same network can open this address, so use it for testing and demos, not as a permanent setting.
Choose another port with:   export WEB_PORT=8081
"""
import os, socket, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import cv2

PORT = int(os.environ.get("WEB_PORT") or 8080)
FPS = 8
PAGE = (b"<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>"
        b"<title>Camera view</title><body style='margin:0;background:#111;color:#eee;font-family:sans-serif'>"
        b"<p style='padding:8px 12px;margin:0'>Live camera. Green box = guardian counts it, grey = filtered out.</p>"
        b"<img src='/stream' style='width:100%;max-width:960px;display:block'></body>")


def _draw(frame):
    """The frame with the sharpness score and the guardian's latest boxes."""
    from camera import sharpness
    img = frame.copy()
    h, w = img.shape[:2]
    try:
        import ask
        good = sharpness(frame) >= ask.BLUR_THRESHOLD
        score = sharpness(frame)
        cv2.putText(img, f"sharpness {score:.0f}  {'OK' if good else 'BLURRY'}", (10, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0) if good else (0, 0, 255), 2, cv2.LINE_AA)
    except Exception:
        pass
    try:
        import guardian
        latest = guardian.latest
        if time.time() - latest["time"] < 2:                 # only boxes from the last 2 seconds
            for name, conf, (x1, y1, x2, y2) in latest["dets"]:
                counted = guardian.passes_filters(name, conf, (x1, y1, x2, y2), w, h)
                color = (0, 200, 0) if counted else (160, 160, 160)
                cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
                cv2.putText(img, f"{name} {conf:.2f}", (x1, max(16, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    except Exception:
        pass
    return img


def _handler_for(cam):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(PAGE)))
                self.end_headers()
                self.wfile.write(PAGE)
            elif self.path.startswith("/stream"):
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                try:
                    while True:
                        ok, frame = cam.read()
                        if ok and frame is not None:
                            good, jpg = cv2.imencode(".jpg", _draw(frame), [cv2.IMWRITE_JPEG_QUALITY, 70])
                            if good:
                                data = jpg.tobytes()
                                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                                 + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n")
                        time.sleep(1.0 / FPS)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass                                      # the browser tab was closed
            else:
                self.send_error(404)
    return Handler


def _my_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))                            # no data is sent; this just picks the Wi-Fi address
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "<the Pi's address>"


def start(cam, port=None):
    """Start the web view in the background. Returns the server."""
    port = port or PORT
    server = ThreadingHTTPServer(("0.0.0.0", port), _handler_for(cam))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Live view: open  http://{_my_address()}:{port}  in a browser on the same Wi-Fi", flush=True)
    return server