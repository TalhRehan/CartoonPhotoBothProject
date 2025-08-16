import numpy as np, cv2

BLUR_THRESHOLD = 110.0   # lower = blur
DARK_THRESHOLD = 60.0    # lower = dark

def assess_quality(image_bytes: bytes) -> dict:
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return {"ok": False, "blur": 0.0, "brightness": 0.0, "reason": "decode_failed"}
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.Laplacian(gray, cv2.CV_64F).var()
    brightness = float(gray.mean())
    if blur < BLUR_THRESHOLD:
        return {"ok": False, "blur": float(blur), "brightness": brightness, "reason": "blurry"}
    if brightness < DARK_THRESHOLD:
        return {"ok": False, "blur": float(blur), "brightness": brightness, "reason": "dark"}
    return {"ok": True, "blur": float(blur), "brightness": brightness, "reason": None}
