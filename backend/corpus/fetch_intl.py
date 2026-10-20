"""Download the official (or verbatim-mirror) documents used by corpus.curate_intl into corpus/raw/."""

from __future__ import annotations

import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parent / "raw"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"

SOURCES = {
    "lk_c029.pdf": ("https://lankalaw.net/wp-content/uploads/2024/12/C29-Forced-Labour-Convention-1930.pdf", None),
    "lk_c095.pdf": ("https://lankalaw.net/wp-content/uploads/2024/12/C95-Protection-of-Wages-Convention-1949.pdf", None),
    "lk_c181.pdf": ("https://lankalaw.net/wp-content/uploads/2024/12/C181-Private-Employment-Agencies-Convention-1997.pdf", None),
    "my_ea_mohr.pdf": ("https://jtksm.mohr.gov.my/sites/default/files/2023-11/Akta%20Kerja%201955%20(Akta%20265).pdf", None),
    "pua376.pdf": ("https://amcham.com.my/wp-content/uploads/PUA-376.pdf", None),
    # CELLAR content negotiation returns the official XHTML (EUR-Lex itself is bot-protected).
    "cellar_32024L1760.xhtml": ("http://publications.europa.eu/resource/celex/32024L1760", "application/xhtml+xml"),
    "cellar_32016R0679.xhtml": ("http://publications.europa.eu/resource/celex/32016R0679", "application/xhtml+xml"),
    "gfet2018.pdf": ("https://bepza.gov.bd/public/storage/upload/content-file/GFET-2018.pdf", None),
    "fe_circ_2020_13.pdf": ("https://cdn5.ogrlegal.com/files/forex/fepd/mar192020fepd13e.pdf", None),
    # --- destination countries (English translations; the Arabic text prevails for the Gulf states) ---
    "sa_labor_wipo.html": ("https://www.wipo.int/wipolex/edocs/lexdocs/laws/en/sa/sa055en.pdf", None),
    "ae_labour_fao.pdf": ("https://faolex.fao.org/docs/pdf/uae217212E.pdf", None),
    "qa_labour_embassy.pdf": ("https://dev.alkarama.org/sites/default/files/2016-11/QTR_LabourLaw_EN_0.pdf", None),
    "om_labour_decree.html": ("https://decree.om/2023/rd20230053/", None),
    # The Hungarian Embassy's copy is served behind a viewer page; the Internet Archive keeps the raw PDF.
    "kw_labour_huembassy.pdf": (
        "https://web.archive.org/web/20240909223937id_/https://kuwait.mfa.gov.hu/assets/03/54/68/2937dc434147a45919353f5d3aa861cc69e84dcf.pdf",
        None,
    ),
    "bh_labour_lloc.docx": ("https://www.lloc.gov.bh/FullEn/K3612.docx", None),
    "bh_lmra_lloc.docx": ("https://www.lloc.gov.bh/FullEn/K1906.docx", None),
    # Singapore Statutes Online lazy-loads whole Acts; a single provision is served complete.
    "sg_efma_s22a.html": ("https://sso.agc.gov.sg/Act/EFMA1990?ProvIds=pr22A-", None),
    "sg_ea_s32.html": ("https://sso.agc.gov.sg/Act/EmA1968?ProvIds=pr32-", None),
    "sg_pa_s47.html": ("https://sso.agc.gov.sg/Act/PA2007?ProvIds=pr47-", None),
    # --- voluntary recruitment standards ---
    "std_ilo_fair.pdf": (
        "https://respect.international/wp-content/uploads/2019/07/General-Principles-and-Operational-Guidelines-for-Fair-Recruitment-and-Definition-of-Recruitment-Fees-and-Related-Costs.pdf",
        None,
    ),
    "std_epp_lgrr.pdf": (
        "https://ihrb-org.files.svdcdn.com/production/assets/uploads/member-uploads/Six_Steps_to_Responsible_Recruitment_-_Leadership_Group_for_Responsible_Recruitment.pdf?dm=1726489439",
        None,
    ),
    "std_rba_8.pdf": ("https://www.responsiblebusiness.org/media/docs/RBACodeofConduct8.0_English.pdf", None),
    # --- ILO supervisory comments (CEACR) on Bangladesh; NORMLEX blocks bots, the ILO's own compilation does not ---
    "ilo_ceacr_bd_2024.pdf": (
        "https://tradefordecentwork.ilo.org/wp-content/uploads/2024/09/Compilation-of-selected-observations-and-direct-requests-of-the-Committee-of-Experts-on-the-Application-of-Conventions-and-Recommendations-Bangladesh.pdf",
        None,
    ),
}


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, (url, accept) in SOURCES.items():
        dest = RAW / name
        if dest.exists() and dest.stat().st_size > 1000:
            print(f"cached  {name}")
            continue
        headers = {"User-Agent": UA}
        if accept:
            headers.update({"Accept": accept, "Accept-Language": "eng"})
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=180) as r:
            dest.write_bytes(r.read())
        print(f"fetched {name} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
