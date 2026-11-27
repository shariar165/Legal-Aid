"""Ablation: what a single plain prompt produces, checked by the same gates.

The plain model gets the (redacted) contract and one instruction - list the risks and cite the
statutes. No retrieval, no playbook, no verification. Its citations are then resolved against the
corpus and passed through existence, currency and entailment. The split screen in the UI shows
how many of its citations survive versus Jukti's.

Outcomes (spec 29 step 2.2). A citation is only called wrong when Jukti can check it:
  supported       the act and section are in the corpus, apply here, are in force, and the judge agrees
  wrong           repealed, the wrong regime for this document, or the section does not say what is claimed
  fabricated      the act is held in full (a complete bdlaws text) and has no such section
  outside_corpus  everything else: real or not, the law is not in the corpus (or only an excerpt is), so it
                  cannot be checked here and is never counted against the model
"""

from __future__ import annotations

import json
import logging
import re
from functools import cache

from rapidfuzz import fuzz

from corpus.scrape_bdlaws import ACTS_FILE, norm_section_no

from ain.agents.verifier import gate_currency, gate_entailment
from ain.llm import LLM, MalformedAnswer, dict_items
from ain.models import AblationResult, AnalysisResult, Claim
from ain.naming import SHORT_EN
from ain.retrieval import Corpus

log = logging.getLogger(__name__)

PLAIN_SYSTEM = """You are a lawyer. Read the contract and list its main legal risks for the weaker party.
For every risk cite the specific statute and section number that applies.
Return JSON: {"risks": [{"risk": "...", "citations": [{"act": "full name of the Act/Convention", "section": "number", "claim": "what that section says"}]}]}"""

# canned stand-in for offline mode: the kinds of citations single-prompt models typically produce
FAKE_PLAIN = {
    "migrant": [
        {"risk": "Passport retention", "citations": [
            {"act": "Overseas Employment and Migrants Act 2013", "section": "31", "claim": "Withholding a migrant worker's passport without lawful reason is an offence."},
            {"act": "Passports Act 1966 (Malaysia)", "section": "12(1)(f)", "claim": "It is an offence for an employer to keep a worker's passport."}]},
        {"risk": "Recruitment fee deductions", "citations": [
            {"act": "Employment Act 1955 (Malaysia)", "section": "24A", "claim": "Recruitment fees may never be deducted from wages."}]},
        {"risk": "Forced labour", "citations": [
            {"act": "Prevention and Suppression of Human Trafficking Act 2012", "section": "9", "claim": "Forced labour is punishable with 5 to 12 years' imprisonment."}]},
        {"risk": "Low wage", "citations": [
            {"act": "Minimum Wages Order 2022 (Malaysia)", "section": "4", "claim": "The minimum wage is RM1,500 per month."}]},
    ],
    "commercial": [
        {"risk": "Non-compete", "citations": [
            {"act": "Contract Act 1872", "section": "27", "claim": "Agreements in restraint of trade are void."}]},
        {"risk": "Maternity leave", "citations": [
            {"act": "Bangladesh Labour Act 2006", "section": "46", "claim": "Women workers are entitled to 16 weeks of paid maternity leave."}]},
        {"risk": "Termination notice", "citations": [
            {"act": "Bangladesh Labour Act 2006", "section": "26", "claim": "Permanent workers must receive 120 days' notice."}]},
        {"risk": "Payment terms", "citations": [
            {"act": "Foreign Exchange Regulation Act 1947", "section": "12", "claim": "Export proceeds must be repatriated within 120 days."},
            {"act": "Bangladesh Export Policy 2021-2024", "section": "5.2", "claim": "Export payments must arrive within 120 days."}]},
        {"risk": "Trade unions", "citations": [
            {"act": "Bangladesh Labour Act 2006", "section": "176", "claim": "Workers have the right to form trade unions of their choice."}]},
    ],
}


def _act_candidates(corpus: Corpus) -> dict[str, list[str]]:
    names: dict[str, list[str]] = {}
    for s in corpus.sections:
        if s.act_key not in names:
            names[s.act_key] = [s.act_en.lower(), s.act.lower(), SHORT_EN.get(s.act_key, "").lower()]
    return names


@cache
def full_acts() -> frozenset[str]:
    """Acts the corpus holds in full: bdlaws scrapes without a section list. Every other act is an excerpt."""
    return frozenset(a["key"] for a in json.loads(ACTS_FILE.read_text(encoding="utf-8")) if not a.get("sections"))


def resolve_act(corpus: Corpus, act: str) -> str | None:
    """Map a free-text act name to a corpus act_key, or None when the corpus does not hold that act."""
    act_l = act.lower()
    year = re.search(r"(1[89]\d\d|20\d\d)", act_l)
    best, best_score = None, 0.0
    for key, names in _act_candidates(corpus).items():
        if year and year.group(1) not in key:
            continue
        if ("malaysia" in act_l) != key.startswith("MY-") and not key.startswith(("ILO-", "EU-")):
            continue
        score = max(fuzz.token_set_ratio(act_l, n) for n in names if n)
        if score > best_score:
            best, best_score = key, score
    return best if best and best_score >= 75 else None


