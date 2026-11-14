"""Rehearsal Council: the coaches cite only the turn's allowed list, and Regal's one citation passes the evidence gate."""

import pytest

from ain.models import RehearsalSetup, RehearsalTurn
from ain.rehearsal import coaches, tactics
from tests.conftest import RecordingLLM

TACTIC = tactics.by_id()["passport_for_processing"]
PACKS = {"bd_migration"}
QUOTE = TACTIC.law[0].quote


def _turn():
    return RehearsalTurn(n=1, tactic_id=TACTIC.id, dalal_line=TACTIC.example_bn, worker_reply="পাসপোর্ট আমার কাছেই থাকবে")


def _llm(regal=None, sunny=None, grey=None):
    answers = {"bench_a": sunny, "bench_b": regal, "bench_c": grey}

    def answer(role, user):
        a = answers.get(role)
        return a if a is not None else coaches._fallback(TACTIC, {"bench_a": "happy", "bench_b": "proud", "bench_c": "gloomy"}[role])

    return RecordingLLM(overrides={"rehearsal_coach": answer})


async def _hints(llm):
    sections = coaches.allowed_sections(TACTIC, TACTIC.example_bn, PACKS)
    return {h.member: h for h in await coaches.coach_all(llm, TACTIC, _turn(), sections, RehearsalSetup())}, sections


def test_allowed_list_starts_with_the_tactics_anchors_and_is_in_force():
    sections = coaches.allowed_sections(TACTIC, TACTIC.example_bn, PACKS)
    ids = list(sections)
    assert ids[: len(TACTIC.law)] == [a.citation_id for a in TACTIC.law]
    assert len(ids) <= len(TACTIC.law) + coaches.EXTRA_SECTIONS
    assert all(s.status != "repealed" for s in sections.values())


async def test_regal_good_citation_keeps_all_four_gates():
    hints, _ = await _hints(_llm())
    regal = hints["proud"]
    assert regal.citations == [TACTIC.law[0].citation_id] and not regal.dropped
    assert [g.gate for g in regal.gates] == ["existence", "fidelity", "entailment", "currency"]
    assert all(g.status == "pass" for g in regal.gates)


@pytest.mark.parametrize(
    "answer, gate",
    [
        ({"text": "পাসপোর্ট রাখা অপরাধ।", "citation_id": "BD-LABOUR-2006-s100", "quote": "কোন শ্রমিক"}, "existence"),
        ({"text": "পাসপোর্ট রাখা অপরাধ।", "citation_id": "BD-OEMA-2013-s31", "quote": "পাসপোর্ট রাখা যাইবে না এবং রাখিলে জেল হইবে"}, "fidelity"),
        ({"text": "পাসপোর্ট আটকে রাখলে ৯ বছরের জেল।", "citation_id": "BD-OEMA-2013-s31", "quote": QUOTE}, "entailment"),
        ({"text": "পাসপোর্ট রাখা অপরাধ।", "citation_id": None, "quote": None}, "existence"),
    ],
)
async def test_regal_failing_a_gate_loses_the_citation(answer, gate):
    hints, _ = await _hints(_llm(regal=answer))
    regal = hints["proud"]
    assert regal.citations == [] and regal.dropped == gate
    assert regal.text == coaches.NO_LAW["bn"]  # no law is stated without a verified citation


async def test_sunny_and_grey_cite_only_the_allowed_list_and_stay_short():
    long = "ক" * 600
    hints, sections = await _hints(
        _llm(sunny={"text": long, "say": "পাসপোর্ট দেব না।", "citations": ["XX-FAKE-1", TACTIC.law[0].citation_id]}, grey={"text": "সতর্ক থাকুন।", "citations": ["BD-FAKE-9999-s1"]})
    )
    assert hints["happy"].citations == [TACTIC.law[0].citation_id]
    assert hints["gloomy"].citations == []
    assert len(hints["happy"].text) <= coaches.HINT_CHARS and hints["happy"].say == "পাসপোর্ট দেব না।"
    assert all(c in sections for h in hints.values() for c in h.citations)


async def test_a_coach_figure_with_no_source_falls_back():
    hints, _ = await _hints(_llm(grey={"text": "সবাই ৭ লাখ টাকা হারায়।", "citations": []}))
    assert hints["gloomy"].text == TACTIC.grey_flag_bn and hints["gloomy"].dropped
