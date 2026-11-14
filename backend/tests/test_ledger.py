"""Four Ledgers (told · paper · paid · law), offline: docs/specs/2026-11-14-19-four-ledgers.md."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from ain import api, config
from ain.agents import ingestion, ledger
from ain.llm import LLM
from ain.models import Promises
from ain.orchestrator import new_job, run_pipeline

MY = "migrant_my_contract.txt"
FIXTURE = config.DEMO_DIR / "promises" / "migrant_text.json"
RAW_PHONE, RAW_NAME = "01812345678", "Rahim Talukder"


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
    assert _types(rows["recruitment_cost"]) == ["paper_vs_law"] and rows["recruitment_cost"].paper.amount == 3000
    assert _types(rows["hours_per_day"]) == ["said_vs_paper"] and rows["hours_per_day"].law.status == "none"
    # the travel clause's risk is about the trip home: its law is shown, but it makes no paper_vs_law on the ticket out
    assert _types(rows["ticket"]) == ["said_vs_paper"]
    assert _types(rows["passport"]) == ["said_vs_paper", "paper_vs_law"] and "BD-OEMA-2013-s31" in rows["passport"].law.citation_ids
    assert _types(rows["contract_months"]) == [] and rows["contract_months"].severity is None
    assert all(row.paid is None for row in four.rows)  # the টাকা ledger waits for the payslip spec

    # the gap on pay and benefits is a playbook risk, verified like any other
    gap = next(k for k in r.risks if k.rule_id == "PB-PROMISE-GAP")
    assert gap.severity == "medium" and gap.bench is None
    assert [(v.claim.citation_id, v.verdict) for v in r.ledger if v.claim.risk_id == gap.id] == [("BD-OEMA-2013-s31", "verified")]
    for term in ("salary", "deductions", "ticket"):
        assert next(m for m in rows[term].mismatches if m.type == "said_vs_paper").risk_id == gap.id
    assert next(m for m in rows["hours_per_day"].mismatches).risk_id is None  # hours are not pay or benefits

    # পাওনা হিসাব: verified law only; the promise gap stays out of the total
    cv = four.claim_value
    assert [(x.amount, x.citation_id) for x in cv.lines] == [(18000, "MY-MWO-2024-p3"), (3000, "MY-EA-1955-s24")]
    assert (cv.total, cv.currency) == (21000, "RM") and "not a prediction" in cv.label.en
    assert (four.promise_gap.total, four.promise_gap.currency) == (21600, "RM")
    be = four.break_even
    assert be.months == 29.8 and be.monthly_net == 550 and be.rate.source == "user-entered"
    assert four.memo_includes_promises


async def test_no_promises_gives_paper_and_law_only(docs, ledger_on):
    r = await _run(docs)
    four = r.four_ledgers
    assert four.rows and all(row.said is None for row in four.rows)
    assert {m.type for row in four.rows for m in row.mismatches} == {"paper_vs_law"}
    assert not any(k.rule_id == "PB-PROMISE-GAP" for k in r.risks)
    assert four.promise_gap is None and four.break_even is None and not four.memo_includes_promises
    # the rule's law is checked once anyway, so promises added later need no model call
    standing = [v for v in r.ledger if v.claim.risk_id == "L"]
    assert [(v.claim.id, v.claim.citation_id, v.verdict) for v in standing] == [("L1", "BD-OEMA-2013-s31", "verified")]


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
    assert "MY-MWO-2024-p3" not in [x.citation_id for x in four.claim_value.lines]
    assert four.claim_value.total == 3000  # the recruitment line still stands on its own verified law


async def test_no_rate_gives_no_break_even(docs, ledger_on):
    r = await _run(docs)
    four = ledger.build(r.facts, r.wage, r.document.clauses, r.risks, r.ledger, _promises(exchange_rate=None), False)
    assert four.break_even.months is None and four.break_even.rate is None and "exchange rate" in four.break_even.note
    assert four.promise_gap.total == 21600 and four.promise_gap.currency == "RM"  # same currency: no rate needed
    # a cost in the pay's own currency needs no rate either
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


def test_promises_recompute_makes_no_outbound_call(docs, ledger_on, monkeypatch):
    with TestClient(api.app) as client:
        job = client.post("/api/analyze", files={"file": (MY, (docs / MY).read_bytes(), "text/plain")}).json()["job_id"]
        assert _wait(client, job)["status"] == "done"
        before = client.get(f"/api/jobs/{job}/result").json()
        assert before["four_ledgers"]["promises"] is None

        async def no_model(*a, **k):
            raise AssertionError("a model was called")

        monkeypatch.setattr(LLM, "json", no_model)
        body = json.loads(FIXTURE.read_text(encoding="utf-8"))
        four = client.post(f"/api/jobs/{job}/promises", json=body)
        assert four.status_code == 200, four.text
        rows = {row["term"]: row for row in four.json()["rows"]}
        assert [m["type"] for m in rows["salary"]["mismatches"]] == ["said_vs_paper", "paper_vs_law"]

        after = client.get(f"/api/jobs/{job}/result").json()
        assert len(after["privacy"]["outbound_calls"]) == len(before["privacy"]["outbound_calls"])
        gap = next(k for k in after["risks"] if k["rule_id"] == "PB-PROMISE-GAP")
        assert gap["id"] == f"R{len(before['risks']) + 1}"
        mine = [v for v in after["ledger"] if v["claim"]["risk_id"] == gap["id"]]
        standing = next(v for v in before["ledger"] if v["claim"]["id"] == "L1")
        assert [v["gates"] for v in mine] == [standing["gates"]] and mine[0]["verdict"] == "verified"
        assert after["four_ledgers"]["memo_includes_promises"] is False
        note = after["four_ledgers"]["promises"]["note"]
        assert RAW_PHONE not in note and "[PHONE_2]" in note  # numbering continues after the contract's own

        # told what the paper says: the gap and its risk go away
        same = client.post(f"/api/jobs/{job}/promises", json={"salary_amount": 1200, "salary_currency": "RM"}).json()
        assert "said_vs_paper" not in [m["type"] for row in same["rows"] for m in row["mismatches"]]
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
        assert not any(v["claim"]["risk_id"] == "L" for v in r["ledger"])
        assert not any(k["rule_id"] == "PB-PROMISE-GAP" for k in r["risks"])
        assert client.post(f"/api/jobs/{job}/promises", json={"salary_amount": 1800}).status_code == 404


def test_the_promise_rule_is_in_no_prompt_while_the_flag_is_off(monkeypatch):
    """The Adversary's prompt lists every active rule: an always-active rule would change its cache key with the flag off."""
    from ain.agents.risk_analyst import load_rules

    rule = next(r for r in load_rules() if r.id == "PB-PROMISE-GAP")
    assert not rule.active({"bd_migration"})
    monkeypatch.setattr(config, "ledger_enabled", lambda: True)
    assert rule.active({"bd_migration"}) and not rule.active({"bd_labour"})


def test_invalid_promises_are_rejected(ledger_on):
    with TestClient(api.app) as client:
        bad = client.post("/api/analyze", data={"sample_id": "control", "promises": json.dumps({"ticket_paid_by": "nobody"})})
        assert bad.status_code == 422