# "s.28A", "28(A)", "২৮ক", "Art. 7", "section 12(1)(f)": the number and a section letter. A lowercase letter in
# brackets is a clause, as in 12(1)(f) or 28(a), and is not part of the section number.
SECTION_RE = re.compile(r"\s*(?:s\.|sec\.|section|art\.?|article|para\.?|ধারা)?\s*([0-9০-৯]+)(?:([A-Za-zকখগঘঙচ])(?![A-Za-z])|\(([A-Zকখগঘঙচ])\))?", re.I)


def section_no(section: str) -> str | None:
    m = SECTION_RE.match(section)
    if not m:
        return None
    letter = m.group(2) or (m.group(3) if m.group(3) and not m.group(3).islower() else "")
    return norm_section_no(m.group(1) + (letter or ""))


def lookup(corpus: Corpus, act: str, section: str) -> tuple[str | None, str | None]:
    """(act_key, citation_id): the act Jukti holds, if any, and the section in it, if it exists."""
    key = resolve_act(corpus, act)
    no = section_no(section) if key else None
    if not key or not no:
        return key, None
    for cid in (f"{key}-s{no}", f"{key}-a{no}"):
        if cid in corpus:
            return key, cid
    return key, None


def resolve(corpus: Corpus, act: str, section: str) -> str | None:
    """Map a free-text citation to a corpus citation_id, or None when it cannot be found."""
    return lookup(corpus, act, section)[1]


OUTSIDE = "This law is not in Jukti's corpus (or only an excerpt of it is), so it cannot be checked here. It may well be real."


async def run(llm: LLM, corpus: Corpus, result: AnalysisResult) -> AblationResult:
    migrant = "bd_migration" in result.route.pack_ids
    try:
        data = await llm.json(
            role="plain",
            system=PLAIN_SYSTEM,
            user=result.document.text[:14000],  # already redacted
            task="ablation_plain",
            agent="Ablation · plain LLM",
            fake=lambda: {"risks": FAKE_PLAIN["migrant" if migrant else "commercial"]},
            temperature=0.2,
        )
    except MalformedAnswer as e:
        log.warning("Ablation: no usable plain answer: %s", e)
        data = {}
    items = dict_items(data.get("risks"), "ablation risks")
    rows: list[dict] = []
    for item in items:
        for c in dict_items(item.get("citations"), "ablation citations"):
            act, section, claim_text = str(c.get("act", "")), str(c.get("section", "")), str(c.get("claim", ""))
            key, cid = lookup(corpus, act, section)
            row = {"risk": item.get("risk", ""), "cited": f"{act} s.{section}", "claim": claim_text, "citation_id": cid}
            if cid is None:
                if key in full_acts():
                    row.update(outcome="fabricated", detail=f"Jukti holds the whole {SHORT_EN.get(key, key)}, and it has no section {section}.")
                else:
                    row.update(outcome="outside_corpus", detail=OUTSIDE)
            else:
                sec = corpus.get(cid)
                cur = gate_currency(sec)
                if cur.status == "fail":
                    row.update(outcome="wrong", why="repealed", detail=cur.detail)
                elif not set(sec.packs) & result.route.pack_ids:
                    row.update(outcome="wrong", why="wrong_regime", detail="Exists, but this law does not govern the document (wrong regime).")
                else:
                    g3 = await gate_entailment(llm, Claim(id="ab", risk_id="ab", proposition=claim_text, citation_id=cid, origin="ablation"), sec)
                    if g3.status == "pass":
                        row.update(outcome="supported", detail=g3.detail)
                    else:
                        row.update(outcome="wrong", why="not_supported", detail=g3.detail)
            rows.append(row)
    ain_rows = [v for v in result.ledger if v.claim.risk_id != "P"]
    return AblationResult(
        plain_model=llm.resolve("plain")[1] if llm.mode != "fake" else "fake (offline demo)",
        plain_answer="\n".join(f"- {i.get('risk')}" for i in items),
        citations_found=len(rows),
        resolvable=sum(r["citation_id"] is not None for r in rows),
        supported=sum(r["outcome"] == "supported" for r in rows),
        wrong=sum(r["outcome"] == "wrong" for r in rows),
        fabricated=sum(r["outcome"] == "fabricated" for r in rows),
        outside_corpus=sum(r["outcome"] == "outside_corpus" for r in rows),
        rows=rows,
        ain_citations=len(ain_rows),
        ain_verified=sum(v.verdict in ("verified", "partial") for v in ain_rows),
    )
