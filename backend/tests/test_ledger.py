"""Four Ledgers (told · paper · paid · law), offline: docs/specs/2026-11-14-19-four-ledgers.md."""

import json
import re
import time

import pytest
from fastapi.testclient import TestClient

from ain import api, config
from ain.agents import ingestion, ledger
from ain.llm import LLM
from ain.models import Deduction, Promises, WageCalc
from ain.orchestrator import new_job, run_pipeline

MY = "migrant_my_contract.txt"
FIXTURE = config.DEMO_DIR / "promises" / "migrant_text.json"
RAW_PHONE, RAW_NAME = "01812345678", "Rahim Talukder"
PAY_TERMS = ("salary", "deductions", "ticket")


@pytest.fixture
def ledger_on(monkeypatch):
    monkeypatch.setattr(config, "ledger_enabled", lambda: True)


def _promises(**changes) -> Promises:
    return Promises.model_validate_json(FIXTURE.read_text(encoding="utf-8")).model_copy(update=changes)


async def _run(docs, promises=None):
    return await run_pipeline(new_job(MY), (docs / MY).read_bytes(), MY, "sample", "fake", promises=promises)


def _rows(four):
    return {r.term: r for r in four.rows}


def _types(row):
    return [m.type for m in row.mismatches]


def _said(row):
    return next(m for m in row.mismatches if m.type == "said_vs_paper")


def _wage(salary: float, deductions: list[Deduction]) -> WageCalc:
    monthly = sum(d.amount for d in deductions if d.per == "month")
    return WageCalc(currency="RM", promised=salary, confirmed_by_user=False, deductions=deductions, monthly_deductions=monthly,
                    net=salary - monthly, pct_deducted=round(100 * monthly / salary, 1))


def test_paper_facts_from_the_malaysia_sample(docs):
    _, facts, _ = ingestion.build_document((docs / MY).read_bytes(), MY, "sample")
    assert (facts.contract_months, facts.hours_per_day, facts.ticket_paid_by, facts.passport_held_by) == (36, 12, "worker", "employer")
    # a return ticket is not the ticket out: the Saudi contract's employer pays the flight to Riyadh
    _, sa, _ = ingestion.build_document((docs / "migrant_sa_contract.txt").read_bytes(), "migrant_sa_contract.txt", "sample")
    assert (sa.contract_months, sa.ticket_paid_by) == (24, "employer")


