from ain.agents import calculator, drafter
from ain.models import Claim, Deduction, DocFacts, GateResult, L10n, PackDecision, Risk, RouteDecision, Verification
from tests.conftest import RecordingLLM

MY_ROUTE = RouteDecision(packs=[PackDecision(pack=p, label=p, reason="t") for p in ("bd_migration", "my_employment")])


def test_wage_maths():
    facts = DocFacts(salary_amount=1200, salary_currency="RM", deductions=[Deduction(label=x, amount=a) for x, a in (("a", 250), ("b", 200), ("c", 100), ("d", 100))])
    w = calculator.compute(facts, MY_ROUTE)
    assert w.monthly_deductions == 650 and w.net == 550 and w.pct_deducted == 54.2
    assert w.below_minimum and w.shortfall == 500 and w.minimum_wage == 1700
    assert w.over_cap and w.deduction_cap_pct == 50


def test_user_confirmed_salary_overrides_ocr():
    w = calculator.compute(DocFacts(salary_amount=1200, salary_currency="RM"), MY_ROUTE, salary=1800, confirmed=True)
    assert w.promised == 1800 and not w.below_minimum and w.confirmed_by_user


def test_no_minimum_wage_outside_routed_jurisdiction():
    facts = DocFacts(salary_amount=12500, salary_currency="BDT", deductions=[Deduction(label="canteen", amount=500)])
    w = calculator.compute(facts, RouteDecision(packs=[]))
    assert w.minimum_wage is None and not w.below_minimum and w.net == 12000
    assert calculator.compute(DocFacts(salary_amount=12500, salary_currency="BDT"), RouteDecision(packs=[])) is None


async def test_drafter_strips_unverified_citations(corpus):
    sec = corpus.get("BD-CONTRACT-1872-s27")
    risk = Risk(id="R1", origin="playbook", category="c", title=L10n(bn="x", en="Non-compete"), severity="high", finding="f",
                citizen_line=L10n(bn="x", en="x"), action=L10n(bn="x", en="x"), claim_ids=["R1.1"])
    c = Claim(id="R1.1", risk_id="R1", proposition="p", citation_id=sec.citation_id)
    ledger = [Verification(claim=c, gates=[GateResult(gate="existence", status="pass", detail="")], verdict="verified", section=sec)]
    rogue = {"executive_summary": "s", "summary_bn": "b", "letter_bn": "l", "letter_en": "l",
             "issues": [{"risk_id": "R1", "issue": "i", "rule": "r", "application": "a", "conclusion": "c",
                         "citation_ids": ["BD-CONTRACT-1872-s27", "BD-LABOUR-2006-s999", "UK-RESTRAINT-ACT-s1"]}]}
    events = []
    memo, _ = await drafter.draft(RecordingLLM(overrides={"draft_memo": rogue}), "doc", DocFacts(), MY_ROUTE, [risk], ledger, None, events.append)
    assert memo.issues[0].citation_ids == ["BD-CONTRACT-1872-s27"]
    assert events and "BD-LABOUR-2006-s999" in events[0].message
