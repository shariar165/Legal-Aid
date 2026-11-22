"""Self-test for `shot.py audit` (spec 29 step 0.1): a fixture page with known counts, served locally.

  python -m pytest web/scripts/check -q        # skipped when no Chrome or no axe-core is found

Every element has an explicit font-size (a button would otherwise default to 13.33 px and count as small text).
"""
import http.server
import os
import threading
import time
from pathlib import Path

import pytest

import shot

FONT = os.urandom(3000)  # not a real font: Chrome still downloads it, which is all the byte count needs
CSS = b"p { margin: 0 0 8px; }\n" * 40
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")
PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>audit fixture</title>
<link rel="stylesheet" href="/a.css">
<style>
  @font-face { font-family: Fx; src: url(/fx.woff2) format("woff2"); }
  * { font-size: 16px; font-family: Fx, sans-serif; line-height: 1.2; }
  .small { font-size: 12px; }
  button { padding: 0; border: 0; }
  .tiny { width: 20px; height: 20px; }
  .big { width: 48px; height: 48px; }
  .wide { width: 2000px; height: 10px; }
  .sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); font-size: 10px; }
</style></head><body><main>
<h1 style="font-size: 24px">Fixture</h1>
<p>Plain text at sixteen pixels. Read <a href="#x">this link</a> inside a longer sentence.</p>
<p class="small">Latin small</p>
<p class="small" lang="bn">বাংলা ছোট</p>
<p lang="bn">বাংলা ঠিক আছে</p>
<span class="sr">hidden helper text</span>
<button class="tiny" aria-label="one">1</button>
<button class="tiny" aria-label="two">2</button>
<button class="big">OK</button>
<img src="/px.png">
<div class="wide"></div>
</main></body></html>""".encode()
FILES = {"/": ("text/html; charset=utf-8", PAGE), "/a.css": ("text/css", CSS), "/fx.woff2": ("font/woff2", FONT),
         "/px.png": ("image/png", PNG)}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        kind, body = FILES.get(self.path.split("?")[0], ("text/plain", b""))
        self.send_response(200 if body else 404)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def measured():
    if not (Path(shot.CHROME).exists() or os.environ.get("CHROME")) or not shot.AXE.exists():
        pytest.skip(f"needs Chrome ({shot.CHROME}) and axe-core ({shot.AXE})")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    proc, ws_url = shot.launch()
    try:
        with shot.connect(ws_url, max_size=None, open_timeout=20) as ws:
            tab = shot.Tab(ws)
            for m in ("Page.enable", "Runtime.enable", "Network.enable"):
                tab.call(m)
            tab.call("Network.setCacheDisabled", cacheDisabled=True)
            shot.set_width(tab, 390)
            tab.goto(f"http://127.0.0.1:{server.server_port}/", 1500)
            for _ in range(20):  # the font loads once text asks for it
                if tab.js("document.fonts.status") == "loaded":
                    break
                time.sleep(0.2)
            yield shot.measure(tab, 390)
    finally:
        proc.terminate()
        proc.wait(5)
        server.shutdown()


def test_targets(measured):
    t = measured["targets"]
    assert t["lt24"] == 2          # the two 20 px buttons
    assert t["inline_lt24"] == 1   # the link inside a sentence is exempt (WCAG 2.2 SC 2.5.8), counted apart
    assert t["lt44"] == 2          # at 390 the 48 px button passes and the inline link is left out


def test_text(measured):
    x = measured["text"]
    assert x["latin_lt14"] == 1    # "Latin small"; the screen-reader-only text is left out
    assert x["bangla"] == 2 and x["bangla_lt16"] == 1 and x["bangla_lt14"] == 1


def test_layout(measured):
    assert measured["sideways"] is True
    assert measured["width"] == 390


def test_axe(measured):
    assert "image-alt" in {v["id"] for v in measured["axe"]}


def test_bytes(measured):
    b = measured["bytes"]
    assert b["font_decoded"] == len(FONT) and b["css_decoded"] == len(CSS)
    assert b["font_wire"] >= b["font_decoded"] and b["css_wire"] >= b["css_decoded"]  # the wire count includes headers
    assert ["a.css", len(CSS)] in b["css"]
