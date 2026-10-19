"""Virtual Bench quality check: do the OpenRouter quota savers leave the answers unchanged?

    python -m eval.bench_quality                            # every arm on the trap set (Groq judges, no OpenRouter quota)
    python -m eval.bench_quality --arms baseline_1,baseline_2 --keep
    python -m eval.bench_quality --probe bench_b=allam-2-7b  # a candidate fallback judge: first opinions only
    python -m eval.bench_quality --gold                     # also gold.yaml recall/precision through the whole pipeline
    python -m eval.bench_quality --arms "" --keep --gold --gold-arms final --gold-routing config
                                                            # the flags as set in config.yaml, real model routing,
                                                            # compared with the earlier live runs in runs/

The judges run at temperature 0 on the Groq backups of their seats (OpenRouter's breaker is tripped for the whole run),
so batched and unbatched arms use the same models and the run costs no OpenRouter quota. The baseline runs twice, with
separate caches, to measure the natural verdict flip rate. Each arm has its own answer cache under
.cache/bench_quality/, so an interrupted run (Groq's daily token limit) resumes where it stopped; results are saved
after every arm. Arms, in run order, and what each is compared with:
  baseline_1 / baseline_2   every flag off (baseline_2 measures run-to-run noise)          vs baseline_1
  no_leans                  bench_leans: false                                            vs baseline_1
  rubric                    no_leans + severity_rubric                                    vs no_leans
  review_skip               rubric + review_only_on_disagreement; shares rubric's answers  vs rubric
  batch                     rubric + batch_bench                                          vs rubric
  window                    rubric + statute_window (anchored on the cited sub-section); from rubric's answers vs rubric
The human-review rate is reported for both rules (any disagreement, and human_review_on_wide_spread) from the same
answers. Severity is also scored against a reference: for each trap whose proposition is a playbook anchor (or a
"correct" trap citing a section only one rule anchors), the rule's own severity; exact and within-one agreement are
reported per judge and for the bench. A flag may be turned on only if its arm has no false "supports", verdict flips
within the baseline's own flip rate, and severity within one notch of its comparison arm for at least 90% of opinions
(severity_rubric, which is meant to move severities, must instead agree with the reference at least as well as
no_leans does), plus no gold.yaml recall/precision drop when --gold is run. A judge call that fails on every route gives
that seat no opinion (as in the app) and is listed; a daily-limit or quota failure stops the run instead, so it can
resume the next day with --keep. Results go to eval/bench_quality.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import shutil
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import replace

import diskcache
import yaml

from ain import config
from ain import llm as llm_mod
from ain.agents import bench
from ain.agents.verifier import fake_entailment, verify_claim
from ain.llm import LLM, LLMError
from ain.models import Claim, L10n, PackDecision, Risk, RouteDecision
from ain.retrieval import get_corpus

TRAPS = config.BACKEND / "eval" / "bench_traps.yaml"
OUT = config.BACKEND / "eval" / "bench_quality.json"
CACHES = config.CACHE_DIR / "bench_quality"
BENCH_ROLES = ("bench_a", "bench_b", "bench_c")
GROUP = 8  # claims per "document": roughly what one contract sends to the bench
MODE = "live"  # --fake: offline dry run of the harness itself

BASE = bench.Options(temperature=0.0)
NO_LEANS = replace(BASE, leans=False)
RUBRIC = replace(NO_LEANS, severity_rubric=True)
ARMS: dict[str, dict] = {
    "baseline_1": {"opts": BASE},
    "baseline_2": {"opts": BASE, "vs": "baseline_1"},
    "no_leans": {"opts": NO_LEANS, "vs": "baseline_1"},
    "rubric": {"opts": RUBRIC, "vs": "no_leans"},
    "review_skip": {"opts": replace(RUBRIC, review_only_on_disagreement=True), "cache": "rubric", "vs": "rubric"},
    "batch": {"opts": replace(RUBRIC, batch=True), "vs": "rubric"},
    "window": {"opts": replace(RUBRIC, statute_window=True), "seed": "rubric", "vs": "rubric"},
}
FLAG_ARMS = {
    "no_leans": "bench_leans: false", "rubric": "severity_rubric", "review_skip": "review_only_on_disagreement",
    "batch": "batch_bench", "window": "statute_window",
}
RULES = config.BACKEND / "ain" / "playbook" / "rules.yaml"


class BudgetOut(LLMError):
    """Groq's daily limit (or a quota) ran out during an arm: stop, and resume with --keep the next day."""


