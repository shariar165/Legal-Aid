"""Warm a demo sample (as POST /api/analyze builds it, flag from AIN_LEDGER) so that every answer in the cache comes
from the configured model. A fallback answer, whether read from the cache or just given live, is deleted after the
pass, and the next pass asks the configured model again. Stops when a pass has no fallback, after --passes, or when
OpenRouter's free quota left falls under --reserve. Prints counts only, never a key.

  python -m scripts.warm_clean <sample_id> [--passes 3] [--reserve 6]
  AIN_LLM_MODE=replay python -m scripts.warm_clean <sample_id> --dry    # list + delete cached fallbacks, no network
"""
import argparse
import asyncio
import collections
import time

import httpx

from ain import api, config
from ain import llm as llm_mod
from ain.models import Promises
from ain.orchestrator import new_job, run_pipeline


def quota_left() -> int:
    prov = config.provider("openrouter")
    r = httpx.get(f"{prov.base_url}/key", headers={"Authorization": f"Bearer {prov.api_key}"}, timeout=30)
    q = r.json()["data"].get("free_model_daily_requests") or {}
    return int(q.get("remaining", 0))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sample_id"); ap.add_argument("--passes", type=int, default=3); ap.add_argument("--reserve", type=int, default=6)
    ap.add_argument("--dry", action="store_true", help="replay mode: list cached fallback answers, delete them, call nothing")
    a = ap.parse_args()

    # Spy on the cache to learn which key each answer came from, and on _record to see which answers were fallbacks.
    cache = llm_mod._get_cache()
    last = {"key": None}

    class Spy:
        def get(self, k, default=None):
            v = cache.get(k, default)
            if v is not None: last["key"] = k
            return v

        def __setitem__(self, k, v):
            cache[k] = v; last["key"] = k

    llm_mod._get_cache = lambda: Spy()
    bad: dict[str, str] = {}
    orig_record = llm_mod.LLM._record

    def record(self, info, call):
        if call.fallback and last["key"]:
            bad[last["key"]] = f"{call.role}:{call.provider}/{call.model}{' cached' if call.cached else ' live'}:{call.fallback_reason}"
        return orig_record(self, info, call)

    llm_mod.LLM._record = record

    s = next(x for x in api.SAMPLES if x["id"] == a.sample_id)
    name = s["file"]; data = (config.DEMO_DIR / "docs" / name).read_bytes()
    kind = "sample" if s["kind"] == "text" else None
    told = Promises.model_validate_json((config.DEMO_DIR / "promises" / s["promises_file"]).read_text(encoding="utf-8")) if "promises_file" in s and config.ledger_enabled() else None
    policy = ((config.DEMO_DIR / "docs" / s["policy_file"]).read_bytes(), s["policy_file"]) if "policy_file" in s else None
    if not a.dry:
        llm_mod.halt_on_quota("openrouter")

    async def one_pass(n):
        bad.clear(); t = time.time()
        r = await run_pipeline(new_job(name), data, name, kind, "replay" if a.dry else "live", confirm_timeout=1, policy=policy, promises=told)
        calls = r.privacy.outbound_calls
        print(f"pass {n}: {r.llm_mode} status={getattr(r, 'status', '')} risks={r.stats.risks_confirmed} calls={len(calls)} cached={sum(c.cached for c in calls)} "
              f"live={sum(not c.cached for c in calls)} fallback={sum(c.fallback for c in calls)} halted={llm_mod.halted()} {time.time()-t:.0f}s")
        for why, k in sorted(collections.Counter(bad.values()).items()): print(f"   fallback {k}x {why}")
        for k in bad: cache.delete(k)
        if bad: print(f"   deleted {len(bad)} fallback answers from the cache")
        return len(bad)

    async def run():
        print(f"== {a.sample_id} ({name}) ledger={config.ledger_enabled()} promises={told is not None} policy={policy is not None}")
        for n in range(1, a.passes + 1):
            if not a.dry:
                left = quota_left(); print(f"   openrouter free requests left: {left}")
                if left < a.reserve: print("   stopping: quota reserve reached"); return
            if await one_pass(n) == 0 or a.dry or llm_mod.halted(): return

    asyncio.run(run())


if __name__ == "__main__":
    main()
