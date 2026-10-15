"""One LLM layer for every agent: Groq + OpenRouter (OpenAI-compatible), cache, retries, PII guard.

Modes (AIN_LLM_MODE):
  live   - call the provider (results cached on disk; cached answers are reused)
  replay - cache only; a miss is an error. Lets the demo run with no network.
  fake   - deterministic offline answers supplied by each agent (`fake=` callable). Used by tests.

Every outbound payload goes through pii.find_pii(); a hit blocks the call (PIILeakError).
OpenRouter calls ask providers not to retain/train on data (provider.data_collection = "deny").
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Callable
from typing import Any

import diskcache
import httpx

from ain import config
from ain.agents.pii import find_pii
from ain.models import OutboundCall

FALLBACKS = {
    # used when the configured provider has no key but the other one does
    ("groq", "openrouter"): {
        "fast": "meta-llama/llama-3.1-8b-instruct",
        "reasoner": "openai/gpt-oss-120b",
        "judge": "qwen/qwen3-32b",
        "plain": "meta-llama/llama-3.3-70b-instruct",
    },
    ("openrouter", "groq"): {
        "bench_a": "llama-3.3-70b-versatile",
        "bench_b": "qwen/qwen3-32b",
        "bench_c": "openai/gpt-oss-120b",
        "chairman": "openai/gpt-oss-120b",
    },
}


class LLMError(RuntimeError):
    pass


class PIILeakError(LLMError):
    pass


_cache: diskcache.Cache | None = None


def _get_cache() -> diskcache.Cache:
    global _cache
    if _cache is None:
        _cache = diskcache.Cache(str(config.CACHE_DIR / "llm"))
    return _cache


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


class LLM:
    """Per-job client. Records every call for the privacy receipt and the trace."""

    def __init__(self, mode: str | None = None, on_call: Callable[[OutboundCall], None] | None = None):
        self.mode = mode or config.llm_mode()
        self.calls: list[OutboundCall] = []
        self.blocked = 0
        self._on_call = on_call
        self._sem = asyncio.Semaphore(6)

    def resolve(self, role: str) -> tuple[config.ProviderConfig, str]:
        rc = config.role(role)
        prov = config.provider(rc.provider)
        if self.mode in ("live", "replay") and not prov.api_key:
            other = "openrouter" if rc.provider == "groq" else "groq"
            alt = config.provider(other)
            model = FALLBACKS.get((rc.provider, other), {}).get(role)
            if alt.api_key and model:
                return alt, model
            if self.mode == "live":
                raise LLMError(f"No API key for {rc.provider} ({prov.key_env}) and no fallback for role '{role}'")
        return prov, rc.model

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
    ) -> dict[str, Any]:
        leaks = find_pii(system) + find_pii(user)
        if leaks:
            self.blocked += 1
            kinds = sorted({k for k, _ in leaks})
            raise PIILeakError(f"Blocked outbound call from {agent}: unredacted {', '.join(kinds)}")

        if self.mode == "fake":
            if fake is None:
                raise LLMError(f"No fake response for task {task}")
            self._record(OutboundCall(agent=agent, role=role, provider="fake", model="fake", chars=len(system) + len(user)))
            return fake()

        prov, model = self.resolve(role)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        key = hashlib.sha256(json.dumps([prov.name, model, messages, temperature, task], ensure_ascii=False).encode()).hexdigest()
        cache = _get_cache()
        if key in cache:
            self._record(OutboundCall(agent=agent, role=role, provider=prov.name, model=model, chars=len(system) + len(user), cached=True))
            return cache[key]
        if self.mode == "replay":
            if fake is not None:
                self._record(OutboundCall(agent=agent, role=role, provider="fake", model="fake", chars=0))
                return fake()
            raise LLMError(f"replay mode: no cached answer for {agent}/{task}")

        async with self._sem:
            data = await self._post(prov, model, messages, temperature, max_tokens)
        cache[key] = data
        self._record(OutboundCall(agent=agent, role=role, provider=prov.name, model=model, chars=len(system) + len(user)))
        return data

    def _record(self, call: OutboundCall) -> None:
        self.calls.append(call)
        if self._on_call:
            self._on_call(call)

    async def _post(self, prov: config.ProviderConfig, model: str, messages: list, temperature: float, max_tokens: int) -> dict:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {prov.api_key}"}
        if prov.name == "openrouter":
            body["provider"] = {"data_collection": "deny"}
            headers.update({"HTTP-Referer": "https://github.com/ain-copilot", "X-Title": "Ain Copilot"})
        if prov.name == "groq" and model.startswith("qwen/"):
            body["reasoning_format"] = "hidden"
        if prov.name == "groq" and model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"

        last: Exception | None = None
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
            for attempt in range(6):
                try:
                    r = await client.post(f"{prov.base_url}/chat/completions", json=body, headers=headers)
                    if r.status_code == 429 or r.status_code >= 500:
                        wait = float(r.headers.get("retry-after") or 0) or min(30, 2 ** attempt)
                        last = LLMError(f"{prov.name} {r.status_code}: {r.text[:200]}")
                        await asyncio.sleep(wait)
                        continue
                    if r.status_code == 400 and "response_format" in body and "json" in r.text.lower():
                        body.pop("response_format")  # some models reject json mode; prompt still demands JSON
                        continue
                    r.raise_for_status()
                    content = r.json()["choices"][0]["message"]["content"] or ""
                    return parse_json(content)
                except (httpx.TransportError, json.JSONDecodeError) as e:
                    last = e
                    await asyncio.sleep(min(20, 2 ** attempt))
        raise LLMError(f"{prov.name}/{model} failed after retries: {last}")