class TimedLLM(LLM):
    """Records how long each real (uncached) provider call took."""

    def __init__(self, skip_chair: bool = True) -> None:
        super().__init__(mode=MODE)
        self.posts: list[tuple[str, float]] = []
        self.errors: list[str] = []  # calls that failed on every route (the bench turns them into "no opinion")
        self.budget_out = ""  # set by the first daily-limit or quota failure
        self.skip_chair = skip_chair

    async def json(self, *, task, fake=None, **kw):
        # the Chief Justice only writes prose from the votes; skipping it saves a third of the Groq tokens per bench
        if task == "bench_chair" and self.skip_chair and fake is not None:
            return fake()
        if self.budget_out:  # stop cleanly: no more calls once one judge model is out of today's budget
            raise BudgetOut(self.budget_out)
        try:
            return await super().json(task=task, fake=fake, **kw)
        except LLMError as e:
            self.errors.append(str(e))
            if "daily" in str(e) or "quota" in str(e):
                self.budget_out = str(e)
            raise

    async def _post(self, route, *a, **kw):
        t = time.perf_counter()
        try:
            return await super()._post(route, *a, **kw)
        finally:
            self.posts.append((route.model, time.perf_counter() - t))


def use_cache(name: str, seed: str | None = None) -> None:
    path = CACHES / name
    if seed and not path.exists() and (CACHES / seed).exists():
        shutil.copytree(CACHES / seed, path)
    if llm_mod._cache is not None:
        llm_mod._cache.close()
    llm_mod._cache = diskcache.Cache(str(path))


def groq_only() -> None:
    """Judges answer on their Groq backups: same models in every arm, no OpenRouter quota. Paced for Groq's free
    tier (8,000 tokens a minute per model, ~1,300 tokens a judge call)."""
    llm_mod.reset_breakers()
    llm_mod.trip("openrouter", time.time() + 10**9)
    config._raw()["providers"]["groq"].update(rpm=15, max_parallel=2)


def load_traps() -> list[dict]:
    corpus = get_corpus()
    traps = yaml.safe_load(TRAPS.read_text(encoding="utf-8"))
    for t in traps:
        sec = corpus.get(t["citation_id"])
        assert sec is not None, f"{t['id']}: {t['citation_id']} is not in the corpus"
        assert (sec.lang == "bn") == t["bangla"], f"{t['id']}: bangla flag does not match the corpus ({sec.lang})"
        assert (sec.status == "repealed") == (t["kind"] == "repealed"), f"{t['id']}: repealed flag does not match the corpus"
        t["section"] = sec
        t["claim"] = Claim(id=t["id"], risk_id=t["id"], proposition=t["proposition"], citation_id=t["citation_id"])
        t["risk"] = Risk(
            id=t["id"], origin="playbook", category="labour_standard", title=L10n(bn=t["id"], en=t["id"]), severity="high",
            finding=t["finding"], citizen_line=L10n(bn="-", en="-"), action=L10n(bn="-", en="-"), claim_ids=[t["id"]],
        )
    return traps


def _anchors(rule: dict) -> list[dict]:
    out = list(rule.get("anchors") or [])
    for key in ("anchors_by_pack", "pack_anchors"):
        for v in (rule.get(key) or {}).values():
            out += v
    return out


def reference_severities(traps: list[dict]) -> dict[str, dict]:
    """trap id -> {rule, severity}: the playbook rule the trap is tied to, and that rule's severity. A trap is tied when
    its proposition is one of the rule's anchor propositions, or when it is a "correct" trap citing a section that only
    one rule anchors. Wrong-section, contradicted and proviso traps are left out: their clauses are not the rule's case."""
    rules = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for t in traps:
        by_prop = [r for r in rules if any(a["proposition"].strip() == t["proposition"].strip() for a in _anchors(r))]
        by_cid = [r for r in rules if any(a["citation_id"] == t["citation_id"] for a in _anchors(r))]
        hit = by_prop[0] if len(by_prop) == 1 else by_cid[0] if t["kind"] == "correct" and len(by_cid) == 1 else None
        if hit:
            out[t["id"]] = {"rule": hit["id"], "severity": hit["severity"]}
    return out


