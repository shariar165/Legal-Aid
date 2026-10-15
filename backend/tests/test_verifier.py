"""Each gate must fail on its own bad case."""

from ain.agents.verifier import verify_claim
from ain.models import Claim, PackDecision, RouteDecision
from tests.conftest import RecordingLLM

ROUTE = RouteDecision(
    packs=[PackDecision(pack=p, label=p, reason="test") for p in ("bd_contract", "bd_migration", "ilo", "my_employment", "eu_dd", "bd_epz")],
    excluded=[PackDecision(pack="bd_labour", label="Labour Act", reason="Switched OFF: workplace is in Dhaka EPZ.")],
)


def claim(cid, prop="Every agreement in restraint of trade is void to that extent.", quote=None):
    return Claim(id="T1", risk_id="R1", proposition=prop, citation_id=cid, quote=quote)


async def test_genuine_claim_is_verified(corpus):
    q = "Every agreement by which any one is restrained from exercising a lawful profession, trade or business of any kind, is to that extent void."
    v = await verify_claim(RecordingLLM(), corpus, ROUTE, claim("BD-CONTRACT-1872-s27", quote=q), None, False)
    assert v.verdict == "verified"
    assert [g.status for g in v.gates] == ["pass", "pass", "pass", "pass"]


async def test_gate1_invented_section_is_dropped(corpus):
    v = await verify_claim(RecordingLLM(), corpus, ROUTE, claim("BD-CONTRACT-1872-s27B"), None, False)
    assert v.verdict == "dropped" and v.gates[0].status == "fail"


async def test_gate1_switched_off_regime_is_dropped(corpus):
    v = await verify_claim(RecordingLLM(), corpus, ROUTE, claim("BD-LABOUR-2006-s46", "Women get maternity benefit for 60 days before and after delivery."), None, False)
    assert v.verdict == "dropped"
    assert "does not apply" in v.gates[0].detail


async def test_gate2_misquote_downgrades_to_partial(corpus):
    v = await verify_claim(RecordingLLM(), corpus, ROUTE, claim("BD-CONTRACT-1872-s27", quote="Non-compete clauses are enforceable if reasonable in time and area."), None, False)
    assert v.gates[1].status == "warn"
    assert v.verdict == "partial"


async def test_gate3_contradiction_is_dropped(corpus):
    llm = RecordingLLM(overrides={"entailment": {"verdict": "contradicts", "reasoning": "The text says the opposite."}})
    v = await verify_claim(llm, corpus, ROUTE, claim("BD-CONTRACT-1872-s27", "Restraint of trade clauses are always valid."), None, False)
    assert v.verdict == "dropped" and v.gates[2].status == "fail"


async def test_gate3_judge_sees_only_the_cited_section(corpus):
    llm = RecordingLLM()
    await verify_claim(llm, corpus, ROUTE, claim("BD-CONTRACT-1872-s27"), None, False)
    payload = next(p for p in llm.payloads if p["task"] == "entailment")
    assert "restrained from exercising a lawful profession" in payload["user"]
    assert "restraint of legal proceedings" not in payload["user"]


async def test_gate4_repealed_act_is_dropped(corpus):
    v = await verify_claim(RecordingLLM(), corpus, RouteDecision(packs=ROUTE.packs), claim("BD-TRAFFICKING-2012-s9", "Forced labour is punishable with 5 to 12 years."), None, False)
    assert v.verdict == "dropped" and v.gates[3].status == "fail"
    assert "BD-TRAFFICKING-2026" in v.gates[3].detail


async def test_gate4_amended_instrument_is_partial(corpus):
    q = "provide targeted and proportionate support to an SME which is a business partner of the company"
    v = await verify_claim(RecordingLLM(), corpus, ROUTE, claim("EU-CSDDD-2024-a10", "Companies must support SME partners.", q), None, False)
    assert v.gates[3].status == "warn" and v.verdict == "partial"


async def test_critic_reanchors_repealed_citation(corpus):
    from ain.agents.critic import heal
    from ain.models import L10n, Risk

    route = RouteDecision(packs=ROUTE.packs)
    c = claim("BD-TRAFFICKING-2012-s9", "Compelling labour through debt bondage is an offence punishable with 5 to 12 years' rigorous imprisonment.")
    risk = Risk(id="R1", origin="adversary", category="x", title=L10n(bn="x", en="x"), severity="high", finding="f",
                citizen_line=L10n(bn="x", en="x"), action=L10n(bn="x", en="x"), claim_ids=["T1"])
    llm = RecordingLLM()
    ledger = [await verify_claim(llm, corpus, route, c, risk, False)]
    added = await heal(llm, corpus, route, [risk], ledger)
    assert added and added[0].claim.citation_id == "BD-TRAFFICKING-2026-s9"
    assert added[0].verdict == "verified" and risk.status == "confirmed"