async def test_malaysia_with_promises_gives_the_expected_rows(docs, ledger_on):
    r = await _run(docs, _promises())
    four = r.four_ledgers
    rows = _rows(four)
    assert list(rows) == list(ledger.TERMS)
    assert _types(rows["salary"]) == ["said_vs_paper", "paper_vs_law"]
    assert rows["salary"].law.status == "verified" and rows["salary"].law.citation_ids == ["MY-MWO-2024-p3"]
    assert (rows["salary"].said.amount, rows["salary"].paper.amount) == (1800, 1200)
    assert _types(rows["deductions"]) == ["said_vs_paper", "paper_vs_law"]
    assert "MY-EA-1955-s24" in rows["deductions"].law.citation_ids
    assert "RM 400 a month after month 12" in rows["deductions"].paper.value.en  # the recruitment deduction ends
    assert _types(rows["recruitment_cost"]) == ["paper_vs_law"] and rows["recruitment_cost"].paper.amount == 3000
    # 12 hours a day on paper: PB-HOURS fills the hours row's law cell (Employment Act 1955 s.60A)
    assert _types(rows["hours_per_day"]) == ["said_vs_paper", "paper_vs_law"] and rows["hours_per_day"].law.status == "verified"
    assert rows["hours_per_day"].law.citation_ids == ["MY-EA-1955-s60A"] and rows["hours_per_day"].severity == "high"
    # the travel clause's risk is about the trip home: its law is shown, but it makes no paper_vs_law on the ticket out
    assert _types(rows["ticket"]) == ["said_vs_paper"]
    assert _types(rows["passport"]) == ["said_vs_paper", "paper_vs_law"] and "BD-OEMA-2013-s31" in rows["passport"].law.citation_ids
    assert _types(rows["contract_months"]) == [] and rows["contract_months"].severity is None
    assert all(row.paid is None for row in four.rows)  # the টাকা ledger waits for the payslip spec

    # the gap on pay and benefits is a playbook risk, verified like any other
    gap = next(k for k in r.risks if k.rule_id == "PB-PROMISE-GAP")
    assert gap.severity == "medium" and gap.bench is None
    assert [(v.claim.citation_id, v.verdict) for v in r.ledger if v.claim.risk_id == gap.id] == [("BD-OEMA-2013-s31", "verified")]
    for term in PAY_TERMS:
        assert (_said(rows[term]).risk_id, _said(rows[term]).risk_status) == (gap.id, "verified")
        assert rows[term].severity in ("medium", "high", "critical")
    hours = _said(rows["hours_per_day"])
    assert (hours.risk_id, hours.risk_status) == (None, None)  # hours are not pay or benefits
    assert four.pending_risks == []

    # a projection under verified law only, never "money owed"; the promise gap stays out of the total
    cp = four.claim_projection
    assert [(x.amount, x.citation_id, x.basis) for x in cp.lines] == [(18000, "MY-MWO-2024-p3", "projected"), (3000, "MY-EA-1955-s24", "projected")]
    assert (cp.projected_total, cp.currency, cp.accrued_total) == (21000, "RM", None)
    assert "not money owed" in cp.label.en.lower() and cp.lines[0].months == 36
    assert (four.promise_gap.total, four.promise_gap.currency) == (21600, "RM")

    # break-even, month by month: RM 16,363.64 at RM 550 for 12 months (6,600), then RM 800 → 12 + 12.2 months
    be = four.break_even
    assert be.months == 24.2 and be.rate.source == "user-entered"
    assert [(s.from_month, s.to_month, s.net) for s in be.steps] == [(1, 12, 550), (13, None, 800)]
    assert be.is_minimum and "whole take-home pay" in be.assumption.en
    assert four.memo_includes_promises


def test_break_even_counts_a_time_limited_deduction_month_by_month():
    w = _wage(1000, [Deduction(label="recovery of recruitment costs", amount=400, months=3), Deduction(label="housing", amount=100)])
    be = ledger.break_even(w, Promises(recruitment_cost_paid=2000, recruitment_cost_currency="RM"), contract_months=24)
    # months 1-3 keep RM 500 each (1,500); then RM 900, so the last RM 500 takes 0.6 of month 4 (a flat 2,000/500 said 4.0)
    assert be.months == 3.6
    assert [(s.from_month, s.to_month, s.net) for s in be.steps] == [(1, 3, 500), (4, None, 900)]
    assert be.monthly_net == 500 and be.rate is None and be.is_minimum


def test_break_even_not_reached_within_the_contract():
    w = _wage(1000, [Deduction(label="recovery of agency fee", amount=850, months=12), Deduction(label="housing", amount=100)])
    be = ledger.break_even(w, Promises(recruitment_cost_paid=9000, recruitment_cost_currency="RM"), contract_months=24)
    # RM 50 a month for 12 months (600), then RM 900: 8,400 more takes 9.3 months; the 24-month contract earns 11,400 in all
    assert be.months == 21.3
    never = ledger.break_even(w, Promises(recruitment_cost_paid=20000, recruitment_cost_currency="RM"), contract_months=24)
    assert never.months is None and never.earned_back == 11400 and "24-month contract" in never.note.en


async def test_no_promises_gives_paper_and_law_only(docs, ledger_on):
    r = await _run(docs)
    four = r.four_ledgers
    assert four.rows and all(row.said is None for row in four.rows)
    assert {m.type for row in four.rows for m in row.mismatches} == {"paper_vs_law"}
    assert not any(k.rule_id == "PB-PROMISE-GAP" for k in r.risks)
    assert four.promise_gap is None and four.break_even is None and not four.memo_includes_promises
    assert not any(v.claim.citation_id == "BD-OEMA-2013-s31" and v.claim.risk_id not in {k.id for k in r.risks} for v in r.ledger)