def groups(traps: list[dict]) -> list[list[dict]]:
    benched = [t for t in traps if t["kind"] != "repealed"]
    random.Random(7).shuffle(benched)  # every "document" mixes kinds, languages and lengths
    return [benched[i : i + GROUP] for i in range(0, len(benched), GROUP)]


async def run_arm(name: str, traps: list[dict]) -> dict:
    arm = ARMS[name]
    use_cache(arm.get("cache", name), arm.get("seed"))
    groq_only()
    llm = TimedLLM()
    stats: Counter = Counter()
    t0 = time.perf_counter()

    async def one(g: list[dict]):
        items = [(t["claim"], t["section"], t["risk"], fake_entailment(t["claim"], t["section"])) for t in g]
        return list(zip(g, await bench.convene_many(llm, items, arm["opts"], stats)))

    done = [pair for chunk in await asyncio.gather(*(one(g) for g in groups(traps))) for pair in chunk]
    wall = time.perf_counter() - t0
    budget = [e for e in llm.errors if "daily" in e or "quota" in e]
    if budget:  # these seats would be "no opinion" only because today's budget ran out: not a result
        raise BudgetOut(f"{len(budget)} calls hit a daily limit or quota, e.g. {budget[0][:200]}")
    rows = {}
    for t, r in done:
        rows[t["id"]] = {
            "majority": r.majority_verdict, "severity": r.majority_severity, "peer_review": r.peer_review,
            "opinions": [{"seat": o.persona, "model": o.model, "verdict": o.verdict, "severity": o.severity} for o in r.opinions],
            "no_opinion": r.no_opinion, "quorum": r.quorum,
        }
    # repealed traps never reach a judge: the currency gate drops them first
    for t in traps:
        if t["kind"] == "repealed":
            route = RouteDecision(packs=[PackDecision(pack=p, label=p, reason="eval") for p in t["section"].packs])
            v = await verify_claim(llm, get_corpus(), route, t["claim"], t["risk"], use_bench=True)
            rows[t["id"]] = {"majority": "dropped" if v.verdict == "dropped" else "kept", "severity": None, "peer_review": False, "opinions": []}
    bench_calls = [c for c in llm.calls if c.role in BENCH_ROLES]
    fresh = [s for _, s in llm.posts]
    return {
        "arm": name, "rows": rows, "stats": dict(stats), "wall_s": round(wall, 1),
        "bench_calls": len(bench_calls), "fresh_calls": len(fresh), "json_retries": llm.json_retries,
        "mean_call_s": round(statistics.mean(fresh), 2) if fresh else None,
        "benched_claims": sum(1 for t in traps if t["kind"] != "repealed"),
        "models": sorted({c.model for c in bench_calls}),
        "errors": llm.errors,  # calls that failed on every route; rerun the arm with --keep to retry just these
    }


# ------------------------------------------------------------------ metrics


def _ok(expect: str, got: str) -> bool:
    if expect == "dropped":
        return got == "dropped"
    return (got == "supports") == (expect == "supports")


def _review(row: dict, wide: bool) -> bool:
    """Would this ruling ask for a human? wide=False: any disagreement; wide=True: a verdict split or a 2+ notch spread."""
    verdicts = {o["verdict"] for o in row["opinions"]}
    sev = [bench.SEV.index(o["severity"]) for o in row["opinions"]]
    return len(verdicts) > 1 or max(sev) - min(sev) >= (2 if wide else 1)


def _sev_agreement(pairs: list[tuple[str, str]]) -> dict:
    """exact and within-one agreement of (got, reference) severity pairs."""
    d = [abs(bench.SEV.index(g) - bench.SEV.index(r)) for g, r in pairs]
    return {"n": len(d), "exact": sum(x == 0 for x in d) / len(d) if d else None, "within_1": sum(x <= 1 for x in d) / len(d) if d else None,
            "mean_signed": statistics.mean(bench.SEV.index(g) - bench.SEV.index(r) for g, r in pairs) if pairs else None}


