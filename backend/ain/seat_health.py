"""Seat health: is each Virtual Bench judge's model still served?

Free models get withdrawn without notice (Xing 4.0 went between two eval days in November 2026, and every Grey call then
spent a request on a 404 before reaching its backup). At startup each seat's model gets one tiny ping, and the result is
kept for six hours, so restarts do not spend more of the free quota. A seat whose model is gone moves to the next model in
its own chain whose family differs from the Chief Justice's and the other seats'. If no such model answers it takes the
nearest one that does, and the warning says which family it shares: two judges of one family are then marked "same family
(fallback)" on every ruling, as after any fallback. A rate limit or an outage is not "gone": the seat keeps its model.

A 401 or 403 is "key rejected": the provider refused our key, so every model on it fails alike. The seat moves to the
first model in its chain on another provider, as for a gone model, but nothing is marked gone, and a rejected or unknown
ping is not kept across restarts, so a replaced key is seen at the next start.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Literal

from pydantic import BaseModel, Field

from ain import config
from ain import llm as llm_mod

log = logging.getLogger(__name__)

SEATS = {"bench_a": "Sunny", "bench_b": "Regal", "bench_c": "Grey"}
CHAIR = "chairman"
TTL_S = 6 * 3600
CACHE_KEY = "__seat_health__"
DOWN = ("gone", "key_rejected")  # ping results that move a seat off its configured model
PING = [
    {"role": "system", "content": 'Reply with this JSON object and nothing else: {"ok": true}'},
    {"role": "user", "content": "ping"},
]


class SeatHealth(BaseModel):
    role: str
    name: str
    configured: str  # provider/model
    using: str | None  # None: nothing in the seat's chain answers, so it gives no opinion
    status: Literal["ok", "gone", "key_rejected", "unknown"] = "unknown"  # the configured model's ping
    gone: list[str] = Field(default_factory=list)
    key_rejected: list[str] = Field(default_factory=list)  # providers in the seat's chain that refused our key
    same_family_as: list[str] = Field(default_factory=list)  # seats, or "Chief Justice", sharing the family of `using`
    warning: str = ""


_last: list[SeatHealth] = []


def last() -> list[SeatHealth]:
    """The most recent check, for /api/health. Empty until a live check has run."""
    return list(_last)


async def ping(llm: llm_mod.LLM, prov: config.ProviderConfig, model: str) -> str:
    """"ok"; "gone" (404: withdrawn, or no endpoint under our data policy); "key_rejected" (401/403: the provider refused
    our key); or "unknown" (rate limit, outage, a bad answer): "gone" and "key_rejected" move a seat. Goes through the
    real request path, data policy and JSON mode included."""
    if not prov.api_key:
        return "unknown"
    try:
        await llm._post(llm_mod.Route(prov, model), PING, 0.0, 50, last=False)
    except llm_mod._Gone:
        return "gone"
    except llm_mod._KeyRejected:
        return "key_rejected"
    except llm_mod.LLMError:
        return "unknown"
    return "ok"


def _key(prov: config.ProviderConfig, model: str) -> str:
    return f"{prov.name}/{model}"


async def check_seats(force: bool = False) -> list[SeatHealth]:
    """Ping each seat's model (or reuse pings under six hours old), mark gone models and pick replacements."""
    global _last
    if config.llm_mode() != "live":
        return []
    cache = llm_mod._get_cache()
    saved = cache.get(CACHE_KEY)
    fresh = force or not saved or time.time() - saved["at"] >= TTL_S
    # only answers about the model are kept: a rejected key may be replaced by the next start, an outage may be over
    pings: dict[str, str] = {} if fresh else {k: v for k, v in saved["pings"].items() if v in ("ok", "gone")}
    at = time.time() if fresh else saved["at"]
    llm = llm_mod.LLM(mode="live")

    async def status(prov: config.ProviderConfig, model: str) -> str:
        k = _key(prov, model)
        if k not in pings:
            refused = any(v == "key_rejected" and p.startswith(f"{prov.name}/") for p, v in pings.items())
            pings[k] = "key_rejected" if refused else await ping(llm, prov, model)  # one refusal speaks for the provider
        return pings[k]

    chains = {role: [(r.prov, m) for r in llm_mod.all_routes(role) for m in (r.model, *r.fallbacks)] for role in SEATS}
    await asyncio.gather(*(status(*chain[0]) for chain in chains.values()))  # one ping per seat when all is well
    using = {role: chain[0] for role, chain in chains.items() if pings[_key(*chain[0])] not in DOWN}
    chair = config.model_family(config.role(CHAIR).model)
    report = []
    for role, chain in chains.items():
        name = SEATS[role]
        choice = using.get(role)
        if choice is None:
            taken = {config.model_family(m): SEATS[r] for r, (_, m) in using.items() if r != role}
            alive = []
            for prov, model in chain[1:]:
                if await status(prov, model) in DOWN:
                    continue
                alive.append((prov, model))
                fam = config.model_family(model)
                if fam != chair and fam not in taken:
                    break
            differs = [c for c in alive if config.model_family(c[1]) != chair and config.model_family(c[1]) not in taken]
            choice = (differs or alive or [None])[0]
            if choice:
                using[role] = choice
                why = "key rejected" if pings[_key(*chain[0])] == "key_rejected" else "model gone"
                llm_mod.pick(role, choice[0].name, choice[1], why)
        gone = [_key(p, m) for p, m in chain if pings.get(_key(p, m)) == "gone"]
        refused = list(dict.fromkeys(p.name for p, m in chain if pings.get(_key(p, m)) == "key_rejected"))
        for p, m in chain:
            if pings.get(_key(p, m)) == "gone":
                llm_mod.mark_gone(p.name, m, ttl=max(60.0, at + TTL_S - time.time()))
        shares = []
        if choice:
            fam = config.model_family(choice[1])
            shares = [SEATS[r] for r, (_, m) in using.items() if r != role and config.model_family(m) == fam]
            shares += ["Chief Justice"] if fam == chair else []
        h = SeatHealth(
            role=role, name=name, configured=_key(*chain[0]), using=_key(*choice) if choice else None,
            status=pings[_key(*chain[0])], gone=gone, key_rejected=refused, same_family_as=shares,
        )
        if h.status in DOWN:
            what = f"{name}'s {chain[0][0].name} key was rejected" if h.status == "key_rejected" else f"{name}'s model {h.configured} is gone"
            h.warning = (
                f"{what}; {name} now answers on {h.using}" + (f", the same family as {' and '.join(shares)}" if shares else "") + "."
                if choice
                else f"{what}, and nothing else in {name}'s chain answers: {name} gives no opinion until one returns."
            )
            log.warning("Seat health: %s", h.warning)
        report.append(h)
    cache.set(CACHE_KEY, {"at": at, "pings": pings})
    _last = report
    return report
