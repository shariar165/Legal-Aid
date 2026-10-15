"""Build verbatim excerpts of non-bdlaws sources (ILO, Malaysia, EU, Bangladesh Bank).

Every excerpt is cut out of a downloaded official document (or a verbatim mirror of
one) between two literal markers, so no statute text is ever typed by hand. If a
marker is missing the build fails loudly instead of silently inventing text.

Sources (downloaded into corpus/raw/ by `python -m corpus.fetch_intl`):
  * ILO C029 / C095 / C181 - verbatim NORMLEX copies (lankalaw.net mirror; NORMLEX blocks bots)
  * Malaysia Employment Act 1955 - AGC updated text as at 1 Jan 2023 (hosted by MOHR/JTKSM)
  * Malaysia Minimum Wages Order 2024, P.U.(A) 376 - Federal Government Gazette
  * EU CSDDD 2024/1760 and GDPR 2016/679 - Publications Office CELLAR (official XHTML)
  * Bangladesh Bank GFET 2018 Vol-1 (BEPZA-hosted copy) and FE Circular 13/2020

Output: corpus/processed/intl_sections.jsonl
"""

from __future__ import annotations

import html
import json
import re
from datetime import date
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
OUT = HERE / "processed" / "intl_sections.jsonl"

NORMLEX = "https://normlex.ilo.org/dyn/nrmlx_en/f?p=NORMLEXPUB:12100:0::NO::P12100_ILO_CODE:{code}"


