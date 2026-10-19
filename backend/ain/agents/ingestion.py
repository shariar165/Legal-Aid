"""Ingestion agent: raw bytes -> text -> clauses -> deterministic facts.

* Digital PDF  -> PyMuPDF text layer (pages without text fall back to OCR)
* DOCX         -> python-docx paragraphs
* Image / scan -> EasyOCR (Bangla + English) on CPU, cached by file hash in demo/ocr_cache/
* Text         -> as is

OCR runs locally, so the photo itself never leaves the machine. Facts extracted here are
regex-based (deterministic and testable); the Router agent refines them with an LLM
after the PII Shield has redacted the text.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import dataclass, field

from ain import config, countries
from ain.models import Clause, Deduction, DocFacts, Document

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".heic"}
BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_reader = None


@dataclass
class OcrLine:
    text: str
    conf: float


@dataclass
class Extracted:
    text: str
    kind: str
    pages: int = 1
    ocr_lines: list[OcrLine] = field(default_factory=list)

    @property
    def ocr_confidence(self) -> float | None:
        if not self.ocr_lines:
            return None
        return round(sum(line.conf for line in self.ocr_lines) / len(self.ocr_lines), 3)


# ------------------------------------------------------------------ text extraction


def _ocr_reader():
    global _reader
    if _reader is None:
        import easyocr

        _reader = easyocr.Reader(["bn", "en"], gpu=False, verbose=False)
    return _reader


def ocr_image(data: bytes) -> list[OcrLine]:
    """OCR an image with EasyOCR; results are cached by content hash (CPU OCR is slow)."""
    digest = hashlib.sha256(data).hexdigest()[:24]
    cache = config.OCR_CACHE_DIR / f"{digest}.json"
    if cache.exists():
        return [OcrLine(**x) for x in json.loads(cache.read_text(encoding="utf-8"))]
    import numpy as np
    from PIL import Image

    img = Image.open(io.BytesIO(data)).convert("RGB")
    if max(img.size) > 2200:
        img.thumbnail((2200, 2200))
    result = _ocr_reader().readtext(np.array(img), paragraph=False, detail=1)
    # group boxes into lines by vertical position
    boxes = sorted(((min(p[1] for p in b), min(p[0] for p in b), max(p[1] for p in b), t, c) for b, t, c in result))
    lines: list[list] = []
    for top, left, bottom, text, conf in boxes:
        if lines and top < lines[-1][0][2] - (lines[-1][0][2] - lines[-1][0][0]) * 0.5:
            lines[-1].append((top, left, bottom, text, conf))
        else:
            lines.append([(top, left, bottom, text, conf)])
    out = []
    for line in lines:
        line.sort(key=lambda x: x[1])
        out.append(OcrLine(text=" ".join(x[3] for x in line), conf=round(float(min(x[4] for x in line)), 3)))
    config.OCR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps([o.__dict__ for o in out], ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def extract(data: bytes, filename: str) -> Extracted:
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext in IMAGE_EXT:
        lines = ocr_image(data)
        return Extracted(text="\n".join(line.text for line in lines), kind="image", ocr_lines=lines)
    if ext == ".pdf":
        import pymupdf

        parts: list[str] = []
        ocr_lines: list[OcrLine] = []
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            for page in doc:
                t = page.get_text().strip()
                if len(t) > 40:
                    parts.append(t)
                else:  # scanned page
                    lines = ocr_image(page.get_pixmap(dpi=200).tobytes("png"))
                    ocr_lines += lines
                    parts.append("\n".join(line.text for line in lines))
            pages = doc.page_count
        return Extracted(text="\n\n".join(parts), kind="pdf", pages=pages, ocr_lines=ocr_lines)
    if ext == ".docx":
        import docx

        d = docx.Document(io.BytesIO(data))
        return Extracted(text="\n".join(p.text for p in d.paragraphs), kind="docx")
    return Extracted(text=data.decode("utf-8", errors="replace"), kind="text")


# ------------------------------------------------------------------ clauses

CLAUSE_START = re.compile(
    r"^\s*(?:PART\s+[A-Z]\b|Clause\s+\d+|Article\s+\d+|\d{1,2}\s*[\.\)]\s+\S|[০-৯]{1,2}\s*[\.।]\s+\S)", re.I
)


def segment(text: str) -> list[Clause]:
    clauses: list[Clause] = []
    buf: list[str] = []
    buf_start = 0
    pos = 0

    def flush(end: int) -> None:
        body = "\n".join(buf).strip()
        if body:
            clauses.append(Clause(id=f"C{len(clauses) + 1}", index=len(clauses), text=body, start=buf_start, end=end))

    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if CLAUSE_START.match(line) and buf:
            flush(pos)
            buf, buf_start = [], pos
        if not buf:
            buf_start = pos
        if stripped or buf:
            buf.append(line.rstrip("\n"))
        pos += len(line)
    flush(pos)
    return clauses


# ------------------------------------------------------------------ facts

# Destination countries and their currencies come from the registry (ain/countries.yaml).
CURRENCY = {"bdt": "BDT", "tk": "BDT", "taka": "BDT", "টাকা": "BDT", "usd": "USD", "$": "USD", **countries.currency_codes()}
_CUR = "|".join(re.escape(k) for k in sorted(CURRENCY, key=len, reverse=True))
_AMOUNT = r"[\d,]+(?:\.\d+)?"
# "RM 1,200" or "1,200 riyals"; the lookarounds keep "rm" in "form 3" or "kd" in "kd5" from counting
MONEY = re.compile(rf"(?<![A-Za-z])({_CUR})\.?\s?({_AMOUNT})|({_AMOUNT})\s?({_CUR})(?![A-Za-z])", re.I)
WORDNUM = re.compile(r"\((\d{1,3})\)")


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _cur(s: str) -> str:
    return CURRENCY.get(s.lower().rstrip("."), s.upper())


def _money(m: re.Match[str]) -> tuple[float, str]:
    """(amount, currency code) from a MONEY match, whichever order the contract wrote them in."""
    return (_num(m.group(2)), _cur(m.group(1))) if m.group(1) else (_num(m.group(3)), _cur(m.group(4)))


def _salary(clauses: list[Clause]) -> tuple[float | None, str | None, str | None]:
    for c in clauses:
        low = c.text.lower()
        if re.search(r"salary|wage|বেতন|মজুরি", low) and not re.search(r"deduct", low):
            m = MONEY.search(c.text)
            if m:
                amount, cur = _money(m)
                return amount, cur, m.group(0)
    return None, None, None


def _deductions(clauses: list[Clause]) -> list[Deduction]:
    out: list[Deduction] = []
    for c in clauses:
        if not re.search(r"deduct|কর্তন|কাটা", c.text, re.I):
            continue
        items = re.split(r"\n\s*\([a-z]\)\s*|;\s*\([a-z]\)\s*", c.text)
        for item in items[1:] if len(items) > 1 else items:
            per_month = re.search(rf"(?:{MONEY.pattern})\s*(?:per|a|each)\s*month", item, re.I)
            if not per_month:
                continue
            months = re.search(r"for\s+(\d{1,3})\s+months", item, re.I)
            item = item.strip()
            label = re.sub(r"(?:\s+(?:of|at)|,)\s*$", "", item[: MONEY.search(item).start()].strip()).strip(" ;.,") or item
            out.append(Deduction(label=label[:90], amount=_money(per_month)[0], per="month", months=int(months.group(1)) if months else None))
    return out


def _days_before(text: str, pattern: str) -> int | None:
    m = re.search(pattern, text, re.I)
    return int(m.group(1)) if m else None


def extract_facts(text: str, clauses: list[Clause]) -> DocFacts:
    low = text.lower()
    f = DocFacts()
    f.languages = (["bn"] if re.search(r"[ঀ-৿]", text) else []) + (["en"] if re.search(r"[a-zA-Z]{4,}", text) else [])
    has_employment = bool(re.search(r"employment contract|appointment|employed as|appointed as|কর্মসংস্থান চুক্তি|নিয়োগপত্র", low))
    has_supply = bool(re.search(r"supply agreement|purchase order|buyer", low))
    f.doc_type = "mixed" if has_employment and has_supply else "employment" if has_employment else "commercial" if has_supply else "unknown"

    country = countries.detect(text)
    f.destination_country = country.name["en"] if country else None

    for m in re.finditer(r"\b(?:EPZ|DEPZ|CEPZ|AEPZ|export processing zone)\b|ইপিজেড", text, re.I):
        before = low[max(0, m.start() - 25) : m.start()]
        if not re.search(r"outside|not (?:in|within)|no ", before):
            f.is_epz = True
            near = text[max(0, m.start() - 40) : m.end() + 10]
            z = re.search(r"(Dhaka|Chattogram|Chittagong|Adamjee|Karnaphuli|Cumilla|Comilla|Mongla|Ishwardi|Uttara)\s+(?:EPZ|Export Processing Zone)", near, re.I)
            if z:
                f.epz_name = f"{z.group(1).title()} EPZ"
            elif re.search(r"\bDEPZ\b", text):
                f.epz_name = "Dhaka EPZ"
            break

    wp = re.search(r"(?:factory|located|situated|at)\s+(?:in|at)?\s*([A-Z][\w ]+?,\s*[A-Z][\w ]+?)(?:,|\.| for)", text)
    f.workplace = wp.group(1) if wp else None
    f.is_export_contract = bool(re.search(r"\bexport|bill of lading|shipment", low))
    f.mentions_eu_buyer = bool(re.search(r"gmbh|european union|\beu\b|csddd|due diligence directive|germany|netherlands", low))
    f.mentions_personal_data = bool(re.search(r"personal data|health records|ব্যক্তিগত তথ্য|ব্যক্তিগত উপাত্ত", low))
    gl = re.search(r"governed by the laws? of ([A-Z][A-Za-z ]+?)(?:\s+and\b|[\.,;])", text)
    f.governing_law = gl.group(1).strip() if gl else None

    f.salary_amount, f.salary_currency, f.salary_text = _salary(clauses)
    f.deductions = _deductions(clauses)

    f.payment_terms_days = _days_before(text, r"\(?(\d{2,3})\)?\s*days?\s+(?:after|from|of)\s+(?:the\s+)?(?:date\s+of\s+)?(?:shipment|bill of lading|invoice)")
    f.notice_days = _days_before(text, r"\(?(\d{1,3})\)?\s*days['’]?\s*(?:prior\s+)?(?:written\s+)?notice")
    weeks = re.search(r"\(?(\d{1,2})\)?\s*weeks?\s+(?:of\s+)?(?:paid\s+)?maternity", text, re.I)
    if weeks:
        f.maternity_days = int(weeks.group(1)) * 7
    else:
        ba = re.findall(r"\(?(\d{2,3})\)?\s*days\s+(?:before|after)\s+(?:and\s+)?(?:\(?\w+\)?\s*)?", text, re.I)
        if ba and re.search(r"maternity", low):
            f.maternity_days = sum(int(x) for x in ba[:2])
    return f


def build_document(data: bytes, filename: str, source_kind: str | None = None) -> tuple[Document, DocFacts, Extracted]:
    ex = extract(data, filename)
    text = ex.text.translate(str.maketrans({"\r": ""}))
    clauses = segment(text)
    facts = extract_facts(text, clauses)
    if ex.ocr_lines and facts.salary_text:
        amount = re.search(r"[\d,]+(?:\.\d+)?", facts.salary_text).group(0)
        hits = [line.conf for line in ex.ocr_lines if amount.replace(",", "") in line.text.replace(",", "")]
        facts.salary_confidence = float(min(hits)) if hits else 0.5
    doc = Document(
        name=filename,
        source_kind=source_kind or ex.kind,  # type: ignore[arg-type]
        text=text,
        clauses=clauses,
        ocr_used=bool(ex.ocr_lines),
        ocr_confidence=ex.ocr_confidence,
        pages=ex.pages,
    )
    return doc, facts, ex
