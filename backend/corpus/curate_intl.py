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
import zipfile
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
        elif path.suffix == ".docx":
            xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
            text = html.unescape(re.sub(r"<[^>]+>", " ", xml.replace("</w:p>", "\n")))
        else:
            page = re.sub(r"<script.*?</script>|<style.*?</style>", " ", path.read_text(encoding="utf-8", errors="replace"), flags=re.S)
            text = html.unescape(re.sub(r"<[^>]+>", " ", page))
        for lig, plain in (("ﬃ", "ffi"), ("ﬄ", "ffl"), ("ﬀ", "ff"), ("ﬁ", "fi"), ("ﬂ", "fl")):
            text = text.replace(lig, plain)
        _cache[name] = _ws(text)
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


def table(name: str, page: int, index: int, title: str) -> str:
    """One table of a PDF, read cell by cell and written out row by row: "Title: Head: value | Head (sub-head): key: value; ...".

    Only the cells' own text is used (joined with ":", ";" and "|"), so nothing is typed by hand. The table must start with a
    row holding just `title`, then a row of column heads; a head spanning several columns (e.g. "Daily" over one column per
    number of working days) is followed by a sub-head row, a row of keys and a row of values. Anything else fails loudly.
    """
    with pymupdf.open(RAW / name) as doc:
        rows = [[_ws(c) if c else None for c in r] for r in doc[page].find_tables().tables[index].extract()]
    rows = [r for r in rows if any(r)]
    if rows[0][0] != title or any(rows[0][1:]):
        raise SystemExit(f"table {name} p.{page} #{index}: first row is not the title {title!r}: {rows[0]}")
    heads = [i for i, c in enumerate(rows[1]) if c]
    spans = [range(a, b) for a, b in zip(heads, [*heads[1:], len(rows[1])])]
    parts = []
    for cols in spans:
        head = rows[1][cols[0]]
        cells = [[r[c] for c in cols] for r in rows[2:]]
        if len(cols) == 1:
            vals = [c[0] for c in cells if c[0]]
            if len(vals) != 1:
                raise SystemExit(f"table {name}: column {head!r} has {len(vals)} values")
            parts.append(f"{head}: {vals[0]}")
            continue
        sub_head, keys, vals = cells[0][0], cells[1], cells[2]
        if not sub_head or any(cells[0][1:]) or not all(keys) or not all(vals):
            raise SystemExit(f"table {name}: column group {head!r} is not sub-head / keys / values: {cells}")
        parts.append(f"{head} ({sub_head}): " + "; ".join(f"{k}: {v}" for k, v in zip(keys, vals)))
    return f"{title}: " + " | ".join(parts)


def _law(common: dict, *sections: dict) -> list[dict]:
    """Several excerpts of one act: the act-level fields are shared, each section adds its own."""
    return [{**common, **sec} for sec in sections]


# the compilation's running page header and footnote links, which can fall inside a cut that crosses a page
CEACR_PAGE_FURNITURE = (
    r" ?►Compilation of selected observations and direct requests of the Committee of Experts on the Application of Conventions"
    r" and Recommendations: Bangladesh \d+| ?\d+ https://www\.ilo\.org/\S+"
)

