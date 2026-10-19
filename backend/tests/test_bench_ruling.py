"""Virtual Bench ruling (council ruling of 2026-10-19): lens labels, the optional no-leans prompt, split/spread rules for
human review, the model that actually answered, and the "same family (fallback)" mark. Offline, fake LLM."""

from ain.agents import bench
from ain.agents.verifier import _bench_detail
from tests.conftest import RecordingLLM
from tests.test_bench import CLAIM, _risk

ANSWERED = {"bench_a": "qwen/qwen3.8-27b", "bench_b": "openai/gpt-oss-20b", "bench_c": "openai/gpt-oss-120b", "chairman": "openai/gpt-oss-120b"}


class AnsweredBy(RecordingLLM):
    """Fake answers, but reported as coming from Groq backups (as after an OpenRouter quota fallback)."""

    async def json(self, *, role, info=None, **kw):
        out = await super().json(role=role, info=info, **kw)
        if info is not None:
            info.update(provider="groq", model=ANSWERED[role], fallback=role != "chairman")
        return out


def _votes(**by_role):
    """Override: each seat answers (verdict, severity)."""

    def answer(role, user):
        v, s = by_role[role]
        return {"verdict": v, "severity": s, "reasoning": "r"}

    return {"bench_opinion": answer, "bench_review": answer}


async def test_each_opinion_records_the_model_that_actually_answered(corpus):
    r = await bench.convene(AnsweredBy(), CLAIM, corpus.get("BD-EPZLABOUR-2019-s22"), _risk(), "supports")
    assert [o.model for o in r.opinions] == [ANSWERED["bench_a"], ANSWERED["bench_b"], ANSWERED["bench_c"]]
    assert all(o.fallback for o in r.opinions) and r.chairman_model == ANSWERED["chairman"]


async def test_a_fallback_into_one_family_is_marked_in_ruling_and_ledger(corpus):
    r = await bench.convene(AnsweredBy(), CLAIM, corpus.get("BD-EPZLABOUR-2019-s22"), _risk(), "supports")
    assert r.same_family == ["Text (Regal, Justice B)", "Enforcement (Grey, Justice C)"]
    assert "Same family (fallback): Text (Regal, Justice B) and Enforcement (Grey, Justice C)." in _bench_detail(r)
    # on their configured models the three seats are three families: no mark
    r = await bench.convene(RecordingLLM(), CLAIM, corpus.get("BD-EPZLABOUR-2019-s22"), _risk(), "supports")
    assert r.same_family == [] and "Same family" not in _bench_detail(r)


def test_lens_labels_come_first_and_titles_are_softened():
    assert [(p.lens_label, p.name) for p in bench.PERSONAS] == [("Remedies", "Sunny"), ("Text", "Regal"), ("Enforcement", "Grey")]
    assert bench.BY_ID["happy"].title == "the Constructive AI" and bench.BY_ID["happy"].label == "Remedies (Sunny, Justice A)"
    assert bench.BY_ID["proud"].tagline == "The words decide, so I read them closely."


async def test_no_leans_drops_only_the_severity_lean(corpus):
    llm = RecordingLLM()
    await bench.convene(llm, CLAIM, corpus.get("BD-EPZLABOUR-2019-s22"), _risk(), "supports", bench.Options(leans=False))
    personas = {p.role: p for p in bench.PERSONAS}
    for task in ("bench_opinion", "bench_review"):
        systems = {p["role"]: p["system"] for p in llm.payloads if p["task"] == task}
        for role, s in systems.items():
            p = personas[role]
            assert p.disposition not in s and "one notch" not in s
            assert p.lens in s and p.voice in s and p.review_stance in s
        # still one neutral verdict test, identical for every judge
        assert len({s.replace(personas[r].personality(False), "<P>") for r, s in systems.items()}) == 1
    assert bench.Options.from_config().leans  # the lean stays until the eval says otherwise


async def test_a_one_one_one_verdict_split_is_split_never_majority(corpus):
    llm = RecordingLLM(overrides=_votes(bench_a=("supports", "high"), bench_b=("neutral", "high"), bench_c=("contradicts", "high")))
    r = await bench.convene(llm, CLAIM, corpus.get("BD-EPZLABOUR-2019-s22"), _risk(), "supports")
    assert r.agreement == "split" and r.vote == "1–1–1"
    assert r.majority_verdict != "supports"  # one judge in three is not a majority for the entailment gate
    assert r.human_review and "split" in r.review_reason and "majority" not in r.majority_opinion.lower().replace("no majority", "")
    assert _bench_detail(r).startswith("Virtual Bench split 1–1–1")


async def test_human_review_on_verdict_split_or_wide_severity_spread_only(corpus):
    sec, opts = corpus.get("BD-EPZLABOUR-2019-s22"), bench.Options(review_on_wide_spread=True)

    async def rule(a, b, c, o=opts):
        llm = RecordingLLM(overrides=_votes(bench_a=a, bench_b=b, bench_c=c))
        return await bench.convene(llm, CLAIM, sec, _risk(), "supports", o)

    one_notch = await rule(("supports", "medium"), ("supports", "high"), ("supports", "high"))
    assert not one_notch.human_review and one_notch.severity_range == "medium–high" and one_notch.agreement == "unanimous"
    two_notches = await rule(("supports", "low"), ("supports", "high"), ("supports", "high"))
    assert two_notches.human_review and "2 notches" in two_notches.review_reason and two_notches.severity_range is None
    verdict_split = await rule(("supports", "high"), ("supports", "high"), ("neutral", "high"))
    assert verdict_split.human_review and verdict_split.agreement == "majority" and "verdicts differ" in verdict_split.review_reason
    # flag off (today's default): any disagreement, even one notch, still asks for a human
    legacy = await rule(("supports", "medium"), ("supports", "high"), ("supports", "high"), bench.Options())
    assert legacy.human_review and legacy.severity_range == "medium–high"
