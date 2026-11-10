"""The gold-set eval run across several days: --stop-on-quota drops the document in progress and writes nothing."""

import pytest

from ain import config, llm as llm_mod
from eval import run_eval


@pytest.fixture
def halt():
    llm_mod.reset_breakers()
    yield
    llm_mod.reset_breakers()


async def test_the_document_in_progress_when_the_quota_runs_out_is_not_scored(halt, monkeypatch):
    real, seen = run_eval.run_pipeline, []

    async def pipeline(job, data, name, **kw):
        seen.append(name)
        r = await real(job, data, name, **kw)
        if len(seen) == 2:
            llm_mod.trip("openrouter")  # as a daily-quota 429 does, halfway through the second document
        return r

    monkeypatch.setattr(run_eval, "run_pipeline", pipeline)
    out = await run_eval.evaluate(stop_on_quota=True)
    assert [r["document"] for r in out["results"]] == seen[:1]
    assert out["incomplete"] == f"openrouter's daily quota ran out during {seen[1]}"


async def test_an_error_from_the_halt_drops_the_document_but_any_other_error_still_fails(halt, monkeypatch):
    async def halted(job, data, name, **kw):
        llm_mod.trip("openrouter")
        raise llm_mod.QuotaHalt("openrouter's daily quota is used up")

    monkeypatch.setattr(run_eval, "run_pipeline", halted)
    out = await run_eval.evaluate(stop_on_quota=True)
    assert out["results"] == [] and out["incomplete"]

    llm_mod.reset_breakers()

    async def broken(job, data, name, **kw):
        raise RuntimeError("a real bug")

    monkeypatch.setattr(run_eval, "run_pipeline", broken)
    with pytest.raises(RuntimeError, match="a real bug"):
        await run_eval.evaluate(stop_on_quota=True)


def test_an_incomplete_run_exits_2_and_keeps_the_last_report(monkeypatch, tmp_path, capsys):
    async def stopped(stop_on_quota):
        assert stop_on_quota
        return {"results": [], "incomplete": "openrouter's daily quota ran out during rmg_dhaka_epz.txt"}

    monkeypatch.setattr(run_eval, "evaluate", stopped)
    monkeypatch.setattr(config, "BACKEND", tmp_path)
    (tmp_path / "eval").mkdir()
    monkeypatch.setattr("sys.argv", ["run_eval", "--stop-on-quota"])
    with pytest.raises(SystemExit) as e:
        run_eval.main()
    assert e.value.code == 2
    assert "INCOMPLETE" in capsys.readouterr().out
    assert not (tmp_path / "eval" / "last_eval.json").exists()
