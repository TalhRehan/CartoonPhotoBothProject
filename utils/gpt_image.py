import os
import io
import base64
import requests
from PIL import Image

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY missing in environment")

# OpenAI Images Edit endpoint (use for img2img style transform)
# Docs: Images API (create/edit) + output options (size, quality, format, background)
# https://platform.openai.com/docs/api-reference/images/createEdit
# https://platform.openai.com/docs/guides/image-generation
IMAGES_EDIT_URL = "https://api.openai.com/v1/images/edits"

# Tunables (balance latency vs quality for booth speed)
IMG_SIZE = os.getenv("GPT_IMAGE_SIZE", "1536x1536")  # 1024x1024, 1024x1536, 1536x1536, etc.
IMG_QUALITY = os.getenv("GPT_IMAGE_QUALITY", "high") # low|medium|high (per docs)
IMG_FORMAT = "png"                                   # want PNG for transparency
TIMEOUT_S = 90

PROMPT = (
    "Convert this portrait photo into a high-quality cartoon/hand-drawn comic style while KEEPING "
    "the same face identity and proportions. Clean line art, subtle shading, vibrant but natural colors. "
    "No text, no watermarks, no background scene. The output MUST have a fully transparent background (alpha). "
    "Center the subject and keep edges clean for die-cut sticker printing."
)

def _decode_image_payload(json_obj: dict) -> bytes:
    """
    Handle possible payload shapes from Images API.
    Historically: {'data':[{'b64_json':'...'}]}
    Some clients may return {'data':[{'image_base64':'...'}]}.
    """
    data = json_obj.get("data", [])
    if not data:
        raise ValueError("Empty image data in API response")
    item = data[0]
    b64 = item.get("b64_json") or item.get("image_base64") or item.get("b64")
    if not b64:
        raise ValueError("No base64 image payload found")
    return base64.b64decode(b64)

def _has_alpha(png_bytes: bytes) -> bool:
    try:
        im = Image.open(io.BytesIO(png_bytes))
        return im.mode in ("LA", "RGBA", "PA") or ("transparency" in im.info)
    except Exception:
        return False

def cartoonize_with_bg_remove(photo_bytes: bytes) -> bytes:
    """
    Send captured photo to OpenAI Images Edit API (gpt-image-1) to stylize as cartoon
    with transparent background, returning high-res PNG bytes.
    """
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    # First attempt: high quality, requested transparent BG
    files = {
        "image[]": ("input.png", photo_bytes, "image/png"),
    }
    data = {
        "model": "gpt-image-1",
        "prompt": PROMPT,
        "size": IMG_SIZE,              # e.g. 1536x1536
        "quality": IMG_QUALITY,        # high
        "background": "transparent",   # request alpha BG (per docs)
        "format": IMG_FORMAT,          # png
        "n": "1",
    }

    resp = requests.post(IMAGES_EDIT_URL, headers=headers, files={**files}, data=data, timeout=TIMEOUT_S)
    if resp.status_code != 200:
        # Fallback: try a smaller size to reduce latency/cost if first fails
        try_small = requests.post(
            IMAGES_EDIT_URL,
            headers=headers,
            files={**files},
            data={**data, "size": "1024x1024"},
            timeout=TIMEOUT_S
        )
        if try_small.status_code != 200:
            raise RuntimeError(f"OpenAI image edit error: {resp.status_code} {resp.text} / fallback: {try_small.status_code} {try_small.text}")
        png_bytes = _decode_image_payload(try_small.json())
    else:
        png_bytes = _decode_image_payload(resp.json())

    # Sanity: ensure image has alpha; if not, still return (frontend can show over white)
    # (If your org observes missing alpha on edits, we can switch to Responses API image_generation tool path next.)
    if not _has_alpha(png_bytes):
        # Not strictly failing—return as-is; printing still OK on white media.
        return png_bytes

    return png_bytes
