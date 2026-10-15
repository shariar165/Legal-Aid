"""Live smoke test: checks keys and model ids, runs the hero documents through Groq + OpenRouter,
and warms the LLM cache so the demo can later run with AIN_LLM_MODE=replay (no network).

    python -m scripts.smoke_live            (from backend/, with keys in ../.env)
"""

from __future__ import annotations

import asyncio
import sys

import httpx

from ain import config
from ain.orchestrator import new_job, run_pipeline

DOCS = ["migrant_my_contract.txt", "rmg_dhaka_epz.txt", "migrant_my_contract_photo.jpg"]
ROLES = ["fast", "reasoner", "judge", "plain", "bench_a", "bench_b", "bench_c", "chairman"]


def check_models() -> bool:
    ok = True
    available: dict[str, set[str]] = {}
    for name in ("groq", "openrouter"):
        prov = config.provider(name)
        if not prov.api_key:
            print(f"  {name}: no key ({prov.key_env}) - roles fall back to the other provider")
            continue
        r = httpx.get(f"{prov.base_url}/models", headers={"Authorization": f"Bearer {prov.api_key}"}, timeout=30)
        if r.status_code != 200:
            print(f"  {name}: key rejected ({r.status_code})")
            ok = False
            continue
        available[name] = {m["id"] for m in r.json()["data"]}
        print(f"  {name}: key OK, {len(available[name])} models")
    for role in ROLES:
        rc = config.role(role)
        if rc.provider in available:
            found = rc.model in available[rc.provider]
            ok &= found
            print(f"  {role:<9} {rc.provider}/{rc.model}: {'OK' if found else 'NOT FOUND - edit ain/config.yaml'}")
    return ok and bool(available)


async def run_docs() -> None:
    for name in DOCS:
        path = config.DEMO_DIR / "docs" / name
        r = await run_pipeline(new_job(name), path.read_bytes(), name, llm_mode="live", confirm_timeout=1)
        s = r.stats
        print(f"\n== {name}: {s.risks_confirmed} risks | {s.verified} verified, {s.partial} partial, {s.dropped} dropped | {s.llm_calls} calls, {s.seconds}s")
        for k in r.risks:
            bench = f" bench {k.bench.vote}{' DISSENT' if k.bench.human_review else ''}" if k.bench else ""
            print(f"   {k.id:<4} {k.status:<9} {k.severity:<8} {k.origin:<10} {k.title.en}{bench}")
        for v in r.ledger:
            if v.verdict == "dropped":
                why = next((g.detail for g in v.gates if g.status == "fail"), "")
                print(f"   x {v.claim.citation_id}: {why[:140]}")


def main() -> None:
    print("Checking providers and model ids…")
    if not check_models():
        print("\nFix the issues above (keys in .env, model ids in ain/config.yaml) and re-run.")
        sys.exit(1)
    asyncio.run(run_docs())
    print("\nCache warmed. To demo without network: set AIN_LLM_MODE=replay")


if __name__ == "__main__":
    main()
