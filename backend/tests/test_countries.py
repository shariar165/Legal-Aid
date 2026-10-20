"""Destination countries: the registry, detection, routing, wage limits and the country-aware playbook."""

import re

import pytest

from ain import countries
from ain.agents import calculator
from ain.agents.ingestion import build_document, extract_facts, segment
from ain.agents.risk_analyst import load_rules
from ain.agents.router import PACK_LABELS, decide
from ain.models import Deduction, DocFacts, PackDecision, RouteDecision

# how each statute words the cap or floor the registry claims it states
FIGURE_WORDING = {50: ("50%", "half", "fifty"), 25: ("25 per cent", "one-fourth", "25%")}


def _route(*packs):
    return RouteDecision(packs=[PackDecision(pack=p, label=p, reason="t") for p in packs])


def test_registry_covers_the_main_destinations():
    codes = {c.code for c in countries.load_countries()}
    assert {"SA", "AE", "MY", "QA", "OM", "KW", "SG", "BH"} <= codes
    packs = [c.pack for c in countries.load_countries()]
    assert len(packs) == len(set(packs))
    assert all(p in PACK_LABELS for p in packs)


def test_registry_figures_are_stated_in_the_cited_sections(corpus):
    for c in countries.load_countries():
        if c.deduction_cap:
            sec = corpus.get(c.deduction_cap["citation_id"])
            assert sec is not None and c.pack in sec.packs, c.code
            assert any(w in sec.text for w in FIGURE_WORDING[c.deduction_cap["pct"]]), c.code
        if c.min_wage:
            sec = corpus.get(c.min_wage["citation_id"])
            assert sec is not None and c.pack in sec.packs, c.code
            assert f"{c.min_wage['amount']:,}" in sec.text, c.code


def test_every_country_has_its_own_law_in_the_playbook(corpus):
    rules = load_rules()
    for c in countries.load_countries():
        anchors = [a for r in rules for a in r.pack_anchors.get(c.pack, [])]
        assert len(anchors) >= 2, f"{c.code} has too little host-country law"
        for a in anchors:
            assert c.pack in corpus.get(a["citation_id"]).packs, f"{a['citation_id']} is not {c.code} law"
    known = {c.pack for c in countries.load_countries()}
    for r in rules:
        assert set(r.pack_anchors) <= known | {"std_recruitment"}, r.id


@pytest.mark.parametrize(
    "text, code",
    [
        ("The worker will be employed at a site in Riyadh.", "SA"),
        ("Place of work: Dubai, U.A.E.", "AE"),
        ("কর্মস্থল: সৌদি আরবে একটি নির্মাণ প্রতিষ্ঠান", "SA"),
        ("কর্মী মালয়েশিয়ায় কাজ করবেন", "MY"),
        ("Employer: Gulf Star W.L.L., Manama", "BH"),
    ],
)
def test_detects_destination_in_english_and_bangla(text, code):
    assert countries.detect(text).code == code


def test_aliases_match_whole_words_only():
    assert countries.detect("A woman worker shall receive maternity leave.") is None  # not "Oman"
    assert countries.detect("Salary paid in Singapore; recruitment through Dhaka; one visit to Doha, Doha.").code == "QA"  # most mentions wins


def test_router_adds_each_country_pack_and_nothing_for_unknown_destinations():
    for c in countries.load_countries():
        for name in (c.name["en"], c.code, c.aliases[0]):
            route = decide(DocFacts(doc_type="employment", destination_country=name), "recruiting agency")
            assert c.pack in route.pack_ids, name
            assert "bd_labour" not in route.pack_ids
    route = decide(DocFacts(doc_type="employment", destination_country="Italy"), "recruiting agency")
    assert route.pack_ids == {"bd_contract", "bd_migration", "ilo", "std_recruitment", "ilo_supervisory"}


def test_money_in_any_destination_currency():
    for text, amount, cur in [
        ("2. Salary. A basic salary of SAR 1,500 per month.", 1500, "SAR"),
        ("2. Salary. The monthly wage is 1,250 riyals.", 1250, "SAR"),
        ("2. Salary. Basic wage KWD 120 per month.", 120, "KWD"),
        ("2. Salary. Basic salary S$ 650 per month.", 650, "SGD"),
    ]:
        f = extract_facts(text, segment(text))
        assert (f.salary_amount, f.salary_currency) == (amount, cur), text
    f = extract_facts("2. Salary. Fill in form 3 and the salary of AED 1,800.", segment("2. Salary. Fill in form 3 and the salary of AED 1,800."))
    assert (f.salary_amount, f.salary_currency) == (1800, "AED")  # "rm 3" inside "form 3" is not money