@pytest.mark.parametrize("how", ["claim dropped", "risk dropped"])
async def test_an_unverified_risk_gives_no_law_cell_and_no_claim_line(docs, ledger_on, how):
    r = await _run(docs, _promises())
    mw = next(k for k in r.risks if k.rule_id == "PB-MIN-WAGE")
    if how == "claim dropped":
        rows = [v.model_copy(update={"verdict": "dropped"}) if v.claim.risk_id == mw.id else v for v in r.ledger]
    else:
        rows = r.ledger
        mw.status = "dropped"
    four = ledger.build(r.facts, r.wage, r.document.clauses, r.risks, rows, r.four_ledgers.promises, True)
    salary = _rows(four)["salary"]
    assert salary.law.status == "not_verified" and salary.law.citation_ids == []
    assert "paper_vs_law" not in _types(salary)
    assert "MY-MWO-2024-p3" not in [x.citation_id for x in four.claim_projection.lines]
    assert four.claim_projection.projected_total == 3000  # the recruitment line still stands on its own verified law


async def test_a_promise_gap_the_gates_refused_is_not_verified(docs, ledger_on):
    r = await _run(docs, _promises())
    gap = next(k for k in r.risks if k.rule_id == "PB-PROMISE-GAP")
    rows = [v.model_copy(update={"verdict": "dropped"}) if v.claim.risk_id == gap.id else v for v in r.ledger]
    four = ledger.build(r.facts, r.wage, r.document.clauses, r.risks, rows, r.four_ledgers.promises, True)
    m = _said(_rows(four)["salary"])
    assert (m.risk_id, m.risk_status) == (gap.id, "not_verified")


async def test_no_rate_gives_no_break_even(docs, ledger_on):
    r = await _run(docs)
    four = ledger.build(r.facts, r.wage, r.document.clauses, r.risks, r.ledger, _promises(exchange_rate=None), False)
    assert four.break_even.months is None and four.break_even.rate is None and "exchange rate" in four.break_even.note.en
    assert four.promise_gap.total == 21600 and four.promise_gap.currency == "RM"  # same currency: no rate needed
    # a cost in the pay's own currency needs no rate either: RM 5,500 at RM 550 a month
    same = ledger.build(r.facts, r.wage, r.document.clauses, r.risks, r.ledger,
                        _promises(exchange_rate=None, recruitment_cost_paid=5500, recruitment_cost_currency="MYR"), False)
    assert same.break_even.months == 10.0 and same.break_even.rate is None
    # a salary told in taka cannot be set against ringgit without the user's rate
    bdt = ledger.build(r.facts, r.wage, r.document.clauses, r.risks, r.ledger,
                       _promises(exchange_rate=None, salary_amount=60000, salary_currency="BDT"), False)
    assert "said_vs_paper" not in _types(_rows(bdt)["salary"]) and bdt.promise_gap is None


async def test_pii_in_the_note_is_redacted(docs, ledger_on):
    r = await _run(docs, _promises())
    note = r.four_ledgers.promises.note
    assert RAW_PHONE not in note and RAW_NAME not in note
    assert "[PHONE_" in note and "[NAME_" in note
    dump = r.model_dump_json()
    assert RAW_PHONE not in dump and RAW_NAME not in dump  # not in the trace, the receipt or anywhere else
    assert r.privacy.counts["PHONE"] >= 2  # the contract's number and the note's


