"""Seat health: a withdrawn judge model is found by one ping and the seat moves to a model of another family.

No network: the providers are played by a MockTransport (tests/test_llm_routing.py)."""

import logging
import time

import httpx
import pytest

from ain import config, seat_health
from ain import llm as llm_mod
from ain.llm import LLM
from tests.test_llm_routing import answer, call, live, serve  # noqa: F401 - `live` is a fixture

GONE = "no longer available on OpenRouter: no provider serves this model anymore"
ERNIE = config.role("bench_c").backup.model
QWEN = config.role("bench_c").model


def gone(*models):
    """Providers that 404 for these models, as OpenRouter did for Xing 4.0, and answer for every other."""

    def handler(req, body):
        if body["model"] in models:
            return httpx.Response(404, json={"error": {"message": f"{body['model']} is {GONE}", "code": 404}})
        return answer(body["model"])

    return handler


@pytest.fixture
def checking(live, monkeypatch):  # noqa: F811
    monkeypatch.setenv("AIN_LLM_MODE", "live")
    monkeypatch.setattr(seat_health, "_last", [])


def pings(seen):
    return [b["model"] for _, b in seen if b["messages"] == seat_health.PING]


async def test_one_ping_per_seat_when_every_model_is_served(checking, monkeypatch):
    seen = serve(monkeypatch, gone())
    report = await seat_health.check_seats()
    assert sorted(pings(seen)) == sorted(config.role(r).model for r in seat_health.SEATS)
    assert [h.using for h in report] == [h.configured for h in report] and not any(h.warning for h in report)
    assert llm_mod.plan("bench_c") == llm_mod.all_routes("bench_c"), "nothing moves while every model answers"


async def test_a_withdrawn_model_moves_the_seat_to_another_family(checking, monkeypatch, caplog):
    seen = serve(monkeypatch, gone(QWEN))
    with caplog.at_level(logging.WARNING, logger="ain.seat_health"):
        report = await seat_health.check_seats()
    grey = next(h for h in report if h.role == "bench_c")
    assert grey.gone == [f"groq/{QWEN}"] and grey.using == f"openrouter/{ERNIE}" and grey.same_family_as == []
    assert config.model_family(ERNIE) not in {config.model_family(config.role(r).model) for r in ("chairman", "bench_a", "bench_b")}
    assert f"Grey's model groq/{QWEN} is gone; Grey now answers on openrouter/{ERNIE}." in caplog.text
    assert seat_health.last() == report

    # Grey's calls now go straight to the replacement, marked as a fallback, with no request spent on the 404
    before = len(seen)
    llm = LLM(mode="live")
    await call(llm, role="bench_c", user="A claim for Grey.")
    assert [b["model"] for _, b in seen[before:]] == [ERNIE]
    assert llm.calls[-1].model == ERNIE and llm.calls[-1].fallback


async def test_with_no_other_family_left_the_seat_takes_one_and_says_which_it_shares(checking, monkeypatch, caplog):
    sunny = [m for r in llm_mod.all_routes("bench_a") if not r.backup for m in (r.model, *r.fallbacks)]
    serve(monkeypatch, gone(*sunny, config.role("bench_b").model))
    with caplog.at_level(logging.WARNING, logger="ain.seat_health"):
        report = {h.name: h for h in await seat_health.check_seats()}
    # Groq serves only two judge families: once OpenRouter's judges are gone, Sunny and Regal both land on GPT-OSS
    assert report["Sunny"].using == f"groq/{config.role('bench_a').backup.model}"
    assert report["Regal"].using == f"groq/{config.role('bench_b').backup.model}"
    assert report["Regal"].same_family_as == ["Sunny", "Chief Justice"]
    assert "the same family as Sunny and Chief Justice" in caplog.text
    assert report["Grey"].using == report["Grey"].configured


async def test_a_rate_limit_is_not_gone(checking, monkeypatch):
    def handler(req, body):
        if body["model"] == QWEN:
            return httpx.Response(429, json={"error": {"message": "Rate limit reached for model on tokens per minute"}}, headers={"retry-after": "120"})
        return answer(body["model"])

    serve(monkeypatch, handler)
    grey = next(h for h in await seat_health.check_seats() if h.role == "bench_c")
    assert grey.using == grey.configured and not grey.gone


async def test_pings_are_kept_for_six_hours(checking, monkeypatch):
    seen = serve(monkeypatch, gone(QWEN))
    await seat_health.check_seats()
    sent = len(pings(seen))
    llm_mod.reset_breakers()  # a restart: the routing state is gone, the cached pings are not
    report = await seat_health.check_seats()
    assert len(pings(seen)) == sent, "a restart within six hours spends no request"
    assert next(h for h in report if h.role == "bench_c").using == f"openrouter/{ERNIE}"
    assert llm_mod.is_gone("groq", QWEN)

    real = time.time
    monkeypatch.setattr(seat_health.time, "time", lambda: real() + seat_health.TTL_S + 1)
    await seat_health.check_seats()
    assert len(pings(seen)) > sent, "older than six hours: ping again"


async def test_a_404_on_an_ordinary_call_skips_that_model_from_then_on(live, monkeypatch):  # noqa: F811
    seen = serve(monkeypatch, gone(QWEN))
    llm = LLM(mode="live")
    await call(llm, role="bench_c", user="first")
    assert [b["model"] for _, b in seen] == [QWEN, ERNIE]
    await call(llm, role="bench_c", user="second")
    assert [b["model"] for _, b in seen[2:]] == [ERNIE]
    assert llm.calls[-1].fallback


async def test_no_ping_outside_live_mode(checking, monkeypatch):
    monkeypatch.setenv("AIN_LLM_MODE", "replay")
    seen = serve(monkeypatch, gone())
    assert await seat_health.check_seats() == [] and seen == []


async def test_the_next_model_in_the_chain_is_skipped_when_it_shares_a_family(checking, monkeypatch):
    # the Chief Justice on a Gemma model: Sunny's own Gemma fallback would then share its family, so Sunny skips it
    monkeypatch.setitem(config._raw()["roles"]["chairman"], "model", "google/gemma-4-26b-a4b-it:free")
    primary, fallback = config.role("bench_a").model, config.role("bench_a").fallbacks[0]
    seen = serve(monkeypatch, gone(primary))
    sunny = next(h for h in await seat_health.check_seats() if h.role == "bench_a")
    backup = config.role("bench_a").backup.model
    assert sunny.using == f"groq/{backup}" and sunny.same_family_as == []
    assert [r.model for r in llm_mod.plan("bench_a")] == [backup, fallback], "the pick first, the rest still there"
    before = len(seen)
    await call(LLM(mode="live"), role="bench_a", user="A claim for Sunny.")
    assert [b["model"] for _, b in seen[before:]] == [backup]


async def test_an_answer_from_a_promoted_fallback_is_still_marked_as_one(checking, monkeypatch):
    primary, fallback = config.role("bench_a").model, config.role("bench_a").fallbacks[0]
    seen = serve(monkeypatch, gone(primary))
    sunny = next(h for h in await seat_health.check_seats() if h.role == "bench_a")
    assert sunny.using == f"openrouter/{fallback}"
    llm = LLM(mode="live")
    before = len(seen)
    await call(llm, role="bench_a", user="A claim for Sunny.")
    assert [b["model"] for _, b in seen[before:]] == [fallback] and "models" not in seen[-1][1]
    assert llm.calls[-1].model == fallback and llm.calls[-1].fallback, "not Sunny's configured model, so the trace says so"
