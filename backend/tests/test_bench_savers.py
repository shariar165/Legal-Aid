"""Virtual Bench OpenRouter quota savers (flags in ain/config.yaml `bench:`): review only on disagreement, batched
judges with a quote check, and the statute window. Offline, fake LLM."""

import re
from collections import Counter

from ain import config, llm as llm_mod
from ain.agents import bench
from ain.models import Claim
from tests.conftest import RecordingLLM
from tests.test_bench import CLAIM, _risk

CLAIMS = [
    ("R1.1", "BD-EPZLABOUR-2019-s22", "Permanent workers must get 120 days' notice."),
    ("R2.1", "BD-EPZLABOUR-2019-s30", "Women workers get 8 weeks of maternity benefit before and after delivery."),
    ("R3.1", "BD-CONTRACT-1872-s27", "Agreements in restraint of trade are void."),
    ("R4.1", "BD-CONTRACT-1872-s28", "Agreements limiting the time to sue are void."),
]


def _items(corpus, n=4):
    out = []
    for cid, sec_id, prop in CLAIMS[:n]:
        c = Claim(id=cid, risk_id=cid.split(".")[0], proposition=prop, citation_id=sec_id)
        out.append((c, corpus.get(sec_id), _risk(), "supports"))
    return out


def test_quota_savers_are_off_by_default_and_leave_prompts_unchanged(corpus):
    opts = bench.Options.from_config()
    assert not (opts.review_only_on_disagreement or opts.batch or opts.statute_window)
    sec = corpus.get("MY-EA-1955-s24")  # longer than any window: without the flag the judges read all of it
    assert bench.statute_text(sec, "query", opts) == sec.text
    assert bench.Case(CLAIM, sec, _risk(), "supports", sec.text).prompt == bench._case(CLAIM, sec, _risk())


# ------------------------------------------------------------------ review only on disagreement


async def test_review_is_skipped_only_when_verdict_and_severity_agree(corpus):
    opts = bench.Options(review_only_on_disagreement=True)
    llm = RecordingLLM()
    [r] = await bench.convene_many(llm, _items(corpus, 1), opts)
    assert not r.peer_review and r.vote == "3–0"
    assert not [p for p in llm.payloads if p["task"] == "bench_review"]
    # same verdict, different severity (Sunny reads a contract clash one notch lower): the review still runs
    llm = RecordingLLM()
    c, s, _, fv = _items(corpus, 1)[0]
    [r] = await bench.convene_many(llm, [(c, s, _risk("valid_abroad_void_bd", "high"), fv)], opts)
    assert r.peer_review and len([p for p in llm.payloads if p["task"] == "bench_review"]) == 3


# ------------------------------------------------------------------ batched judges


async def test_batch_asks_each_judge_once_for_up_to_four_claims_in_its_own_order(corpus):
    llm = RecordingLLM()
    stats = Counter()
    results = await bench.convene_many(llm, _items(corpus), bench.Options(batch=True), stats)
    assert [r.question for r in results] == [p for _, _, p in CLAIMS]
    for task in ("bench_opinion_batch", "bench_review_batch"):
        calls = [p for p in llm.payloads if p["task"] == task]
        assert len(calls) == 3 and all(p["user"].count("=== CASE C") == 4 for p in calls)
    assert not [p for p in llm.payloads if p["task"] in ("bench_opinion", "bench_review")]
    orders = {tuple(re.findall(r"PROPOSITION: (.+)", p["user"])) for p in llm.payloads if p["task"] == "bench_opinion_batch"}
    assert len(orders) > 1  # the judges do not all see the claims in the same order
    assert stats["batch_answers_ok"] == 24 and stats["batch_reruns"] == 0


def test_batch_prompts_keep_the_verdict_test_identical():
    personas = {p.role: p for p in bench.PERSONAS}
    for template in (bench.JUDGE_BATCH_SYSTEM, bench.REVIEW_BATCH_SYSTEM):
        systems = {p.role: bench.system_prompt(template, p, 4) for p in bench.PERSONAS}
        assert len({s.replace(personas[r].personality(), "<P>") for r, s in systems.items()}) == 1
        assert all(bench.VERDICT_TEST in s and s.index(bench.VERDICT_TEST) < s.index("PERSONALITY") for s in systems.values())


def _batch_answer(quote_for):
    """A batched answer whose quote for each case is `quote_for(case_label, own_text, all_texts)`."""

    def answer(role, user):
        blocks = re.findall(r"=== CASE (C\d) ===\n.*?TEXT:\n(.*?)\n\nPROPOSITION", user, re.S)
        texts = dict(blocks)
        return {"opinions": [{"case": lab, "quote": quote_for(lab, t, texts), "verdict": "supports", "severity": "high", "reasoning": "r"} for lab, t in blocks]}

    return answer


async def test_batch_answer_quoting_another_cases_text_is_rerun_alone(corpus):
    def quote(lab, own, texts):
        if lab == "C2":  # this answer quotes C1's statute: it may be judging the wrong case
            own = texts["C1"]
        return " ".join(own.split()[:8])

    llm = RecordingLLM(overrides={"bench_opinion_batch": _batch_answer(quote)})
    stats = Counter()
    await bench.convene_many(llm, _items(corpus), bench.Options(batch=True), stats)
    singles = [p for p in llm.payloads if p["task"] == "bench_opinion"]
    assert len(singles) == 3 and stats["batch_bad_quote"] == 3 and stats["batch_reruns"] == 3  # once per judge
    assert all(p["user"].count("PROPOSITION:") == 1 for p in singles)


