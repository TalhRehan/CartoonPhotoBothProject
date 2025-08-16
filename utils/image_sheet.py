# Import necessary libraries for image processing and mathematical operations
from PIL import Image, ImageDraw, ImageOps, ImageFont, ImageFilter
import io
import os
import math

# === Define print metrics for A4 sheet ===
DPI = 300  # Set resolution to 300 DPI
A4_MM = (210, 297)  # A4 dimensions in millimeters (width, height)

# Convert millimeters to pixels based on DPI
def mm_to_px(mm):
    inches = mm / 25.4  # Convert mm to inches
    return int(round(inches * DPI))  # Convert inches to pixels and round

# Calculate A4 dimensions in pixels
A4_PX = (mm_to_px(A4_MM[0]), mm_to_px(A4_MM[1]))

# Define layout constants in millimeters
MARGIN_MM = 15  # Margin around the sheet
GUTTER_MM = 10  # Space between stickers
SAFE_PAD_MM = 4  # Safe padding within each sticker
BLEED_MM = 2  # Bleed area for printing

# Define border thickness options for stickers
BORDER_MAP = {
    "none": 0,    # No border
    "thin": 4,    # Thin border (4px)
    "medium": 7,  # Medium border (7px)
    "thick": 12,  # Thick border (12px)
    "dotted": 6,  # Dotted border (6px)
}

# Draw a dashed line between two points
def _draw_dashed_line(draw, p1, p2, dash=20, gap=14, fill=(0,0,0,120), width=3):
    x1, y1 = p1; x2, y2 = p2
    total_len = math.hypot(x2 - x1, y2 - y1)  # Calculate line length
    if total_len == 0: return  # Exit if line has no length
    dx = (x2 - x1) / total_len  # Normalize x direction
    dy = (y2 - y1) / total_len  # Normalize y direction
    n = int(total_len // (dash + gap)) + 1  # Number of dash segments
    for i in range(n):
        start_len = i * (dash + gap)  # Start position of dash
        end_len = min(total_len, start_len + dash)  # End position of dash
        sx = x1 + dx * start_len; sy = y1 + dy * start_len  # Start coordinates
        ex = x1 + dx * end_len;   ey = y1 + dy * end_len    # End coordinates
        draw.line([(sx, sy), (ex, ey)], fill=fill, width=width)  # Draw dash segment


# Draw a dotted ellipse with specified parameters
def _dotted_ellipse(draw, bbox, fill, width=4, dot_arc_deg=6, gap_arc_deg=6):
    start = 0
    while start < 360:  # Loop through 360 degrees
        end = min(360, start + dot_arc_deg)  # Calculate arc end
        draw.arc(bbox, start=start, end=end, fill=fill, width=width)  # Draw arc segment
        start += dot_arc_deg + gap_arc_deg  # Move to next arc start

# Draw a dotted rectangle using dashed lines
def _dotted_rect(draw, bbox, fill, width=4, dash=16, gap=10):
    x0, y0, x1, y1 = bbox  # Unpack bounding box coordinates
    _draw_dashed_line(draw, (x0, y0), (x1, y0), dash=dash, gap=gap, fill=fill, width=width)  # Top
    _draw_dashed_line(draw, (x1, y0), (x1, y1), dash=dash, gap=gap, fill=fill, width=width)  # Right
    _draw_dashed_line(draw, (x1, y1), (x0, y1), dash=dash, gap=gap, fill=fill, width=width)  # Bottom
    _draw_dashed_line(draw, (x0, y1), (x0, y0), dash=dash, gap=gap, fill=fill, width=width)  # Left



# Create a mask for a rounded rectangle
def _rounded_rect_mask(size, radius):
    w, h = size  # Unpack size
    mask = Image.new("L", size, 0)  # Create a grayscale mask
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0,0,w,h], radius=radius, fill=255)  # Draw filled rounded rectangle
    return mask

