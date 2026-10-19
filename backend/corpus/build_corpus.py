"""Merge the processed section files into corpus/processed/corpus.jsonl (the file the app loads).

Order: Bangladesh statutes (scrape_bdlaws), then international and destination-country
excerpts (curate_intl), then published company policies (curate_companies) when present.
Fails if two files define the same citation_id. Rebuild the embeddings afterwards with
`python -m ain.retrieval`, otherwise dense search switches itself off (corpus hash mismatch).
"""

from __future__ import annotations

import json
from pathlib import Path

PROCESSED = Path(__file__).resolve().parent / "processed"
PARTS = ["bd_sections.jsonl", "intl_sections.jsonl", "company_sections.jsonl"]
OUT = PROCESSED / "corpus.jsonl"


def main() -> None:
    lines: list[str] = []
    seen: dict[str, str] = {}
    for name in PARTS:
        path = PROCESSED / name
        if not path.exists():
            print(f"skip    {name} (not built)")
            continue
        n = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            cid = json.loads(line)["citation_id"]
            if cid in seen:
                raise SystemExit(f"duplicate citation_id {cid} in {name} (already in {seen[cid]})")
            seen[cid] = name
            lines.append(line)
            n += 1
        print(f"merged  {name:<24} {n:>5} sections")
    OUT.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    print(f"wrote {len(lines)} sections -> {OUT}")


if __name__ == "__main__":
    main()
