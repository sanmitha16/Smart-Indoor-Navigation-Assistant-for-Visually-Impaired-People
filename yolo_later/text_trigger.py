"""Local text check: is there something written in front of the camera?  No internet, no model file.

It looks for rows of small, dense, text-like blobs (words and lines) on a small copy of the frame.
This is a cheap heuristic. It decides only whether to ASK the user; Gemini does the actual reading.
"""
import cv2
import numpy as np

# Tuning values. If it asks too often on plain walls, raise MIN_BOXES or MIN_COVER.
# If it misses real text, lower them. Check with:  python text_trigger.py frame.jpg
WORK_WIDTH = 320          # the frame is shrunk to this width first (fast on the Pi)
MIN_BOXES = 5             # many small word/line blobs (a page, a notice board) ...
MIN_COVER = 0.02          # ... covering at least this fraction of the picture
FEW_BOXES = 2             # OR a few big blobs (a sign, a label) ...
FEW_COVER = 0.05          # ... covering at least this much
ONE_COVER = 0.08          # OR one large blob (one big word on a sign) covering at least this much
MIN_EDGE = 40             # flat, featureless scenes (a plain wall) are skipped


def find_text(frame):
    """Return (boxes, cover). boxes = list of (x, y, w, h) on the small frame; cover = area fraction."""
    h0, w0 = frame.shape[:2]
    small = cv2.resize(frame, (WORK_WIDTH, max(1, int(h0 * WORK_WIDTH / w0))))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    if np.percentile(grad, 99) < MIN_EDGE:               # nothing sharp in the picture at all
        return [], 0.0

    _, bw = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    joined = cv2.morphologyEx(bw, cv2.MORPH_CLOSE,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (9, 1)))
    contours, _ = cv2.findContours(joined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    H, W = gray.shape
    boxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w < 14 or h < 5 or h > 100:                   # too small, or too tall for text
            continue
        if w / h < 1.5:                                   # words and lines are wider than tall
            continue
        fill = cv2.countNonZero(bw[y:y + h, x:x + w]) / float(w * h)
        if fill < 0.25 or fill > 0.9:                     # letters leave gaps; solid blocks are not text
            continue
        boxes.append((x, y, w, h))

    cover = sum(w * h for _, _, w, h in boxes) / float(W * H)
    return boxes, cover


def has_text(frame):
    boxes, cover = find_text(frame)
    n = len(boxes)
    return ((n >= MIN_BOXES and cover >= MIN_COVER) or (n >= FEW_BOXES and cover >= FEW_COVER)
            or (n >= 1 and cover >= ONE_COVER))


if __name__ == "__main__":
    import sys
    for path in sys.argv[1:] or ["frame.jpg"]:
        img = cv2.imread(path)
        boxes, cover = find_text(img)
        print(f"{path}: {len(boxes)} text-like blobs, cover {cover:.3f} -> "
              f"{'TEXT' if has_text(img) else 'no text'}")