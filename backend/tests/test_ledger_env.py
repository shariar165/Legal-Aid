"""AIN_LEDGER=1/0 overrides `ledger.enabled` in config.yaml for one process (a deployment); unset, the file decides."""

import time

import pytest
from fastapi.testclient import TestClient

from ain import api, config
from ain.config import ConfigError


def _with_file_flag(monkeypatch, on: bool) -> None:
    raw = dict(config._raw())
    raw["ledger"] = {**(raw.get("ledger") or {}), "enabled": on}
    monkeypatch.setattr(config, "_raw", lambda: raw)


def _wait(client, job, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/jobs/{job}").json()
        if s["status"] in ("done", "error"):
            return s
        time.sleep(0.2)
    raise AssertionError("job did not finish")


def test_unset_or_empty_uses_config_yaml(monkeypatch):
    monkeypatch.delenv("AIN_LEDGER", raising=False)
    assert config.ledger_enabled() is False  # the shipped default stays off
    monkeypatch.setenv("AIN_LEDGER", "")
    assert config.ledger_enabled() is False
    _with_file_flag(monkeypatch, True)
    assert config.ledger_enabled() is True


@pytest.mark.parametrize("env, file_flag, expected", [("1", False, True), ("0", True, False), (" 1 ", False, True)])
def test_the_variable_overrides_the_file_both_ways(monkeypatch, env, file_flag, expected):
    _with_file_flag(monkeypatch, file_flag)
    monkeypatch.setenv("AIN_LEDGER", env)
    assert config.ledger_enabled() is expected


@pytest.mark.parametrize("bad", ["true", "on", "yes", "2"])
def test_anything_but_1_or_0_is_refused(monkeypatch, bad):
    monkeypatch.setenv("AIN_LEDGER", bad)
    with pytest.raises(ConfigError, match="AIN_LEDGER must be 1 or 0"):
        config.ledger_enabled()
    with pytest.raises(ConfigError):
        with TestClient(api.app):  # the start fails, not the first request
            pass


def test_ain_ledger_1_turns_the_feature_on_end_to_end(monkeypatch, docs):
    """Through the environment only (no monkeypatched function): ledgers, the demo promises and PB-PROMISE-GAP appear."""
    monkeypatch.setenv("AIN_LEDGER", "1")
    with TestClient(api.app) as client:
        assert client.get("/api/health").json()["four_ledgers"] is True
        job = client.post("/api/analyze", data={"sample_id": "migrant_text"}).json()["job_id"]
        assert _wait(client, job)["status"] == "done"
        r = client.get(f"/api/jobs/{job}/result").json()
        assert r["four_ledgers"]["promises"]["salary_amount"] == 1800
        rules = {k["rule_id"] for k in r["risks"]}
        assert {"PB-PROMISE-GAP", "PB-HOURS"} <= rules


def test_ain_ledger_0_turns_it_off_even_when_the_file_says_on(monkeypatch, docs):
    _with_file_flag(monkeypatch, True)
    monkeypatch.setenv("AIN_LEDGER", "0")
    with TestClient(api.app) as client:
        assert client.get("/api/health").json()["four_ledgers"] is False
        job = client.post("/api/analyze", data={"sample_id": "migrant_text"}).json()["job_id"]
        assert _wait(client, job)["status"] == "done"
        r = client.get(f"/api/jobs/{job}/result").json()
        assert r["four_ledgers"] is None
        assert not {"PB-PROMISE-GAP", "PB-HOURS"} & {k["rule_id"] for k in r["risks"]}
