"""Rehearsal Council over HTTP: create -> turns -> finish -> record -> DOCX, the SSE trace, ownership, deletion, and the
quota lock (offline while `rehearsal.live` is false, whatever AIN_LLM_MODE says)."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from ain import api, config
from ain.rehearsal import session, store


@pytest.fixture
def client():
    with TestClient(api.app) as c:
        yield c


def _wait(client, sid, pred, timeout=30):
    t = time.time()
    while time.time() - t < timeout:
        s = client.get(f"/api/rehearsals/{sid}").json()
        if pred(s):
            return s
        time.sleep(0.05)
    raise AssertionError(f"rehearsal did not get there: {s}")


def _ready(s):
    return s["status"] == "done" or (s["turns"] and not s["turns"][-1]["hints"] and not s["turns"][-1]["worker_reply"])


def test_full_rehearsal_flow_and_trace(client):
    created = client.post("/api/rehearsals", json={"country": "Saudi Arabia", "promises": {"salary": "১৫০০ রিয়াল", "passport_keeper": "agent"}})
    assert created.status_code == 201
    sid = created.json()["id"]
    replies = ["লাইসেন্স নম্বর কী?", "বেতনের কথা লিখিত চুক্তিতে দেখান", "পাসপোর্ট দেব না", "মোট খরচ কত, লিখে দিন", "রসিদ দেবেন তো?", "ভেবে জানাব"]
    for i, reply in enumerate(replies):
        s = _wait(client, sid, _ready)
        assert len(s["turns"]) == i + 1
        assert client.post(f"/api/rehearsals/{sid}/turns", json={"reply": reply}).status_code == 202
        s = _wait(client, sid, lambda s, i=i: s["turns"][i]["hints"])
        assert [h["member"] for h in s["turns"][i]["hints"]] == ["happy", "proud", "gloomy"]
    _wait(client, sid, _ready)
    assert client.post(f"/api/rehearsals/{sid}/finish").status_code == 202
    s = _wait(client, sid, lambda s: s["status"] == "done")
    assert s["debrief"]["score"] == 100 and s["record"]["paths"]
    assert s["mapping"] == {} and s["trace"] == []  # the browser never gets the placeholder mapping
    assert client.post(f"/api/rehearsals/{sid}/turns", json={"reply": "x"}).status_code == 409

    put = client.put(f"/api/rehearsals/{sid}/record", json={"agent_name": "রহিম উদ্দিন", "agent_phone": "01712345678"})
    assert put.json()["record"]["contacts"]["agent_name"].startswith("[NAME_")
    assert client.get(f"/api/rehearsals/{sid}/record/print").json()["contacts"]["agent_name"] == "রহিম উদ্দিন"
    docx = client.get(f"/api/rehearsals/{sid}/record.docx")
    assert docx.status_code == 200 and docx.content[:2] == b"PK"

    events = []
    with client.stream("GET", f"/api/rehearsals/{sid}/events") as resp:
        for line in resp.iter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:]))
            if line.startswith("event: end"):
                break
    types = [e.get("type") for e in events if "type" in e]
    assert types[0] == "rehearsal_started" and types[1] == "dalal_line"
    assert types[2:7] == ["worker_turn", "coach_hint", "coach_hint", "coach_hint", "turn_done"]
    assert types[-2:] == ["debrief", "record_ready"]
    assert all(e["data"].get("mode", "fake") == "fake" for e in events if e.get("type") == "rehearsal_started")


def test_another_user_gets_404_and_delete_removes_the_file(client):
    sid = client.post("/api/rehearsals", json={}).json()["id"]
    _wait(client, sid, _ready)
    with TestClient(api.app) as other:
        assert other.get(f"/api/rehearsals/{sid}").status_code == 404
        assert other.post(f"/api/rehearsals/{sid}/turns", json={"reply": "hi"}).status_code == 404
    path = config.RUNS_DIR / f"rehearsal-{sid}.json.enc"
    assert path.exists()
    assert client.delete(f"/api/rehearsals/{sid}").json() == {"ok": True}
    assert not path.exists() and client.get(f"/api/rehearsals/{sid}").status_code == 404


def test_bad_inputs(client):
    assert client.post("/api/rehearsals", json={"country": "Atlantis"}).status_code == 400
    sid = client.post("/api/rehearsals", json={}).json()["id"]
    _wait(client, sid, _ready)
    assert client.post(f"/api/rehearsals/{sid}/turns", json={"reply": "  "}).status_code == 422
    assert client.get(f"/api/rehearsals/{sid}/record.docx").status_code == 409


def test_quota_lock_keeps_rehearsals_offline(monkeypatch):
    monkeypatch.setenv("AIN_LLM_MODE", "live")
    assert config.rehearsal_settings()["live"] is False
    assert session.mode() == "fake"
    monkeypatch.setattr(config, "rehearsal_settings", lambda: {"live": True})
    assert session.mode() == "live"  # only the flag can let a rehearsal spend quota


def test_purge_orphans_removes_sessions_of_deleted_users(client):
    sid = client.post("/api/rehearsals", json={}).json()["id"]
    _wait(client, sid, _ready)
    from ain import auth

    with auth._db() as c:
        c.execute("DELETE FROM rehearsals WHERE id = ?", (sid,))
    assert sid in store.purge_orphans()
    assert not (config.RUNS_DIR / f"rehearsal-{sid}.json.enc").exists()
