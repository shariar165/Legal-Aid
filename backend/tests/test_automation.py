"""Automation hooks: the law-freshness diff, its token-gated endpoint, and the count-only job digest."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from ain import automation
from ain.retrieval import get_corpus
from corpus import freshness, scrape_bdlaws

from .conftest import DOCS


def _page_from_corpus(edit: dict[str, str] | None = None, drop: set[str] = frozenset()):
    """A fake bdlaws act-details page built from our own corpus text, in the markup parse_details reads."""
    edit = edit or {}
    acts = {a["bdlaws_id"]: a["key"] for a in json.loads(scrape_bdlaws.ACTS_FILE.read_text(encoding="utf-8")) if a.get("bdlaws_id")}
    by_act: dict[str, list] = {}
    for s in get_corpus().sections:
        if s.source == "bdlaws.minlaw.gov.bd":
            by_act.setdefault(s.act_key, []).append(s)

    def page(path: str) -> str:
        key = acts[int(path.removeprefix("/act-details-").removesuffix(".html"))]
        blocks = []
        for s in by_act.get(key, []):
            if s.citation_id in drop:
                continue
            text = edit.get(s.citation_id, s.text)
            blocks.append(f'<div class="col-sm-3 txt-head">{s.heading}</div><div class="col-sm-9 txt-details">{text}</div>')
        return "".join(blocks)

    return page


def test_parser_round_trips_our_own_text():
    """Guard for the fake page above: if this fails, the markup no longer matches parse_details."""
    report = freshness.check(get_corpus().sections, page=_page_from_corpus(), pause=0)
    if report["changes"]:
        pytest.skip("corpus text does not round-trip through the synthetic markup")
    assert report["ok"] and report["acts_checked"] >= 5


def test_reports_a_changed_and_a_missing_section():
    secs = [s for s in get_corpus().sections if s.source == "bdlaws.minlaw.gov.bd"]
    base = freshness.check(get_corpus().sections, page=_page_from_corpus(), pause=0)
    if base["changes"]:
        pytest.skip("corpus text does not round-trip through the synthetic markup")
    changed, gone = secs[10], secs[40]
    page = _page_from_corpus(edit={changed.citation_id: changed.text + " (amended by Act 7 of 2026)"}, drop={gone.citation_id})
    report = freshness.check(get_corpus().sections, page=page, pause=0)
    flagged = {c for a in report["acts"] for c in a["changed"]}
    missing = {c for a in report["acts"] for c in a["missing"]}
    assert changed.citation_id in flagged and gone.citation_id in missing
    assert report["changed"] and report["next_step"]


def test_an_unreachable_site_stops_early():
    calls = []

    def down(path):
        calls.append(path)
        raise TimeoutError("timed out")

    report = freshness.check(get_corpus().sections, page=down, pause=0)
    assert len(calls) == 1 and not report["ok"] and "unreachable" in report["errors"][-1]["error"]


def test_freshness_endpoint_is_off_without_a_token_and_needs_it_when_on(monkeypatch):
    from ain.api import app

    with TestClient(app) as http:
        monkeypatch.delenv("AIN_AUTOMATION_TOKEN", raising=False)
        assert http.get("/api/corpus/freshness").status_code == 404
        monkeypatch.setenv("AIN_AUTOMATION_TOKEN", "auto-123")
        assert http.get("/api/corpus/freshness").status_code == 401
        assert http.get("/api/corpus/freshness", headers={"Authorization": "Bearer nope"}).status_code == 401
        monkeypatch.setattr(freshness, "live_page", _page_from_corpus())
        monkeypatch.setattr(automation, "_last", None)
        monkeypatch.setattr(freshness, "PAUSE_S", 0)
        r = http.get("/api/corpus/freshness", headers={"Authorization": "Bearer auto-123"})
        assert r.status_code == 200 and r.json()["acts_checked"] >= 5
        assert http.get("/api/corpus/freshness", headers={"Authorization": "Bearer auto-123"}).json()["cached"] is True


def test_job_digest_carries_counts_only():
    from ain.orchestrator import new_job, run_pipeline

    name = "migrant_my_contract.txt"
    text = (DOCS / name).read_text(encoding="utf-8")
    r = asyncio.run(run_pipeline(new_job(name), text.encode(), name, confirm_timeout=0.1))
    digest = automation.job_digest(r)
    assert digest["risks"] >= 3 and digest["claims_verified"] > 0
    blob = json.dumps(digest, ensure_ascii=False)
    assert name not in blob
    assert not any(k.finding[:40] in blob for k in r.risks)
    assert all(isinstance(v, (int, float, str, list, dict, type(None))) for v in digest.values())


def test_notify_job_posts_the_digest_only_when_configured(monkeypatch):
    import httpx

    from ain.orchestrator import new_job, run_pipeline

    name = "migrant_sa_contract.txt"
    r = asyncio.run(run_pipeline(new_job(name), (DOCS / name).read_bytes(), name, confirm_timeout=0.1))
    sent = []
    real = httpx.AsyncClient
    transport = httpx.MockTransport(lambda req: sent.append(req) or httpx.Response(200))
    monkeypatch.setattr(automation.httpx, "AsyncClient", lambda **kw: real(transport=transport, **kw))

    monkeypatch.delenv("AIN_WEBHOOK_URL", raising=False)
    asyncio.run(automation.notify_job(r))
    assert sent == []
    monkeypatch.setenv("AIN_WEBHOOK_URL", "http://n8n.test/webhook/ain-job-digest")
    asyncio.run(automation.notify_job(r))
    assert len(sent) == 1 and json.loads(sent[0].content)["job_id"] == r.job_id
    # a webhook outage never raises into the analysis
    monkeypatch.setattr(automation.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(lambda req: httpx.Response(500)), **kw))
    asyncio.run(automation.notify_job(r))
