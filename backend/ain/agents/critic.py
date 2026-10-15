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
        nv.note = f"Critic re-anchored {v.claim.citation_id} (repealed) to {succ.citation_id} and re-verified."
        v.note = f"Dropped: cites a repealed Act. Replaced by {succ.citation_id}."
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