def _ws(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


_cache: dict[str, str] = {}


def load(name: str) -> str:
    if name not in _cache:
        path = RAW / name
        if path.suffix == ".pdf":
            with pymupdf.open(path) as doc:
                text = " ".join(p.get_text() for p in doc)
        else:
            text = html.unescape(re.sub(r"<[^>]+>", " ", path.read_text(encoding="utf-8", errors="replace")))
        _cache[name] = _ws(text.replace("ﬁ", "fi").replace("ﬂ", "fl"))
    return _cache[name]


def cut(name: str, start: str, end: str | None, occurrence: int = 0) -> str:
    text = load(name)
    idx = -1
    for _ in range(occurrence + 1):
        idx = text.find(start, idx + 1)
        if idx < 0:
            raise SystemExit(f"start marker not found in {name}: {start!r}")
    if end is None:
        return text[idx:].strip()
    j = text.find(end, idx + len(start))
    if j < 0:
        raise SystemExit(f"end marker not found in {name}: {end!r}")
    return text[idx:j].strip()


SPECS = [
    # --- ILO ---------------------------------------------------------------------------
    dict(citation_id="ILO-C029-a2", jurisdiction="INTL", act_key="ILO-C029", act="Forced Labour Convention, 1930 (No. 29)",
         year=1930, section="2", heading="Definition of forced or compulsory labour", file="lk_c029.pdf",
         start="Article 2 1. For the purposes", end=" 2. Nevertheless", url=NORMLEX.format(code="C029"),
         via="https://lankalaw.net/wp-content/uploads/2024/12/C29-Forced-Labour-Convention-1930.pdf", packs=["ilo"]),
    dict(citation_id="ILO-C095-a8", jurisdiction="INTL", act_key="ILO-C095", act="Protection of Wages Convention, 1949 (No. 95)",
         year=1949, section="8", heading="Deductions from wages", file="lk_c095.pdf",
         start="Article 8 1. Deductions", end="Article 9", url=NORMLEX.format(code="C095"),
         via="https://lankalaw.net/wp-content/uploads/2024/12/C95-Protection-of-Wages-Convention-1949.pdf", packs=["ilo"]),
    dict(citation_id="ILO-C095-a9", jurisdiction="INTL", act_key="ILO-C095", act="Protection of Wages Convention, 1949 (No. 95)",
         year=1949, section="9", heading="Prohibition of deductions to obtain or retain employment", file="lk_c095.pdf",
         start="Article 9 Any deduction", end="Article 10", url=NORMLEX.format(code="C095"),
         via="https://lankalaw.net/wp-content/uploads/2024/12/C95-Protection-of-Wages-Convention-1949.pdf", packs=["ilo"]),
    dict(citation_id="ILO-C181-a7", jurisdiction="INTL", act_key="ILO-C181", act="Private Employment Agencies Convention, 1997 (No. 181)",
         year=1997, section="7", heading="No fees or costs to workers", file="lk_c181.pdf",
         start="Article 7 1. Private employment agencies", end="Article 8", url=NORMLEX.format(code="C181"),
         via="https://lankalaw.net/wp-content/uploads/2024/12/C181-Private-Employment-Agencies-Convention-1997.pdf", packs=["ilo"]),
    # --- Malaysia ------------------------------------------------------------------------
    dict(citation_id="MY-EA-1955-s24", jurisdiction="MY", act_key="MY-EA-1955", act="Employment Act 1955 (Act 265), Malaysia",
         year=1955, section="24", heading="Lawful deductions", file="my_ea_mohr.pdf",
         start="24. (1) No deductions shall be made", end="(9) The limitation in subsection (8)",
         url="https://jtksm.mohr.gov.my/sites/default/files/2023-11/Akta%20Kerja%201955%20(Akta%20265).pdf",
         via=None, packs=["my_employment"], note="AGC updated text as at 1 January 2023."),
    dict(citation_id="MY-MWO-2024-p3", jurisdiction="MY", act_key="MY-MWO-2024", act="Minimum Wages Order 2024, P.U.(A) 376 (Malaysia)",
         year=2024, section="3", heading="Minimum wages rates with effect from 1 February 2025", file="pua376.pdf",
         start="Minimum wages rates and rate of wages paid to employee based only on piece rate, tonnage, etc. with effect from 1 February 2025",
         end="Minimum wages rates and rate of wages paid to employee based only on piece rate, tonnage, etc. for the period",
         url="https://amcham.com.my/wp-content/uploads/PUA-376.pdf", via=None, packs=["my_employment"],
         extra_start="Minimum Wages Rate Monthly Daily Hourly RM1,700", extra_end=" Minimum Wages Rate Monthly Daily Hourly RM1,500",
         note="Federal Government Gazette, 4 December 2024; revokes Minimum Wages Order 2022."),
    # --- EU ------------------------------------------------------------------------------
    dict(citation_id="EU-CSDDD-2024-a10", jurisdiction="EU", act_key="EU-CSDDD-2024",
         act="Directive (EU) 2024/1760 on corporate sustainability due diligence (CSDDD)", year=2024, section="10",
         heading="Preventing potential adverse impacts", file="cellar_32024L1760.xhtml",
         start="Article 10 Preventing potential adverse impacts", end=" 3. Companies may take",
         url="https://eur-lex.europa.eu/eli/dir/2024/1760/oj", via="http://publications.europa.eu/resource/celex/32024L1760",
         packs=["eu_dd"], status="amended",
         note="Application dates postponed by Directive (EU) 2025/794 ('stop-the-clock'); further substantive amendments under the Omnibus I simplification package. Verify the consolidated text before relying on it."),
    dict(citation_id="EU-GDPR-2016-a44", jurisdiction="EU", act_key="EU-GDPR-2016", act="Regulation (EU) 2016/679 (GDPR)", year=2016,
         section="44", heading="General principle for transfers", file="cellar_32016R0679.xhtml",
         start="Article 44 General principle for transfers", end="Article 45 Transfers on the basis",
         url="https://eur-lex.europa.eu/eli/reg/2016/679/oj", via="http://publications.europa.eu/resource/celex/32016R0679", packs=["eu_data"]),
    # --- Bangladesh Bank (FX) ----------------------------------------------------------
    dict(citation_id="BD-GFET-2018-ch8p13", jurisdiction="BD", act_key="BD-GFET-2018",
         act="Guidelines for Foreign Exchange Transactions 2018, Vol-1 (Bangladesh Bank)", year=2018, section="Ch.8 para 13",
         heading="Prescribed period within which payment should be received", file="gfet2018.pdf",
         start="13. Prescribed period within which payment should be received", end="(b) Permissible period for repatriation",
         url="https://bepza.gov.bd/public/storage/upload/content-file/GFET-2018.pdf", via=None, packs=["bd_fx"]),
    dict(citation_id="BD-FENOTIF-1977-p2", jurisdiction="BD", act_key="BD-FENOTIF-1977",
         act="Bangladesh Bank Notification No. FE 1/77-BB (16 April 1977) under FER Act 1947", year=1977, section="2",
         heading="Full export value to be paid within four months of shipment", file="gfet2018.pdf",
         start="2. For export of goods to any country an amount representing the full export value", end=" 3. An amount representing",
         url="https://bepza.gov.bd/public/storage/upload/content-file/GFET-2018.pdf", via=None, packs=["bd_fx"],
         note="Reproduced as GFET 2018 Appendix 3/5."),
    dict(citation_id="BD-FECIRC-2020-13-p2a", jurisdiction="BD", act_key="BD-FECIRC-2020-13",
         act="Bangladesh Bank FE Circular No. 13 (19 March 2020)", year=2020, section="02(a)",
         heading="Extension of realisation period of export proceeds", file="fe_circ_2020_13.pdf",
         start="(a) ADs may allow exporters to extend the tenure", end="(b) ADs may allow importers",
         url="https://www.bb.org.bd/mediaroom/circulars/circulars.php", via="https://cdn5.ogrlegal.com/files/forex/fepd/mar192020fepd13e.pdf",
         packs=["bd_fx"], note="Time-bound COVID-era relaxation; check whether still in effect."),
]


def main() -> None:
    today = date.today().isoformat()
    out = []
    for s in SPECS:
        text = cut(s["file"], s["start"], s["end"])
        if s.get("extra_start"):
            text += " " + cut(s["file"], s["extra_start"], s["extra_end"])
        out.append(
            {
                "citation_id": s["citation_id"],
                "jurisdiction": s["jurisdiction"],
                "act_key": s["act_key"],
                "act": s["act"],
                "act_en": s["act"],
                "year": s["year"],
                "section": s["section"],
                "heading": s["heading"],
                "text": text,
                "lang": "en",
                "url": s["url"],
                "act_url": s["url"],
                "source": s.get("via") or s["url"],
                "retrieved_at": today,
                "status": s.get("status", "in_force"),
                "superseded_by": None,
                "amendment_notes": [s["note"]] if s.get("note") else [],
                "packs": s["packs"],
            }
        )
        print(f"{s['citation_id']:<24} {len(text):>5} chars  {text[:70]}…")
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    print(f"wrote {len(out)} records -> {OUT}")


if __name__ == "__main__":
    main()
