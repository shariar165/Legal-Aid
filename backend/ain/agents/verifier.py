"""Citation Verifier: every legal claim must pass four gates before it can appear in the memo.

  G1 existence    the citation_id resolves to a real section in the corpus, AND that law applies to this document
                  (a section from a regime the router switched off - e.g. Labour Act inside an EPZ - fails)
  G2 fidelity     any quoted statutory text fuzzy-matches the source (rapidfuzz >= threshold); otherwise it is
                  shown as a paraphrase (warn)
  G3 entailment   a judge model from a different family reads ONLY the section text and decides whether it
                  supports the proposition; for high/critical risks the Virtual Bench decides instead (without a
                  quorum of two judges' opinions, the single judge decides and the claim is flagged for human review)
  G4 currency     the section is in force; amended -> warn with the amendment note; repealed -> fail

verified = all pass/skip · partial = some warn · dropped = any fail (kept in the ledger, never shown as advice)
"""

from __future__ import annotations

import asyncio
import re

from rapidfuzz import fuzz

from ain import companies, config
from ain.agents import bench as bench_mod
from ain.llm import LLM, LLMError
from ain.models import BenchResult, Claim, GateResult, Risk, RouteDecision, Section, Verification
from ain.naming import SHORT_EN
from ain.retrieval import Corpus, nfc, tokenize

ENTAIL_SYSTEM = """You verify legal citations. You get the text of ONE statute section and ONE proposition.
Use ONLY the given text - not your own knowledge of the law. If the text clearly supports the proposition answer
"supports"; if it does not address it, "neutral"; if it says otherwise (e.g. different numbers), "contradicts".
Return JSON: {"verdict": "supports|neutral|contradicts", "reasoning": "one sentence"}"""

BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def _ws(t: str) -> str:
    return re.sub(r"\s+", " ", nfc(t)).strip()


def gate_existence(claim: Claim, corpus: Corpus, route: RouteDecision) -> tuple[GateResult, Section | None]:
    sec = corpus.get(claim.citation_id)
    if sec is None:
        return GateResult(gate="existence", status="fail", detail=f"{claim.citation_id} does not exist in the verified corpus."), None
    routed, excluded = route.pack_ids, {p.pack: p.reason for p in route.excluded}
    if not set(sec.packs) & routed:
        hit = next((excluded[p] for p in sec.packs if p in excluded), None)
        if hit:
            return GateResult(gate="existence", status="fail", detail=f"Exists, but does not apply to this document. {hit}"), sec
        return GateResult(gate="existence", status="warn", detail=f"Exists ({sec.act_en} s.{sec.section}) but lies outside the law packs routed for this document."), sec
    return GateResult(gate="existence", status="pass", detail=f"Found {sec.act_en} s.{sec.section} - {sec.heading}"), sec


def gate_fidelity(claim: Claim, sec: Section) -> GateResult:
    if not claim.quote:
        return GateResult(gate="fidelity", status="skip", detail="No direct quotation; the proposition is a paraphrase checked by entailment.")
    score = fuzz.partial_ratio(_ws(claim.quote), _ws(sec.text))
    if score >= config.quote_threshold():
        return GateResult(gate="fidelity", status="pass", detail=f"Quotation matches the official text ({score:.0f}%).")
    return GateResult(gate="fidelity", status="warn", detail=f"Quotation does not match the official text ({score:.0f}%); shown as a paraphrase.")


def gate_currency(sec: Section) -> GateResult:
    if sec.kind == "company_policy" and sec.jurisdiction == "COMPANY" and companies.is_stale(sec.retrieved_at):
        return GateResult(gate="currency", status="warn", detail=f"The company's published policy was fetched on {sec.retrieved_at}, over a year ago; it may have changed. Re-check {sec.source}.")
    if sec.kind == "company_policy":  # the employer's own words; they bind it as a promise, not as law
        return GateResult(gate="currency", status="pass", detail=f"The employer's own policy text, not law ({sec.source}, {sec.retrieved_at}).")
    if sec.kind == "standard":  # not law: "in force" means this is the current version of the standard
        return GateResult(gate="currency", status="pass", detail=f"Current version of a voluntary standard, not law (retrieved {sec.retrieved_at} from {sec.source}).")
    if sec.status == "repealed":
        succ = f" It was superseded by the {SHORT_EN.get(sec.superseded_by, sec.superseded_by)} ({sec.superseded_by})." if sec.superseded_by else ""
        return GateResult(gate="currency", status="fail", detail=f"{sec.act_en} has been repealed.{succ}")
    if sec.status == "amended":
        note = sec.amendment_notes[0] if sec.amendment_notes else "amended"
        return GateResult(gate="currency", status="warn", detail=f"In force but amended: {note}")
    extra = f" Consolidated text includes {len(sec.amendment_notes)} amendment note(s)." if sec.amendment_notes else ""
    return GateResult(gate="currency", status="pass", detail=f"In force (text retrieved {sec.retrieved_at} from {sec.source}).{extra}")