def score(res: dict, traps: list[dict], base: dict | None, ref: dict[str, dict] | None = None) -> dict:
    by = {t["id"]: t for t in traps}
    rows = res["rows"]
    out: dict = {}
    out["accuracy"] = sum(_ok(by[i]["expect"], r["majority"]) for i, r in rows.items()) / len(rows)
    out["exact_label"] = sum(r["majority"] == by[i]["expect"] for i, r in rows.items()) / len(rows)
    out["false_supports"] = sorted(i for i, r in rows.items() if r["majority"] == "supports" and by[i]["expect"] != "supports")
    out["missed_supports"] = sorted(i for i, r in rows.items() if r["majority"] != "supports" and by[i]["expect"] == "supports")
    per_kind = defaultdict(list)
    for i, r in rows.items():
        per_kind[by[i]["kind"]].append(_ok(by[i]["expect"], r["majority"]))
    out["by_kind"] = {k: f"{sum(v)}/{len(v)}" for k, v in per_kind.items()}
    bn = [_ok(by[i]["expect"], r["majority"]) for i, r in rows.items() if by[i]["bangla"]]
    out["bangla_accuracy"] = sum(bn) / len(bn) if bn else None
    benched = [r for r in rows.values() if len(r["opinions"]) >= 2]
    out["human_review_any"] = sum(_review(r, wide=False) for r in benched) / len(benched) if benched else None
    out["human_review_wide"] = sum(_review(r, wide=True) for r in benched) / len(benched) if benched else None
    # each judge's own verdicts, split by statute language
    judge = defaultdict(lambda: {"bn": [0, 0], "en": [0, 0]})
    for i, r in rows.items():
        for o in r["opinions"]:
            cell = judge[f"{o['seat']} · {o['model']}"]["bn" if by[i]["bangla"] else "en"]
            cell[0] += _ok(by[i]["expect"], o["verdict"])
            cell[1] += 1
    out["judges"] = {k: {lang: f"{a}/{n}" for lang, (a, n) in v.items()} for k, v in judge.items()}
    out["no_opinion"] = sorted(f"{i}/{n}" for i, r in rows.items() for n in r.get("no_opinion", []))
    if ref:
        tied = [i for i in rows if i in ref and rows[i]["opinions"]]
        out["reference"] = {"bench": _sev_agreement([(rows[i]["severity"], ref[i]["severity"]) for i in tied])}
        for i in tied:
            for o in rows[i]["opinions"]:
                out["reference"].setdefault(o["seat"], []).append((o["severity"], ref[i]["severity"]))
        out["reference"] = {k: v if k == "bench" else _sev_agreement(v) for k, v in out["reference"].items()}
    if base is not None:
        flips = sev_ok = pairs = maj_flips = 0
        flipped = []
        for i, r in rows.items():
            b = base["rows"].get(i)
            if not b or not r["opinions"]:
                continue
            maj_flips += r["majority"] != b["majority"]
            seats = {o["seat"]: o for o in b["opinions"]}
            for o, bo in ((o, seats[o["seat"]]) for o in r["opinions"] if o["seat"] in seats):  # matched by seat: a seat may have no opinion
                pairs += 1
                if o["verdict"] != bo["verdict"]:
                    flips += 1
                    flipped.append(f"{i}/{o['seat']}: {bo['verdict']}->{o['verdict']}")
                sev_ok += abs(bench.SEV.index(o["severity"]) - bench.SEV.index(bo["severity"])) <= 1
        out["verdict_flips"] = flips
        out["opinion_pairs"] = pairs
        out["majority_flips"] = maj_flips
        out["flipped"] = flipped
        out["severity_within_1"] = sev_ok / pairs if pairs else None
    out["reviews_skipped"] = res["stats"].get("reviews_skipped", 0)
    out["bench_calls_per_claim"] = res["bench_calls"] / res["benched_claims"]
    return out


