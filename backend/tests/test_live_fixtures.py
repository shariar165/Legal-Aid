"""Real council round 2 answers from live runs, replayed offline through the real gate.

Each fixture in tests/fixtures/live_council_*.json holds what the members actually returned on the real routing. The gate
must decide them exactly as it did live, so a change to the gate shows up here against real model output, not only
against answers we wrote ourselves."""

import json
from pathlib import Path

import pytest

from ain.agents import bench, council
from ain.models import AnalysisResult, CouncilReply
from ain.retrieval import get_corpus
from tests.conftest import RecordingLLM

FIXTURES = sorted((Path(__file__).parent / "fixtures").glob("live_council_*.json"))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_there_is_at_least_one_live_fixture():
    assert FIXTURES


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_the_fixture_is_real_live_output(path):
    fx = _load(path)
    assert fx["result"]["llm_mode"] == "live"
    assert all(r["provider"] in ("openrouter", "groq") for r in fx["rebuttals"].values())
    assert any(e["flip_basis"] == "evidence" if fx["kind"] == "evidence" else e["restated"] for e in fx["expected"].values())


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
async def test_a_live_round_two_replays_to_the_same_gate_decision(path):
    fx = _load(path)
    result = AnalysisResult.model_validate(fx["result"])
    risk = next(r for r in result.risks if r.id == fx["risk_id"])
    first = [CouncilReply.model_validate(x) for x in fx["first"]]
    extras = [get_corpus().get(c) for c in fx["extras"]]
    assert all(extras), "an extra section is no longer in the corpus"
    for p in bench.PERSONAS:
        if p.id not in fx["rebuttals"]:
            continue
        raw = fx["rebuttals"][p.id]["out"]
        llm = RecordingLLM(overrides={"council_rebuttal": lambda role, user, raw=raw: raw})
        got = await council.rebut(llm, result, p, fx["question"], risk, first, "en", extras)
        want = fx["expected"][p.id]
        assert (got.flip_basis, got.restated, got.revised, got.severity, got.verdict) == (
            want["flip_basis"], want["restated"], want["revised"], want["severity"], want["verdict"]
        ), p.name
        assert got.flip_note == want["flip_note"] and got.position == want["position"], p.name
        assert (got.changed_because.model_dump(mode="json") if got.changed_because else None) == want["changed_because"], p.name
