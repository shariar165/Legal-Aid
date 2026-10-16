from ain.agents import bench
from ain.models import Claim, L10n, Risk
from tests.conftest import RecordingLLM


def _risk(category="labour_standard", severity="high"):
    return Risk(id="R1", origin="playbook", category=category, title=L10n(bn="x", en="x"), severity=severity,
                finding="Notice is 30 days for Ms. [NAME_1].", citizen_line=L10n(bn="x", en="x"), action=L10n(bn="x", en="x"))


CLAIM = Claim(id="R1.1", risk_id="R1", proposition="Permanent workers must get 120 days' notice.", citation_id="BD-EPZLABOUR-2019-s22")


async def test_unanimous_bench_has_no_dissent(corpus):
    r = await bench.convene(RecordingLLM(), CLAIM, corpus.get("BD-EPZLABOUR-2019-s22"), _risk(), "supports")
    assert r.vote == "3–0" and r.dissent is None and not r.human_review
    assert r.majority_verdict == "supports" and r.majority_severity == "high"


async def test_dissent_flags_human_review(corpus):
    def by_seat(role, user):
        return {"verdict": "neutral" if role == "bench_c" else "supports", "severity": "high", "reasoning": "r"}

    llm = RecordingLLM(overrides={"bench_opinion": by_seat, "bench_review": by_seat})
    r = await bench.convene(llm, CLAIM, corpus.get("BD-EPZLABOUR-2019-s22"), _risk(), "supports")
    assert r.majority_verdict == "supports" and r.vote == "2–1"
    assert r.human_review and r.dissent
    assert {o.seat for o in r.opinions} == {"Justice A", "Justice B", "Justice C"}
    assert [(o.persona, o.name) for o in r.opinions] == [("happy", "Sunny"), ("proud", "Regal"), ("gloomy", "Grey")]
    assert "Grey (Justice C)" in r.dissent


async def test_each_judge_has_its_own_personality(corpus):
    llm = RecordingLLM()
    await bench.convene(llm, CLAIM, corpus.get("BD-EPZLABOUR-2019-s22"), _risk(), "supports")
    for task in ("bench_opinion", "bench_review"):
        systems = {p["role"]: p["system"] for p in llm.payloads if p["task"] == task}
        assert "Sunny, the Happy AI" in systems["bench_a"]
        assert "Regal, the Proud AI" in systems["bench_b"]
        assert "Grey, the Gloomy AI" in systems["bench_c"]
        assert all("Decide ONLY from the statute text" in s or "do not use outside" in s for s in systems.values())


async def test_happy_member_reads_contract_clashes_leniently(corpus):
    r = await bench.convene(RecordingLLM(), CLAIM, corpus.get("BD-EPZLABOUR-2019-s22"), _risk("valid_abroad_void_bd", "high"), "supports")
    sev = {o.persona: o.severity for o in r.opinions}
    assert sev == {"happy": "medium", "proud": "high", "gloomy": "high"}
    assert r.majority_severity == "high" and r.vote == "2–1" and r.human_review


async def test_judges_see_only_statute_claim_and_redacted_finding(corpus):
    llm = RecordingLLM()
    sec = corpus.get("BD-EPZLABOUR-2019-s22")
    await bench.convene(llm, CLAIM, sec, _risk(), "supports")
    first = [p for p in llm.payloads if p["task"] == "bench_opinion"]
    assert len(first) == 3
    for p in first:
        assert sec.text[:200] in p["user"] and CLAIM.proposition in p["user"]
        assert "BD-LABOUR-2006" not in p["user"]
    reviews = [p for p in llm.payloads if p["task"] == "bench_review"]
    assert len(reviews) == 3 and all("anonymised" in p["user"] for p in reviews)
    assert not any("claude" in p["user"] or "gemini" in p["user"] or "deepseek" in p["user"] for p in reviews)