async def probe(seat_model: str, traps: list[dict]) -> dict:
    """First opinions only, from a candidate model in one seat (via that seat's Groq backup)."""
    role, model = seat_model.split("=", 1)
    raw = config._raw()
    raw["roles"][role]["backup"]["model"] = model
    use_cache(f"probe_{model.replace('/', '_')}")
    groq_only()
    llm = TimedLLM()
    p = next(x for x in bench.PERSONAS if x.role == role)
    rows, errors = {}, []

    async def one(t: dict) -> None:
        case = bench.Case(t["claim"], t["section"], t["risk"], "neutral", bench.cited_text(t["section"], t["claim"]))
        try:
            a = await bench._single_call(llm, p, bench.PERSONAS.index(p), case, None, BASE)
            o = bench._clean(p, model, *a)
            rows[t["id"]] = {"majority": o.verdict, "severity": o.severity, "peer_review": False,
                             "opinions": [{"seat": p.id, "model": model, "verdict": o.verdict, "severity": o.severity}]}
        except Exception as e:  # noqa: BLE001 - a failing candidate is a result, not a crash
            errors.append(f"{t['id']}: {type(e).__name__}: {str(e)[:160]}")

    await asyncio.gather(*(one(t) for t in traps if t["kind"] != "repealed"))
    fresh = [s for _, s in llm.posts]
    res = {"arm": f"probe {seat_model}", "rows": rows, "stats": {}, "bench_calls": len(rows), "benched_claims": max(1, len(rows)),
           "errors": errors, "json_retries": llm.json_retries, "mean_call_s": round(statistics.mean(fresh), 2) if fresh else None}
    res["score"] = score(res, traps, None)
    return res


# ------------------------------------------------------------------ gold.yaml through the whole pipeline


async def bench_claims_per_doc() -> float:
    """How many claims one gold document sends to the bench (offline pipeline; the count does not need a model)."""
    from eval.run_eval import GOLD
    from ain.orchestrator import new_job, run_pipeline

    counts = []
    for doc in yaml.safe_load(GOLD.read_text(encoding="utf-8")):
        r = await run_pipeline(new_job(doc), (config.DEMO_DIR / "docs" / doc).read_bytes(), doc, confirm_timeout=0.1, llm=LLM(mode="fake"))
        counts.append(sum(1 for v in r.ledger if v.bench))
    return statistics.mean(counts)


def _citations(ledger) -> dict:
    """Citation ids by verdict, for comparing two runs of one document."""
    out: dict[str, list[str]] = {"verified": [], "partial": [], "dropped": []}
    for v in ledger:
        c, verdict = (v["claim"]["citation_id"], v["verdict"]) if isinstance(v, dict) else (v.claim.citation_id, v.verdict)
        out[verdict].append(c)
    return {k: sorted(set(x)) for k, x in out.items()}


