"""Shape Bangla text with HarfBuzz from Noto Serif Bengali Bold and print SVG path data (y down, origin at baseline).

One-off helper for the logo (spec 22). Usage: python shape_glyphs.py FONT.ttf TEXT [wght]
Prints JSON: {"d": path, "advance": x, "bbox": [xmin, ymin, xmax, ymax], "upem": n}.
"""
import io
import json
import sys

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer


def shape(font_path: str, text: str, wght: float = 700) -> dict:
    font = TTFont(font_path)
    if "fvar" in font:
        font = instancer.instantiateVariableFont(font, {"wght": wght, "wdth": 100})
    buf_io = io.BytesIO()
    font.save(buf_io)
    data = buf_io.getvalue()
    font = TTFont(io.BytesIO(data))

    hb_font = hb.Font(hb.Face(hb.Blob(data)))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf, {})

    glyphs = font.getGlyphSet()
    order = font.getGlyphOrder()
    svg = SVGPathPen(glyphs)
    bounds = BoundsPen(glyphs)
    x = 0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        g = glyphs[order[info.codepoint]]
        # flip y so the path is in SVG space: baseline at y=0, ascenders negative
        t = (1, 0, 0, -1, x + pos.x_offset, -pos.y_offset)
        g.draw(TransformPen(svg, t))
        g.draw(TransformPen(bounds, t))
        x += pos.x_advance
    return {"d": svg.getCommands(), "advance": x, "bbox": list(bounds.bounds), "upem": font["head"].unitsPerEm}


if __name__ == "__main__":
    print(json.dumps(shape(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 700)))
