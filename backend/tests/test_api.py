"""HTTP flow: analyze -> SSE trace -> (human salary check) -> result -> DOCX -> ablation."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from ain import api
from ain.agents import ingestion


@pytest.fixture
def client():
    with TestClient(api.app) as c:
        yield c


def _wait(client, job_id, timeout=60):
    t = time.time()
    while time.time() - t < timeout:
        s = client.get(f"/api/jobs/{job_id}").json()
        if s["status"] in ("done", "error", "waiting"):
            return s
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_health_and_samples(client):
    h = client.get("/api/health").json()
    assert h["ok"] and h["corpus_sections"] > 1000 and h["llm_mode"] == "fake"
    ids = {s["id"] for s in client.get("/api/samples").json()}
    assert {"migrant_text", "rmg_epz", "control"} <= ids


def test_sample_run_streams_trace_and_returns_result(client):
    job = client.post("/api/analyze", data={"sample_id": "rmg_epz"}).json()
    events = []
    with client.stream("GET", f"/api/jobs/{job['job_id']}/events") as resp:
        for line in resp.iter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:]))
            if line.startswith("event: end"):
                break
    types = [e.get("type") for e in events if "type" in e]
    assert "agent_start" in types and "claim_verified" in types and "done" in types
    assert [e["data"]["step"] for e in events if e.get("type") == "step"] == ["read", "redact", "match", "verify"]

    r = client.get(f"/api/jobs/{job['job_id']}/result").json()
    assert len(r["risks"]) >= 3 and r["memo"]["issues"]
    docx = client.get(f"/api/jobs/{job['job_id']}/memo.docx")
    assert docx.status_code == 200 and docx.content[:2] == b"PK"
    ab = client.post(f"/api/jobs/{job['job_id']}/ablation").json()
    assert ab["citations_found"] > 0 and ab["supported"] < ab["citations_found"]
    assert ab["ain_verified"] > 0


def test_upload_and_bad_inputs(client, docs):
    data = (docs / "control_clean.txt").read_bytes()
    ok = client.post("/api/analyze", files={"file": ("contract.txt", data, "text/plain")})
    assert ok.status_code == 200
    assert _wait(client, ok.json()["job_id"])["status"] == "done"
    assert client.post("/api/analyze", files={"file": ("x.exe", b"MZ", "application/octet-stream")}).status_code == 415
    assert client.post("/api/analyze").status_code == 400
    assert client.get("/api/jobs/nope/result").status_code == 404
    assert client.get("/api/corpus/BD-CONTRACT-1872-s27").json()["section"] == "27"


def test_countries_and_destination_override(client):
    listed = client.get("/api/countries").json()
    assert {c["code"] for c in listed} >= {"SA", "AE", "MY", "QA", "OM", "KW", "SG", "BH"}
    assert all(c["supported"] and c["help"]["bn"] for c in listed)
    text = b"EMPLOYMENT CONTRACT\n\n1. Salary. A basic salary of 1,000 per month.\n\n2. Recruiting agency fees are paid by the worker."
    bad = client.post("/api/analyze", data={"destination_country": "Atlantis"}, files={"file": ("c.txt", text, "text/plain")})
    assert bad.status_code == 400
    job = client.post("/api/analyze", data={"destination_country": "QA"}, files={"file": ("c.txt", text, "text/plain")}).json()
    assert _wait(client, job["job_id"])["status"] == "done"
    r = client.get(f"/api/jobs/{job['job_id']}/result").json()
    assert r["destination"]["code"] == "QA" and r["destination"]["supported"]
    assert "qa_labour" in {p["pack"] for p in r["route"]["packs"]}


def test_blurry_salary_waits_for_human_confirmation(client, docs, monkeypatch):
    real = ingestion.build_document

    def blurry(data, filename, source_kind=None):
        doc, facts, ex = real(data, filename, source_kind)
        doc.ocr_used = True
        facts.salary_confidence = 0.42
        return doc, facts, ex

    monkeypatch.setattr(ingestion, "build_document", blurry)
    job = client.post("/api/analyze", data={"sample_id": "migrant_text"}).json()["job_id"]
    assert _wait(client, job)["status"] == "waiting"
    assert client.get(f"/api/jobs/{job}/result").status_code == 409
    assert client.post(f"/api/jobs/{job}/confirm", json={"field": "salary", "value": "১,৮০০"}).json()["value"] == 1800
    assert _wait(client, job)["status"] == "done"
    r = client.get(f"/api/jobs/{job}/result").json()
    assert r["wage"]["promised"] == 1800 and r["wage"]["confirmed_by_user"] is True
    assert not r["wage"]["below_minimum"]


def test_council_members_and_chat(client):
    ms = client.get("/api/council").json()
    assert [m["name"] for m in ms] == ["Sunny", "Regal", "Grey"]

    job = client.post("/api/analyze", data={"sample_id": "rmg_epz"}).json()["job_id"]
    assert _wait(client, job)["status"] == "done"
    r = client.get(f"/api/jobs/{job}/result").json()
    benched = next(k for k in r["risks"] if k["bench"])
    assert {o["persona"] for o in benched["bench"]["opinions"]} == {"happy", "proud", "gloomy"}
    calls_before = len(r["privacy"]["outbound_calls"])

    url = f"/api/jobs/{job}/council/chat"
    all3 = client.post(url, json={"message": "Should I sign?", "members": ["happy", "proud", "gloomy"], "risk_id": benched["id"]})
    assert all3.status_code == 200 and [x["name"] for x in all3.json()["replies"]] == ["Sunny", "Regal", "Grey"]
    one = client.post(url, json={"message": "And you?", "members": ["proud"], "history": [{"speaker": "user", "text": "Should I sign?"}]})
    assert one.status_code == 200 and len(one.json()["replies"]) == 1
    after = client.get(f"/api/jobs/{job}/result").json()["privacy"]["outbound_calls"]
    assert len(after) == calls_before + 4 and all(c["agent"].startswith("LLM Council") for c in after[calls_before:])

    pii = client.post(url, json={"message": "Call me on 01712345678", "members": ["happy"]})
    assert pii.status_code == 422 and "personal identifiers" in pii.json()["detail"]
    assert client.post(url, json={"message": "hi", "members": ["angry"]}).status_code == 422
    assert client.post(url, json={"message": "hi", "members": ["happy"], "risk_id": "R99"}).status_code == 404
    assert client.post("/api/jobs/nope/council/chat", json={"message": "hi", "members": ["happy"]}).status_code == 404

    # deliberation: round 2 + Chief Justice ruling, in Bangla
    first = all3.json()["replies"]
    d = client.post(
        f"/api/jobs/{job}/council/deliberate",
        json={"message": "Should I sign?", "replies": first, "risk_id": benched["id"], "language": "bn"},
    )
    assert d.status_code == 200
    body = d.json()
    assert [x["member"] for x in body["rebuttals"]] == ["happy", "proud", "gloomy"] and all(x["round"] == 2 for x in body["rebuttals"])
    assert body["ruling"]["agreement"] in ("unanimous", "majority", "split") and body["ruling"]["next_step"]
    deliberate = f"/api/jobs/{job}/council/deliberate"
    assert client.post(deliberate, json={"message": "x", "replies": first[:1]}).status_code == 422
    leak = [dict(first[0], text="Call 01712345678"), *first[1:]]
    assert client.post(deliberate, json={"message": "x", "replies": leak}).status_code == 422
