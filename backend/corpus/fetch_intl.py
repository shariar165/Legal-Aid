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
