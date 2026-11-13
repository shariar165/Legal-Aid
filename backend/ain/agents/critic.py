"""Critic: enforces "no verified citation, no advice" and repairs what can be repaired.

* A claim dropped only because its Act was repealed is re-anchored to the same section of the
  successor Act (if the corpus has one) and re-verified from scratch - the ledger keeps both rows.
* A risk keeps its place in the memo only if at least one of its claims is verified or partial.
"""

from __future__ import annotations

from ain.agents.verifier import verify_claim
from ain.llm import LLM
from ain.models import Claim, Risk, RouteDecision, Verification
from ain.retrieval import Corpus


async def heal(llm: LLM, corpus: Corpus, route: RouteDecision, risks: list[Risk], ledger: list[Verification], on_result=None) -> list[Verification]:
    by_risk = {r.id: r for r in risks}
    added: list[Verification] = []
    for v in list(ledger):
        sec = v.section
        if v.verdict != "dropped" or sec is None or sec.status != "repealed" or not sec.superseded_by:
            continue
        succ = corpus.get(f"{sec.superseded_by}-s{sec.section}")
        if succ is None:
            hits = [s for s, _ in corpus.search(f"{sec.heading} {v.claim.proposition}", k=10) if s.act_key == sec.superseded_by]
            succ = hits[0] if hits else None
        if succ is None:
            v.note = f"Repealed and no successor provision found in {sec.superseded_by}."
            continue
        risk = by_risk.get(v.claim.risk_id)
        new = Claim(
            id=f"{v.claim.id}r",
            risk_id=v.claim.risk_id,
            proposition=v.claim.proposition,
            citation_id=succ.citation_id,
            quote=None,
            origin="critic",
        )
        nv = await verify_claim(llm, corpus, route, new, risk, use_bench=False)
        nv.note = f"Critic re-anchored this claim from the repealed {sec.act_en} s.{sec.section} to the Act in force, and re-verified it."
        v.note = f"Dropped: cites a repealed Act. The Critic replaced it with {succ.act_en} s.{succ.section}."
        added.append(nv)
        if risk:
            risk.claim_ids.append(new.id)
        if on_result:
            on_result(nv)
    ledger.extend(added)

    for r in risks:
        verdicts = [v.verdict for v in ledger if v.claim.risk_id == r.id]
        if "verified" in verdicts:
            r.status = "confirmed"
        elif "partial" in verdicts:
            r.status = "partial"
        else:
            r.status = "dropped"
    return added


def restated_after_verification(risks: list[Risk], ledger: list[Verification]) -> list[tuple[Risk, str]]:
    """Adversary risks that, once verified, stand only on law that a playbook or calculator risk on an overlapping clause
    already cites: a restatement the filter before grounding could not see. Live, a "no medical insurance" risk whose own
    claim was refuted survived on the return-ticket article, so it was the return-ticket risk again under a new title.
    Returns each with the id of the risk it restates; the caller withdraws it."""
    standing: dict[str, set[str]] = {}  # risk id -> citations it has a verified or partial claim on
    for v in ledger:
        if v.verdict in ("verified", "partial"):
            standing.setdefault(v.claim.risk_id, set()).add(v.claim.citation_id)
    others = [r for r in risks if r.origin != "adversary" and r.status != "dropped"]
    out = []
    for r in risks:
        mine = standing.get(r.id, set())
        if r.origin != "adversary" or r.status == "dropped" or not mine or not r.clause_ids:
            continue
        near = [k for k in others if set(k.clause_ids) & set(r.clause_ids)]
        if near and mine <= set().union(*(standing.get(k.id, set()) for k in near)):
            dup = next(k for k in near if standing.get(k.id, set()) & mine)
            out.append((r, dup.rule_id or dup.id))
    return out
