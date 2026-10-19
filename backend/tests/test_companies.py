"""Named employers: the contract is checked against the company's own published policy."""

from datetime import date

from ain import companies
from ain.agents.verifier import gate_currency
from ain.orchestrator import new_job, run_pipeline

# A made-up contract for the test only; it is not a real document of the company.
CONTRACT = """EMPLOYMENT CONTRACT

1. Employer. Top Glove Sdn. Bhd., Klang, Selangor, Malaysia employs the Worker as a production operator.

2. Salary. A basic salary of RM 1,800 per month.

3. Deductions. The Worker agrees that recruitment, visa and agency costs of RM 3,000 shall be deducted from his salary at RM 250 per month.

4. Passport. The Worker shall surrender his passport to the Employer for safekeeping during the contract.
"""


def test_registry_quotes_only_the_companies_own_documents(corpus):
    cos = companies.load_companies()
    assert {c.slug for c in cos} >= {"ioi", "topglove"}
    for c in cos:
        secs = [s for s in corpus.sections if c.pack in s.packs]
        assert secs, c.slug
        for s in secs:
            assert s.kind == "company_policy" and s.jurisdiction == "COMPANY"
            assert s.url == c.policy_url and s.url.startswith("https://")
            assert any("published" in n for n in s.amendment_notes)


def test_detects_named_employer_on_whole_words():
    assert companies.detect("Employer: IOI Plantation Services Sdn Bhd, Sabah").slug == "ioi"
    assert companies.detect("employed by TOP GLOVE CORPORATION BHD").slug == "topglove"
    assert companies.detect("Atop Glovemaker Sdn Bhd and Ioio Trading") is None


def test_old_published_policies_ask_for_a_recheck(corpus):
    sec = next(s for s in corpus.sections if s.jurisdiction == "COMPANY")
    assert companies.is_stale("2020-01-01") and not companies.is_stale(date.today().isoformat())
    assert gate_currency(sec.model_copy(update={"retrieved_at": "2020-01-01"})).status == "warn"
    assert gate_currency(sec.model_copy(update={"retrieved_at": date.today().isoformat()})).status == "pass"


async def test_contract_naming_a_company_is_checked_against_its_published_policy():
    r = await run_pipeline(new_job("co"), CONTRACT.encode(), "contract.txt", None, "fake", confirm_timeout=0.1)
    assert "co_topglove" in r.route.pack_ids
    found = [k for k in r.risks if k.origin == "policy"]
    cited = {v.claim.citation_id: v for v in r.ledger if v.claim.risk_id in {k.id for k in found}}
    assert {"CO-TOPGLOVE-s1.2", "CO-TOPGLOVE-s2"} <= set(cited)
    assert all(v.verdict == "verified" for v in cited.values())
    assert all("published policy" in k.finding and "says otherwise" in k.finding for k in found)
