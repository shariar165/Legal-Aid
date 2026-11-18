"""Lite deployment (requirements-lite.txt, no EasyOCR): cached photos still read, new ones fail with a clear message."""

import io
import sys

import pytest
from PIL import Image

from ain import config
from ain.agents import ingestion


@pytest.fixture
def no_easyocr(monkeypatch):
    monkeypatch.setitem(sys.modules, "easyocr", None)  # `import easyocr` now raises ImportError
    monkeypatch.setattr(ingestion, "_reader", None)


def test_uncached_photo_says_ocr_is_not_installed(no_easyocr, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OCR_CACHE_DIR", tmp_path)
    buf = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(buf, "PNG")
    with pytest.raises(ingestion.OcrUnavailable, match="not installed"):
        ingestion.extract(buf.getvalue(), "contract.png")


def test_cached_demo_photo_still_reads_without_easyocr(no_easyocr):
    photo = config.DEMO_DIR / "docs" / "migrant_my_contract_photo.jpg"
    got = ingestion.extract(photo.read_bytes(), photo.name)
    assert got.kind == "image" and got.ocr_lines and got.text.strip()
