"""Employer's own policy: contradictions are verified against the policy text, which is redacted like the contract."""

import pytest
from fastapi.testclient import TestClient

from ain import api
from ain.agents import policy_check
from ain.agents.ingestion import segment
from ain.agents.verifier import gate_existence, gate_fidelity
from ain.models import Claim, PackDecision, RouteDecision
from ain.orchestrator import new_job, run_pipeline
from ain.retrieval import CorpusOverlay


async def _run_with_policy(docs, policy_bytes=None):
    contract = (docs / "migrant_sa_contract.txt").read_bytes()
    policy = policy_bytes or (docs / "employer_policy_sample.txt").read_bytes()
    return await run_pipeline(
        new_job("pol"), contract, "migrant_sa_contract.txt", None, "fake", confirm_timeout=0.1, policy=(policy, "handbook.txt")
    )


async def test_contract_is_checked_against_the_employers_own_promises(docs):
    r = await _run_with_policy(docs)
    assert policy_check.POLICY_PACK in r.route.pack_ids
    found = [k for k in r.risks if k.origin == "policy"]
    topics = " ".join(k.title.en for k in found)
    for t in ("recruitment fees", "passports", "ticket home", "end-of-service", "complain"):
        assert t in topics
    for k in found:
        v = next(v for v in r.ledger if v.claim.id == k.claim_ids[0])
        assert v.claim.citation_id.startswith("POLICY-c") and v.verdict == "verified"
        assert v.claim.quote in v.section.text  # the quote really is in the uploaded policy
        assert k.clause_ids and all(c.startswith("C") for c in k.clause_ids)
    assert r.policy is not None and r.policy.clauses


def test_a_made_up_policy_promise_fails_the_gates(docs):
    text = (docs / "employer_policy_sample.txt").read_text(encoding="utf-8")
    secs = policy_check.sections_from_clauses(segment(text), "handbook.txt", "uploaded by the user")
    corpus = CorpusOverlay(api.get_corpus(), secs)
    route = RouteDecision(packs=[PackDecision(pack=policy_check.POLICY_PACK, label="p", reason="t")])
    invented = Claim(id="X.1", risk_id="X", proposition="p", citation_id=secs[1].citation_id, quote="Every worker gets a bonus of SAR 10,000 a year.")
    g1, sec = gate_existence(invented, corpus, route)
    assert g1.status == "pass" and gate_fidelity(invented, sec).status == "warn"
    missing = Claim(id="X.2", risk_id="X", proposition="p", citation_id="POLICY-c99")
    assert gate_existence(missing, corpus, route)[0].status == "fail"
    assert corpus.get("BD-OEMA-2013-s31") is not None  # the statutes are still there


async def test_policy_is_redacted_with_the_same_placeholders_as_the_contract(docs):
    policy = b"WORKER WELFARE POLICY\n\n1. Passports. The passport EC0987654 of the worker remains with the worker at all times.\n"
    r = await _run_with_policy(docs, policy)
    assert "EC0987654" not in r.policy.text and "EC0987654" not in r.document.text
    placeholder = next(red.placeholder for red in r.privacy.redactions if red.kind == "PASSPORT")
    assert placeholder in r.policy.text and placeholder in r.document.text


@pytest.fixture
def client():
    with TestClient(api.app) as c:
        yield c


def test_policy_upload_and_sample_over_http(client, docs):
    samples = {s["id"]: s for s in client.get("/api/samples").json()}
    assert samples["migrant_sa_policy"]["with_policy"] and not samples["migrant_text"]["with_policy"]
    files = {
        "file": ("contract.txt", (docs / "migrant_sa_contract.txt").read_bytes(), "text/plain"),
        "policy": ("handbook.txt", (docs / "employer_policy_sample.txt").read_bytes(), "text/plain"),
    }
    job = client.post("/api/analyze", files=files).json()
    from tests.test_api import _wait

    assert _wait(client, job["job_id"])["status"] == "done"
    r = client.get(f"/api/jobs/{job['job_id']}/result").json()
    assert any(k["origin"] == "policy" for k in r["risks"]) and r["policy"]["clauses"]
    bad = {"file": files["file"], "policy": ("x.exe", b"MZ", "application/octet-stream")}
    assert client.post("/api/analyze", files=bad).status_code == 415
