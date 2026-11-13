# Grey on Qwen, ERNIE as its backup, and a seat health check

Approved in chat on 2026-11-13, after the live gold-set eval (spec 16) found Grey's model withdrawn.

## Context
- OpenRouter stopped serving `xingchen-agi/xing4.0-29b-a4b:free` between the two eval days: 404, "no provider serves this model anymore". Every Grey call then spent a request on the 404 before reaching its Groq backup (25 times on day 2). Xing was also `fast`'s backup.
- The obvious OpenRouter replacement, `baidu/ernie-5.5-flash-preview:free`, is a preview released on 10 November with a single provider. As a primary it is a high withdrawal risk before final judging.
- Nothing noticed a withdrawn model except the trace of each run.

## Decisions (the user's)
1. **Grey's primary is Groq `qwen/qwen3.8-27b`.** Qwen is a different family from the Chief Justice (GPT-OSS). Qwen was Sunny's backup, so Sunny's backup becomes Groq `openai/gpt-oss-120b`, and no two seats share a model.
2. **ERNIE 5.5 Flash is Grey's backup**, if a live probe under `data_collection: deny` returns valid JSON 2 times out of 2.
3. **A startup health check** pings each seat's model once, keeps the result for six hours, and moves a seat whose model is gone to a fallback of a family different from the Chief Justice's and the other seats'. If that is impossible, the seat takes the nearest model that answers, the warning says which family it shares, and the bench's existing "same family (fallback)" badge marks any two judges of one family.

## Approach
- **Routing (`ain/config.yaml`).**
  - `bench_c`: Groq Qwen 3.8 27B, backup OpenRouter ERNIE 5.5 Flash preview.
  - `bench_a`: backup changes from Qwen to GPT-OSS 120B.
  - `fast`: backup changes from Xing to Gemma 4 26B (it is not a seat, so sharing Sunny's fallback model is fine).
  - Groq serves only two families usable as judges, GPT-OSS and Qwen (Allam 2 7B has a 4k context). So when OpenRouter is out of quota, Sunny and Regal both land on GPT-OSS, as they did before (then Sunny's backup was Qwen and Grey's GPT-OSS 120B). The badge already marks that.
- **Gone models (`ain/llm.py`).**
  - A 404 raises `_Gone` (a `_RouteFailed`, so the next route is still tried) and marks that model gone for six hours.
  - `plan(role)` is the configured routes with gone models taken out and the health check's pick moved first. Models left of one configured route stay together, so OpenRouter still gets them as `models: [...]`.
  - A configured route that now starts on one of its fallbacks is `rerouted`, so its answers are still marked as fallbacks.
  - A rerouted answer is cached under its own model, and cache lookups read those keys too.
  - With nothing gone, `plan(role)` equals the configured routes, so routing and cache keys are unchanged.
- **Seat health (`ain/seat_health.py`).**
  - At startup (live mode only) each seat's model gets one ping. It goes through the real request path, with the data policy and JSON mode.
  - "Gone" means a 404. A rate limit or an outage is "unknown" and moves nothing.
  - Pings are kept in the LLM cache for six hours, so a restart spends no request.
  - A seat whose model is gone takes the first model in its own chain that answers and whose family is not the Chief Justice's or another seat's current one. Failing that, it takes the first that answers and reports `same_family_as`.
  - The API runs the check in the background at startup. `/api/health` lists each seat (`configured`, `using`, `gone`, `same_family_as`, `warning`), and a warning is logged.
- **Probe (`scripts/smoke_live.py --probe provider/model`).** One ping, then two JSON verdict calls on a corpus section, through the real request path and never the cache. Valid means the verdict is one of supports / contradicts / neutral and the reason is non-empty.

## Files
`ain/config.yaml`, `ain/llm.py`, `ain/seat_health.py`, `ain/api.py`, `scripts/smoke_live.py`, `tests/test_seat_health.py`, `README.md`, `docs/AI_USAGE.md`, `web/src/app/docs/page.tsx`.

## Verification
- **Probe of ERNIE (2026-11-13), `smoke_live --docs 0 --probe openrouter/baidu/ernie-5.5-flash-preview:free`:** the ping was answered, so the endpoint is allowed under `data_collection: deny`. 2 of 2 verdicts were valid JSON (supports, 2.0 s; contradicts, 1.2 s). The first try crashed after its first valid answer, because the Windows console could not print a Bangla word from the reply; `smoke_live` now replaces unprintable characters.
- **`tests/test_seat_health.py`** (9 tests), with a fake "no provider serves this model anymore" 404:
  - one ping per seat;
  - a withdrawn model moves the seat to another family, logs a warning, and sends later calls straight to the replacement, marked as a fallback;
  - with no other family left, the seat says which family it shares;
  - a rate limit is not "gone";
  - pings are kept for six hours, then sent again;
  - a 404 on an ordinary call skips that model from then on;
  - nothing is pinged outside live mode;
  - a same-family next model is skipped for a later one;
  - a promoted fallback's answer is still marked as one.
- **Mutations:** removing the pick, the family test, the 404 classification, the six-hour reuse or the `rerouted` mark each fail a test. The `rerouted` one was missed at first, so its test was added.
- **`pytest`:** 299 passed.
- **`run_eval` in fake mode:** every check passes on all five gold documents (the live report was kept aside and restored).
- **Grey's part of `bench_quality`** (`--probe bench_c=qwen/qwen3.8-27b`, first opinions on the 36 trap claims):
  - **86% correct** (31 of 36: Bangla 12 of 14, English 19 of 22), with no false "supports", 0 errors and 0 JSON retries.
  - By kind: wrong section 6 of 6, contradicted 7 of 7, proviso 10 of 10, but correct only 8 of 13. Qwen as Grey errs on the cautious side, refusing some propositions the section does support. That raises dissents and human-review flags, not false approvals.
  - For comparison, in the baseline arm Grey's previous Groq backup (GPT-OSS 120B) got 36 of 36, and Qwen in Sunny's seat 32 of 36. GPT-OSS is the Chief Justice's family, which is why it was not chosen. Qwen's weaker "correct" score is a known cost of this decision.
- **`smoke_live --docs 1`** (Malaysia, live, new routing): 7 risks (2 off-playbook), 17 verified, 1 partial, 3 dropped. 74 calls, 12 via fallback: Sunny was rate-limited upstream and answered on GPT-OSS 120B. Grey answered on Groq Qwen with no 404. 7 of 8 risks had a bench dissent, against 6 of 7 in the eval (spec 16), so this is not new. OpenRouter: 44 of 50 used today.
