"""End-to-end runs of the full agent graph on the hero documents (offline, fake LLM)."""

import pytest

from ain.agents.pii import find_pii
from ain.agents.risk_analyst import load_rules
from ain.orchestrator import new_job, run_pipeline
from tests.conftest import RecordingLLM


async def _run(docs, name):
    llm = RecordingLLM()
    result = await run_pipeline(new_job(name), (docs / name).read_bytes(), name, llm=llm)
    return result, llm


@pytest.mark.parametrize("name", ["migrant_my_contract.txt", "rmg_dhaka_epz.txt"])
async def test_hero_document_meets_the_challenge(docs, name):
    r, llm = await _run(docs, name)
    live = [k for k in r.risks if k.status != "dropped"]
    # at least three risks, each backed by a verified (or partial) citation
    assert len(live) >= 3
    by_risk = {}
    for v in r.ledger:
        by_risk.setdefault(v.claim.risk_id, []).append(v.verdict)
    for k in live:
        assert {"verified", "partial"} & set(by_risk[k.id]), k.title.en
    # every citation the memo uses passed verification
    ok = {v.claim.citation_id for v in r.ledger if v.verdict in ("verified", "partial")}
    for issue in r.memo.issues:
        assert issue.citation_ids and set(issue.citation_ids) <= ok
    # hallucination control is visible: at least one claim was dropped
    assert any(v.verdict == "dropped" for v in r.ledger)
    # at least one confirmed risk was found by Adversarial Counsel outside the playbook
    playbook_titles = {rule.title["en"] for rule in load_rules()}
    adv = [k for k in live if k.origin == "adversary"]
    assert adv and all(k.title.en not in playbook_titles for k in adv)
    # nothing identifying ever left the machine
    for p in llm.payloads:
        assert find_pii(p["system"] + p["user"]) == [], p["agent"]
    assert r.privacy.counts and r.privacy.pii_leaks_blocked == 0
    # the served document is the redacted one
    assert find_pii(r.document.text) == [] and all(find_pii(c.text) == [] for c in r.document.clauses)


async def test_epz_document_never_relies_on_labour_act(docs):
    r, _ = await _run(docs, "rmg_dhaka_epz.txt")
    for v in r.ledger:
        if v.claim.citation_id.startswith("BD-LABOUR-2006"):
            assert v.verdict == "dropped"
    used = {c for i in r.memo.issues for c in i.citation_ids}
    assert not any(c.startswith("BD-LABOUR-2006") for c in used)
    assert "BD-EPZLABOUR-2019-s30" in used and "BD-EPZLABOUR-2019-s22" in used


async def test_migrant_document_wage_and_repealed_law(docs):
    r, _ = await _run(docs, "migrant_my_contract.txt")
    assert r.wage.net == 550 and r.wage.below_minimum and r.wage.over_cap
    dropped = [v for v in r.ledger if v.verdict == "dropped"]
    assert any(v.claim.citation_id == "BD-TRAFFICKING-2012-s9" for v in dropped)
    assert any(v.claim.citation_id == "BD-TRAFFICKING-2026-s9" and v.verdict == "verified" for v in r.ledger)
    kinds = [c.kind for c in r.citizen.cards]
    assert kinds[:2] == ["danger", "pay"] and "deadline" in kinds
    assert r.citizen.dangerCount >= 3
    for card in r.citizen.cards:
        assert all(c.status in ("verified", "partial") for c in card.citations)
    assert "BMET" in r.citizen.letter.en or "Agency" in r.citizen.letter.en


async def test_control_document_raises_no_risks(docs):
    r, _ = await _run(docs, "control_clean.txt")
    assert [k for k in r.risks if k.status != "dropped"] == []


async def test_high_risks_go_to_the_virtual_bench(docs):
    r, _ = await _run(docs, "rmg_dhaka_epz.txt")
    benched = [k for k in r.risks if k.bench]
    assert benched and all(k.severity in ("critical", "high", "medium") for k in benched)
    assert any(k.bench.human_review for k in benched)  # a dissent is surfaced, not hidden
