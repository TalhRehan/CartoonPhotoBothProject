import os
import io
import base64
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv

from utils.gpt_image import cartoonize_with_bg_remove
from utils.image_sheet import make_a4_sheet

load_dotenv()

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.post("/api/cartoonize")
def api_cartoonize():
    """
    Expects: JSON { "imageData": "data:image/png;base64,...." }
    Returns: JSON { "cartoonData": "data:image/png;base64,...." }
    """
    data = request.get_json()
    if not data or "imageData" not in data:
        return jsonify({"error": "imageData missing"}), 400

    try:
        b64_uri = data["imageData"]
        header, b64 = b64_uri.split(",", 1) if "," in b64_uri else ("", b64_uri)
        img_bytes = base64.b64decode(b64)

        cartoon_png_bytes = cartoonize_with_bg_remove(img_bytes)

        out_b64 = base64.b64encode(cartoon_png_bytes).decode("utf-8")
        return jsonify({"cartoonData": "data:image/png;base64," + out_b64})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.post("/api/print-sheet")
def api_print_sheet():
    """
    Expects: JSON { "imageData": "data:image/png;base64,...." }
    Returns: A4 PNG (4 stickers + cut lines), as a file download
    """
    data = request.get_json()
    if not data or "imageData" not in data:
        return jsonify({"error": "imageData missing"}), 400
    try:
        b64_uri = data["imageData"]
        header, b64 = b64_uri.split(",", 1) if "," in b64_uri else ("", b64_uri)
        img_bytes = base64.b64decode(b64)

        a4_png_bytes = make_a4_sheet(img_bytes)

        return send_file(
            io.BytesIO(a4_png_bytes),
            mimetype="image/png",
            as_attachment=True,
            download_name="sticker_sheet_a4.png"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
