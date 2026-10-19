"""Model routing: free-only guard, OpenRouter fallbacks, the daily-quota breaker and the Groq backup.

No network: httpx is served by a MockTransport that plays the provider."""

import asyncio
import json

import diskcache
import httpx
import pytest

from ain import config, llm as llm_mod
from ain.llm import LLM

REAL_SLEEP = asyncio.sleep  # the `live` fixture stubs asyncio.sleep out of the retry backoff


@pytest.fixture
def live(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-or")
    monkeypatch.setattr(llm_mod, "_cache", diskcache.Cache(str(tmp_path / "llm")))

    async def no_sleep(_):
        return None

    monkeypatch.setattr(llm_mod.asyncio, "sleep", no_sleep)
    llm_mod.reset_breakers()
    yield
    llm_mod.reset_breakers()


def serve(monkeypatch, handler):
    """Route every provider call through `handler(request, body) -> httpx.Response`; returns the request log."""
    seen: list[tuple[str, dict]] = []

    def transport(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append((request.url.host, body))
        return handler(request, body)

    real = httpx.AsyncClient
    monkeypatch.setattr(llm_mod.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(transport), **kw))
    return seen


def answer(model, content='{"ok": true}'):
    return httpx.Response(200, json={"model": model, "choices": [{"message": {"content": content}}]})


async def call(llm, role="bench_a", user="Statute text and proposition."):
    return await llm.json(role=role, system="Reply in JSON.", user=user, task="t", agent="Test")


def test_config_ships_only_free_openrouter_models():
    for name in config.role_names():
        for r in llm_mod.all_routes(name):
            if r.prov.name == "openrouter":
                assert all(config.is_free_model(m) for m in (r.model, *r.fallbacks)), name


def test_free_only_guard_rejects_paid_model():
    raw = {
        "providers": {"openrouter": {"base_url": "x", "key_env": "K", "free_only": True}, "groq": {"base_url": "y", "key_env": "G"}},
        "roles": {"bench_a": {"provider": "openrouter", "model": "google/gemma-4-31b-it:free", "fallbacks": ["openai/gpt-5.4-mini"]}},
    }
    with pytest.raises(config.ConfigError, match="gpt-5.4-mini"):
        config.validate(raw)
    raw["roles"] = {"judge": {"provider": "groq", "model": "qwen/qwen3.8-27b", "backup": {"provider": "openrouter", "model": "deepseek/deepseek-v4-flash"}}}
    with pytest.raises(config.ConfigError, match="deepseek"):
        config.validate(raw)


async def test_openrouter_body_carries_fallbacks_privacy_and_reasoning(live, monkeypatch):
    seen = serve(monkeypatch, lambda req, body: answer(body["model"]))
    llm = LLM(mode="live")
    assert await call(llm) == {"ok": True}
    host, body = seen[0]
    rc = config.role("bench_a")
    assert host == "openrouter.ai"
    assert body["models"] == [rc.model, *rc.fallbacks]
    assert body["provider"] == {"data_collection": "deny"}
    assert body["reasoning"] == config.provider("openrouter").reasoning
    assert body["max_tokens"] >= config.provider("openrouter").max_tokens_floor
    assert llm.calls[0].provider == "openrouter" and not llm.calls[0].fallback


async def test_daily_quota_trips_breaker_and_falls_back_to_groq(live, monkeypatch):
    def handler(req, body):
        if req.url.host == "openrouter.ai":
            return httpx.Response(429, json={"error": {"message": "Rate limit exceeded: free-models-per-day."}})
        return answer(body["model"])

    seen = serve(monkeypatch, handler)
    llm = LLM(mode="live")
    await call(llm, user="first")
    backup = config.role("bench_a").backup
    assert llm.calls[-1].provider == "groq" and llm.calls[-1].model == backup.model and llm.calls[-1].fallback
    assert llm_mod.is_tripped("openrouter")
    # the breaker is open: the next call goes straight to Groq without touching OpenRouter
    before = sum(h == "openrouter.ai" for h, _ in seen)
    await call(llm, user="second")
    assert sum(h == "openrouter.ai" for h, _ in seen) == before
    assert llm.resolve("bench_a") == (config.provider("groq"), backup.model)


async def test_empty_answer_moves_to_next_route(live, monkeypatch):
    def handler(req, body):
        if req.url.host == "openrouter.ai":
            return answer(body["model"], content="")
        return answer(body["model"])

    serve(monkeypatch, handler)
    llm = LLM(mode="live")
    await call(llm)
    assert llm.calls[-1].provider == "groq" and llm.calls[-1].fallback
    assert not llm_mod.is_tripped("openrouter")


async def test_openrouter_fallback_model_is_marked(live, monkeypatch):
    serve(monkeypatch, lambda req, body: answer("google/gemma-4-26b-a4b-it:free"))
    llm = LLM(mode="live")
    await call(llm)
    assert llm.calls[-1].model == "google/gemma-4-26b-a4b-it:free" and llm.calls[-1].fallback


def test_routed_free_model_is_not_a_fallback():
    # openrouter/free always answers with some concrete free model: that is its routing, not a fallback
    route = llm_mod.Route(config.provider("openrouter"), "openrouter/free")
    assert not llm_mod._is_fallback(route, "dots-studio/dots-3-note-preview:free")


def test_judge_seats_never_share_a_model():
    # every model a seat can land on (primary, OpenRouter fallbacks, backup) belongs to that seat alone; a shared
    # *family* after a fallback is allowed but marked on the ruling (see test_bench_savers)
    chains = [{m for r in llm_mod.all_routes(role) for m in (r.model, *r.fallbacks)} for role in ("bench_a", "bench_b", "bench_c")]
    assert not (chains[0] & chains[1]) and not (chains[0] & chains[2]) and not (chains[1] & chains[2])
    assert all("openrouter/free" not in c for c in chains)


async def test_free_endpoints_run_at_most_max_parallel_per_model(live, monkeypatch):
    active = peak = 0

    async def slow_post(self, route, *a, **kw):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await REAL_SLEEP(0.01)
        active -= 1
        return {"ok": True}, route.model

    monkeypatch.setattr(LLM, "_post", slow_post)
    llm = LLM(mode="live")
    await asyncio.gather(*(call(llm, user=f"q{i}") for i in range(6)))
    assert peak == config.provider("openrouter").max_parallel


async def test_replay_finds_answer_cached_by_the_backup(live, monkeypatch):
    def handler(req, body):
        if req.url.host == "openrouter.ai":
            return httpx.Response(429, json={"error": {"message": "free-models-per-day"}})
        return answer(body["model"], '{"from": "groq"}')

    serve(monkeypatch, handler)
    await call(LLM(mode="live"))
    llm_mod.reset_breakers()
    replay = LLM(mode="replay")
    assert await call(replay) == {"from": "groq"}
    assert replay.calls[-1].cached and replay.calls[-1].provider == "groq"


async def test_no_usable_route_is_an_error(live, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY")
    llm_mod.trip("openrouter")
    with pytest.raises(llm_mod.LLMError, match="No usable provider"):
        LLM(mode="live").resolve("bench_a")


async def test_one_models_daily_limit_fails_that_route_at_once(live, monkeypatch):
    def handler(req, body):
        if req.url.host == "api.groq.com":
            return httpx.Response(429, headers={"retry-after": "900"}, json={"error": {"message": "Rate limit reached on tokens per day (TPD): Limit 200000"}})
        return answer(body["model"])

    seen = serve(monkeypatch, handler)
    llm = LLM(mode="live")
    await call(llm, role="fast")
    # one Groq request, no 15-minute sleep, then the OpenRouter backup; Groq's other models stay usable
    assert sum(h == "api.groq.com" for h, _ in seen) == 1
    assert llm.calls[-1].provider == "openrouter" and llm.calls[-1].fallback
    assert not llm_mod.is_tripped("groq")