def _wait(client, job_id, timeout=90):
    t = time.time()
    while time.time() - t < timeout:
        s = client.get(f"/api/jobs/{job_id}").json()
        if s["status"] in ("done", "error"):
            return s
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_promises_added_later_are_not_verified_until_the_gates_run(docs, ledger_on, monkeypatch):
    with TestClient(api.app) as client:
        job = client.post("/api/analyze", files={"file": (MY, (docs / MY).read_bytes(), "text/plain")}).json()["job_id"]
        assert _wait(client, job)["status"] == "done"
        before = client.get(f"/api/jobs/{job}/result").json()
        assert before["four_ledgers"]["promises"] is None

        async def no_model(*a, **k):
            raise AssertionError("a model was called")

        real_json = LLM.json
        monkeypatch.setattr(LLM, "json", no_model)
        body = json.loads(FIXTURE.read_text(encoding="utf-8"))
        four = client.post(f"/api/jobs/{job}/promises", json=body)
        assert four.status_code == 200, four.text
        f = four.json()
        rows = {row["term"]: row for row in f["rows"]}
        assert [m["type"] for m in rows["salary"]["mismatches"]] == ["said_vs_paper", "paper_vs_law"]

        # no model call on this path, so the gap's risk is held back: never shown as verified, never a live risk
        [pending] = f["pending_risks"]
        assert pending["rule_id"] == "PB-PROMISE-GAP" and pending["id"] == f"R{len(before['risks']) + 1}"
        for term in PAY_TERMS:
            said = next(m for m in rows[term]["mismatches"] if m["type"] == "said_vs_paper")
            assert (said["risk_id"], said["risk_status"]) == (pending["id"], "not_verified_yet")
        after = client.get(f"/api/jobs/{job}/result").json()
        assert len(after["privacy"]["outbound_calls"]) == len(before["privacy"]["outbound_calls"])
        assert not any(k["rule_id"] == "PB-PROMISE-GAP" for k in after["risks"])
        assert not any(v["claim"]["risk_id"] == pending["id"] for v in after["ledger"])
        assert after["stats"] == before["stats"] and after["four_ledgers"]["memo_includes_promises"] is False
        note = after["four_ledgers"]["promises"]["note"]
        assert RAW_PHONE not in note and "[PHONE_2]" in note  # numbering continues after the contract's own

        # a later run verifies it: the same verifier and 4 gates, with a model call
        monkeypatch.setattr(LLM, "json", real_json)
        v = client.post(f"/api/jobs/{job}/promises/verify")
        assert v.status_code == 200, v.text
        assert v.json()["pending_risks"] == []
        final = client.get(f"/api/jobs/{job}/result").json()
        gap = next(k for k in final["risks"] if k["rule_id"] == "PB-PROMISE-GAP")
        mine = [x for x in final["ledger"] if x["claim"]["risk_id"] == gap["id"]]
        assert [(x["claim"]["citation_id"], x["verdict"]) for x in mine] == [("BD-OEMA-2013-s31", "verified")]
        assert [g["gate"] for g in mine[0]["gates"]] == ["existence", "fidelity", "entailment", "currency"]
        new_calls = final["privacy"]["outbound_calls"][len(after["privacy"]["outbound_calls"]):]
        assert any(c["agent"] == "Citation Verifier" for c in new_calls)
        said = next(m for row in final["four_ledgers"]["rows"] if row["term"] == "salary" for m in row["mismatches"] if m["type"] == "said_vs_paper")
        assert (said["risk_id"], said["risk_status"]) == (gap["id"], "verified")
        assert final["stats"]["risks_found"] == before["stats"]["risks_found"] + 1
        assert client.post(f"/api/jobs/{job}/promises/verify").status_code == 409  # nothing left to verify

        # told what the paper says: the gap and its risk go away
        same = client.post(f"/api/jobs/{job}/promises", json={"salary_amount": 1200, "salary_currency": "RM"}).json()
        assert "said_vs_paper" not in [m["type"] for row in same["rows"] for m in row["mismatches"]] and same["pending_risks"] == []
        assert not any(k["rule_id"] == "PB-PROMISE-GAP" for k in client.get(f"/api/jobs/{job}/result").json()["risks"])
        assert client.post(f"/api/jobs/{job}/promises", json={"hours_per_day": 30}).status_code == 422


