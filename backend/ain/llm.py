"""One LLM layer for every agent: Groq + OpenRouter (OpenAI-compatible), cache, retries, PII guard.

Modes (AIN_LLM_MODE):
  live   - call the provider (results cached on disk; cached answers are reused)
  replay - cache only; a miss is an error. Lets the demo run with no network.
  fake   - deterministic offline answers supplied by each agent (`fake=` callable). Used by tests.

Every outbound payload goes through pii.find_pii(); a hit blocks the call (PIILeakError).
OpenRouter calls ask providers not to retain/train on data (provider.data_collection = "deny").

Routing (ain/config.yaml): each role has a primary model, optional same-provider `fallbacks` (sent to
OpenRouter as `models: [...]` so it retries upstream 429s itself) and a `backup` on the other provider.
The backup is used when the primary provider has no key, is out of its daily free quota (a circuit
breaker skips it until the quota resets) or keeps failing. Fallback answers are marked in the trace.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import diskcache
import httpx

from ain import config
from ain.agents.pii import find_pii
from ain.models import OutboundCall

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class PIILeakError(LLMError):
    pass


class _RouteFailed(LLMError):
    """This route cannot answer; try the next one."""


@dataclass(frozen=True)
class Route:
    prov: config.ProviderConfig
    model: str
    fallbacks: tuple[str, ...] = ()
    backup: bool = False  # on the role's other provider


_cache: diskcache.Cache | None = None


def _get_cache() -> diskcache.Cache:
    global _cache
    if _cache is None:
        _cache = diskcache.Cache(str(config.CACHE_DIR / "llm"))
    return _cache


class _Pacer:
    """Sliding-window requests-per-minute limit, shared by every job in the process."""

    def __init__(self) -> None:
        self.slots: list[float] = []

    async def wait(self, rpm: int) -> None:
        now = time.monotonic()
        self.slots = [s for s in self.slots if s > now - 60]
        slot = now
        if len(self.slots) >= rpm:
            slot = max(now, self.slots[-rpm] + 60)
        if self.slots:
            slot = max(slot, self.slots[-1])
        self.slots.append(slot)
        if slot > now:
            await asyncio.sleep(slot - now)


_pacers: dict[str, _Pacer] = {}
_tripped: dict[str, float] = {}  # provider -> wall-clock time its daily quota resets


def _pacer(name: str) -> _Pacer:
    return _pacers.setdefault(name, _Pacer())


def is_tripped(name: str) -> bool:
    until = _tripped.get(name)
    if until is None:
        return False
    if time.time() >= until:
        _tripped.pop(name, None)
        return False
    return True


def trip(name: str, until: float | None = None) -> None:
    if until is None:
        tomorrow = datetime.now(UTC).date() + timedelta(days=1)
        until = datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=UTC).timestamp()
    _tripped[name] = until


def reset_breakers() -> None:
    _tripped.clear()
    _pacers.clear()


def _quota_reset(r: httpx.Response) -> float | None:
    """OpenRouter sends X-RateLimit-Reset in epoch milliseconds."""
    raw = r.headers.get("x-ratelimit-reset")
    try:
        return float(raw) / 1000 if raw else None
    except ValueError:
        return None


def parse_json(content: str) -> dict:
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.S)
        if m:
            return json.loads(m.group(0))
        raise


def all_routes(role: str) -> list[Route]:
    """Every configured route for a role, in order, regardless of keys or breakers."""
    rc = config.role(role)
    out = [Route(config.provider(rc.provider), rc.model, rc.fallbacks)]
    if rc.backup:
        out.append(Route(config.provider(rc.backup.provider), rc.backup.model, rc.backup.fallbacks, backup=True))
    return out


class LLM:
    """Per-job client. Records every call for the privacy receipt and the trace."""

    def __init__(self, mode: str | None = None, on_call: Callable[[OutboundCall], None] | None = None):
        self.mode = mode or config.llm_mode()
        self.calls: list[OutboundCall] = []
        self.blocked = 0
        self.json_retries = 0  # answers that were not valid JSON and had to be asked again
        self._on_call = on_call
        self._sem = asyncio.Semaphore(6)
        self._per_model: dict[tuple[str, str], asyncio.Semaphore] = {}

    def routes(self, role: str) -> list[Route]:
        """Routes that can be called right now: the provider has a key and is not out of quota."""
        live = [r for r in all_routes(role) if r.prov.api_key and not is_tripped(r.prov.name)]
        if not live and self.mode == "live":
            primary = all_routes(role)[0]
            raise LLMError(f"No usable provider for role '{role}' ({primary.prov.key_env} missing or quota exhausted)")
        return live

    def resolve(self, role: str) -> tuple[config.ProviderConfig, str]:
        """The provider + model the next call for this role will try first."""
        live = self.routes(role)
        r = live[0] if live else all_routes(role)[0]
        return r.prov, r.model

    async def json(
        self,
        *,
        role: str,
        system: str,
        user: str,
        task: str,
        agent: str,
        fake: Callable[[], dict] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2500,
        info: dict | None = None,
    ) -> dict[str, Any]:
        """`info`, if given, is filled with the provider, model and fallback flag of the call that actually answered."""
        leaks = find_pii(system) + find_pii(user)
        if leaks:
            self.blocked += 1
            kinds = sorted({k for k, _ in leaks})
            raise PIILeakError(f"Blocked outbound call from {agent}: unredacted {', '.join(kinds)}")

        if self.mode == "fake":
            if fake is None:
                raise LLMError(f"No fake response for task {task}")
            self._record(info, OutboundCall(agent=agent, role=role, provider="fake", model="fake", chars=len(system) + len(user)))
            return fake()

        chars = len(system) + len(user)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        cache = _get_cache()

        def key(r: Route) -> str:
            return hashlib.sha256(json.dumps([r.prov.name, r.model, messages, temperature, task], ensure_ascii=False).encode()).hexdigest()

        for r in all_routes(role):
            hit = cache.get(key(r))
            if hit is not None:
                data, used = _unwrap(hit, r.model)
                self._record(info, OutboundCall(agent=agent, role=role, provider=r.prov.name, model=used, chars=chars, cached=True, fallback=_is_fallback(r, used)))
                return data
        if self.mode == "replay":
            if fake is not None:
                self._record(info, OutboundCall(agent=agent, role=role, provider="fake", model="fake", chars=0))
                return fake()
            raise LLMError(f"replay mode: no cached answer for {agent}/{task}")

        routes = self.routes(role)
        errors: list[str] = []
        for i, r in enumerate(routes):
            try:
                async with self._sem, self._model_slot(r):
                    data, used = await self._post(r, messages, temperature, max_tokens, last=i == len(routes) - 1)
            except _RouteFailed as e:
                log.warning("%s: %s", agent, e)
                errors.append(str(e))
                continue
            cache[key(r)] = {"__ain__": 1, "data": data, "model": used}
            self._record(info, OutboundCall(agent=agent, role=role, provider=r.prov.name, model=used, chars=chars, fallback=_is_fallback(r, used)))
            return data
        raise LLMError(f"{agent}: every route for role '{role}' failed: " + " | ".join(errors))

    def _model_slot(self, r: Route) -> asyncio.Semaphore | contextlib.nullcontext:
        if not r.prov.max_parallel:
            return contextlib.nullcontext()
        return self._per_model.setdefault((r.prov.name, r.model), asyncio.Semaphore(r.prov.max_parallel))

    def _record(self, info: dict | None, call: OutboundCall) -> None:
        if info is not None:
            info.update(provider=call.provider, model=call.model, fallback=call.fallback, cached=call.cached)
        self.calls.append(call)
        if self._on_call:
            self._on_call(call)

    async def _post(self, route: Route, messages: list, temperature: float, max_tokens: int, last: bool) -> tuple[dict, str]:
        prov, model = route.prov, route.model
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max(max_tokens, prov.max_tokens_floor),
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {prov.api_key}"}
        if prov.name == "openrouter":
            if route.fallbacks:
                body["models"] = [model, *route.fallbacks]
            body["provider"] = {"data_collection": "deny"}
            headers.update({"HTTP-Referer": "https://github.com/ain-copilot", "X-Title": "Ain Copilot"})
        if prov.reasoning:
            body["reasoning"] = prov.reasoning
        if prov.name == "groq" and model.startswith("qwen/"):
            body["reasoning_format"] = "hidden"
        if prov.name == "groq" and model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"

        where = f"{prov.name}/{model}"
        last_err: Exception | None = None
        # with a backup route waiting, fail over fast instead of sitting out a long backoff
        attempts = 6 if last else 3
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
            for attempt in range(attempts):
                await _pacer(prov.name).wait(prov.rpm)
                try:
                    r = await client.post(f"{prov.base_url}/chat/completions", json=body, headers=headers)
                except httpx.TransportError as e:
                    last_err = e
                    await asyncio.sleep(min(20, 2 ** attempt))
                    continue
                if r.status_code == 429 and "per-day" in r.text:
                    trip(prov.name, _quota_reset(r))
                    raise _RouteFailed(f"{where}: daily free quota exhausted")
                if r.status_code == 429 and "per day" in r.text:
                    # one model's daily token/request limit (Groq: "tokens per day (TPD)"); its siblings still work
                    raise _RouteFailed(f"{where}: daily limit for this model reached")
                if r.status_code == 429 or r.status_code >= 500:
                    wait = float(r.headers.get("retry-after") or 0) or min(30, 2 ** attempt)
                    last_err = LLMError(f"{r.status_code}: {r.text[:200]}")
                    if wait > 60 and not last:
                        raise _RouteFailed(f"{where}: rate limited for {wait:.0f}s")
                    await asyncio.sleep(wait)
                    continue
                if r.status_code == 400 and "response_format" in body and "json" in r.text.lower():
                    body.pop("response_format")  # some models reject json mode; prompt still demands JSON
                    continue
                if r.status_code >= 400:
                    # bad key, no endpoint for our data policy, model gone: this route cannot answer
                    raise _RouteFailed(f"{where}: {r.status_code} {r.text[:200]}")
                payload = r.json()
                content = (payload.get("choices") or [{}])[0].get("message", {}).get("content") or ""
                used = payload.get("model") or model
                if not content.strip():
                    raise _RouteFailed(f"{where}: empty answer (reasoning used up the token budget)")
                try:
                    return parse_json(content), used
                except json.JSONDecodeError as e:
                    self.json_retries += 1
                    last_err = e
                    await asyncio.sleep(min(20, 2 ** attempt))
        raise _RouteFailed(f"{where} failed after retries: {last_err}")


def _unwrap(hit: Any, model: str) -> tuple[dict, str]:
    """Cache entries written before routing was added are the bare answer dict."""
    if isinstance(hit, dict) and hit.get("__ain__") == 1:
        return hit["data"], hit.get("model") or model
    return hit, model


def _is_fallback(route: Route, used: str) -> bool:
    # openrouter/free always answers with some concrete free model; that is routing, not a fallback
    return route.backup or (used != route.model and route.model != "openrouter/free")
