"""PII Shield: redacts personal identifiers before any text leaves the machine.

Detection works on a digit-normalised copy of the text (Bangla digits -> ASCII). The
translation is one character to one character, so match offsets apply to the original.
The same value always maps to the same placeholder, so cross-references survive.
`find_pii` is also used by the LLM layer as a last-line guard on every outbound payload.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ain.models import PrivacyReceipt, Redaction

BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
PLACEHOLDER_RE = re.compile(r"\[[A-Z]+_\d+\]")

_LABELS_NAME = (
    r"name|full name|worker'?s? name|employee'?s? name|name of (?:the )?(?:worker|employee)|"
    r"father'?s name|mother'?s name|spouse'?s? name|husband'?s name|nominee|next of kin|"
    r"নাম|কর্মীর নাম|শ্রমিকের নাম|পিতার নাম|মাতার নাম|স্বামীর নাম|নমিনি"
)
_LABELS_ADDR = r"address|permanent address|present address|home address|ঠিকানা|স্থায়ী ঠিকানা|বর্তমান ঠিকানা"
_LABELS_DOB = r"date of birth|d\.?o\.?b\.?|birth date|জন্ম তারিখ"
_LABELS_ACCT = r"bank account(?: no\.?| number)?|account no\.?|account number|a/c no\.?|হিসাব নম্বর|ব্যাংক হিসাব"
_LABELS_PASS = r"passport(?: no\.?| number)?|পাসপোর্ট(?: নং| নম্বর)?"
_LABELS_NID = r"nid(?: no\.?| number)?|national id(?: no\.?| number)?|জাতীয় পরিচয়পত্র(?: নং| নম্বর)?|এনআইডি"

PATTERNS: list[tuple[str, re.Pattern[str], int]] = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), 0),
    ("PHONE", re.compile(r"(?<![\d])(?:\+?880[\s-]?1\d{3}[\s-]?\d{6}|01[3-9]\d{2}[\s-]?\d{6}|\+?60[\s-]?1\d[\s-]?\d{3,4}[\s-]?\d{4})(?![\d])"), 0),
    ("PASSPORT", re.compile(rf"(?i)(?:{_LABELS_PASS})\s*[:：#\-]?\s*([A-Z]{{1,2}}\s?\d{{7,8}})"), 1),
    ("PASSPORT", re.compile(r"(?<![A-Za-z0-9])[A-Z]{1,2}\d{7,8}(?![A-Za-z0-9])"), 0),
    ("NID", re.compile(rf"(?i)(?:{_LABELS_NID})\s*[:：#\-]?\s*(\d[\d\s]{{8,20}}\d)"), 1),
    ("NID", re.compile(r"(?<![\d,.])(?:\d{17}|\d{13}|\d{10})(?![\d,.])"), 0),
    ("ACCOUNT", re.compile(rf"(?i)(?:{_LABELS_ACCT})\s*[:：#\-]?\s*([\d][\d\s-]{{6,24}}\d)"), 1),
    ("DOB", re.compile(rf"(?i)(?:{_LABELS_DOB})\s*[:：\-]\s*([^\n,;]{{4,30}})"), 1),
    ("ADDRESS", re.compile(rf"(?im)(?:{_LABELS_ADDR})\s*[:：\-]\s*([^\n]{{4,120}})"), 1),
    ("NAME", re.compile(rf"(?im)(?:^|\b)(?:{_LABELS_NAME})\s*[:：\-]\s*([^\n,;()]{{2,60}})"), 1),
    ("NAME", re.compile(r"\b(?:Mr|Mrs|Ms|Md|Mst|Mohammad|Mohammed)\.?[ \t]+[A-Z][a-z]+(?:[ \t][A-Z][a-z]+){0,3}"), 0),
]


@dataclass
class RedactionResult:
    text: str
    mapping: dict[str, str] = field(default_factory=dict)  # placeholder -> original (never leaves the machine)
    redactions: list[Redaction] = field(default_factory=list)

    def receipt(self) -> PrivacyReceipt:
        counts: dict[str, int] = {}
        for r in self.redactions:
            counts[r.kind] = counts.get(r.kind, 0) + 1
        return PrivacyReceipt(redactions=self.redactions, counts=counts, redacted_text=self.text)


def _spans(text: str) -> list[tuple[int, int, str]]:
    norm = text.translate(BN_DIGITS)
    spans: list[tuple[int, int, str]] = []
    for kind, pat, grp in PATTERNS:
        for m in pat.finditer(norm):
            s, e = m.span(grp)
            value = norm[s:e].rstrip()
            e = s + len(value)
            if e - s < 2 or PLACEHOLDER_RE.fullmatch(value.strip()):
                continue
            spans.append((s, e, kind))
    # keep earliest, longest, non-overlapping spans
    spans.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    out: list[tuple[int, int, str]] = []
    last_end = -1
    for s, e, k in spans:
        if s >= last_end:
            out.append((s, e, k))
            last_end = e
    return out


def redact(text: str, mapping: dict[str, str] | None = None) -> RedactionResult:
    """Replace PII with stable placeholders like [PASSPORT_1]."""
    mapping = dict(mapping or {})
    reverse = {v: k for k, v in mapping.items()}
    counters: dict[str, int] = {}
    for ph in mapping:
        kind, n = ph.strip("[]").rsplit("_", 1)
        counters[kind] = max(counters.get(kind, 0), int(n))
    result: list[str] = []
    redactions: list[Redaction] = []
    pos = 0
    for s, e, kind in _spans(text):
        original = text[s:e].strip()
        if original in reverse:
            ph = reverse[original]
        else:
            counters[kind] = counters.get(kind, 0) + 1
            ph = f"[{kind}_{counters[kind]}]"
            mapping[ph] = original
            reverse[original] = ph
        result.append(text[pos:s])
        result.append(ph)
        redactions.append(Redaction(placeholder=ph, kind=kind))
        pos = e
    result.append(text[pos:])
    return RedactionResult(text="".join(result), mapping=mapping, redactions=redactions)


def find_pii(text: str) -> list[tuple[str, str]]:
    """Return (kind, value) for every identifier still present. Empty list means clean."""
    return [(k, text[s:e]) for s, e, k in _spans(text)]


def rehydrate(text: str, mapping: dict[str, str]) -> str:
    """Restore placeholders locally (only for documents rendered on the user's own device)."""
    return PLACEHOLDER_RE.sub(lambda m: mapping.get(m.group(0), m.group(0)), text)
