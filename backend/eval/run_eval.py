"""Evaluation harness: recall / precision against the gold set, citation validity, drop rate,
latency, and the plain-LLM ablation.

    python -m eval.run_eval                 (uses AIN_LLM_MODE / keys from .env)
    AIN_LLM_MODE=fake python -m eval.run_eval
"""

from __future__ import annotations

import asyncio
import json
import time

import yaml

from ain import config
from ain.agents import ablation
from ain.llm import LLM
from ain.orchestrator import new_job, run_pipeline
from ain.retrieval import get_corpus

GOLD = config.BACKEND / "eval" / "gold.yaml"


def _match(expect: dict, risk) -> bool:
    if "rule" in expect:
        return risk.rule_id == expect["rule"]
    title = (risk.title.en + " " + risk.title.bn + " " + risk.finding).lower()
    return any(k.lower() in title for k in expect["keywords"])


async def evaluate() -> dict:
    gold = yaml.safe_load(GOLD.read_text(encoding="utf-8"))
    corpus = get_corpus()
    rows = []
    for name, spec in gold.items():
        data = (config.DEMO_DIR / "docs" / name).read_bytes()
        t = time.time()
        r = await run_pipeline(new_job(name), data, name, confirm_timeout=0.1)
        secs = time.time() - t
        live = [k for k in r.risks if k.status != "dropped"]
        expected = spec.get("expect", [])
        found = sum(any(_match(e, k) for k in live) for e in expected)
        correct = sum(any(_match(e, k) for e in expected) for k in live)
        memo_cites = [c for i in r.memo.issues for c in i.citation_ids]
        ok = {v.claim.citation_id for v in r.ledger if v.verdict in ("verified", "partial")}
        valid = sum(c in corpus and c in ok for c in memo_cites)
        checks = []
        for c in spec.get("must_cite", []):
            checks.append((f"cites {c}", c in memo_cites))
        for p in spec.get("must_not_cite_prefix", []):
            checks.append((f"never relies on {p}", not any(c.startswith(p) for c in memo_cites)))
        ab = await ablation.run(LLM(mode=r.llm_mode), corpus, r) if live else None
        rows.append(
            {
                "document": name,
                "risks_confirmed": len(live),
                "adversary_risks": sum(k.origin == "adversary" for k in live),
                "recall": round(found / len(expected), 3) if expected else None,
                "precision": round(correct / len(live), 3) if live else (1.0 if not expected else 0.0),
                "memo_citations": len(memo_cites),
                "citation_validity": round(valid / len(memo_cites), 3) if memo_cites else None,
                "claims": r.stats.claims,
                "dropped": r.stats.dropped,
                "drop_rate": round(r.stats.dropped / r.stats.claims, 3) if r.stats.claims else 0.0,
                "bench_dissents": sum(1 for k in live if k.bench and k.bench.human_review),
                "seconds": round(secs, 2),
                "llm_calls": r.stats.llm_calls,
                "checks": {k: v for k, v in checks},
                "ablation_plain_supported": f"{ab.supported}/{ab.citations_found}" if ab else None,
                "mode": r.llm_mode,
            }
        )
    return {"results": rows}


def main() -> None:
    out = asyncio.run(evaluate())
    print(f"{'document':<28}{'risks':>6}{'adv':>5}{'recall':>8}{'prec':>7}{'cite-ok':>9}{'drop':>7}{'secs':>8}  plain-LLM")
    for r in out["results"]:
        fmt = lambda x: "-" if x is None else f"{x:.0%}" if isinstance(x, float) else str(x)  # noqa: E731
        print(f"{r['document']:<28}{r['risks_confirmed']:>6}{r['adversary_risks']:>5}{fmt(r['recall']):>8}{fmt(r['precision']):>7}"
              f"{fmt(r['citation_validity']):>9}{fmt(r['drop_rate']):>7}{r['seconds']:>8}  {r['ablation_plain_supported'] or '-'}")
        for k, v in r["checks"].items():
            print(f"    {'PASS' if v else 'FAIL'}  {k}")
    (config.BACKEND / "eval" / "last_eval.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
