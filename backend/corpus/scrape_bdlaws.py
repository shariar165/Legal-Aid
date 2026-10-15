"""Polite scraper for bdlaws.minlaw.gov.bd (Laws of Bangladesh, Legislative and Parliamentary Affairs Division).

The site serves UTF-16 HTML. For each act we read two pages:
  * /act-N.html          -> ordered list of (section number, heading, per-section URL)
  * /act-details-N.html  -> full consolidated text of every section, with amendment footnotes

Raw pages are cached under corpus/raw/ so the site is hit at most once per page.
Output: corpus/processed/bd_sections.jsonl (one record per section).

Usage:  python -m corpus.scrape_bdlaws            (from backend/)
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

BASE = "http://bdlaws.minlaw.gov.bd"
HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
OUT = HERE / "processed" / "bd_sections.jsonl"
ACTS_FILE = HERE / "acts.json"

BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
# Bangla section-number suffix letters (৩ক -> 3A)
BN_SUFFIX = {"ক": "A", "খ": "B", "গ": "C", "ঘ": "D", "ঙ": "E", "চ": "F"}


def fetch(path: str) -> str:
    """Fetch a bdlaws page (UTF-16) once, caching the decoded UTF-8 copy."""
    RAW.mkdir(parents=True, exist_ok=True)
    cache = RAW / (path.strip("/").replace("/", "__"))
    if cache.exists() and cache.stat().st_size > 1000:
        return cache.read_text(encoding="utf-8")
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "AinCopilot-research/0.1 (hackathon corpus build)"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read()
            break
        except Exception as e:  # noqa: BLE001 - network flakiness on a government site
            if attempt == 3:
                raise
            print(f"  retry {path}: {e}", file=sys.stderr)
            time.sleep(3 * (attempt + 1))
    text = data.decode("utf-16") if data[:2] in (b"\xff\xfe", b"\xfe\xff") else data.decode("utf-8", errors="replace")
    cache.write_text(text, encoding="utf-8")
    time.sleep(1.0)  # be polite
    return text


def norm_section_no(raw: str) -> str:
    """'২৭' -> '27', '৩ক' -> '3A', '44A' -> '44A'."""
    s = raw.strip().translate(BN_DIGITS)
    for bn, en in BN_SUFFIX.items():
        s = s.replace(bn, en)
    return s.upper()


def clean(fragment: str) -> str:
    fragment = re.sub(r"<span class='footnote'[^>]*>.*?</span></span>", "", fragment, flags=re.S)
    fragment = re.sub(r"<br\s*/?>|</p>|<div class=\"clbr\">", "\n", fragment)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    fragment = html.unescape(fragment).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in fragment.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def footnotes(fragment: str) -> list[str]:
    notes = re.findall(r"class='footnote'[^>]*title='([^']*)'", fragment)
    return [html.unescape(n).strip() for n in notes if n.strip()]


INDEX_RE = re.compile(
    r'<p class="act-section-name[^"]*">\s*<a href="(/act-\d+/section-\d+\.html)">\s*(.*?)\s*</a>', re.S
)
NO_RE = re.compile(r"^\s*\[?\s*([0-9০-৯]+[A-Za-zকখগঘঙচ]?)\s*[\.।৷]\s*(.*)$", re.S)


def parse_index(page: str) -> list[dict]:
    out = []
    for url, label in INDEX_RE.findall(page):
        label = re.sub(r"\s+", " ", html.unescape(label)).strip()
        m = NO_RE.match(label)
        if not m:
            continue
        out.append({"section": norm_section_no(m.group(1)), "heading": m.group(2).strip(), "url": BASE + url})
    return out


BLOCK_RE = re.compile(
    r'<div class="col-sm-3 txt-head"[^>]*>(.*?)</div>\s*<div class="col-sm-9 txt-details"[^>]*>(.*?)(?=<div class="row lineremoves|<section|<div class="col-sm-3 txt-head"|$)',
    re.S,
)


def parse_details(page: str) -> list[dict]:
    blocks = []
    for head, body in BLOCK_RE.findall(page):
        text = clean(body)
        m = NO_RE.match(text)
        if not m:
            continue
        blocks.append(
            {
                "section": norm_section_no(m.group(1)),
                "heading": clean(head),
                "text": text,
                "amendment_notes": footnotes(head + body),
            }
        )
    return blocks


def scrape_act(act: dict) -> list[dict]:
    aid = act["bdlaws_id"]
    print(f"[bdlaws] act-{aid} {act['title']}")
    index = parse_index(fetch(f"/act-{aid}.html"))
    details = parse_details(fetch(f"/act-details-{aid}.html"))
    by_no = {}
    for d in details:
        by_no.setdefault(d["section"], d)
    wanted = set(act.get("sections") or [])
    records = []
    for entry in index:
        sec = entry["section"]
        if wanted and sec not in wanted:
            continue
        d = by_no.get(sec)
        if not d:
            print(f"  ! no text for s.{sec}", file=sys.stderr)
            continue
        notes = d["amendment_notes"]
        records.append(
            {
                "citation_id": f"{act['key']}-s{sec}",
                "jurisdiction": "BD",
                "act_key": act["key"],
                "act": act["title"],
                "act_en": act.get("title_en", act["title"]),
                "year": act["year"],
                "section": sec,
                "heading": entry["heading"] or d["heading"],
                "text": d["text"],
                "lang": act["lang"],
                "url": entry["url"],
                "act_url": f"{BASE}/act-{aid}.html",
                "source": "bdlaws.minlaw.gov.bd",
                "retrieved_at": date.today().isoformat(),
                "status": act.get("status", "in_force"),
                "superseded_by": act.get("superseded_by"),
                "amendment_notes": notes,
                "packs": act["packs"],
            }
        )
    print(f"  {len(records)} sections")
    return records


def main() -> None:
    acts = json.loads(ACTS_FILE.read_text(encoding="utf-8"))
    only = set(sys.argv[1:])
    all_records = []
    for act in acts:
        if only and act["key"] not in only:
            continue
        all_records.extend(scrape_act(act))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(all_records)} records -> {OUT}")


if __name__ == "__main__":
    main()