# Offline judge only: lets English propositions be matched against Bangla statute text.
BN_GLOSSARY = {
    "passport": "পাসপোর্ট", "visa": "ভিসা", "maternity": "প্রসূতি", "notice": "নোটিশ", "terminate": "অবসান",
    "termination": "অবসান", "union": "ইউনিয়ন", "welfare": "কল্যাণ", "association": "সমিতি", "wage": "মজুরি", "wages": "মজুরী",
    "deduction": "কর্তন", "deductions": "কর্তন", "consent": "সম্মতি", "forced": "জবরদস্তি", "debt": "ঋণ", "contract": "চুক্তি",
    "compensation": "ক্ষতিপূরণ", "suit": "মামলা", "migrant": "অভিবাসী", "return": "ফেরত", "imprisonment": "কারাদণ্ড",
    "fine": "অর্থদণ্ড", "clearance": "ছাড়পত্র", "withholding": "আটকাইয়া", "offence": "অপরাধ", "permanent": "স্থায়ী",
}


def fake_entailment(claim: Claim, sec: Section) -> str:
    """Offline stand-in for the judge: numbers and wording of the proposition must appear in the section."""
    text = _ws(sec.text).translate(BN_DIGITS).lower()
    if claim.quote and _ws(claim.quote).translate(BN_DIGITS).lower() in text:
        return "supports"
    nums = set(re.findall(r"\d+", claim.proposition)) - {str(sec.year), re.sub(r"\D", "", sec.section) or "-"}
    if nums and len(nums & set(re.findall(r"\d+", text))) / len(nums) >= 0.5:
        return "supports"
    toks = set(tokenize(claim.proposition)) - {"act", "under", "s", "section", "art", "article"}
    if sec.lang == "bn":
        terms = [BN_GLOSSARY[t] for t in toks if t in BN_GLOSSARY]
        hits = sum(1 for t in terms if t in text)
        return "supports" if terms and hits >= max(2, len(terms) // 2) else "neutral"
    overlap = len(toks & set(tokenize(text))) / max(1, len(toks))
    return "supports" if overlap >= 0.35 else "neutral"


async def gate_entailment(llm: LLM, claim: Claim, sec: Section) -> GateResult:
    fv = fake_entailment(claim, sec)
    try:
        data = await llm.json(
            role="judge",
            system=ENTAIL_SYSTEM,
            user=f"STATUTE: {sec.act_en}, s.{sec.section} - {sec.heading}\nTEXT:\n{bench_mod.cited_text(sec, claim)}\n\nPROPOSITION: {claim.proposition}",
            task="entailment",
            agent="Citation Verifier",
            fake=lambda: {"verdict": fv, "reasoning": "Offline check: proposition terms found in the section text." if fv == "supports" else "Offline check: the section text does not address the proposition."},
        )
    except LLMError:  # fail closed: a claim no judge could check is dropped (and kept in the ledger), never shown as advice
        return GateResult(gate="entailment", status="fail", detail="Not checked: no judge model could be reached on any route, so the claim is held back.")
    verdict = data.get("verdict", "neutral")
    reason = str(data.get("reasoning", ""))[:300]
    if verdict == "supports":
        return GateResult(gate="entailment", status="pass", detail=f"Judge: supports. {reason}")
    return GateResult(gate="entailment", status="fail", detail=f"Judge: {verdict}. {reason}")


def _verdict(gates: list[GateResult]) -> str:
    if any(g.status == "fail" for g in gates):
        return "dropped"
    if any(g.status == "warn" for g in gates):
        return "partial"
    return "verified"


async def verify_claim(
    llm: LLM, corpus: Corpus, route: RouteDecision, claim: Claim, risk: Risk | None, use_bench: bool, bench: BenchResult | None = None
) -> Verification:
    """`bench`: a ruling the Virtual Bench already gave on this claim (batched with others); otherwise it convenes here."""
    g1, sec = gate_existence(claim, corpus, route)
    if sec is None or g1.status == "fail":
        skipped = [GateResult(gate=g, status="skip", detail="Not checked: the citation failed the existence/applicability gate.") for g in ("fidelity", "entailment", "currency")]
        return Verification(claim=claim, gates=[g1, *skipped], verdict="dropped", section=sec)
    g2 = gate_fidelity(claim, sec)
    g4 = gate_currency(sec)
    if g4.status == "fail":
        g3 = GateResult(gate="entailment", status="skip", detail="Not checked: the cited law is no longer in force.")
        return Verification(claim=claim, gates=[g1, g2, g3, g4], verdict="dropped", section=sec)
    bench_result = bench
    if bench_result is None and use_bench and risk is not None:
        bench_result = await bench_mod.convene(llm, claim, sec, risk, fake_entailment(claim, sec))
    if bench_result is not None and bench_result.quorum:
        ok = bench_result.majority_verdict == "supports"
        g3 = GateResult(
            gate="entailment",
            status="pass" if ok else "fail",
            detail=_bench_detail(bench_result),
        )
    elif bench_result is not None:  # fewer than two judges answered: the single judge decides, flagged for human review
        single = await gate_entailment(llm, claim, sec)
        g3 = GateResult(gate="entailment", status=single.status, detail=f"{_bench_detail(bench_result)} Single-judge check instead: {single.detail}")
    else:
        g3 = await gate_entailment(llm, claim, sec)
    gates = [g1, g2, g3, g4]
    return Verification(claim=claim, gates=gates, verdict=_verdict(gates), section=sec, bench=bench_result)  # type: ignore[arg-type]


def _bench_detail(b: BenchResult) -> str:
    if not b.quorum:
        head = f"Virtual Bench had no quorum: {' and '.join(b.no_opinion)} gave no opinion."
    elif b.agreement == "split":
        head = f"Virtual Bench split {b.vote}: no majority, so not supported."
    else:
        head = f"Virtual Bench {b.vote}: {b.majority_verdict}."
    sev = f" Severity {b.severity_range}." if b.severity_range else ""
    review = f" Human review: {b.review_reason}." if b.human_review else ""
    fam = f" Same family (fallback): {' and '.join(b.same_family)}." if b.same_family else ""
    return head + sev + review + fam


async def verify_all(llm: LLM, corpus: Corpus, route: RouteDecision, risks: list[Risk], claims: list[Claim], on_result=None) -> list[Verification]:
    by_risk = {r.id: r for r in risks}
    bench_sev = config.bench_severities()
    # the bench sits on ONE claim per high/critical risk: the first one that exists, applies and is in force
    bench_items: dict[str, tuple[Claim, Section, Risk, str]] = {}
    for r in risks:
        if r.severity in bench_sev:
            for cid in r.claim_ids:
                c = next(c for c in claims if c.id == cid)
                g1, sec = gate_existence(c, corpus, route)
                if sec is not None and g1.status != "fail" and sec.status != "repealed":
                    bench_items[cid] = (c, sec, r, fake_entailment(c, sec))
                    break
    # batch_bench: the bench sits once for all its claims, so each judge can answer several in one call
    together = None
    if bench_mod.Options.from_config().batch and len(bench_items) > 1:
        together = asyncio.ensure_future(bench_mod.convene_many(llm, list(bench_items.values())))
    order = list(bench_items)

    async def one(c: Claim) -> Verification:
        ruling = (await together)[order.index(c.id)] if together is not None and c.id in bench_items else None
        v = await verify_claim(llm, corpus, route, c, by_risk.get(c.risk_id), c.id in bench_items, bench=ruling)
        if on_result:
            on_result(v)
        return v

    ledger = list(await asyncio.gather(*(one(c) for c in claims)))
    for v in ledger:
        if v.bench is not None:
            risk = by_risk[v.claim.risk_id]
            risk.bench = v.bench
            if v.bench.quorum:  # without a quorum the risk keeps its own severity
                risk.severity = v.bench.majority_severity
    return ledger
