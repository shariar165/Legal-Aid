"""Hooks for workflow automation (the n8n workflows in automation/n8n/). Both are off unless configured.

- Law freshness watch: GET /api/corpus/freshness, behind AIN_AUTOMATION_TOKEN. Re-reads bdlaws and reports any corpus
  section whose official text changed (corpus/freshness.py). One check runs at a time and its result is reused for
  FRESHNESS_TTL_S, so the endpoint can't be used to hammer a government site.
- Job digest: when an analysis finishes, POST a summary to AIN_WEBHOOK_URL. Counts only: no file name, no document
  text, no finding, nothing a person could be identified from.
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import os
import time

import httpx

from ain.models import AnalysisResult
from ain.retrieval import get_corpus
from corpus import freshness

FRESHNESS_TTL_S = 600
log = logging.getLogger("ain.automation")

_lock = asyncio.Lock()
_last: tuple[float, dict] | None = None


def token() -> str | None:
    return os.getenv("AIN_AUTOMATION_TOKEN") or None


def authorized(header: str | None) -> bool:
    t = token()
    return bool(t) and hmac.compare_digest((header or "").encode(), f"Bearer {t}".encode())


async def law_freshness(force: bool = False) -> dict:
    global _last
    async with _lock:
        if _last and not force and time.time() - _last[0] < FRESHNESS_TTL_S:
            return {**_last[1], "cached": True}
        report = await asyncio.to_thread(freshness.check, get_corpus().sections)
        _last = (time.time(), report)
        return {**report, "cached": False}


def job_digest(r: AnalysisResult) -> dict:
    live = [k for k in r.risks if k.status != "dropped"]
    by_sev = {s: sum(k.severity == s for k in live) for s in ("critical", "high", "medium", "low")}
    return {
        "event": "analysis.completed",
        "job_id": r.job_id,
        "llm_mode": r.llm_mode,
        "destination": r.destination.code if r.destination else None,
        "law_packs": [p.pack for p in r.route.packs],
        "risks": len(live),
        "risks_by_severity": by_sev,
        "off_playbook_risks": sum(k.origin == "adversary" for k in live),
        "claims_verified": r.stats.verified,
        "claims_partial": r.stats.partial,
        "claims_dropped": r.stats.dropped,
        "human_review": sum(1 for k in live if k.bench and k.bench.human_review),
        "seconds": r.stats.seconds,
        "llm_calls": r.stats.llm_calls,
    }


async def notify_job(r: AnalysisResult) -> None:
    url = os.getenv("AIN_WEBHOOK_URL")
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            (await client.post(url, json=job_digest(r))).raise_for_status()
    except Exception as e:  # noqa: BLE001 - a webhook outage never affects the analysis
        log.warning("job digest webhook failed: %s", e)
