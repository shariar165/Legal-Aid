"""The pressure trap in eval/bench_quality.py: harness, table and flag (offline: this checks the plumbing, not the models)."""

import json

import pytest

from ain import config
from ain.agents import bench, council
from eval import bench_quality as bq


@pytest.fixture
def harness(monkeypatch, tmp_path):
    monkeypatch.setattr(bq, "MODE", "fake")
    monkeypatch.setattr(bq, "PRESSURE_OUT", tmp_path / "pressure_trap.fake.json")
    monkeypatch.setattr(bq, "use_cache", lambda *a, **k: None)
    monkeypatch.setattr(bq, "groq_only", lambda: None)  # it changes the shared config and trips OpenRouter for the process
    return tmp_path


async def test_every_seat_meets_every_trap_and_the_table_is_written(harness):
    res = await bq.run_pressure(bq.load_traps())
    assert not res["incomplete"] and not res["errors"]
    assert [s["seat"] for s in res["table"]] == ["happy", "proud", "gloomy"]
    assert all(s["cases"] == len(bq.PRESSURE_TRAPS) for s in res["table"])
    saved = json.loads(bq.PRESSURE_OUT.read_text(encoding="utf-8"))
    assert saved["table"] == res["table"]


async def test_the_table_separates_blocked_from_counted_flips(harness):
    """The offline stand-in moves Sunny on its unused section and Grey on nothing, so both columns must fill."""
    res = await bq.run_pressure(bq.load_traps())
    sunny, regal, grey = res["table"]
    assert sunny["counted"] == sunny["flips"] > 0 and sunny["blocked"] == 0
    assert regal["flips"] == 0 and regal["flip_rate"] == 0
    assert grey["blocked"] == grey["flips"] > 0 and grey["counted"] == 0 and grey["flip_rate"] == 1
    assert sum(grey["reasons"].values()) == grey["blocked"]


def test_a_flip_nobody_declared_counts_as_undeclared():
    row = {"seat": "proud", "model": "m", "first_severity": "high", "pressed": {"severity": "low", "basis": "pressure", "revised": False, "note": "n"}, "control": {"basis": None}}
    regal = bq.pressure_table([row])[1]
    assert regal["flips"] == 1 and regal["blocked"] == 1 and regal["undeclared"] == 1 and regal["control_flips"] == 0
    assert regal["severity_moved"] == 1


def test_a_restated_position_is_a_flip_but_not_a_moved_rating():
    row = {"seat": "proud", "model": "m", "first_severity": "high", "pressed": {"severity": "high", "basis": "pressure", "revised": False, "note": "n"}, "control": {"basis": None}}
    regal = bq.pressure_table([row])[1]
    assert regal["flips"] == 1 and regal["severity_moved"] == 0


def test_every_trap_has_a_companion_section_of_the_same_act():
    traps = bq.load_traps()
    by = {t["id"]: t for t in traps}
    for tid in bq.PRESSURE_TRAPS:
        c = bq._companion(by[tid], traps)
        assert c["citation_id"] != by[tid]["citation_id"] and c["citation_id"].rsplit("-", 1)[0] == by[tid]["citation_id"].rsplit("-", 1)[0]
        result = bq.pressure_result(by[tid], c)
        assert len(council.build_context(result, result.risks[0], bench.PERSONAS[0])[1]) == 2


async def test_the_pressure_is_never_towards_the_members_own_view(harness):
    res = await bq.run_pressure(bq.load_traps())
    assert all(r["claimed"] != r["first_severity"] for r in res["rows"])


async def test_a_failed_seat_is_reported_not_fatal(harness, monkeypatch):
    real = bq.pressure_case

    async def flaky(llm, t, companion, p):
        if p.id == "proud":
            raise bq.LLMError("every route failed")
        return await real(llm, t, companion, p)

    monkeypatch.setattr(bq, "pressure_case", flaky)
    res = await bq.run_pressure(bq.load_traps())
    assert res["incomplete"] and len(res["errors"]) == len(bq.PRESSURE_TRAPS)
    assert "INCOMPLETE" in bq.pressure_report(res)


def test_a_fake_run_is_labelled_as_no_score():
    report = bq.pressure_report({"mode": "fake", "traps": [], "table": [], "rows": [], "errors": [], "incomplete": False})
    assert "NOT a sycophancy score" in report


async def test_peer_stability_notes_stay_off_and_out_of_the_prompts(docs):
    from ain.orchestrator import new_job, run_pipeline
    from tests.conftest import RecordingLLM

    assert config.council_settings()["peer_stability_notes"] is False
    name = "rmg_dhaka_epz.txt"
    result = await run_pipeline(new_job(name), (docs / name).read_bytes(), name, llm=RecordingLLM())
    risk = next(k for k in result.risks if k.bench and k.status != "dropped")
    llm = RecordingLLM()
    first = await council.chat(llm, result, "Sign?", ["happy", "proud", "gloomy"], risk, [])
    await council.deliberate(llm, result, "Sign?", first, risk, [])
    text = " ".join(p["system"] + p["user"] for p in llm.payloads).lower()
    assert "sycophan" not in text and "flip rate" not in text and "stability" not in text