def earlier_runs() -> dict:
    """recall / precision / citations of the earlier live runs saved in runs/ (replays of them give the same answers)."""
    from eval.run_eval import GOLD, _match
    from ain import vault
    from ain.models import Risk

    spec = yaml.safe_load(GOLD.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for f in sorted(config.RUNS_DIR.glob("*.json*")):
        raw = f.read_bytes()
        d = json.loads(vault.decrypt(raw) if f.name.endswith(".enc") else raw)
        doc = d["document"]["name"]
        if d.get("llm_mode") != "live" or doc not in spec:
            continue
        live = [k for k in (Risk(**r) for r in d["risks"]) if k.status != "dropped"]
        expected = spec[doc].get("expect", [])
        out.setdefault(doc, []).append({
            "run": f.name,
            "recall": sum(any(_match(e, k) for k in live) for e in expected) / len(expected) if expected else None,
            "precision": sum(any(_match(e, k) for e in expected) for k in live) / len(live) if live else (1.0 if not expected else 0.0),
            "risks": len(live),
            "citations": _citations(d["ledger"]),
        })
    return out


async def gold(arm_names: list[str], routing: str = "groq") -> dict:
    from eval.run_eval import GOLD, _match
    from ain.orchestrator import new_job, run_pipeline

    spec = yaml.safe_load(GOLD.read_text(encoding="utf-8"))
    # one shared cache, started from the app's own: every stage before the bench answers identically in every arm
    if not (CACHES / "gold").exists() and (config.CACHE_DIR / "llm").exists():
        shutil.copytree(config.CACHE_DIR / "llm", CACHES / "gold")
    out = {}
    original = bench.Options.from_config
    try:
        for name in arm_names:
            opts = original() if name == "final" else ARMS[name]["opts"]  # final: the flags as set in config.yaml
            bench.Options.from_config = classmethod(lambda cls, o=opts: o)  # type: ignore[method-assign]
            use_cache("gold")
            if routing == "groq":
                groq_only()
            else:  # the app's own routing: OpenRouter judges while the free quota lasts, then their Groq backups
                llm_mod.reset_breakers()
            docs = {}
            for doc, s in spec.items():
                llm = TimedLLM(skip_chair=False)
                t0 = time.perf_counter()
                r = await run_pipeline(new_job(doc), (config.DEMO_DIR / "docs" / doc).read_bytes(), doc, confirm_timeout=0.1, llm=llm)
                live = [k for k in r.risks if k.status != "dropped"]
                expected = s.get("expect", [])
                docs[doc] = {
                    "recall": sum(any(_match(e, k) for k in live) for e in expected) / len(expected) if expected else None,
                    "precision": sum(any(_match(e, k) for e in expected) for k in live) / len(live) if live else (1.0 if not expected else 0.0),
                    "openrouter_calls": sum(1 for c in llm.calls if c.role in BENCH_ROLES),
                    "bench_claims": sum(1 for v in r.ledger if v.bench),
                    "wall_s": round(time.perf_counter() - t0, 1),
                    "fresh_calls": len(llm.posts),
                    "risks": len(live),
                    "citations": _citations(r.ledger),
                    "flags": {k: getattr(opts, k) for k in ("review_only_on_disagreement", "batch", "statute_window", "leans", "review_on_wide_spread")},
                    "routing": routing,
                }
            out[name] = docs
    finally:
        bench.Options.from_config = original  # type: ignore[method-assign]
    return out


# ------------------------------------------------------------------ report


def report(results: dict, traps: list[dict]) -> str:
    arms = results["arms"]
    base = arms.get("baseline_1")
    lines = [f"Trap set: {len(traps)} pairs ({sum(t['bangla'] for t in traps)} Bangla), "
             f"{sum(t['kind'] != 'repealed' for t in traps)} reach the bench. Judges on Groq, temperature 0."]
    if base:
        lines.append("Judge models: " + ", ".join(base["models"]))
    noise = arms["baseline_2"]["score"].get("verdict_flips") if "baseline_2" in arms else None
    per_doc = results.get("bench_claims_per_doc")
    if per_doc:
        lines.append(f"OpenRouter calls/doc = bench calls per claim x {per_doc:.1f} benched claims per gold document (offline pipeline count).")
    hdr = (f"{'arm':<12}{'vs':<11}{'acc':>5}{'bn':>5}{'exact':>6}{'falseS':>7}{'flips':>8}{'majFl':>6}{'sev±1':>6}"
           f"{'HRany':>6}{'HRwide':>7}{'OR/doc':>7}{'skip':>5}{'json':>5}{'s/call':>7}")
    lines += ["", hdr]
    for name, a in arms.items():
        s = a["score"]
        jf = a["json_retries"] + sum(a["stats"].get(k, 0) for k in ("batch_bad_json", "batch_missing_id", "batch_bad_fields", "batch_call_failed"))
        flips = "-" if "verdict_flips" not in s else f"{s['verdict_flips']}/{s['opinion_pairs']}"
        sev = "-" if s.get("severity_within_1") is None else f"{s['severity_within_1']:.0%}"
        pct = lambda x: "-" if x is None else f"{x:.0%}"  # noqa: E731
        or_doc = f"{s['bench_calls_per_claim'] * per_doc:.1f}" if per_doc else "-"
        lines.append(f"{name:<12}{ARMS.get(name, {}).get('vs', '-'):<11}{pct(s['accuracy']):>5}{pct(s['bangla_accuracy']):>5}{pct(s['exact_label']):>6}"
                     f"{len(s['false_supports']):>7}{flips:>8}{s.get('majority_flips', '-'):>6}{sev:>6}{pct(s['human_review_any']):>6}"
                     f"{pct(s['human_review_wide']):>7}{or_doc:>7}{s['reviews_skipped']:>5}{jf:>5}{a['mean_call_s'] or 0:>7}")
    ref = results.get("reference") or {}
    if ref:
        seats = [p.id for p in bench.PERSONAS]
        lines += ["", f"Severity vs the playbook rule's severity ({len(ref)} traps tied to a rule): exact / within one notch / mean signed notches"]
        lines.append(f"  {'arm':<12}" + "".join(f"{x:>24}" for x in ["bench", *(f'{p.lens_label} ({p.name})' for p in bench.PERSONAS)]))
        for name, a in arms.items():
            r = a["score"].get("reference") or {}
            cell = lambda v: "-" if not v or v["exact"] is None else f"{v['exact']:.0%} / {v['within_1']:.0%} / {v['mean_signed']:+.2f}"  # noqa: E731
            lines.append(f"  {name:<12}" + "".join(f"{cell(r.get(k)):>24}" for k in ["bench", *seats]))
    lines.append("")
    for name, a in arms.items():
        s = a["score"]
        extra = {k: v for k, v in a["stats"].items() if k.startswith("batch") or k == "statute_trimmed"}
        lines.append(f"{name}: by kind {s['by_kind']}; false supports {s['false_supports'] or 'none'}; missed {s['missed_supports'] or 'none'}"
                     + (f"; batch/window {extra}" if extra else "") + (f"; flipped {s['flipped']}" if s.get("flipped") else "")
                     + (f"; NO OPINION {s['no_opinion']} (rerun with --keep to retry)" if s.get("no_opinion") else ""))
    lines += ["", "Per judge (own verdict correct / opinions), Bangla vs English statutes:"]
    for name in ("baseline_1", "baseline_2", "no_leans", "rubric"):
        if name in arms:
            for j, v in arms[name]["score"]["judges"].items():
                lines.append(f"  {name} {j}: Bangla {v['bn']}, English {v['en']}")
    for p in results.get("probes", []):
        s = p["score"]
        lines.append(f"Probe {p['arm']}: accuracy {s['accuracy']:.0%}, false supports {s['false_supports'] or 'none'}, "
                     f"answered {len(p['rows'])}, errors {len(p['errors'])}, json retries {p['json_retries']}, {s['judges']}")
        lines += [f"    {e}" for e in p["errors"][:6]]
    if results.get("gold"):
        lines += ["", "gold.yaml (whole pipeline): recall / precision / OpenRouter calls per doc"]
        for name, docs in results["gold"].items():
            cells = []
            for d, v in docs.items():
                rec = "-" if v["recall"] is None else f"{v['recall']:.0%}"
                cells.append(f"{d.split('.')[0]} {rec}/{v['precision']:.0%}/{v['openrouter_calls']}")
            lines.append(f"  {name:<12}" + "  ".join(cells))
        final, before = results["gold"].get("final"), results.get("earlier_runs") or {}
        if final:
            lines += ["", "final config vs the earlier live runs (runs/): recall / precision / risks; citations"]
            for doc, v in final.items():
                rec = lambda x: "-" if x["recall"] is None else f"{x['recall']:.0%}"  # noqa: E731
                lines.append(f"  {doc}: final {rec(v)} / {v['precision']:.0%} / {v['risks']} risks")
                if doc not in before:
                    lines.append("      no earlier live run of this document")
                    continue
                for e in before[doc]:
                    lines.append(f"      earlier {e['run']}: {rec(e)} / {e['precision']:.0%} / {e['risks']} risks")
                e = before[doc][-1]
                for kind in ("verified", "partial", "dropped"):
                    now, then = set(v["citations"][kind]), set(e["citations"][kind])
                    if now != then:
                        lines.append(f"      {kind}: added {sorted(now - then) or 'none'}; gone {sorted(then - now) or 'none'}")
                    else:
                        lines.append(f"      {kind}: same {len(now)}")
    lines += ["", "Verdict (a flag may be turned on only if every check passes):"]
    for name, flag in FLAG_ARMS.items():
        if name not in arms or noise is None:
            continue
        s = arms[name]["score"]
        checks = {
            "0 false supports": not s["false_supports"],
            f"flips {s['verdict_flips']} <= noise {noise}": s["verdict_flips"] <= noise,
        }
        if name == "rubric":  # meant to move severities: it must match the playbook's severities at least as well instead
            mine = (s.get("reference") or {}).get("bench") or {}
            theirs = ((arms.get("no_leans") or {}).get("score", {}).get("reference") or {}).get("bench") or {}
            if mine.get("within_1") is not None and theirs.get("within_1") is not None:
                checks[f"reference ±1 {mine['within_1']:.0%} >= no_leans {theirs['within_1']:.0%}"] = mine["within_1"] >= theirs["within_1"]
                checks[f"reference exact {mine['exact']:.0%} >= no_leans {theirs['exact']:.0%}"] = mine["exact"] >= theirs["exact"]
        else:
            checks[f"severity ±1 {s['severity_within_1']:.0%} >= 90%"] = (s["severity_within_1"] or 0) >= 0.9
        if s.get("no_opinion"):
            checks[f"{len(s['no_opinion'])} seats with no opinion (retry)"] = False
        g = results.get("gold") or {}
        if name in g and "baseline_1" in g:
            drop = any((g[name][d]["recall"] or 0) < (g["baseline_1"][d]["recall"] or 0) or g[name][d]["precision"] < g["baseline_1"][d]["precision"] for d in g[name])
            checks["no gold recall/precision drop"] = not drop
        ok = all(checks.values())
        lines.append(f"  {flag:<28} {'PASS' if ok else 'HOLD'}  " + "; ".join(f"{'ok' if v else 'NO'} {k}" for k, v in checks.items()))
    return "\n".join(lines)


async def main_async(args) -> None:
    traps = load_traps()
    results = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() and args.keep else {"arms": {}}
    results.setdefault("arms", {})
    results["bench_claims_per_doc"] = await bench_claims_per_doc()
    results["reference"] = reference_severities(traps)

    def rescore() -> None:
        for name, res in results["arms"].items():
            base = results["arms"].get(ARMS.get(name, {}).get("vs", ""))
            res["score"] = score(res, traps, base, results["reference"])

    for name in [a for a in args.arms.split(",") if a]:
        print(f"... {name}", flush=True)
        try:
            results["arms"][name] = await run_arm(name, traps)
        except LLMError as e:  # BudgetOut, or an error outside the bench
            print(f"stopped at {name}: {e}\nThe answers so far are cached; run again with --keep (e.g. tomorrow) to resume.", flush=True)
            results["stopped_at"] = name
            break
        results.pop("stopped_at", None)
        rescore()
        OUT.write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    rescore()
    if args.probe:
        results["probes"] = [await probe(sm, traps) for sm in args.probe]
    if args.gold:
        names = [a for a in args.gold_arms.split(",") if a == "final" or a in ARMS]
        results["gold"] = {**results.get("gold", {}), **await gold(names, args.gold_routing)}
        results["earlier_runs"] = earlier_runs()
    OUT.write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(report(results, traps))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--probe", action="append", default=[], help="seat=model, e.g. bench_b=allam-2-7b")
    ap.add_argument("--gold", action="store_true")
    ap.add_argument("--gold-arms", default="baseline_1,no_leans,review_skip,batch,window", help="arm names, or final for config.yaml's flags")
    ap.add_argument("--gold-routing", choices=("groq", "config"), default="groq", help="config: the app's own model routing")
    ap.add_argument("--keep", action="store_true", help="keep arms already in bench_quality.json")
    ap.add_argument("--fake", action="store_true", help="offline dry run with the fake LLM (checks the harness, not the models)")
    args = ap.parse_args()
    global MODE, OUT, CACHES
    if args.fake:  # never touch the live arms' caches
        MODE, OUT, CACHES = "fake", OUT.with_name("bench_quality.fake.json"), CACHES.with_name("bench_quality_fake")
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