def test_the_sample_loads_its_fictional_promises(ledger_on):
    with TestClient(api.app) as client:
        job = client.post("/api/analyze", data={"sample_id": "migrant_text"}).json()["job_id"]
        assert _wait(client, job)["status"] == "done"
        r = client.get(f"/api/jobs/{job}/result").json()
        assert r["four_ledgers"]["promises"]["salary_amount"] == 1800
        assert any(k["rule_id"] == "PB-PROMISE-GAP" for k in r["risks"])


def test_flag_off_refuses_promises_and_adds_nothing(docs):
    assert config.ledger_enabled() is False  # the shipped default
    with TestClient(api.app) as client:
        bad = client.post("/api/analyze", data={"sample_id": "control", "promises": FIXTURE.read_text(encoding="utf-8")})
        assert bad.status_code == 400
        job = client.post("/api/analyze", data={"sample_id": "migrant_text"}).json()["job_id"]
        assert _wait(client, job)["status"] == "done"
        r = client.get(f"/api/jobs/{job}/result").json()
        assert r["four_ledgers"] is None
        assert not any(k["rule_id"] == "PB-PROMISE-GAP" for k in r["risks"])
        assert client.post(f"/api/jobs/{job}/promises", json={"salary_amount": 1800}).status_code == 404
        assert client.post(f"/api/jobs/{job}/promises/verify").status_code == 404
        assert client.post(f"/api/jobs/{job}/term", json={"months": 24}).status_code == 404


@pytest.mark.parametrize("rule_id, pack", [("PB-PROMISE-GAP", "bd_migration"), ("PB-HOURS", "my_employment")])
def test_the_ledger_rules_are_in_no_prompt_while_the_flag_is_off(monkeypatch, rule_id, pack):
    """The Adversary's prompt lists every active rule: an always-active rule would change its cache key with the flag off."""
    from ain.agents.risk_analyst import load_rules

    rule = next(r for r in load_rules() if r.id == rule_id)
    assert not rule.active({pack})
    monkeypatch.setattr(config, "ledger_enabled", lambda: True)
    assert rule.active({pack}) and not rule.active({"bd_labour"})


async def test_hours_over_the_limit_read_as_a_sentence_in_both_languages(docs, ledger_on):
    r = await _run(docs)
    hours = next(k for k in r.risks if k.rule_id == "PB-HOURS")
    assert hours.finding == "The contract sets normal working hours of 12 hours a day (the limit is 8)."
    assert [(v.claim.citation_id, v.verdict) for v in r.ledger if v.claim.risk_id == hours.id] == [("MY-EA-1955-s60A", "verified")]
    law = next(m for m in _rows(r.four_ledgers)["hours_per_day"].mismatches if m.type == "paper_vs_law")
    assert law.detail.en == "The contract sets 12 hours a day; the cited law limits a day to 8 hours."
    assert law.detail.bn == "চুক্তিতে দিনে ১২ ঘণ্টা কাজ, অথচ উল্লেখিত আইনে দিনে সর্বোচ্চ ৮ ঘণ্টা।"
    assert law.title.en == "Limit on working hours"


def test_hours_within_the_limit_or_stated_only_weekly():
    from ain.agents.risk_analyst import run_fact_check
    from ain.models import DocFacts

    my = {"my_employment"}
    assert run_fact_check("hours_over_limit", DocFacts(hours_per_day=8, hours_per_week=45), None, my) is None
    assert run_fact_check("hours_over_limit", DocFacts(hours_per_day=8, hours_per_week=48), None, my) == (
        "The contract sets normal working hours of 48 hours a week (the limit is 45).")
    assert run_fact_check("hours_over_limit", DocFacts(hours_per_day=12), None, {"sa_labour"}) is None  # no limit on file


async def test_a_mismatch_with_no_verified_law_gives_the_row_no_severity(docs, ledger_on):
    r = await _run(docs, _promises(contract_months=24))  # told 24 months, the paper says 36: no law of its own
    months = _rows(r.four_ledgers)["contract_months"]
    assert _types(months) == ["said_vs_paper"] and months.law.status == "none"
    assert months.severity is None


