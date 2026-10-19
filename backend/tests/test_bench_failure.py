"""Graceful failure and the severity rubric. A judge whose call fails on every route gives no opinion and the claim is
flagged for human review; with two or more seats missing the single-judge check decides. The analysis never fails
because a judge could not be reached. Offline, fake LLM."""

from ain.agents import bench
from ain.agents.verifier import _bench_detail, verify_claim
from ain.llm import LLMError
from ain.orchestrator import new_job, run_pipeline
from tests.conftest import RecordingLLM
from tests.test_bench import CLAIM, _risk
from tests.test_bench_ruling import _votes
from tests.test_verifier import ROUTE


class Failing(RecordingLLM):
    """Calls for the given roles fail on every route (optionally only for some tasks)."""

    def __init__(self, roles, tasks=("bench_",), **kw):
        super().__init__(**kw)
        self.roles, self.tasks = set(roles), tasks

    async def json(self, *, role, task, **kw):
        if role in self.roles and task.startswith(self.tasks):
            raise LLMError(f"every route for role '{role}' failed: test")
        return await super().json(role=role, task=task, **kw)


async def test_one_judge_failing_gives_no_opinion_and_flags_human_review(corpus):
    r = await bench.convene(Failing({"bench_b"}), CLAIM, corpus.get("BD-EPZLABOUR-2019-s22"), _risk(), "supports")
    assert r.quorum and r.no_opinion == ["Text (Regal, Justice B)"]
    assert [o.persona for o in r.opinions] == ["happy", "gloomy"]  # the failed seat does not vote
    assert r.majority_verdict == "supports" and r.vote == "2–0 (1 no opinion)"
    assert r.human_review and "Text (Regal, Justice B) gave no opinion" in r.review_reason
    assert "no opinion" in _bench_detail(r)


async def test_a_missing_seat_never_lowers_the_severity(corpus):
    votes = _votes(bench_a=("supports", "medium"), bench_b=("supports", "low"), bench_c=("supports", "high"))
    r = await bench.convene(Failing({"bench_b"}, overrides=votes), CLAIM, corpus.get("BD-EPZLABOUR-2019-s22"), _risk(), "supports")
    assert r.majority_severity == "high"  # the higher of the two remaining opinions


async def test_two_answering_judges_who_disagree_are_split(corpus):
    votes = _votes(bench_a=("supports", "high"), bench_b=("supports", "high"), bench_c=("neutral", "high"))
    r = await bench.convene(Failing({"bench_b"}, overrides=votes), CLAIM, corpus.get("BD-EPZLABOUR-2019-s22"), _risk(), "supports")
    assert r.agreement == "split" and r.majority_verdict == "neutral" and r.vote.startswith("1–1")


async def test_a_failed_review_call_keeps_the_first_opinion(corpus):
    llm = Failing({"bench_c"}, tasks=("bench_review",))
    r = await bench.convene(llm, CLAIM, corpus.get("BD-EPZLABOUR-2019-s22"), _risk(), "supports")
    assert len(r.opinions) == 3 and not r.no_opinion
    assert r.human_review and "review call failed" in r.review_reason


async def test_without_the_chief_justice_the_ruling_is_written_from_the_votes(corpus):
    r = await bench.convene(Failing({"chairman"}), CLAIM, corpus.get("BD-EPZLABOUR-2019-s22"), _risk(), "supports")
    assert r.vote == "3–0" and r.majority_opinion and r.chairman_model.startswith("none")


async def test_two_failed_judges_fall_back_to_the_single_judge_gate(corpus):
    llm = Failing({"bench_a", "bench_c"})
    v = await verify_claim(llm, corpus, ROUTE, CLAIM, _risk(), use_bench=True)
    assert v.bench is not None and not v.bench.quorum and v.bench.agreement == "no_quorum"
    assert v.bench.human_review and len(v.bench.no_opinion) == 2
    g3 = v.gates[2]
    assert "no quorum" in g3.detail and "Single-judge check instead" in g3.detail
    assert any(p["task"] == "entailment" and p["role"] == "judge" for p in llm.payloads)
    assert g3.status == "pass" and v.verdict == "verified"  # the single judge's own result decides


async def test_no_judge_reachable_drops_the_claim_instead_of_failing(corpus):
    v = await verify_claim(Failing({"bench_a", "bench_b", "bench_c", "judge"}, tasks=("bench_", "entailment")), corpus, ROUTE, CLAIM, _risk(), use_bench=True)
    assert v.verdict == "dropped" and "Not checked" in v.gates[2].detail


async def test_a_judge_down_for_the_whole_analysis_never_fails_it(docs):
    name = "rmg_dhaka_epz.txt"
    r = await run_pipeline(new_job(name), (docs / name).read_bytes(), name, llm=Failing({"bench_b"}))
    benched = [k for k in r.risks if k.bench]
    assert benched and all(k.bench.no_opinion == ["Text (Regal, Justice B)"] and k.bench.human_review for k in benched)
    assert r.memo is not None


async def test_two_judges_down_keeps_each_risks_own_severity(docs):
    name = "rmg_dhaka_epz.txt"
    r = await run_pipeline(new_job(name), (docs / name).read_bytes(), name, llm=Failing({"bench_a", "bench_c"}))
    benched = [k for k in r.risks if k.bench]
    assert benched and all(not k.bench.quorum and k.bench.human_review for k in benched)
    assert all(k.severity == k.bench.majority_severity for k in benched)  # no quorum: the risk's own severity is kept


# ------------------------------------------------------------------ severity rubric


async def test_severity_rubric_is_one_text_for_every_judge_and_the_verdict_test_is_unchanged(corpus):
    llm = RecordingLLM()
    await bench.convene(llm, CLAIM, corpus.get("BD-EPZLABOUR-2019-s22"), _risk(), "supports", bench.Options(severity_rubric=True))
    personas = {p.role: p for p in bench.PERSONAS}
    for task in ("bench_opinion", "bench_review"):
        systems = {p["role"]: p["system"] for p in llm.payloads if p["task"] == task}
        assert len(systems) == 3
        for role, s in systems.items():
            p = personas[role]
            assert bench.SEVERITY_RUBRIC in s and bench.VERDICT_TEST in s
            assert "forced-labour indicator" in s and "procedural or documentary" in s
            # the lens and voice stay; the severity lean and the severity stance in peer review go
            assert p.lens in s and p.voice in s and p.disposition not in s and p.review_stance not in s
        # apart from the personality, every judge gets the same prompt
        assert len({s.replace(personas[r].personality(rubric=True), "<P>") for r, s in systems.items()}) == 1
    chair = next(p["system"] for p in llm.payloads if p["task"] == "bench_chair")
    assert "one written rubric" in chair


async def test_without_the_rubric_flag_the_prompts_are_unchanged(corpus):
    llm = RecordingLLM()
    await bench.convene(llm, CLAIM, corpus.get("BD-EPZLABOUR-2019-s22"), _risk(), "supports")
    assert not bench.Options.from_config().severity_rubric
    for p in llm.payloads:
        assert "rubric" not in p["system"]
    opinion = next(p["system"] for p in llm.payloads if p["task"] == "bench_opinion")
    assert bench.SEVERITY_QUESTION in opinion