# Create a mask for a circular shape
def _circle_mask(size):
    w, h = size  # Unpack size
    r = min(w, h) // 2  # Calculate radius
    mask = Image.new("L", (w, h), 0)  # Create a grayscale mask
    draw = ImageDraw.Draw(mask)
    draw.ellipse([(w//2 - r, h//2 - r), (w//2 + r, h//2 + r)], fill=255)  # Draw filled circle
    return mask

# Center an image within a base image
def _place_center(base_rgba, fg_rgba):
    bw, bh = base_rgba.size  # Base image dimensions
    fw, fh = fg_rgba.size    # Foreground image dimensions
    x = (bw - fw) // 2      # Calculate x offset for centering
    y = (bh - fh) // 2      # Calculate y offset for centering
    base_rgba.alpha_composite(fg_rgba, dest=(x, y))  # Composite foreground onto base

# Load brand icon from possible file paths
def _load_brand_icon():
    candidates = [
        os.path.join("static", "img", "brand.png"),  # Path to brand icon
        os.path.join("static", "img", "brand-icon.png"),  # Alternate path
    ]
    for p in candidates:
        if os.path.exists(p):  # Check if file exists
            try:
                return Image.open(p).convert("RGBA")  # Open and convert to RGBA
            except Exception:
                pass
    return None  # Return None if no valid icon is found


# Parse hex color code to RGB tuple
def _parse_hex(color_hex, default=(255,64,129)):
    try:
        ch = color_hex.lstrip("#")  # Remove '#' from hex code
        if len(ch) == 3:  # Handle shorthand hex (e.g., #FFF)
            ch = "".join([c*2 for c in ch])  # Expand to full hex
        r = int(ch[0:2],16); g = int(ch[2:4],16); b = int(ch[4:6],16)  # Convert to RGB
        return (r,g,b)
    except Exception:
        return default  # Return default color on error



# Create themed underlay with ring and glow effects
def _theme_underlay(size, shape, theme, brand_color="#FF4081"):
    """Return an RGBA underlay with ring/glow per theme."""
    w, h = size
    layer = Image.new("RGBA", size, (255,255,255,0))  # Create transparent RGBA layer
    draw = ImageDraw.Draw(layer)

    # Define insets for ring
    pad = mm_to_px(2)
    bbox = [pad, pad, w - pad, h - pad]
    ring_width = mm_to_px(3.5)

    if theme == "gold":
        gold = (255, 200, 60)  # Define gold color
        # Draw ring
        if shape == "circle":
            draw.ellipse(bbox, outline=gold, width=ring_width)
        else:
            draw.rounded_rectangle(bbox, radius=max(8, min(w,h)//20), outline=gold, width=ring_width)
        # Add soft glow
        glow = Image.new("RGBA", size, (255,255,255,0))
        gdraw = ImageDraw.Draw(glow)
        expand = mm_to_px(4)
        gb = [bbox[0]-expand, bbox[1]-expand, bbox[2]+expand, bbox[3]+expand]
        if shape == "circle":
            gdraw.ellipse(gb, outline=(255,220,120,120), width=mm_to_px(6))
        else:
            gdraw.rounded_rectangle(gb, radius=max(10, min(w,h)//18), outline=(255,220,120,120), width=mm_to_px(6))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=mm_to_px(2)))  # Apply blur
        layer = Image.alpha_composite(layer, glow)

    elif theme == "neon":
        neon1 = (255, 64, 129, 200)  # Inner neon color
        neon2 = (0, 229, 255, 200)   # Outer neon color
        # Draw inner ring
        if shape == "circle":
            draw.ellipse(bbox, outline=neon1, width=ring_width)
        else:
            draw.rounded_rectangle(bbox, radius=max(8, min(w,h)//20), outline=neon1, width=ring_width)
        # Add outer glow
        glow = Image.new("RGBA", size, (255,255,255,0))
        gdraw = ImageDraw.Draw(glow)
        expand = mm_to_px(3)
        gb = [bbox[0]-expand, bbox[1]-expand, bbox[2]+expand, bbox[3]+expand]
        if shape == "circle":
            gdraw.ellipse(gb, outline=neon2, width=mm_to_px(8))
        else:
            gdraw.rounded_rectangle(gb, radius=max(10, min(w,h)//18), outline=neon2, width=mm_to_px(8))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=mm_to_px(3)))  # Apply blur
        layer = Image.alpha_composite(layer, glow)

    elif theme == "brand":
        col = _parse_hex(brand_color)  # Parse brand color
        if shape == "circle":
            draw.ellipse(bbox, outline=(*col, 230), width=ring_width)
        else:
            draw.rounded_rectangle(bbox, radius=max(8, min(w,h)//20), outline=(*col,230), width=ring_width)
        # Add subtle glow
        glow = Image.new("RGBA", size, (255,255,255,0))
        gdraw = ImageDraw.Draw(glow)
        expand = mm_to_px(2)
        gb = [bbox[0]-expand, bbox[1]-expand, bbox[2]+expand, bbox[3]+expand]
        gcol = (*col, 140)
        if shape == "circle":
            gdraw.ellipse(gb, outline=gcol, width=mm_to_px(6))
        else:
            gdraw.rounded_rectangle(gb, radius=max(10, min(w,h)//18), outline=gcol, width=mm_to_px(6))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=mm_to_px(2)))  # Apply blur
        layer = Image.alpha_composite(layer, glow)

    # theme == "none": transparent
    return layer

# Compose a single sticker tile with specified options
def _compose_sticker_tile(user_png_bytes, target_size, shape="circle", border="none",
                          branding=False, brand_text="", theme="none", brand_color="#FF4081"):
    tile = Image.new("RGBA", target_size, (255,255,255,0))  # Create transparent tile
    w, h = target_size

    # Define content area with bleed and padding
    safe_pad = mm_to_px(SAFE_PAD_MM)
    bleed = mm_to_px(BLEED_MM)
    content_box = [bleed + safe_pad, bleed + safe_pad, w - bleed - safe_pad, h - bleed - safe_pad]
    cw = content_box[2] - content_box[0]
    ch = content_box[3] - content_box[1]

    # Add themed underlay (ring/glow) behind subject
    underlay = _theme_underlay(target_size, shape, theme, brand_color)
    tile = Image.alpha_composite(tile, underlay)

    # Fit user image within content area
    user_img = Image.open(io.BytesIO(user_png_bytes)).convert("RGBA")
    user_img = ImageOps.contain(user_img, (cw, ch), Image.LANCZOS)  # Resize with aspect ratio
    content_layer = Image.new("RGBA", target_size, (255,255,255,0))
    _place_center(content_layer, user_img)  # Center the user image

    # Apply shape mask (circle or rounded rectangle)
    if shape == "circle":
        mask = _circle_mask(target_size)
    else:
        radius = max(8, min(w, h) // 20)  # Calculate corner radius
        mask = _rounded_rect_mask(target_size, radius)
    shaped = Image.new("RGBA", target_size, (255,255,255,0))
    shaped.paste(content_layer, (0,0), mask=mask)  # Apply mask to content

    # Add border if specified
    border_px = BORDER_MAP.get(border, 0)
    if border_px > 0 or border == "dotted":
        draw = ImageDraw.Draw(shaped)
        inset = max(bleed // 2, 8)
        bbox = [inset, inset, w - inset, h - inset]
        if shape == "circle":
            if border == "dotted":
                _dotted_ellipse(draw, bbox, fill=(0,0,0,230), width=BORDER_MAP["dotted"])
            else:
                draw.ellipse(bbox, outline=(0,0,0,230), width=border_px)
        else:
            if border == "dotted":
                _dotted_rect(draw, bbox, fill=(0,0,0,230), width=BORDER_MAP["dotted"])
            else:
                draw.rounded_rectangle(bbox, radius=max(8, min(w,h)//20), outline=(0,0,0,230), width=border_px)

    # Add branding (icon and/or text) if enabled
    if branding:
        brand_layer = Image.new("RGBA", target_size, (255,255,255,0))
        draw_b = ImageDraw.Draw(brand_layer)
        pad = mm_to_px(3)
        icon_h = mm_to_px(10)
        x_right = w - pad
        y_bottom = h - pad

        # Add brand icon if available
        icon = _load_brand_icon()
        if icon:
            iw, ih = icon.size
            scale = icon_h / ih
            new_size = (int(iw*scale), int(ih*scale))
            icon_r = icon.resize(new_size, Image.LANCZOS)
            bx = x_right - new_size[0]
            by = y_bottom - new_size[1]
            brand_layer.alpha_composite(icon_r, dest=(bx, by))
            x_right = bx - pad

        # Add brand text if provided
        if brand_text:
            try:
                font = ImageFont.truetype("arial.ttf", size=mm_to_px(3.2))
            except Exception:
                font = ImageFont.load_default()
            tw, th = draw_b.textsize(brand_text, font=font)  # Calculate text size
            bx = x_right - tw
            by = y_bottom - th
            bg_pad = 6
            draw_b.rounded_rectangle([bx-bg_pad, by-bg_pad, x_right+bg_pad, y_bottom+bg_pad],
                                     radius=8, fill=(255,255,255,180))  # Draw text background
            draw_b.text((bx, by), brand_text, fill=(10,10,10,255), font=font)  # Draw text
        shaped = Image.alpha_composite(shaped, brand_layer)

    # Combine underlay and shaped content
    tile = Image.alpha_composite(tile, shaped)
    return tile

# Create an A4 sheet with multiple stickers
def make_a4_sheet(sticker_png_bytes: bytes, options: dict = None) -> bytes:
    options = options or {}  # Default to empty dict if options is None
    shape = options.get("shape", "circle")  # Sticker shape (circle or rounded rectangle)
    border = options.get("border", "none")  # Border style
    branding = bool(options.get("branding", False))  # Enable/disable branding
    brand_text = options.get("brand_text", "")  # Brand text
    theme = options.get("theme", "none")  # Theme for ring/glow
    brand_color = options.get("brand_color", "#FF4081")  # Brand color

    W, H = A4_PX  # A4 dimensions in pixels
    base = Image.new("RGBA", (W, H), (255,255,255,255))  # Create white A4 canvas

    # Calculate layout dimensions
    margin = mm_to_px(MARGIN_MM)
    gutter = mm_to_px(GUTTER_MM)
    cols = rows = 2  # 2x2 grid of stickers
    cell_w = (W - margin*2 - gutter) // cols  # Width of each cell
    cell_h = (H - margin*2 - gutter) // rows  # Height of each cell
    inner_pad = mm_to_px(3)  # Padding within each cell
    tile_size = (cell_w - inner_pad*2, cell_h - inner_pad*2)  # Sticker size

    # Create a single sticker tile
    tile = _compose_sticker_tile(
        sticker_png_bytes,
        target_size=tile_size,
        shape=shape,
        border=border,
        branding=branding,
        brand_text=brand_text,
        theme=theme,
        brand_color=brand_color
    )

    # Define positions for stickers on A4 sheet
    positions = [
        (margin + inner_pad, margin + inner_pad),
        (margin + cell_w + gutter + inner_pad, margin + inner_pad),
        (margin + inner_pad, margin + cell_h + gutter + inner_pad),
        (margin + cell_w + gutter + inner_pad, margin + cell_h + gutter + inner_pad),
    ]
    for (x, y) in positions:
        base.alpha_composite(tile, dest=(x, y))  # Place sticker at each position

    # Draw cutting guidelines
    draw = ImageDraw.Draw(base)
    mid_x = margin + cell_w + gutter//2  # Vertical center line
    mid_y = margin + cell_h + gutter//2  # Horizontal center line
    _draw_dashed_line(draw, (mid_x, margin), (mid_x, H - margin), dash=26, gap=18, fill=(0,0,0,130), width=3)
    _draw_dashed_line(draw, (margin, mid_y), (W - margin, mid_y), dash=26, gap=18, fill=(0,0,0,130), width=3)
    draw.rectangle([margin, margin, W - margin, H - margin], outline=(0,0,0,50), width=2)  # Draw sheet border

    # Save output as PNG
    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG", optimize=True)  # Convert to RGB and save
    return out.getvalue()  # Return PNG bytes