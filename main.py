import os
import io
import base64
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
from utils.quality import assess_quality
from utils.image_sheet import make_a4_sheet
from utils.gpt_image import (
    cartoonize_with_bg_remove,
    IMAGE_MODEL,
    IMG_SIZE,
    IMG_QUALITY,
    OPENAI_API_KEY,
)
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader


load_dotenv()

app = Flask(__name__)

# Optional: protect against giant uploads (adjust as you like)
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH_MB", "12")) * 1024 * 1024


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/info")
def api_info():
    """
    Small helper so you (or the client) can verify current model + settings and key presence.
    """
    return jsonify({
        "model": IMAGE_MODEL,
        "size": IMG_SIZE,
        "quality": IMG_QUALITY,
        "key_present": bool(OPENAI_API_KEY),
    })


@app.post("/api/cartoonize")
def api_cartoonize():
    data = request.get_json()
    if not data or "imageData" not in data:
        return jsonify({"error": "imageData missing"}), 400

    try:
        b64_uri = data["imageData"]
        header, b64 = b64_uri.split(",", 1) if "," in b64_uri else ("", b64_uri)
        img_bytes = base64.b64decode(b64)

        force_fresh = bool(data.get("forceFresh", False))
        quality_gate = bool(data.get("qualityGate", True))

        # 1) Quality check (reject blurry/dark before spending API)
        if quality_gate:
            q = assess_quality(img_bytes)
            if not q["ok"]:
                # 422 Unprocessable Entity with reason
                return jsonify({
                    "error": "low_quality",
                    "reason": q["reason"],
                    "metrics": {"blur": q["blur"], "brightness": q["brightness"]},
                    "action": "retake"
                }), 422

        cartoon_png_bytes, used_fallback = cartoonize_with_bg_remove(
            img_bytes, force_fresh=force_fresh
        )
        out_b64 = base64.b64encode(cartoon_png_bytes).decode("utf-8")
        return jsonify({
            "cartoonData": "data:image/png;base64," + out_b64,
            "fallback": used_fallback
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/print-sheet")
def api_print_sheet():
    data = request.get_json()
    if not data or "imageData" not in data:
        return jsonify({"error": "imageData missing"}), 400
    try:
        b64_uri = data["imageData"]
        header, b64 = b64_uri.split(",", 1) if "," in b64_uri else ("", b64_uri)
        img_bytes = base64.b64decode(b64)
        options = data.get("options", {})

        a4_png_bytes = make_a4_sheet(img_bytes, options=options)
        return send_file(
            io.BytesIO(a4_png_bytes),
            mimetype="image/png",
            as_attachment=True,
            download_name="sticker_sheet_a4.png"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/print-sheet-pdf")
def api_print_sheet_pdf():
    """
    Same payload as /api/print-sheet, but returns A4 PDF with the composed PNG placed full-page.
    Helps with printer drivers that scale PNG oddly.
    """
    data = request.get_json()
    if not data or "imageData" not in data:
        return jsonify({"error": "imageData missing"}), 400
    try:
        b64_uri = data["imageData"]
        header, b64 = b64_uri.split(",", 1) if "," in b64_uri else ("", b64_uri)
        img_bytes = base64.b64decode(b64)
        options = data.get("options", {})

        a4_png_bytes = make_a4_sheet(img_bytes, options=options)

        # Create PDF in-memory
        pdf_buf = io.BytesIO()
        c = canvas.Canvas(pdf_buf, pagesize=A4)
        w, h = A4  # points
        img = ImageReader(io.BytesIO(a4_png_bytes))
        # Cover full page (no margins) — your print dialog can set margins if needed
        c.drawImage(img, 0, 0, width=w, height=h, preserveAspectRatio=True, mask='auto')
        c.showPage()
        c.save()
        pdf_buf.seek(0)

        return send_file(
            pdf_buf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="sticker_sheet_a4.pdf"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/log")
def api_log():
    """
    Expects: JSON { level: "info"|"warn"|"error", message: str, meta?: dict }
    Writes to logs/app.log (server-side).
    """
    try:
        data = request.get_json() or {}
        level = data.get("level", "info")
        message = data.get("message", "")
        meta = data.get("meta", {})
        os.makedirs("logs", exist_ok=True)
        line = f"{datetime.utcnow().isoformat()}Z\t{level.upper()}\t{message}\t{meta}\n"
        with open(os.path.join("logs", "app.log"), "a", encoding="utf-8") as f:
            f.write(line)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
