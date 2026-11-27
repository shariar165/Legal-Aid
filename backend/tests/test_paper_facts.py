"""The four paper facts the Four Ledgers read (contract term, hours, ticket, passport): regex only, per clause and per
sentence, with the clause they came from. An ambiguous reading gives None, never a guess. Spec 20, backend round."""

import pytest

from ain.agents import ingestion


def _facts(text: str):
    return ingestion.extract_facts(text, ingestion.segment(text))


def _doc(*clauses: str) -> str:
    return "\n\n".join(f"{i}. {c}" for i, c in enumerate(clauses, 1))


# ---------------------------------------------------------------- contract term


def test_a_probation_period_is_not_the_contract_term():
    f = _facts(_doc("Probation. A probation period of three (3) months applies.", "Term. The term of this Contract is two (2) years."))
    assert f.contract_months == 24 and f.fact_clauses["contract_months"] == "C2"


def test_a_notice_period_is_not_the_contract_term():
    f = _facts(_doc("Notice. Either party may end this Contract with a notice period of 1 month."))
    assert f.contract_months is None and "contract_months" not in f.fact_clauses


def test_a_period_after_the_term_is_not_the_term():
    f = _facts(_doc('"Contract Term" means two (2) years from arrival.',
                    "Confidentiality applies during the Contract Term and for three (3) years afterwards."))
    assert f.contract_months == 24


def test_two_different_terms_give_none():
    f = _facts(_doc("Term. The term of this Contract is two (2) years.", "Duration. The period of employment is three (3) years."))
    assert f.contract_months is None


# ---------------------------------------------------------------- hours


def test_an_overtime_limit_is_not_the_working_day():
    f = _facts(_doc("Hours. Overtime shall not exceed 2 hours per day. Normal working hours are 8 hours per day."))
    assert f.hours_per_day == 8 and f.fact_clauses["hours_per_day"] == "C1"


def test_ramadan_hours_are_not_the_working_day():
    f = _facts(_doc("Normal working hours are eight (8) hours per day, reduced to six (6) hours per day during Ramadan."))
    assert f.hours_per_day == 8


def test_two_working_days_give_none():
    f = _facts(_doc("Hours. Working hours are 8 hours per day.", "Site work. Working hours are 10 hours per day."))
    assert f.hours_per_day is None


# ---------------------------------------------------------------- passport


@pytest.mark.parametrize("text", [
    "Passport. The passport shall remain in the Worker's own custody.",
    "Passport. The Worker shall keep his passport. A security deposit of RM 500 is payable.",
    "Passport. The Employer shall not keep or hold the Worker's passport.",
])
def test_the_worker_keeps_the_passport(text):
    f = _facts(_doc(text))
    assert f.passport_held_by == "worker" and f.fact_clauses["passport"] == "C1"


@pytest.mark.parametrize("text", [
    "Passport. Upon arrival the Worker shall surrender his passport to the Employer, to be kept in the Employer's custody.",
    "Passport. On arrival the Worker shall hand over his passport to the Employer, who shall keep it in safe custody.",
    "Passport. The Worker shall deposit his passport with the Company, which shall keep it in safe custody.",
])
def test_the_employer_keeps_the_passport(text):
    assert _facts(_doc(text)).passport_held_by == "employer"


def test_conflicting_passport_clauses_give_none():
    f = _facts(_doc("Passport. The Employer shall keep the Worker's passport.", "Documents. The Worker shall retain his passport at all times."))
    assert f.passport_held_by is None


# ---------------------------------------------------------------- ticket


def test_a_return_ticket_is_not_the_ticket_out():
    f = _facts(_doc("Travel. The Employer shall provide the air ticket from Dhaka to Riyadh.",
                    "Repatriation. The Worker shall bear the cost of his own return ticket to Bangladesh."))
    assert f.ticket_paid_by == "employer" and f.fact_clauses["ticket"] == "C1"


def test_conflicting_ticket_clauses_give_none():
    f = _facts(_doc("Travel. The Employer shall pay the air ticket to Malaysia.", "Costs. The Worker shall bear the cost of his air ticket."))
    assert f.ticket_paid_by is None


# ---------------------------------------------------------------- the samples


def test_the_samples_give_their_facts_with_clause_ids(docs):
    _, my, _ = ingestion.build_document((docs / "migrant_my_contract.txt").read_bytes(), "migrant_my_contract.txt", "sample")
    assert (my.contract_months, my.hours_per_day, my.ticket_paid_by, my.passport_held_by) == (36, 12, "worker", "employer")
    assert my.fact_clauses == {"salary": "C3", "contract_months": "C2", "passport": "C5", "hours_per_day": "C6", "ticket": "C7"}
    _, msa, _ = ingestion.build_document((docs / "long_migrant_msa.txt").read_bytes(), "long_migrant_msa.txt", "sample")
    assert (msa.contract_months, msa.hours_per_day, msa.ticket_paid_by, msa.passport_held_by) == (24, 8, "employer", "employer")
    assert (msa.hours_per_week, my.hours_per_week) == (48, None)  # "six (6) days per week" states no weekly hours