def test_calculator_applies_each_countrys_cap():
    deductions = [Deduction(label="fees", amount=400), Deduction(label="room", amount=150)]
    w = calculator.compute(DocFacts(salary_amount=1000, salary_currency="SAR", deductions=deductions), _route("sa_labour"))
    assert w.over_cap and w.deduction_cap_pct == 50 and w.cap_citation == "SA-LABOR-2005-a93"
    assert w.minimum_wage is None and not w.below_minimum  # no Saudi minimum wage in the corpus
    w = calculator.compute(DocFacts(salary_amount=200, salary_currency="KWD", deductions=[Deduction(label="room", amount=60)]), _route("kw_labour"))
    assert w.over_cap and w.deduction_cap_pct == 25  # Kuwait allows only a quarter
    w = calculator.compute(DocFacts(salary_amount=300, salary_currency="BHD", deductions=[Deduction(label="room", amount=200)]), _route("bh_labour"))
    assert w.deduction_cap_pct is None and not w.over_cap  # Bahrain has no overall cap we can cite


def test_saudi_contract_routes_saudi_law(docs):
    doc, facts, _ = build_document((docs / "migrant_sa_contract.txt").read_bytes(), "migrant_sa_contract.txt")
    assert facts.destination_country == "Saudi Arabia" and facts.salary_currency == "SAR"
    assert sum(d.amount for d in facts.deductions) == 650
    route = decide(facts, doc.text.lower())
    assert {"bd_migration", "ilo", "sa_labour"} <= route.pack_ids


async def test_saudi_contract_risks_cite_saudi_law(docs):
    from ain.orchestrator import new_job, run_pipeline

    data = (docs / "migrant_sa_contract.txt").read_bytes()
    r = await run_pipeline(new_job("sa"), data, "migrant_sa_contract.txt", None, "fake", confirm_timeout=0.1)
    found = {k.rule_id for k in r.risks}
    assert {"PB-PASSPORT", "PB-RECRUIT-FEE", "PB-DEDUCTION-CAP", "PB-RETURN-TICKET", "PB-END-OF-SERVICE", "PB-CLAIM-WAIVER"} <= found
    cited = {v.claim.citation_id for v in r.ledger if v.verdict != "dropped"}
    assert {"SA-LABOR-2005-a40", "SA-LABOR-2005-a84", "SA-LABOR-2005-a93"} <= cited
    cap = next(k for k in r.risks if k.rule_id == "PB-DEDUCTION-CAP")
    assert "50%" in cap.title.en and "৫০%" in cap.title.bn
    ticket = next(k for k in r.risks if k.rule_id == "PB-RETURN-TICKET")
    assert "Saudi Arabia's" in ticket.citizen_line.en and "সৌদি আরবের" in ticket.citizen_line.bn
    assert not re.search(r"\{\w+\}", ticket.mitigation_clause)  # every placeholder was filled


async def test_recruitment_standards_back_the_law_but_are_marked_as_not_law(docs, corpus):
    from ain.agents.verifier import gate_currency
    from ain.orchestrator import new_job, run_pipeline

    standards = [s for s in corpus.sections if s.kind == "standard"]
    assert {s.act_key for s in standards} >= {"STD-ILO-FAIR-2019", "STD-EPP", "STD-RBA-2024"}
    assert all(s.packs == ["std_recruitment"] for s in standards)
    assert "voluntary standard, not law" in gate_currency(standards[0]).detail

    data = (docs / "migrant_sa_contract.txt").read_bytes()
    r = await run_pipeline(new_job("sa-std"), data, "migrant_sa_contract.txt", None, "fake", confirm_timeout=0.1)
    fee = next(k for k in r.risks if k.rule_id == "PB-RECRUIT-FEE")
    claims = [v for v in r.ledger if v.claim.risk_id == fee.id]
    order = [v.claim.citation_id for v in claims]
    assert order.index("SA-LABOR-2005-a40") < order.index("STD-EPP-LGRR")  # the law first, the standard after
    assert all(v.verdict == "verified" for v in claims if v.section and v.section.kind == "standard")