def test_invalid_promises_are_rejected(ledger_on):
    with TestClient(api.app) as client:
        bad = client.post("/api/analyze", data={"sample_id": "control", "promises": json.dumps({"ticket_paid_by": "nobody"})})
        assert bad.status_code == 422


# ---------------------------------------------------------------- spec 20, backend round

LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
CURRENCY = re.compile(r"\b(?:RM|MYR|BDT|SAR|AED|QAR|OMR|KWD|BHD|SGD|USD|Tk)\b")


def _latin(bn: str) -> list[str]:
    return LATIN_WORD.findall(CURRENCY.sub("", bn))


async def test_every_bangla_string_is_bangla(docs, ledger_on):
    r = await _run(docs, _promises())
    no_rate = ledger.build(r.facts, r.wage, r.document.clauses, r.risks, r.ledger, _promises(exchange_rate=None), False)
    texts = []
    for four in (r.four_ledgers, no_rate):
        for row in four.rows:
            texts += [c.value.bn for c in (row.said, row.paper) if c]
            texts += [m.detail.bn for m in row.mismatches] + [t.bn for t in (row.law.title, *(m.title for m in row.mismatches)) if t]
        cp = four.claim_projection
        texts += [x.label.bn for x in cp.lines] + [cp.term.label.bn, four.break_even.note.bn]
    assert not [t for t in texts if _latin(t)], [t for t in texts if _latin(t)]

    rows = _rows(r.four_ledgers)
    assert (rows["ticket"].said.value.bn, rows["ticket"].paper.value.bn) == ("মালিক দেবে", "কর্মী দেবে")
    assert (rows["ticket"].said.party, rows["ticket"].paper.party) == ("employer", "worker")
    assert rows["hours_per_day"].paper.value.bn == "দিনে ১২ ঘণ্টা" and rows["contract_months"].paper.value.bn == "৩৬ মাস"
    assert _said(rows["salary"]).detail.bn == "বলা হয়েছিল মাসে RM 1,800, কিন্তু চুক্তিতে লেখা মাসে RM 1,200।"
    assert rows["salary"].said.value.en == "RM 1,800 a month" and rows["ticket"].paper.value.en == "the worker pays"


def test_an_older_saved_cell_loads_as_english():
    from ain.models import LedgerCell

    old = LedgerCell.model_validate({"value": "RM 1,200 a month", "amount": 1200, "currency": "RM", "source": "contract"})
    assert (old.value.en, old.value.bn) == ("RM 1,200 a month", "RM 1,200 a month")


async def test_law_cells_have_a_short_title_and_mismatches_carry_their_status(docs, ledger_on):
    r = await _run(docs, _promises())
    rows = _rows(r.four_ledgers)
    assert rows["salary"].law.title.en == "Minimum wage" and rows["salary"].law.title.bn == "ন্যূনতম মজুরি"
    law = next(m for m in rows["salary"].mismatches if m.type == "paper_vs_law")
    assert (law.risk_status, law.title.en) == ("verified", "Minimum wage")
    # the promise gap rests on the worker's account: it "may fall under" the section, never a proven offence
    gap = _said(rows["salary"])
    assert gap.title.en.lower().startswith("may fall under") and "offence" not in gap.title.en.lower()
    assert gap.citation_ids == ["BD-OEMA-2013-s31"]
    assert _said(rows["hours_per_day"]).title is None  # hours are not pay or benefits: no law of their own
    # every cited section has a name in both languages, built from the corpus record
    names = r.model_dump()["citation_names"]
    assert "ন্যূনতম মজুরি আদেশ" in names["MY-MWO-2024-p3"]["bn"] and "Minimum Wages Order" in names["MY-MWO-2024-p3"]["en"]


