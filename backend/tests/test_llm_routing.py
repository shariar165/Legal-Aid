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


# ------------------------------------------------------------------ rate_wait: announced once, before the wait


def waits(monkeypatch):
    """(LLM, its rate_wait events, every sleep it took)."""
    events, sleeps = [], []

    async def sleep(s):
        sleeps.append(s)

    monkeypatch.setattr(llm_mod.asyncio, "sleep", sleep)
    return LLM(mode="live", on_event=lambda type_, agent, message, **data: events.append((type_, data))), events, sleeps


async def test_a_retry_after_is_announced_once_with_provider_and_model(live, monkeypatch):
    replies = iter([httpx.Response(429, headers={"retry-after": "7"}, json={"error": {"message": "slow down"}})])
    serve(monkeypatch, lambda req, body: next(replies, None) or answer(body["model"]))
    llm, events, sleeps = waits(monkeypatch)
    await call(llm, role="fast")
    model = config.role("fast").model
    assert events == [("rate_wait", {"seconds": 7.0, "provider": "groq", "model": model})]
    assert 7.0 in sleeps


async def test_a_long_token_wait_is_one_event_and_one_sleep_never_one_per_second(live, monkeypatch):
    serve(monkeypatch, lambda req, body: answer(body["model"]))
    prov = config.provider("groq")
    model = config.role("fast").model
    llm_mod._bucket(prov, model).level = -4000.0
    llm, events, sleeps = waits(monkeypatch)
    await call(llm, role="fast")
    assert len(events) == 1 and events[0][1]["provider"] == "groq" and events[0][1]["seconds"] >= 30
    assert len(sleeps) == 1 and sleeps[0] >= 30


async def test_the_requests_per_minute_pacer_announces_its_wait(live, monkeypatch):
    serve(monkeypatch, lambda req, body: answer(body["model"]))
    prov = config.provider("groq")
    now = llm_mod.time.monotonic()
    llm_mod._pacer("groq").slots = [now] * prov.rpm
    llm, events, _ = waits(monkeypatch)
    await call(llm, role="fast")
    assert [t for t, _ in events] == ["rate_wait"] and events[0][1]["seconds"] > 50


async def test_pacer_and_token_bucket_together_wait_the_longer_of_the_two(live, monkeypatch):
    """They run at once: adding them would slow every queued call down for nothing, and report a wait that never happens."""
    serve(monkeypatch, lambda req, body: answer(body["model"]))
    prov = config.provider("groq")
    model = config.role("fast").model
    llm_mod._pacer("groq").slots = [llm_mod.time.monotonic()] * prov.rpm
    llm_mod._bucket(prov, model).level = -2000.0
    llm, events, sleeps = waits(monkeypatch)
    await call(llm, role="fast")
    assert len(events) == 1 and len(sleeps) == 1 and 50 < sleeps[0] < 62


def test_gaps_under_a_second_are_normal_pacing_and_stay_quiet():
    events = []
    llm = LLM(mode="fake", on_event=lambda type_, agent, message, **data: events.append(data))
    prov = config.provider("groq")
    llm._rate_wait(0.4, prov, "m")
    assert events == []
    llm._rate_wait(1.0, prov, "m")
    assert events == [{"seconds": 1.0, "provider": "groq", "model": "m"}]


async def test_network_and_server_error_backoffs_are_not_rate_waits(live, monkeypatch):
    state = {"n": 0}

    def handler(request, body):
        state["n"] += 1
        if state["n"] == 1:
            raise httpx.ConnectError("no route")
        if state["n"] == 2:
            return httpx.Response(503, json={"error": {"message": "overloaded"}})
        return answer(body["model"])

    serve(monkeypatch, handler)
    llm, events, sleeps = waits(monkeypatch)
    await call(llm, role="fast")
    assert events == [] and len(sleeps) >= 2


async def test_a_server_error_with_retry_after_is_a_rate_wait(live, monkeypatch):
    replies = iter([httpx.Response(503, headers={"retry-after": "5"}, json={"error": {"message": "overloaded"}})])
    serve(monkeypatch, lambda req, body: next(replies, None) or answer(body["model"]))
    llm, events, _ = waits(monkeypatch)
    await call(llm, role="fast")
    assert [d["seconds"] for _, d in events] == [5.0]


# ------------------------------------------------------------------ answers that are not a JSON object


async def test_a_bare_list_is_retried_until_the_model_gives_an_object(live, monkeypatch):
    replies = iter([answer("m", '["a plain string"]')])
    serve(monkeypatch, lambda req, body: next(replies, None) or answer(body["model"]))
    llm = LLM(mode="live")
    assert await call(llm, role="fast") == {"ok": True}
    assert llm.json_retries == 1


@pytest.mark.parametrize("content", ['["a plain string"]', '"just text"', "7", "not json at all"])
async def test_a_model_that_never_gives_an_object_is_malformed_not_an_outage(live, monkeypatch, content):
    serve(monkeypatch, lambda req, body: answer(body["model"], content))
    with pytest.raises(llm_mod.MalformedAnswer):
        await call(LLM(mode="live"), role="fast")


async def test_an_empty_answer_is_malformed_too(live, monkeypatch):
    serve(monkeypatch, lambda req, body: answer(body["model"], ""))
    with pytest.raises(llm_mod.MalformedAnswer):
        await call(LLM(mode="live"), role="fast")


async def test_an_outage_stays_a_plain_llm_error(live, monkeypatch):
    serve(monkeypatch, lambda req, body: httpx.Response(401, json={"error": {"message": "bad key"}}))
    with pytest.raises(llm_mod.LLMError) as e:
        await call(LLM(mode="live"), role="fast")
    assert not isinstance(e.value, llm_mod.MalformedAnswer)


async def test_a_cached_answer_that_is_not_an_object_is_asked_again(live, monkeypatch):
    seen = serve(monkeypatch, lambda req, body: answer(body["model"]))
    llm = LLM(mode="live")
    await call(llm, role="fast")
    cache = llm_mod._cache
    for k in list(cache):
        cache[k] = {"__ain__": 1, "data": ["a plain string"], "model": "m"}
    assert await call(LLM(mode="live"), role="fast") == {"ok": True}
    assert len(seen) == 2
