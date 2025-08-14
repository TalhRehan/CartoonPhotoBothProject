from PIL import Image, ImageDraw
import io

A4_PX = (2480, 3508)  # 300 DPI approx

def make_a4_sheet(sticker_png_bytes: bytes) -> bytes:
    base = Image.new("RGBA", A4_PX, (255, 255, 255, 255))
    sticker = Image.open(io.BytesIO(sticker_png_bytes)).convert("RGBA")

    # Rough layout: 2x2 grid with margins (will fine-tune later)
    W, H = A4_PX
    margin = 120
    cols, rows = 2, 2
    cell_w = (W - margin * 3) // cols
    cell_h = (H - margin * 3) // rows

    # Fit sticker into cell while preserving aspect
    sticker = sticker.copy()
    sticker.thumbnail((cell_w, cell_h), Image.LANCZOS)

    positions = [
        (margin, margin),
        (margin*2 + cell_w, margin),
        (margin, margin*2 + cell_h),
        (margin*2 + cell_w, margin*2 + cell_h),
    ]
    for pos in positions:
        base.alpha_composite(sticker, dest=pos)

    # Cut lines (dotted)
    draw = ImageDraw.Draw(base)
    # vertical
    x = margin*1.5 + cell_w
    draw.line([(int(x), margin), (int(x), H-margin)], fill=(0,0,0,120), width=3)
    # horizontal
    y = margin*1.5 + cell_h
    draw.line([(margin, int(y)), (W-margin, int(y))], fill=(0,0,0,120), width=3)

    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()
