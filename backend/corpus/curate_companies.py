"""Cut companies' own published policy statements into citable sections (see corpus/companies.yaml).

Each document is downloaded from the company's own website into corpus/raw/ and cut between two
literal markers with the same `cut()` as the statutes, so no promise is ever typed by hand; a missing
marker fails the build.

    python -m corpus.curate_companies          (downloads missing files first)

Output: corpus/processed/company_sections.jsonl (merge with `python -m corpus.build_corpus`)
"""

from __future__ import annotations

import json
import urllib.request
from datetime import date
from pathlib import Path

import yaml

from corpus.curate_intl import RAW, cut
from corpus.fetch_intl import UA

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "companies.yaml"
OUT = HERE / "processed" / "company_sections.jsonl"


def load() -> list[dict]:
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


def fetch(company: dict) -> None:
    dest = RAW / company["file"]
    if dest.exists() and dest.stat().st_size > 1000:
        return
    with urllib.request.urlopen(urllib.request.Request(company["policy_url"], headers={"User-Agent": UA}), timeout=180) as r:
        dest.write_bytes(r.read())
    print(f"fetched {company['file']} ({dest.stat().st_size} bytes)")


def main() -> None:
    out = []
    for co in load():
        fetch(co)
        retrieved = date.fromtimestamp((RAW / co["file"]).stat().st_mtime).isoformat()
        key = f"CO-{co['slug'].upper()}"
        for spec in co["specs"]:
            text = cut(co["file"], spec["start"], spec["end"])
            note = f"{co['document']}, published {co['published']} by the company itself. Quoted as published; it says what the company promises, not what it does."
            out.append(
                {
                    "citation_id": f"{key}-s{spec['section']}",
                    "jurisdiction": "COMPANY",
                    "act_key": key,
                    "act": f"{co['name']}: {co['document']}",
                    "act_en": f"{co['name']}: {co['document']}",
                    "year": int(str(co["published"])[-4:]) if str(co["published"])[-4:].isdigit() else int(str(co["published"])[:4]),
                    "section": spec["section"],
                    "heading": spec["heading"],
                    "text": text,
                    "lang": "en",
                    "url": co["policy_url"],
                    "act_url": co["policy_url"],
                    "source": co["policy_url"],
                    "retrieved_at": retrieved,
                    "status": "in_force",
                    "superseded_by": None,
                    "amendment_notes": [note] + ([co["notes"]] if co.get("notes") else []),
                    "packs": [f"co_{co['slug']}"],
                    "kind": "company_policy",
                }
            )
            print(f"{out[-1]['citation_id']:<20} {len(text):>5} chars  {text[:70]}…")
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    print(f"wrote {len(out)} records -> {OUT}")


if __name__ == "__main__":
    main()
