"""Live smoke test: checks keys and model ids, runs the hero documents through Groq + OpenRouter,
and warms the LLM cache so the demo can later run with AIN_LLM_MODE=replay (no network).

    python -m scripts.smoke_live            (from backend/, with keys in ../.env)
    python -m scripts.smoke_live --docs 1   (warm one hero doc: the OpenRouter free tier allows 50 requests/day)
    python -m scripts.smoke_live --doc long_migrant_msa.txt   (one named document, e.g. the ~25 page long-context sample)
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import httpx

from ain import config
from ain.llm import all_routes
from ain.orchestrator import new_job, run_pipeline

DOCS = ["migrant_my_contract.txt", "rmg_dhaka_epz.txt", "migrant_my_contract_photo.jpg", "migrant_sa_contract.txt"]


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
    for role in config.role_names():
        for route in all_routes(role):
            if route.prov.name not in available:
                continue
            for i, model in enumerate((route.model, *route.fallbacks)):
                found = model in available[route.prov.name]
                kind = "backup" if route.backup else ("primary" if i == 0 else "fallback")
                ok &= found or kind != "primary"  # a missing fallback or backup is a warning, not a failure
                print(f"  {role:<9} {kind:<8} {route.prov.name}/{model}: {'OK' if found else 'NOT FOUND - edit ain/config.yaml'}")
    return ok and bool(available)


def free_quota() -> None:
    prov = config.provider("openrouter")
    if not prov.api_key:
        return
    r = httpx.get(f"{prov.base_url}/key", headers={"Authorization": f"Bearer {prov.api_key}"}, timeout=30)
    if r.status_code == 200:
        q = r.json()["data"].get("free_model_daily_requests") or {}
        print(f"  openrouter free requests today: {q.get('used', '?')}/{q.get('limit', '?')} used, {q.get('remaining', '?')} left")


async def run_docs(docs: list[str]) -> None:
    for name in docs:
        path = config.DEMO_DIR / "docs" / name
        r = await run_pipeline(new_job(name), path.read_bytes(), name, llm_mode="live", confirm_timeout=1)
        s = r.stats
        fallbacks = sum(c.fallback for c in r.privacy.outbound_calls)
        adv = sum(k.origin == "adversary" and k.status != "dropped" for k in r.risks)
        restated = [e.message for e in r.trace if e.type == "hypothesis_dropped"]
        print(f"\n== {name}: {len(path.read_bytes()):,} bytes, {len(r.document.clauses)} clauses | {s.risks_confirmed} risks ({adv} off-playbook) | "
              f"{s.verified} verified, {s.partial} partial, {s.dropped} dropped | {s.llm_calls} calls ({fallbacks} via fallback), {s.seconds}s")
        for m in restated:
            print(f"   - adversary hypothesis dropped (restates the playbook): {m}")
        for k in r.risks:
            bench = f" bench {k.bench.vote}{' DISSENT' if k.bench.human_review else ''}" if k.bench else ""
            print(f"   {k.id:<4} {k.status:<9} {k.severity:<8} {k.origin:<10} {k.title.en}{bench}")
        for v in r.ledger:
            if v.verdict == "dropped":
                why = next((g.detail for g in v.gates if g.status == "fail"), "")
                print(f"   x {v.claim.citation_id}: {why[:140]}")
        models = sorted({f"{c.provider}/{c.model}{' (fallback)' if c.fallback else ''}" for c in r.privacy.outbound_calls})
        print("   models: " + ", ".join(models))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", type=int, default=len(DOCS), help="how many hero documents to run")
    ap.add_argument("--doc", action="append", help="run this document from demo/docs instead (repeatable)")
    args = ap.parse_args()
    print("Checking providers and model ids…")
    if not check_models():
        print("\nFix the issues above (keys in .env, model ids in ain/config.yaml) and re-run.")
        sys.exit(1)
    free_quota()
    asyncio.run(run_docs(args.doc or DOCS[: args.docs]))
    free_quota()
    print("\nCache warmed. To demo without network: set AIN_LLM_MODE=replay")


if __name__ == "__main__":
    main()
