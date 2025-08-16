import os
import io
import base64
import time
import requests
from dotenv import load_dotenv
from PIL import Image, ImageFilter, ImageOps, ImageEnhance
from .cache import get as cache_get, set as cache_set

load_dotenv()

# --- Config (env-driven) ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")                # may be None; handled at call time
IMAGE_MODEL    = os.getenv("GPT_IMAGE_MODEL", "gpt-image-1")
IMG_SIZE       = os.getenv("GPT_IMAGE_SIZE", "1536x1536")
IMG_QUALITY    = os.getenv("GPT_IMAGE_QUALITY", "high")
IMG_FORMAT     = "png"
TIMEOUT_S      = int(os.getenv("GPT_IMAGE_TIMEOUT_S", "90"))
ALLOW_FALLBACK = os.getenv("GPT_ALLOW_FALLBACK_WITHOUT_KEY", "false").lower() == "true"

IMAGES_EDIT_URL = "https://api.openai.com/v1/images/edits"

PROMPT = (
    "Convert this portrait photo into a high-quality cartoon/hand-drawn comic style while KEEPING "
    "the same face identity and proportions. Clean line art, subtle shading, vibrant but natural colors. "
    "No text, no watermarks, no background scene. The output MUST have a fully transparent background (alpha). "
    "Center the subject and keep edges clean for die-cut sticker printing."
)

def _decode_image_payload(json_obj: dict) -> bytes:
    data = json_obj.get("data", [])
    if not data:
        raise ValueError("Empty image data in API response")
    item = data[0]
    b64 = item.get("b64_json") or item.get("image_base64") or item.get("b64")
    if not b64:
        raise ValueError("No base64 image payload found")
    return base64.b64decode(b64)

def _local_cartoon_fallback(photo_bytes: bytes) -> bytes:
    """
    Simple, fast local stylization (no BG removal) — last resort to keep booth running.
    """
    im = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
    base = ImageOps.posterize(im, 3)
    base = ImageEnhance.Color(base).enhance(1.2)
    base = ImageEnhance.Sharpness(base).enhance(1.3)

    edges = im.convert("L").filter(ImageFilter.FIND_EDGES).filter(ImageFilter.SMOOTH_MORE)
    edges_col = ImageOps.colorize(edges, black=(10,10,10), white=(255,255,255))
    out = Image.blend(base, edges_col, alpha=0.15).convert("RGBA")

    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()

def cartoonize_with_bg_remove(photo_bytes: bytes, *, force_fresh: bool = False) -> tuple[bytes, bool]:
    """
    Returns: (png_bytes, used_fallback: bool)
    - Uses disk cache (unless force_fresh=True)
    - Calls OpenAI Images Edit with background=transparent
    - Falls back to local stylize on error (or when key missing and ALLOW_FALLBACK is true)
    """
    # 0) If key missing, decide whether to fallback or error
    if not OPENAI_API_KEY:
        if ALLOW_FALLBACK:
            png_bytes = _local_cartoon_fallback(photo_bytes)
            return png_bytes, True
        raise RuntimeError("OPENAI_API_KEY not set. Please configure it on the server.")

    # 1) Cache check (skip when force_fresh)
    if not force_fresh:
        cached = cache_get("cartoon", photo_bytes, IMAGE_MODEL, IMG_SIZE, IMG_QUALITY, "v1")
        if cached:
            return cached, False

    # 2) Call OpenAI (with fallback size)
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    files = {"image[]": ("input.png", photo_bytes, "image/png")}
    data = {
        "model": IMAGE_MODEL,
        "prompt": PROMPT,
        "size": IMG_SIZE,
        "quality": IMG_QUALITY,
        "background": "transparent",
        "format": IMG_FORMAT,
        "n": "1",
    }

    t0 = time.time()
    try:
        resp = requests.post(IMAGES_EDIT_URL, headers=headers, files=files, data=data, timeout=TIMEOUT_S)
        if resp.status_code != 200:
            # fallback: try smaller size once
            data_small = {**data, "size": "1024x1024"}
            resp2 = requests.post(IMAGES_EDIT_URL, headers=headers, files=files, data=data_small, timeout=TIMEOUT_S)
            if resp2.status_code != 200:
                png_bytes = _local_cartoon_fallback(photo_bytes)
                return png_bytes, True
            png_bytes = _decode_image_payload(resp2.json())
        else:
            png_bytes = _decode_image_payload(resp.json())
    except Exception:
        png_bytes = _local_cartoon_fallback(photo_bytes)
        return png_bytes, True
    finally:
        t1 = time.time()
        print(f"[cartoonize] {IMAGE_MODEL} total {t1 - t0:.2f}s, size={data.get('size')}")

    # 3) Cache & return
    cache_set("cartoon", photo_bytes, png_bytes, IMAGE_MODEL, IMG_SIZE, IMG_QUALITY, "v1")
    return png_bytes, False
