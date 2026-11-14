"""Guardrails on the dalal's lines and on the coaches' figures, all in code.

The dalal is a role-play of a pressure tactic, never a source of law, insults or real names. A line that breaks a rule
is replaced by its tactic's curated example line, and the reason is recorded (`guardrail` trace event).
"""

from __future__ import annotations

import re

from ain.agents.pii import BN_DIGITS, find_pii
from ain.companies import load_companies
from ain.retrieval import nfc

MAX_LINE = 260

LEGAL = re.compile(
    nfc(
        r"আইন|ধারা|বিধি|বিধান|বৈধ|অবৈধ|বেআইনি|আদালত|মামলা|অপরাধ|দণ্ড|সরকারি?\s*(?:নির্ধারিত|রেট|নিয়ম|হিসাব)"
        r"|\blaws?\b|\blegal\b|\billegal\b|\blawful\b|\bsection\b|\bact\b|\bcourt\b|\bcrime\b|\boffen[cs]e\b"
        r"|\b[A-Z]{2,4}-[A-Z0-9]+-\d{4}"
    ),
    re.I,
)
INSULT = re.compile(
    nfc(r"বোকা|গাধা|মূর্খ|ছাগল|বেকুব|হারামি|শালা|কুত্তা|বেয়াদব|গেঁয়ো|অশিক্ষিত|ফকির|\bidiot\b|\bstupid\b|\bfool\b|\bbastard\b|\bdumb\b"),
    re.I,
)
AGENCY = re.compile(
    nfc(r"ওভারসিজ|ট্রাভেলস|ট্রাভেল্স|এন্টারপ্রাইজ|ইন্টারন্যাশনাল|লিমিটেড|এজেন্সি লি|\boverseas\b|\btravels?\b|\binternational\b|\bltd\b|\blimited\b|\benterprises?\b|\bmanpower\b"),
    re.I,
)
HONORIFIC_NAME = re.compile(nfc(r"(?:মোঃ|মো\.|মোহাম্মদ|মুহাম্মদ|জনাব|মিস্টার|মিসেস|বেগম|শ্রী)\s*[^\s,।]+"))
LATIN_NAME = re.compile(r"\b[A-Z][a-z]{2,}\b")  # the dalal writes Bangla; a capitalised Latin word is likely a name
LATIN_OK = {"Visa", "Ok", "Okay", "Overtime", "Bmet", "Dubai", "Saudi", "Malaysia", "Qatar", "Oman", "Kuwait", "Singapore"}
NUMBER_WORDS = re.compile(nfc(r"(?:এক|দুই|দু|তিন|চার|পাঁচ|ছয়|সাত|আট|নয়|দশ|বিশ|ত্রিশ|চল্লিশ|পঞ্চাশ|শত|শো)\s*(?:লাখ|লক্ষ|হাজার|কোটি)"))


def numbers(text: str) -> set[str]:
    """Digit runs, Bangla digits made ASCII, with thousands separators dropped ('৪,৫০,০০০' -> '450000')."""
    t = nfc(text).translate(BN_DIGITS)
    return {re.sub(r"[,\s]", "", m) for m in re.findall(r"\d[\d,]*", t) if re.sub(r"[,\s]", "", m)}


def _company_names() -> list[str]:
    return [n for c in load_companies() for n in (c.name, *c.aliases) if len(n) >= 3]


def check_dalal(line: str, tactic_id: str | None, scheduled: str, allowed_numbers: set[str]) -> str:
    """'' if the line may be shown, otherwise the reason it is replaced."""
    text = nfc(" ".join((line or "").split()))
    if not text:
        return "empty line"
    if len(text) > MAX_LINE:
        return "line too long"
    if tactic_id != scheduled:
        return f"used tactic {tactic_id!r} instead of the scheduled {scheduled!r}"
    if LEGAL.search(text):
        return "stated something about the law"
    if INSULT.search(text):
        return "insulted the worker"
    if find_pii(text) or HONORIFIC_NAME.search(text) or AGENCY.search(text):
        return "named a person or an agency"
    if any(re.search(rf"(?<!\w){re.escape(n)}(?!\w)", text, re.I) for n in _company_names()):
        return "named a real company"
    if any(w not in LATIN_OK for w in LATIN_NAME.findall(text)):
        return "named a person or an agency"
    if NUMBER_WORDS.search(text) or numbers(text) - allowed_numbers:
        return "gave a figure the worker never mentioned"
    return ""


def unsourced_numbers(text: str, *sources: str) -> set[str]:
    """Figures in a coach's hint that appear in none of the sources (the cited section's text, the worker's own words)."""
    seen: set[str] = set()
    for s in sources:
        seen |= numbers(s)
    return numbers(text) - seen
