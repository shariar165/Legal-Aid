"""Law freshness watch: has bdlaws changed any section our corpus quotes?

For each Bangladesh act in acts.json, re-read its consolidated text from bdlaws.minlaw.gov.bd, parse it with the
scraper's own parser, and compare every corpus section of that act, after NFC and whitespace normalisation. A changed
section matters because the verifier's fidelity and currency gates compare claims against our stored copy.

    python -m corpus.freshness            (from backend/; live, ~1 s per act)
    GET /api/corpus/freshness             (the same, for the n8n workflow; needs AIN_AUTOMATION_TOKEN)

It only reports. Re-run the build (`scrape_bdlaws`, `build_corpus`, `python -m ain.retrieval`) after a human looks.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone

from corpus import scrape_bdlaws

_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", unicodedata.normalize("NFC", text)).strip()


def live_page(path: str) -> str:
    """Short timeout, one retry: a scheduled check should report an unreachable site, not hang on it."""
    return scrape_bdlaws.download(path, timeout=30, attempts=2)


PAUSE_S = 1.0  # between acts: be polite to a government site


def check(sections: list, page: Callable[[str], str] | None = None, pause: float | None = None) -> dict:
    """`sections`: the corpus sections; `page(path)` returns one decoded bdlaws page (live by default)."""
    page = page or live_page
    pause = PAUSE_S if pause is None else pause
    acts = [a for a in json.loads(scrape_bdlaws.ACTS_FILE.read_text(encoding="utf-8")) if a.get("bdlaws_id")]
    ours: dict[str, dict[str, str]] = defaultdict(dict)
    for s in sections:
        if s.source == "bdlaws.minlaw.gov.bd":
            ours[s.act_key][s.section] = s.text
    rows, errors = [], []
    for i, act in enumerate(acts):
        stored = ours.get(act["key"])
        if not stored:
            continue
        if i and pause:
            time.sleep(pause)
        try:
            live = {d["section"]: d["text"] for d in scrape_bdlaws.parse_details(page(f"/act-details-{act['bdlaws_id']}.html"))}
        except Exception as e:  # noqa: BLE001 - one unreachable act must not hide the others
            errors.append({"act": act["key"], "error": f"{type(e).__name__}: {e}"[:300]})
            if not rows and isinstance(e, OSError):  # the first act failed on the network: the site is down, stop here
                errors.append({"act": None, "error": "bdlaws.minlaw.gov.bd unreachable; remaining acts not checked"})
                break
            continue
        if not live:
            errors.append({"act": act["key"], "error": "page parsed to no sections (layout change?)"})
            continue
        changed = sorted(n for n, t in stored.items() if n in live and _norm(live[n]) != _norm(t))
        missing = sorted(n for n in stored if n not in live)
        added = sorted(n for n in live if n not in stored) if not act.get("sections") else []
        rows.append(
            {
                "act": act["key"],
                "title": act.get("title_en", act["title"]),
                "url": f"{scrape_bdlaws.BASE}/act-details-{act['bdlaws_id']}.html",
                "checked_sections": len(stored),
                "changed": [f"{act['key']}-s{n}" for n in changed],
                "missing": [f"{act['key']}-s{n}" for n in missing],
                "new_sections": [f"{act['key']}-s{n}" for n in added],
            }
        )
    changes = sum(len(r["changed"]) + len(r["missing"]) + len(r["new_sections"]) for r in rows)
    return {
        "ok": not errors,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "acts_checked": len(rows),
        "sections_checked": sum(r["checked_sections"] for r in rows),
        "changed": changes > 0,
        "changes": changes,
        "acts": [r for r in rows if r["changed"] or r["missing"] or r["new_sections"]],
        "errors": errors,
        "next_step": "Review the changes, then rebuild: python -m corpus.scrape_bdlaws, python -m corpus.build_corpus, python -m ain.retrieval" if changes else None,
    }


def main() -> None:
    from ain.retrieval import get_corpus

    print(json.dumps(check(get_corpus().sections), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
