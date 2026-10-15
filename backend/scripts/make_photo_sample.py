"""Render the migrant contract as a realistic phone photo (for the OCR + human-check demo).

PyMuPDF's HTML layout shapes Bangla correctly; PIL then adds perspective-ish rotation,
uneven lighting, blur and noise. The salary line is printed slightly faded, as on a worn copy.
"""

from __future__ import annotations

import html
import io
import random
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFilter

DOCS = Path(__file__).resolve().parent.parent / "demo" / "docs"
SRC = DOCS / "migrant_my_contract.txt"
OUT = DOCS / "migrant_my_contract_photo.jpg"


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines()
    parts = []
    for ln in lines:
        esc = html.escape(ln) or "&nbsp;"
        if ln.startswith("2. Salary"):
            parts.append(f'<p style="color:#6d6d6d">{esc}</p>')
        elif ln.isupper() or ln.startswith("EMPLOYMENT"):
            parts.append(f"<p><b>{esc}</b></p>")
        else:
            parts.append(f"<p>{esc}</p>")
    body = "".join(parts)
    css = "p{font-family:sans-serif;font-size:10.5pt;margin:0 0 3pt 0;line-height:1.25} b{font-size:12pt}"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=900)
    page.insert_htmlbox(pymupdf.Rect(40, 40, 555, 870), body, css=css)
    pix = page.get_pixmap(dpi=170)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

    random.seed(7)
    # paper on a desk: pad, rotate slightly, uneven light, mild blur and sensor noise
    canvas = Image.new("RGB", (img.width + 160, img.height + 160), (92, 78, 62))
    canvas.paste(img, (80, 80))
    canvas = canvas.rotate(-1.6, resample=Image.BICUBIC, expand=False, fillcolor=(92, 78, 62))
    shade = Image.new("L", canvas.size, 0)
    d = ImageDraw.Draw(shade)
    for i in range(0, canvas.width, 4):
        d.line([(i, 0), (i, canvas.height)], fill=int(55 * i / canvas.width))
    canvas = Image.composite(Image.new("RGB", canvas.size, (40, 34, 28)), canvas, shade.point(lambda v: v // 2))
    canvas = canvas.filter(ImageFilter.GaussianBlur(0.9))
    px = canvas.load()
    for _ in range(canvas.width * canvas.height // 30):
        x, y = random.randrange(canvas.width), random.randrange(canvas.height)
        r, g, b = px[x, y]
        n = random.randint(-28, 28)
        px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
    canvas.save(OUT, quality=82)
    print(f"wrote {OUT} {canvas.size}")


if __name__ == "__main__":
    main()
