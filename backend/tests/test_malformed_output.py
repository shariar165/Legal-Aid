"""A job must never die on malformed model output, while a real outage still fails loudly (offline, fake LLM)."""

import logging

import pytest

from ain.agents import adversary, bench, policy_check
from ain.llm import LLMError, MalformedAnswer, dict_items, str_items, text_of
from ain.orchestrator import new_job, run_pipeline
from tests.conftest import RecordingLLM
from tests.test_bench import CLAIM, _risk

EPZ = "rmg_dhaka_epz.txt"
MODEL_TASKS = ("facts", "risk_check", "adversary", "draft_memo", "policy_check")


class Unusable(RecordingLLM):
    """Every provider answered, but never with a usable object, for the given tasks."""

    def __init__(self, tasks, error=MalformedAnswer, **kw):
        super().__init__(**kw)
        self.tasks, self.error = tasks, error

    async def json(self, *, task, **kw):
        if task.startswith(self.tasks):
            raise self.error(f"{task}: no usable answer")
        return await super().json(task=task, **kw)


async def _run(docs, llm, name=EPZ):
    return await run_pipeline(new_job(name), (docs / name).read_bytes(), name, llm=llm)


def _every_list_is(value):
    return {k: value for k in ("hypotheses", "risks", "claims", "issues", "contradictions", "clause_ids", "digest", "citation_ids")}


@pytest.mark.parametrize(
    "shape",
    [
        pytest.param(_every_list_is(["a plain string", 7, None]), id="lists-of-strings"),
        pytest.param(_every_list_is("not a list"), id="string-instead-of-list"),
        pytest.param(_every_list_is(7), id="number-instead-of-list"),
        pytest.param(_every_list_is(None), id="nulls"),
        pytest.param(_every_list_is([["nested"], {"key": ["unhashable"], "risk_id": ["x"], "claims": "oops", "severity": ["high"], "category": {"a": 1}}]), id="unhashable-fields"),
        pytest.param({}, id="empty-object"),
    ],
)
async def test_the_whole_pipeline_survives_any_shape_of_answer(docs, shape):
    r = await _run(docs, RecordingLLM(overrides={t: shape for t in MODEL_TASKS}))
    assert r.memo and r.citizen and r.stats.claims >= 0


async def test_plain_string_claims_are_skipped_with_a_warning_and_good_ones_kept(docs, monkeypatch, caplog):
    """The live crash: a grounding answer whose `claims` were plain strings."""
    real = adversary._fake_ground

    def strings(keys):
        out = real(keys)
        first, *rest = out["risks"]
        first["claims"] = ["Section 27 voids this clause.", *first["claims"]]
        for g in rest[:1]:
            g["claims"] = ["Only a plain string, no citation."]
        return out

    monkeypatch.setattr(adversary, "_fake_ground", strings)
    with caplog.at_level(logging.WARNING, logger="ain.llm"):
        r = await _run(docs, RecordingLLM())
    kept = [k for k in r.risks if k.origin == "adversary"]
    assert kept and all(k.claim_ids for k in kept)  # the risk with good claims stays; the one with none is not shown
    assert "adversary claims for" in caplog.text and "malformed" in caplog.text
    assert r.memo


async def test_a_malformed_quote_never_reaches_a_claim(docs, monkeypatch):
    real = adversary._fake_ground

    def bad_quote(keys):
        out = real(keys)
        for g in out["risks"]:
            for c in g["claims"]:
                c["quote"] = ["not", "a", "string"]
        return out

    monkeypatch.setattr(adversary, "_fake_ground", bad_quote)
    r = await _run(docs, RecordingLLM())
    assert all(v.claim.quote is None for v in r.ledger if v.claim.origin == "adversary")


@pytest.mark.parametrize("task", ["facts", "risk_check", "adversary", "draft_memo"])
async def test_an_unusable_answer_from_one_agent_does_not_sink_the_job(docs, task):
    r = await _run(docs, Unusable((task,)))
    assert r.memo.issues


async def test_an_unconfirmed_rule_keeps_its_risk_rather_than_hiding_it(docs):
    baseline = await _run(docs, RecordingLLM())
    r = await _run(docs, Unusable(("risk_check",)))
    playbook = lambda x: {k.rule_id for k in x.risks if k.origin == "playbook"}  # noqa: E731
    assert playbook(r) == playbook(baseline)


async def test_a_malformed_policy_answer_shows_no_unverified_contradiction():
    risks, claims = await policy_check.run(Unusable(("policy_check",)), [], [], lambda t: t, start=1, source_label="own policy")
    assert risks == [] and claims == []


async def test_a_judge_with_a_malformed_answer_gives_no_opinion_never_a_vote(corpus):
    llm = Unusable(("bench_opinion",))
    r = await bench.convene(llm, CLAIM, corpus.get("BD-EPZLABOUR-2019-s22"), _risk(), "supports")
    assert r.opinions == [] and not r.quorum and r.human_review


async def test_a_real_outage_still_fails_loudly(docs):
    """A clean-looking report after an outage would be worse than an error."""
    with pytest.raises(LLMError):
        await _run(docs, Unusable(("risk_check",), error=LLMError))


def test_the_helpers_keep_only_what_the_schema_promised(caplog):
    with caplog.at_level(logging.WARNING, logger="ain.llm"):
        assert dict_items([{"a": 1}, "x", 2], "t") == [{"a": 1}]
        assert dict_items("nope", "t") == []
    assert dict_items(None, "t") == [] and "skipped 2 of 3" in caplog.text
    assert str_items(["a", ["b"], "", {"c": 1}, 3]) == ["a"] and str_items("a") == []
    assert text_of("x") == "x" and text_of(["x"], "d") == "d" and text_of("  ", "d") == "d"