BH_NOTE ="Legislation & Legal Opinion Commission English version for reference (published May 2024); the Arabic text in the Official Gazette prevails."

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
         # para 3(1)'s rate table heads the next page; the plain text flattens it ("Monthly Daily Hourly RM1,700 ... RM98.08"),
         # so it is read cell by cell and put back where 3(1) introduces it
         table=dict(page=6, index=0, title="Minimum Wages Rate", after="shall be as follows:"),
         drop=r" P\.U\. \(A\) 376 \d+(?= \()",  # the gazette's running page header, not part of the text
         note="Federal Government Gazette, 4 December 2024; revokes Minimum Wages Order 2022."),
    dict(citation_id="MY-EA-1955-s90B", jurisdiction="MY", act_key="MY-EA-1955", act="Employment Act 1955 (Act 265), Malaysia",
         year=1955, section="90B", heading="Forced labour", file="my_ea_mohr.pdf",
         start="90B. Any employer who threatens, deceives or forces an employee", end=" Employment 101",
         url="https://jtksm.mohr.gov.my/sites/default/files/2023-11/Akta%20Kerja%201955%20(Akta%20265).pdf",
         via=None, packs=["my_employment"], note="AGC updated text as at 1 January 2023."),
    # --- Saudi Arabia ------------------------------------------------------------------
    *_law(
        dict(jurisdiction="SA", act_key="SA-LABOR-2005", act="Labor Law, Royal Decree No. M/51 of 1426H (Saudi Arabia)", year=2005,
             file="sa_labor_wipo.html", url="https://www.wipo.int/wipolex/en/legislation/details/14685",
             via="https://www.wipo.int/wipolex/edocs/lexdocs/laws/en/sa/sa055en.pdf", packs=["sa_labour"], status="amended",
             note="English translation of the 2005 text (the Arabic text prevails). The Labor Law has since been amended, including by "
                  "Royal Decree M/44 in force from 19 February 2025; check the current Arabic text before relying on it."),
        dict(citation_id="SA-LABOR-2005-a40", section="40", heading="Employer bears recruitment, iqama, work-permit and return-ticket costs",
             start="Article (40): (1) An employer shall incur the fees", end=" (3) An employer shall bear the fees of transferring"),
        dict(citation_id="SA-LABOR-2005-a61", section="61", heading="No unpaid work; wages may not be withheld",
             start="Article (61): In addition to the duties provided for in this Law", end=" (2) Give the workers the time required"),
        dict(citation_id="SA-LABOR-2005-a84", section="84", heading="End-of-service award",
             start="Article (84): Upon the end of the work relation", end=" Article (85):"),
        dict(citation_id="SA-LABOR-2005-a93", section="93", heading="Deductions may not exceed half the wage",
             start="Article (93): In all cases, deductions made may not exceed",
             end=" PART VI WORK CONDITIONS AND CIRCUMSTANCES Chapter One Wages PART VI"),
    ),
    # --- United Arab Emirates ----------------------------------------------------------
    *_law(
        dict(jurisdiction="AE", act_key="AE-LABOUR-2021", act="Federal Decree-Law No. 33 of 2021 Regulating Labour Relations (UAE)", year=2021,
             file="ae_labour_fao.pdf", url="https://u.ae/en/information-and-services/jobs/employment-laws-and-regulations-in-the-private-sector",
             via="https://faolex.fao.org/docs/pdf/uae217212E.pdf", packs=["ae_labour"], status="amended",
             note="MOHRE English text of the 2021 Decree-Law, marked 'not an official translation' (the Arabic text prevails). "
                  "Later amended, including by Federal Decree-Laws 14/2022 and 20/2023."),
        dict(citation_id="AE-LABOUR-2021-a6", section="6", heading="Recruitment and employment of workers; no recruitment fees for workers",
             start="Article (6) Recruitment and Employment of Workers", end=" 5. Te Minister, in coordination"),
        dict(citation_id="AE-LABOUR-2021-a13", section="13", heading="Obligations of the employer (documents, repatriation)",
             start="Article (13) Employer’s Obligations", end="Article (14) Prohibition of Forced Labour"),
        dict(citation_id="AE-LABOUR-2021-a14", section="14", heading="Prohibition of forced labour",
             start="Article (14) Prohibition of Forced Labour", end=" 2. Sexual harassment"),
        dict(citation_id="AE-LABOUR-2021-a25", section="25", heading="Cases of deduction or withholding from the wage",
             start="Article (25) Cases of Deduction or Withhold", end="Article (26) Enabling the Worker to Work"),
        dict(citation_id="AE-LABOUR-2021-a51", section="51", heading="End-of-service benefits for full-time workers",
             start="Article (51) End of Service Benefits for Full-Time Workers", end=" 3. Te foreign worker shall be entitled to a benefit for parts"),
    ),
    # --- Qatar -------------------------------------------------------------------------
    *_law(
        dict(jurisdiction="QA", act_key="QA-LABOUR-2004", act="Labour Law, Law No. 14 of 2004 (Qatar)", year=2004,
             file="qa_labour_embassy.pdf", url="https://www.almeezan.qa/LawView.aspx?opt&LawID=3961&language=en",
             via="https://dev.alkarama.org/sites/default/files/2016-11/QTR_LabourLaw_EN_0.pdf", packs=["qa_labour"], status="amended",
             note="English translation distributed by the Embassy of Qatar (the Arabic text prevails). Amended since 2004, "
                  "including by Law No. 18 of 2020; check the consolidated text on Al Meezan."),
        dict(citation_id="QA-LABOUR-2004-a33", section="33", heading="Recruiters may not take recruitment fees from the worker",
             start="Article (33) The person who is licensed to recruit workers", end=" 2. To carry out in the office"),
        dict(citation_id="QA-LABOUR-2004-a54", section="54", heading="End-of-service gratuity",
             start="Article (54) In addition to any sums", end=" The worker's service shall be considered"),
        dict(citation_id="QA-LABOUR-2004-a57", section="57", heading="Employer returns the worker home at its own cost",
             start="Article (57) Upon termination of the service of the worker", end=" If the worker joins another employer"),
        dict(citation_id="QA-LABOUR-2004-a70", section="70", heading="Limits on attachment and deduction of wages",
             start="Article (70) Any part of the wage", end=" Article (71)"),
    ),
    # --- Oman --------------------------------------------------------------------------
    *_law(
        dict(jurisdiction="OM", act_key="OM-LABOUR-2023", act="Labour Law, Royal Decree 53/2023 (Oman)", year=2023,
             file="om_labour_decree.html", url="https://decree.om/2023/rd20230053/", via=None, packs=["om_labour"],
             note="Unofficial English translation published by Decree.om; the Arabic text in the Official Gazette prevails."),
        dict(citation_id="OM-LABOUR-2023-a5", section="5", heading="No compulsory or forced labour",
             start="Article 5 The employer is prohibited from imposing", end=" Article 6 It is not permitted"),
        dict(citation_id="OM-LABOUR-2023-a6", section="6", heading="Employer may not keep the worker's passport",
             start="Article 6 It is not permitted for the employer to keep the passport", end=" Article 7 The Arabic language"),
        dict(citation_id="OM-LABOUR-2023-a14", section="14", heading="Employer returns the non-Omani worker home",
             start="Article 14 The employer shall return the non-Omani worker", end=" Article 15 The minister shall issue"),
        dict(citation_id="OM-LABOUR-2023-a31", section="31", heading="No amounts may be charged to recruited workers",
             start="Article 31 It is prohibited to practise the activity of recruiting", end=" Article 32 It is prohibited to advertise"),
        dict(citation_id="OM-LABOUR-2023-a96", section="96", heading="Wages may be withheld only up to one-fourth",
             start="Article 96 It is not permitted to withhold or waive the wages", end=" Article 97 The right"),
    ),
    # --- Kuwait ------------------------------------------------------------------------
    *_law(
        dict(jurisdiction="KW", act_key="KW-LABOUR-2010", act="Law No. 6 of 2010 on Labour in the Private Sector (Kuwait)", year=2010,
             file="kw_labour_huembassy.pdf", url="https://kuwait.mfa.gov.hu/assets/03/54/68/2937dc434147a45919353f5d3aa861cc69e84dcf.pdf",
             via="https://web.archive.org/web/20240909223937/https://kuwait.mfa.gov.hu/assets/03/54/68/2937dc434147a45919353f5d3aa861cc69e84dcf.pdf",
             packs=["kw_labour"], status="amended",
             note="Unofficial English translation hosted by the Embassy of Hungary in Kuwait (archived copy); the Arabic text prevails. "
                  "Amended since 2010 (e.g. 2017-2018 changes to Articles 51 and 70)."),
        dict(citation_id="KW-LABOUR-2010-a10", section="10", heading="Employer bears the worker's return to his country",
             start="Article -10- The employer shall be prohibited from employing foreign labor", end="Article -11-"),
        dict(citation_id="KW-LABOUR-2010-a51", section="51", heading="End-of-service gratuity",
             start="Article -51- The laborer shall be entitled the end of service gratuity", end="Article -52-"),
        dict(citation_id="KW-LABOUR-2010-a59", section="59", heading="Limits on deductions from wages",
             start="Article -59-", end="Article -60-"),
    ),
    # --- Bahrain -----------------------------------------------------------------------
    *_law(
        dict(jurisdiction="BH", act_key="BH-LMRA-2006", act="Law No. 19 of 2006 Regulating the Labour Market (Bahrain)", year=2006,
             file="bh_lmra_lloc.docx", url="https://www.lloc.gov.bh/FullEn/K1906.docx", via=None, packs=["bh_labour"], note=BH_NOTE),
        dict(citation_id="BH-LMRA-2006-a23", section="23", heading="Work permits; no money may be taken from a worker for a permit or a job",
             start="Article (23) Work Permits", end="Article (24) Conditions and Procedures"),
    ),
    *_law(
        dict(jurisdiction="BH", act_key="BH-LABOUR-2012", act="Labour Law for the Private Sector, Law No. 36 of 2012 (Bahrain)", year=2012,
             file="bh_labour_lloc.docx", url="https://www.lloc.gov.bh/FullEn/K3612.docx", via=None, packs=["bh_labour"], note=BH_NOTE),
        dict(citation_id="BH-LABOUR-2012-a44", section="44", heading="Loan deductions limited to 10% of the wage",
             start="Article (44): (a) An employer shall not deduct", end="Article (45):"),
        dict(citation_id="BH-LABOUR-2012-a45", section="45", heading="Wages may be attached only up to 25%",
             start="Article (45): The wage due to a worker shall not be attached", end="Article (46):"),
        dict(citation_id="BH-LABOUR-2012-a116", section="116", heading="Leaving indemnity",
             start="Article (116): A worker who is not subject", end=" Article (117):"),
    ),
    # --- Singapore ---------------------------------------------------------------------
    dict(citation_id="SG-EFMA-1990-s22A", jurisdiction="SG", act_key="SG-EFMA-1990", act="Employment of Foreign Manpower Act 1990 (Singapore)",
         year=1990, section="22A", heading="No money may be taken from a foreign employee for getting or keeping a job", file="sg_efma_s22a.html",
         start="22A. —(1) A person must not deduct", end=" (3) Any person who deducts",
         url="https://sso.agc.gov.sg/Act/EFMA1990?ProvIds=pr22A-", via=None, packs=["sg_labour"], note="Singapore Statutes Online, current version."),
    dict(citation_id="SG-EA-1968-s32", jurisdiction="SG", act_key="SG-EA-1968", act="Employment Act 1968 (Singapore)",
         year=1968, section="32", heading="Deductions not to exceed prescribed limit", file="sg_ea_s32.html",
         start="32. —(1) The total amount of all deductions", end=" Singapore Statutes Online FAQs",
         url="https://sso.agc.gov.sg/Act/EmA1968?ProvIds=pr32-", via=None, packs=["sg_labour"], note="Singapore Statutes Online, current version."),
    dict(citation_id="SG-PA-2007-s47", jurisdiction="SG", act_key="SG-PA-2007", act="Passports Act 2007 (Singapore)",
         year=2007, section="47(5)", heading="Offence to keep another person's foreign travel document", file="sg_pa_s47.html",
         start="(5) If — ( a ) a person has or retains possession", end=" (6) If",
         url="https://sso.agc.gov.sg/Act/PA2007?ProvIds=pr47-", via=None, packs=["sg_labour"], note="Singapore Statutes Online, current version."),
    # --- voluntary recruitment standards (not law) ---------------------------------------
    *_law(
        dict(jurisdiction="INTL", act_key="STD-ILO-FAIR-2019", act="ILO General Principles and Operational Guidelines for Fair Recruitment (2019)",
             year=2019, file="std_ilo_fair.pdf", url="https://www.ilo.org/publications/general-principles-and-operational-guidelines-fair-recruitment-and",
             via="https://respect.international/wp-content/uploads/2019/07/General-Principles-and-Operational-Guidelines-for-Fair-Recruitment-and-Definition-of-Recruitment-Fees-and-Related-Costs.pdf",
             packs=["std_recruitment"], kind="standard", note="Non-binding ILO guidance adopted by a tripartite meeting of experts."),
        dict(citation_id="STD-ILO-FAIR-2019-p7", section="7", heading="No recruitment fees or related costs for workers",
             start="7. No recruitment fees or related costs should be charged to, or otherwise borne by, workers or jobseekers.", end=" 8. The terms and conditions"),
        dict(citation_id="STD-ILO-FAIR-2019-p8", section="8", heading="Clear written contracts; no contract substitution",
             start="8. The terms and conditions of a worker’s employment should be specified", end=" 9. Workers’ agreements"),
        dict(citation_id="STD-ILO-FAIR-2019-p11", section="11", heading="Identity documents must not be retained",
             start="11. Freedom of workers to move within a country or to leave a country should be respected.", end=" 12. Workers should be free"),
        dict(citation_id="STD-ILO-FAIR-2019-p12", section="12", heading="Freedom to end the job and return home",
             start="12. Workers should be free to terminate their employment", end=" 13. Workers, irrespective"),
    ),
    dict(citation_id="STD-EPP-LGRR", jurisdiction="INTL", act_key="STD-EPP", act="Employer Pays Principle (Leadership Group for Responsible Recruitment)",
         year=2016, section="policy commitment", heading="No worker should pay for a job", file="std_epp_lgrr.pdf",
         start="The policy commitment should reflect the Employer Pays Principle", end=" • The commitment should clearly expl",
         url="https://www.ihrb.org/employerpays/the-employer-pays-principle", via=None, packs=["std_recruitment"], kind="standard",
         note="Voluntary industry commitment; from the Leadership Group's 'Six Steps to Responsible Recruitment' guide."),
    dict(citation_id="STD-RBA-2024-A1", jurisdiction="INTL", act_key="STD-RBA-2024", act="Responsible Business Alliance Code of Conduct 8.0 (2024)",
         year=2024, section="A.1", heading="Prohibition of forced labor (documents, fees, contracts)", file="std_rba_8.pdf",
         start="1) Prohibition of Forced Labor Forced labor in any form", end=" 2) Young Workers",
         url="https://www.responsiblebusiness.org/code-of-conduct/", via="https://www.responsiblebusiness.org/media/docs/RBACodeofConduct8.0_English.pdf",
         packs=["std_recruitment"], kind="standard", note="Industry code binding RBA members and their suppliers by contract; in effect from 1 January 2024."),
    # --- ILO supervisory comments (CEACR observations on Bangladesh; interpretive, not binding) ---
    *_law(
        dict(jurisdiction="INTL", file="ilo_ceacr_bd_2024.pdf", packs=["ilo_supervisory"], kind="supervisory",
             via="https://tradefordecentwork.ilo.org/wp-content/uploads/2024/09/Compilation-of-selected-observations-and-direct-requests-of-the-Committee-of-Experts-on-the-Application-of-Conventions-and-Recommendations-Bangladesh.pdf",
             drop=CEACR_PAGE_FURNITURE,
             note="Observation of the ILO Committee of Experts on the Application of Conventions and Recommendations (CEACR), from the ILO's own compilation (2024). Interpretive, not binding; a later comment may exist on NORMLEX."),
        dict(citation_id="ILO-CEACR-C087-2023-EPZ", act_key="ILO-CEACR-C087-2023",
             act="ILO CEACR Observation on Convention No. 87 (Freedom of Association), Bangladesh, adopted 2023", year=2023, section="EPZ",
             heading="Right to organise in export processing zones", url=NORMLEX.format(code="C087"),
             start="Right to organize in export processing zones. In its previous comment",
             end=" In its previous comment, the Committee also encouraged the Government to continue to review the inspection framework"),
        dict(citation_id="ILO-CEACR-C098-2023-EPZ", act_key="ILO-CEACR-C098-2023",
             act="ILO CEACR Observation on Convention No. 98 (Right to Organise and Collective Bargaining), Bangladesh, adopted 2023", year=2023,
             section="EPZ", heading="Protection against anti-union discrimination in export processing zones", url=NORMLEX.format(code="C098"),
             start="Protection of workers in export-processing zones (EPZs) against acts of anti-union discrimination.",
             end=" The Committee also requested the Government to provide its observations on the allegations"),
        dict(citation_id="ILO-CEACR-C029-2021-FL", act_key="ILO-CEACR-C029-2021",
             act="ILO CEACR Observation on Convention No. 29 (Forced Labour), Bangladesh, adopted 2021", year=2021, section="2",
             heading="Forced labour practices", url="https://www.ilo.org/dyn/normlex/en/f?p=1000:13100:0::NO:13100:P13100_COMMENT_ID,P13100_COUNTRY_ID:4116528,103500",
             start="2. Forced labour practices. The Committee previously noted",
             end=" The Committee is raising other matters in a request addressed directly"),
    ),
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
    out = []
    for s in SPECS:
        text = cut(s["file"], s["start"], s["end"])
        if s.get("extra_start"):
            text += " " + cut(s["file"], s["extra_start"], s["extra_end"])
        if s.get("drop"):
            text = re.sub(s["drop"], "", text)
        if s.get("table"):
            t = s["table"]
            if text.count(t["after"]) != 1:
                raise SystemExit(f"{s['citation_id']}: table anchor {t['after']!r} must occur exactly once")
            text = text.replace(t["after"], f"{t['after']} {table(s['file'], t['page'], t['index'], t['title'])}")
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
                "retrieved_at": date.fromtimestamp((RAW / s["file"]).stat().st_mtime).isoformat(),  # when the file was downloaded
                "status": s.get("status", "in_force"),
                "superseded_by": None,
                "amendment_notes": [s["note"]] if s.get("note") else [],
                "packs": s["packs"],
                "kind": s.get("kind", "law"),
            }
        )
        print(f"{s['citation_id']:<24} {len(text):>5} chars  {text[:70]}…")
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    print(f"wrote {len(out)} records -> {OUT}")


if __name__ == "__main__":
    main()