async def test_the_projection_says_where_its_term_came_from(docs, ledger_on):
    r = await _run(docs, _promises())
    term = r.four_ledgers.claim_projection.term
    assert (term.months, term.source, term.clause_id, term.label.en) == (36, "contract", "C2", "Term read from the contract")
    r.facts.contract_months = None  # nothing on paper: the term the worker was told, marked as such
    told = ledger.build(r.facts, r.wage, r.document.clauses, r.risks, r.ledger, _promises(), False).claim_projection.term
    assert (told.months, told.source) == (36, "worker") and "none on paper" in told.label.en


def test_the_contract_term_can_be_confirmed_with_no_model_call(docs, ledger_on, monkeypatch):
    with TestClient(api.app) as client:
        job = client.post("/api/analyze", data={"sample_id": "migrant_text"}).json()["job_id"]
        assert _wait(client, job)["status"] == "done"
        before = client.get(f"/api/jobs/{job}/result").json()

        async def no_model(*a, **k):
            raise AssertionError("a model was called")

        monkeypatch.setattr(LLM, "json", no_model)
        resp = client.post(f"/api/jobs/{job}/term", json={"months": 24})
        assert resp.status_code == 200, resp.text
        f = resp.json()
        cp = f["claim_projection"]
        assert (cp["term"]["months"], cp["term"]["source"], cp["term"]["label"]["en"]) == (24, "user", "Term confirmed by user")
        assert cp["lines"][0]["months"] == 24 and cp["lines"][0]["amount"] == 12000  # RM 500 short a month × 24
        assert f["promise_gap"]["total"] == 14400 and f["break_even"]["horizon_months"] == 24
        rows = {row["term"]: row for row in f["rows"]}
        paper = rows["contract_months"]["paper"]
        assert (paper["amount"], paper["confirmed_by_user"]) == (24, True)
        assert "said_vs_paper" in [m["type"] for m in rows["contract_months"]["mismatches"]]  # told 36, the paper says 24

        after = client.get(f"/api/jobs/{job}/result").json()
        assert (after["facts"]["contract_months"], after["facts"]["contract_months_confirmed"]) == (24, True)
        assert len(after["privacy"]["outbound_calls"]) == len(before["privacy"]["outbound_calls"])
        # a later change to the promises keeps the confirmed term
        again = client.post(f"/api/jobs/{job}/promises", json=json.loads(FIXTURE.read_text(encoding="utf-8"))).json()
        assert again["claim_projection"]["term"]["source"] == "user"
        for bad in (0, 300):
            assert client.post(f"/api/jobs/{job}/term", json={"months": bad}).status_code == 422


async def test_an_adversary_risk_on_a_term_with_no_rule_raises_no_paper_vs_law(docs, ledger_on):
    """Live run, 2026-11-19: the Adversary's annual-leave risk sat on the contract-length clause and the row read
    "The contract says 36 months, against the cited law", rated high. A term with no playbook rule shows the law the
    risk rests on, but the paper is not said to break it."""
    r = await _run(docs, _promises())
    rows = _rows(r.four_ledgers)
    src = next(k for k in r.risks if k.rule_id == "PB-PASSPORT")
    risks, ledger_rows = list(r.risks), list(r.ledger)
    for n, term in enumerate(("contract_months", "ticket")):
        rid = f"RX{n}"
        risks.append(src.model_copy(update={"id": rid, "rule_id": None, "origin": "adversary", "clause_ids": [rows[term].paper.clause_id]}))
        ledger_rows += [v.model_copy(update={"claim": v.claim.model_copy(update={"risk_id": rid})}) for v in r.ledger if v.claim.risk_id == src.id]
    risks = [k for k in risks if k.rule_id != "PB-RETURN-COST"]  # leave the Adversary risk as the ticket clause's only one
    four = ledger.build(r.facts, r.wage, r.document.clauses, risks, ledger_rows, r.four_ledgers.promises, memo_includes_promises=False)
    after = _rows(four)
    assert after["contract_months"].law.status == "verified"  # the law is still shown
    assert _types(after["contract_months"]) == [] and after["contract_months"].severity is None
    assert "paper_vs_law" not in _types(after["ticket"])
    assert _types(after["passport"]) == ["said_vs_paper", "paper_vs_law"]  # a term's own rule still counts
