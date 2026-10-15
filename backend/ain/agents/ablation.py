"""Ablation: what a single plain prompt produces, checked by the same gates.

The plain model gets the (redacted) contract and one instruction - list the risks and cite the
statutes. No retrieval, no playbook, no verification. Its citations are then resolved against the
corpus and passed through existence, currency and entailment. The split screen in the UI shows
how many of its citations survive versus Ain Copilot's.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from ain.agents.verifier import gate_currency, gate_entailment
from ain.llm import LLM
from ain.models import AblationResult, AnalysisResult, Claim
from ain.naming import SHORT_EN
from ain.retrieval import Corpus

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


def resolve(corpus: Corpus, act: str, section: str) -> str | None:
    """Map a free-text citation to a corpus citation_id, or None when it cannot be found."""
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
    if not best or best_score < 75:
        return None
    m = re.match(r"\s*(?:s\.|section|art\.?|article|para\.?)?\s*([0-9]+[A-Z]?)", section, re.I)
    if not m:
        return None
    cid = f"{best}-s{m.group(1).upper()}"
    if cid in corpus:
        return cid
    alt = f"{best}-a{m.group(1)}"
    return alt if alt in corpus else None


async def run(llm: LLM, corpus: Corpus, result: AnalysisResult) -> AblationResult:
    migrant = "bd_migration" in result.route.pack_ids
    data = await llm.json(
        role="plain",
        system=PLAIN_SYSTEM,
        user=result.document.text[:14000],  # already redacted
        task="ablation_plain",
        agent="Ablation · plain LLM",
        fake=lambda: {"risks": FAKE_PLAIN["migrant" if migrant else "commercial"]},
        temperature=0.2,
    )
    rows: list[dict] = []
    for item in data.get("risks", []):
        for c in item.get("citations", []):
            act, section, claim_text = str(c.get("act", "")), str(c.get("section", "")), str(c.get("claim", ""))
            cid = resolve(corpus, act, section)
            row = {"risk": item.get("risk", ""), "cited": f"{act} s.{section}", "claim": claim_text, "citation_id": cid}
            if cid is None:
                row.update(outcome="unresolvable", detail="No such section in the verified corpus - cannot be checked (possible hallucination or out-of-scope law).")
            else:
                sec = corpus.get(cid)
                cur = gate_currency(sec)
                if cur.status == "fail":
                    row.update(outcome="repealed", detail=cur.detail)
                elif not set(sec.packs) & result.route.pack_ids:
                    row.update(outcome="inapplicable", detail="Exists, but this law does not govern the document (wrong regime).")
                else:
                    g3 = await gate_entailment(llm, Claim(id="ab", risk_id="ab", proposition=claim_text, citation_id=cid, origin="ablation"), sec)
                    row.update(outcome="supported" if g3.status == "pass" else "unsupported", detail=g3.detail)
            rows.append(row)
    ain_rows = [v for v in result.ledger if v.claim.risk_id != "P"]
    return AblationResult(
        plain_model=llm.resolve("plain")[1] if llm.mode != "fake" else "fake (offline demo)",
        plain_answer="\n".join(f"- {i.get('risk')}" for i in data.get("risks", [])),
        citations_found=len(rows),
        resolvable=sum(r["citation_id"] is not None for r in rows),
        supported=sum(r["outcome"] == "supported" for r in rows),
        rows=rows,
        ain_citations=len(ain_rows),
        ain_verified=sum(v.verdict in ("verified", "partial") for v in ain_rows),
    )
