"""Browser OCR (spec 28): on a server without EasyOCR, the citizen app reads a photo on the device and sends only the
lines and their confidences. The same salary check, OCR confidence and pipeline apply; the photo is never uploaded."""

import io
import json
import sys
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ain import api, config
from ain.agents import ingestion

# The demo photo, as EasyOCR read it (demo/ocr_cache): a realistic payload, salary line "... RM 1,200" at 0.768.
DEMO_LINES = json.loads(next(config.OCR_CACHE_DIR.glob("*.json")).read_text(encoding="utf-8"))


@pytest.fixture
def client():
    with TestClient(api.app) as c:
        yield c


@pytest.fixture
def no_easyocr(monkeypatch):
    monkeypatch.setitem(sys.modules, "easyocr", None)  # `import easyocr` now raises ImportError
    monkeypatch.setattr(ingestion, "_reader", None)


def _floors(monkeypatch, **floors):
    raw = config._raw()
    monkeypatch.setattr(config, "_raw", lambda: {**raw, "ocr": {"confirm_floor": {**raw["ocr"]["confirm_floor"], **floors}}})


def _wait(client, job_id, timeout=60):
    t = time.time()
    while time.time() - t < timeout:
        s = client.get(f"/api/jobs/{job_id}").json()
        if s["status"] in ("done", "error", "waiting"):
            return s
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_health_says_whether_the_server_reads_photos(client, no_easyocr):
    assert client.get("/api/health").json()["ocr"] is False


def test_ain_ocr_0_makes_a_full_install_behave_like_lite(client, monkeypatch, tmp_path):
    monkeypatch.setenv("AIN_OCR", "0")
    monkeypatch.setattr(ingestion, "_reader", None)
    monkeypatch.setattr(config, "OCR_CACHE_DIR", tmp_path)
    assert client.get("/api/health").json()["ocr"] is False
    with pytest.raises(ingestion.OcrUnavailable):
        ingestion._ocr_reader()


def test_lines_read_on_the_device_run_the_pipeline_with_the_salary_check(client, monkeypatch):
    _floors(monkeypatch, tesseract=0.9)
    job = client.post("/api/analyze", data={"ocr_lines": json.dumps(DEMO_LINES), "ocr_name": "IMG_0042.jpg"}).json()
    assert job["name"] == "IMG_0042.jpg"
    assert _wait(client, job["job_id"])["status"] == "waiting"  # 0.768 < 0.9
    client.post(f"/api/jobs/{job['job_id']}/confirm", json={"field": "salary", "value": "1200"})
    assert _wait(client, job["job_id"])["status"] == "done"
    r = client.get(f"/api/jobs/{job['job_id']}/result").json()
    d = r["document"]
    assert d["source_kind"] == "image" and d["ocr_used"] and d["ocr_engine"] == "tesseract"
    assert d["ocr_confidence"] == pytest.approx(sum(x["conf"] for x in DEMO_LINES) / len(DEMO_LINES), abs=1e-3)
    assert r["wage"]["promised"] == 1200 and r["wage"]["confirmed_by_user"]
    assert r["stats"]["risks_confirmed"] >= 3


def test_each_engine_has_its_own_floor(client, monkeypatch):
    _floors(monkeypatch, tesseract=0.5, easyocr=0.9)
    job = client.post("/api/analyze", data={"ocr_lines": json.dumps(DEMO_LINES)}).json()["job_id"]
    assert _wait(client, job)["status"] == "done"  # 0.768 >= 0.5: no question for the worker
    assert config.ocr_confirm_floor("easyocr") == 0.9 and config.ocr_confirm_floor("tesseract") == 0.5
    assert config.ocr_confirm_floor(None) == 0.9


BAD = [
    ("not json", "not valid JSON"),
    ("[]", "non-empty list"),
    (json.dumps([{"text": "x", "conf": 1.5}]), "between 0 and 1"),
    (json.dumps([{"text": "x", "conf": True}]), "must be"),
    (json.dumps([{"text": "x"}]), "must be"),
    (json.dumps([{"text": "   ", "conf": 0.9}]), "No text"),
    (json.dumps([{"text": "x", "conf": 0.9}] * (ingestion.MAX_OCR_LINES + 1)), "more than"),
    (json.dumps([{"text": "x" * (ingestion.MAX_OCR_CHARS + 1), "conf": 0.9}]), "characters"),
]


@pytest.mark.parametrize("payload, why", BAD, ids=[f"{i}-{w.split()[0]}" for i, (_, w) in enumerate(BAD)])
def test_bad_ocr_lines_are_refused(client, payload, why):
    r = client.post("/api/analyze", data={"ocr_lines": payload})
    assert r.status_code == 400 and why in r.json()["detail"]


def test_ocr_lines_cannot_come_with_a_file_or_sample(client):
    lines = json.dumps(DEMO_LINES)
    assert client.post("/api/analyze", data={"ocr_lines": lines, "sample_id": "control"}).status_code == 400
    assert client.post("/api/analyze", data={"ocr_lines": lines}, files={"file": ("a.txt", b"hello", "text/plain")}).status_code == 400


def test_a_new_photo_on_a_server_without_ocr_says_so_plainly(client, no_easyocr, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OCR_CACHE_DIR", tmp_path)
    buf = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(buf, "PNG")
    job = client.post("/api/analyze", files={"file": ("contract.png", buf.getvalue(), "image/png")}).json()["job_id"]
    s = _wait(client, job)
    assert s["status"] == "error"
    assert s["error"].startswith("Photo reading (OCR) is not installed") and "OcrUnavailable" not in s["error"]
