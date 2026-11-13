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
    async def stopped(stop_on_quota, only=None):
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


def test_every_gold_anchor_clause_exists_in_its_document():
    import yaml

    from ain.agents import ingestion

    gold = yaml.safe_load(run_eval.GOLD.read_text(encoding="utf-8"))
    for name, spec in gold.items():
        data = (config.DEMO_DIR / "docs" / name).read_bytes()
        text = {c.id: c.text for c in ingestion.build_document(data, name)[0].clauses}  # as the pipeline numbers them
        for e in spec.get("expect", []):
            assert set(e.get("clauses", ())) <= set(text), f"{name}: {e}"
            if e.get("clauses"):
                assert e["at"] in text[e["clauses"][0]], f"{name}: {e['clauses'][0]} is not the clause this finding is about: {e}"
            assert "rule" in e or e.get("clauses"), f"{name}: a keyword finding must name the clauses it is about: {e}"


def test_a_keyword_finding_needs_its_clauses_as_well():
    from ain.models import L10n, Risk

    def risk(clauses, title):
        return Risk(id="R1", origin="adversary", category="x", title=L10n(en=title, bn=""), severity="high", clause_ids=clauses,
                    finding="", citizen_line=L10n(en="", bn=""), action=L10n(en="", bn=""))

    union = {"keywords": ["union", "association"], "clauses": ["C6"]}
    assert run_eval._match(union, risk(["C6"], "Multi-union clause cannot be performed in an EPZ"))
    assert not run_eval._match(union, risk(["C7"], "Worker data shared with the buyer's association")), "right word, wrong clause"
    assert not run_eval._match(union, risk(["C6"], "Code of conduct costs")), "right clause, no keyword"


async def test_a_subset_run_scores_only_those_documents(halt):
    out = await run_eval.evaluate(only=["control_clean.txt"])
    assert [r["document"] for r in out["results"]] == ["control_clean.txt"]
    with pytest.raises(AssertionError, match="not in the gold set"):
        await run_eval.evaluate(only=["no_such.txt"])


def test_a_subset_run_keeps_the_full_report(monkeypatch, tmp_path):
    async def one(stop_on_quota, only=None):
        assert only == ["control_clean.txt"]
        return {"results": [], "incomplete": None}

    monkeypatch.setattr(run_eval, "evaluate", one)
    monkeypatch.setattr(config, "BACKEND", tmp_path)
    (tmp_path / "eval").mkdir()
    monkeypatch.setattr("sys.argv", ["run_eval", "--doc", "control_clean.txt"])
    run_eval.main()
    assert not (tmp_path / "eval" / "last_eval.json").exists() and (tmp_path / "eval" / "last_eval.subset.json").exists()
