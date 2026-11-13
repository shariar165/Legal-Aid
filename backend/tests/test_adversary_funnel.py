"""Where Adversarial Counsel lost risks in the live eval (spec 18): a grounding batch that came back without some of its
hypotheses, a calculator risk it could not see, and a restatement that only showed once the claims were verified."""

import re

from ain.agents import adversary, critic
from ain.models import Claim, L10n, Risk, Verification
from ain.orchestrator import new_job, run_pipeline
from tests.conftest import RecordingLLM

EPZ = "rmg_dhaka_epz.txt"


def keys_of(user: str) -> list[str]:
    return re.findall(r"^HYPOTHESIS (\S+):", user, re.M)


async def _run(docs, name, llm):
    return await run_pipeline(new_job(name), (docs / name).read_bytes(), name, llm=llm)


def _adversary_ids(result) -> list[str]:
    return sorted(k.title.en for k in result.risks if k.origin == "adversary")


async def test_hypotheses_a_grounding_batch_left_out_are_asked_again_one_at_a_time(docs, monkeypatch):
    normal = await _run(docs, EPZ, RecordingLLM())
    monkeypatch.setattr(adversary, "_ground_batches", lambda c: [list(c)])  # every hypothesis in one batch

    def ground(role, user):
        keys = keys_of(user)
        return {"risks": []} if len(keys) > 1 else adversary._fake_ground(keys)  # live: one batch came back empty

    llm = RecordingLLM(overrides={"adversary_ground": ground})
    result = await _run(docs, EPZ, llm)
    asked = [keys_of(p["user"]) for p in llm.payloads if p["task"] == "adversary_ground"]
    assert len(asked[0]) > 1 and all(len(k) == 1 for k in asked[1:]) and sorted(sum(asked[1:], [])) == sorted(asked[0])
    assert _adversary_ids(result) == _adversary_ids(normal), "nothing is lost to the empty batch"
    assert any("asking again one at a time" in e.message for e in result.trace)


async def test_a_hypothesis_the_model_did_answer_is_not_asked_again(docs, monkeypatch):
    monkeypatch.setattr(adversary, "_ground_batches", lambda c: [list(c)])
    llm = RecordingLLM(overrides={"adversary_ground": lambda role, user: {"risks": [{"key": k, "keep": False} for k in keys_of(user)]}})
    result = await _run(docs, EPZ, llm)
    assert sum(p["task"] == "adversary_ground" for p in llm.payloads) == 1
    assert not any(k.origin == "adversary" for k in result.risks), "keep: false is an answer, and it stands"


async def test_the_adversary_is_told_about_the_calculator_risks(docs):
    llm = RecordingLLM()
    result = await _run(docs, "migrant_my_contract.txt", llm)
    calc = [k for k in result.risks if k.origin == "calculator"]
    assert calc, "the Malaysia sample has wage risks"
    prompt = next(p["user"] for p in llm.payloads if p["task"].startswith("adversary_hyp"))
    flagged = prompt.split("ALREADY FLAGGED:", 1)[1].split("PLAYBOOK RULES", 1)[0]
    for k in calc:
        assert f"- {k.rule_id or k.id} [{', '.join(k.clause_ids)}] {k.title.en}" in flagged


def _risk(rid, origin, clauses, rule=None):
    return Risk(id=rid, rule_id=rule, origin=origin, category="x", title=L10n(en=rid, bn=rid), severity="high", clause_ids=clauses,
                finding="", citizen_line=L10n(en="", bn=""), action=L10n(en="", bn=""))


def _v(rid, cid, verdict):
    return Verification(claim=Claim(id=f"{rid}.{cid}", risk_id=rid, proposition="p", citation_id=cid), gates=[], verdict=verdict)


def test_an_adversary_risk_standing_only_on_a_playbook_risks_law_is_withdrawn():
    # the live Saudi shape: R8 "no medical insurance" lost its own claim and kept only the return-ticket article
    ticket = _risk("R4", "playbook", ["C7"], "PB-RETURN-TICKET")
    insurance = _risk("R8", "adversary", ["C3", "C7"])
    iqama = _risk("R7", "adversary", ["C6"])  # the same article, but on a clause no playbook risk is about: a risk of its own
    consular = _risk("R9", "adversary", ["C5", "C9"])
    passport = _risk("R1", "playbook", ["C5"], "PB-PASSPORT")
    ledger = [
        _v("R4", "SA-LABOR-2005-a40", "partial"), _v("R1", "BD-OEMA-2013-s31", "verified"),
        _v("R8", "SA-LABOR-2005-a40", "partial"), _v("R8", "BD-OEMA-2013-s24", "dropped"),
        _v("R7", "SA-LABOR-2005-a40", "partial"),
        _v("R9", "BD-OEMA-2013-s31", "partial"), _v("R9", "BD-OEMA-2013-s29", "verified"),  # one law of its own
    ]
    out = critic.restated_after_verification([ticket, insurance, iqama, consular, passport], ledger)
    assert [(r.id, dup) for r, dup in out] == [("R8", "PB-RETURN-TICKET")]


def test_the_safety_net_never_withdraws_a_playbook_risk_or_an_unverified_one():
    deductions = _risk("R6", "calculator", ["C4"], "PB-DEDUCTION-CAP")
    housing = _risk("R10", "adversary", ["C4"])
    ledger = [_v("R6", "SA-LABOR-2005-a93", "partial"), _v("R10", "SA-LABOR-2005-a93", "dropped")]
    assert critic.restated_after_verification([deductions, housing], ledger) == []
    housing2 = _risk("R10", "adversary", ["C4"])
    ledger2 = [_v("R6", "SA-LABOR-2005-a93", "partial"), _v("R10", "SA-LABOR-2005-a93", "verified")]
    assert [(r.id, d) for r, d in critic.restated_after_verification([deductions, housing2], ledger2)] == [("R10", "PB-DEDUCTION-CAP")]


async def test_a_withdrawn_restatement_is_dropped_and_traced(docs, monkeypatch):
    llm = RecordingLLM()
    first = await _run(docs, EPZ, llm)
    target = next(k for k in first.risks if k.origin == "adversary" and k.status != "dropped")
    monkeypatch.setattr(critic, "restated_after_verification", lambda risks, ledger: [(next(r for r in risks if r.title.en == target.title.en), "PB-X")])
    result = await _run(docs, EPZ, RecordingLLM())
    k = next(r for r in result.risks if r.title.en == target.title.en)
    assert k.status == "dropped"
    ev = next(e for e in result.trace if e.type == "hypothesis_dropped" and e.agent == "Critic")
    assert "restates PB-X once verified" in ev.message