async def test_batch_with_bad_json_or_missing_ids_falls_back_to_single_calls(corpus):
    for broken, counter in (({"verdict": "supports"}, "batch_bad_json"), ({"opinions": []}, "batch_missing_id")):
        llm = RecordingLLM(overrides={"bench_opinion_batch": broken})
        stats = Counter()
        results = await bench.convene_many(llm, _items(corpus), bench.Options(batch=True), stats)
        assert len([p for p in llm.payloads if p["task"] == "bench_opinion"]) == 12
        assert stats[counter] and all(r.majority_verdict == "supports" for r in results)


def test_quote_check_is_exact_but_tolerates_spacing_case_and_ellipsis(corpus):
    text = corpus.get("BD-CONTRACT-1872-s27").text
    assert bench.quote_in("restrained from exercising a lawful profession", text)
    assert bench.quote_in("RESTRAINED  from exercising ... is to that extent void", text)
    assert not bench.quote_in("restrained from exercising an unlawful profession", text)
    assert not bench.quote_in("void", text)  # too short to tell which text it came from
    bn = corpus.get("BD-EPZLABOUR-2019-s30").text
    assert bench.quote_in("তবে শর্ত থাকে যে, কোনো মহিলা শ্রমিক", bn)


async def test_pipeline_sends_all_bench_claims_to_one_batched_sitting(docs, monkeypatch):
    from ain.orchestrator import new_job, run_pipeline

    monkeypatch.setattr(bench.Options, "from_config", classmethod(lambda cls: bench.Options(batch=True)))
    llm = RecordingLLM()
    name = "rmg_dhaka_epz.txt"
    r = await run_pipeline(new_job(name), (docs / name).read_bytes(), name, llm=llm)
    benched = [v for v in r.ledger if v.bench]
    assert len(benched) > 1
    n = len(benched)  # chunks of four; a lone leftover claim runs as a normal single call
    assert len([p for p in llm.payloads if p["task"] == "bench_opinion_batch"]) == 3 * (n // 4 + (n % 4 > 1))


# ------------------------------------------------------------------ statute window


def test_statute_window_keeps_provisos_and_whole_sub_sections(corpus):
    sec = corpus.get("BD-EPZLABOUR-2019-s30")
    assert bench.window(sec.text, "maternity", 5000) == sec.text  # short enough: untouched
    assert "তবে শর্ত থাকে যে" in bench.window(sec.text, "maternity benefit", 300)  # the proviso survives a tight limit
    long = corpus.get("MY-EA-1955-s24")
    w = bench.window(long.text, "total deductions in any one month shall not exceed fifty per centum", 1500)
    assert len(w) < len(long.text) and "[...]" in w
    assert w.startswith("24. (1) No deductions") and "(8) The total of any amounts deducted" in w
    flat = " ".join(long.text.split())
    pieces = [p for p in w.split("\n") if p != "[...]"]
    assert all(" ".join(p.split()) in flat for p in pieces)  # verbatim pieces only
    assert all(p.rstrip().endswith(bench._CLAUSE_END) for p in pieces)  # never stops mid-sentence
    # a list item is never shown without the lead-in sentence it completes
    assert "(c) deductions for the recovery of advances" not in w or "(2) It shall be lawful" in w


def test_statute_window_finishes_a_sentence_that_runs_into_the_next_unit(corpus):
    sec = corpus.get("BD-CONTRACT-1872-s25")
    w = bench.window(sec.text, "agreement without consideration void", 1500)
    for m in bench.PROVISO.finditer(sec.text):
        assert " ".join(sec.text[m.start(): m.end() + 12].split()) in " ".join(w.split())


def test_statute_window_never_loses_a_proviso_anywhere_in_the_corpus(corpus):
    for sec in corpus.sections:
        w = bench.window(sec.text, sec.heading, 1500)
        if w == sec.text:
            continue
        flat_w, flat_t = " ".join(w.split()), " ".join(sec.text.split())
        assert all(" ".join(p.split()) in flat_t for p in w.split("\n") if p != "[...]"), sec.citation_id
        for m in bench.PROVISO.finditer(sec.text):
            assert " ".join(sec.text[m.start(): m.end() + 12].split()) in flat_w, (sec.citation_id, m.group(0))


async def test_window_flag_trims_what_the_judges_see(corpus):
    llm = RecordingLLM()
    sec = corpus.get("MY-EA-1955-s24")
    c = Claim(id="R1.1", risk_id="R1", proposition="Total deductions may not exceed fifty per cent of monthly wages.", citation_id=sec.citation_id)
    stats = Counter()
    await bench.convene_many(llm, [(c, sec, _risk(), "supports")], bench.Options(statute_window=True), stats)
    [p, *_] = [x for x in llm.payloads if x["task"] == "bench_opinion"]
    assert "[...]" in p["user"] and stats["statute_trimmed"] == 1


# ------------------------------------------------------------------ fallback families


def test_model_family_names():
    assert config.model_family("qwen/qwen3.8-27b") == "qwen"
    assert config.model_family("openai/gpt-oss-120b") == config.model_family("openai/gpt-oss-20b") == "gpt-oss"
    assert config.model_family("meta-llama/llama-3.3-70b-instruct:free") == config.model_family("llama-3.3-70b-versatile") == "llama"
    assert config.model_family("google/gemma-4-31b-it:free") == "gemma"


def test_ablation_stays_on_the_reasoners_model():
    plain, reasoner = config.role("plain"), config.role("reasoner")
    assert (plain.provider, plain.model) == (reasoner.provider, reasoner.model)
