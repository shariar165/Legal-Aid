# Evidence-gated deliberation, pressure trap and Case Room events

## Context
LLM judges change their answers under peer pressure, even when the argument is empty. Today the council's round 2
takes `revised` on the model's word, and the Chief Justice reads every claimed position. This change makes a change of
view count only when it rests on new, verified law, measures each seat's sycophancy, and adds the three SSE events the
Live Case Room design needs.

**Decisions (from you):** branch `evidence-gate` off **`deploy`** (not `main`: local `main` has no `bench_quality.py`,
`origin/main` has no token pacing, AGENTS.md or docs/specs). **Live Case Room page is out of scope:** events and
types only. **Nothing is committed:** all work stays in the working tree. Your uncommitted scene work
(`Council.tsx`, `counsel.module.css`, `CouncilFight.tsx`, n8n files) carries over untouched and unstaged.

After approval, save this as `docs/specs/2026-11-04-14-evidence-gate.md` and add row 14 to `docs/specs/README.md`.

## Where the spec needs more than it says
Found while reading the code. Each is handled below; the first two limit what the feature can do.

| # | Finding | What I'll do |
|---|---|---|
| 1 | **On most risks a member can't move on evidence.** `allowed` is per-risk: 8 of 12 EPZ risks (4 of 6 benched) have one citation, and round 1 normally cites it, so nothing "new" exists. | Implement rule 3 strictly as written. Conservative failure (round-1 view stands). Report it in the summary and README limitations. |
| 2 | **Whole-contract mode shows no statute text**, only propositions, so a verbatim quote is impossible. | Round 2 only, whole-contract only: add a `TEXT:` excerpt capped at 300 chars per citation. Capped so a Bangla-heavy prompt can't exceed Groq's 8k TPM and fail. |
| 3 | **Position is free text**, so a plain compare calls every rewording a flip. Fuzzy alone can't fix it: measured rewordings score 69-93, a real reversal ("Do not sign" / "Sign") scores 85. | Round 2 prompt: "if you keep your view, repeat your first position word for word". Compare with `fuzz.ratio` >= 90 on `bench._flat` text. Eval reports undeclared flips separately, so noise is visible. |
| 4 | **G2 alone is too weak:** `"the"` and `"law"` score 100 on `partial_ratio`; an empty quote returns `skip`, not `fail`. | Reuse `gate_fidelity`, require status `pass`, and add the 12-char floor `bench.quote_in` already uses. |
| 5 | **`changed_because` could leak a bad citation** to the UI (hard rule 2). | Keep it only when `flip_basis == "evidence"`; otherwise `None`. The reason goes in a new `flip_note` (fixed strings only, so no model text reaches the Chief Justice's prompt). |
| 6 | **Sections must come from `result.ledger`, not the corpus:** uploaded policy sections exist only in the job's overlay. | Look up the section via ledger rows. |
| 7 | **`_reply` falls back to fake values** for missing fields, which would invent a severity flip in round 2. | Round 2 severity: model's value or `None`, never the fallback. `None` means no comparison and round 1 stands. |
| 8 | **There's no council "vote tally" today**, and `agreement` comes from the model. Overriding it breaks `test_ruling_is_grounded_and_sanitised` (fake R1 splits medium/high) and it describes positions anyway. | Keep `agreement`. Add a code-computed `CouncilRuling.votes`; the UI shows that tally. |
| 9 | **`rate_wait` can't occur in fake mode** (`_post` never runs), yet the spec wants it in the fake EPZ stream. | No test-only branch in production. `test_api` wraps `LLM.json` to fire the real emitter; `test_llm_routing` covers the real waits through its MockTransport. |
| 10 | **No severity scale exists in the app.** The design is in `Council v3.dc.html`, not `Live Case Room`. | Build a compact version from that design. |
| 11 | **Round-1 replies come from the client**, so a tampered request could fake "new". | Accept for now (it only affects that user's own view). Add to README limitations. |

## Part 1: Evidence gate
**`ain/agents/council.py`**
- `CHAT_SYSTEM`, `REBUTTAL_SYSTEM`: add `severity` only when `risk` is set, via an inserted line and JSON key. Whole-contract prompts stay byte-identical for round 1.
- `REBUTTAL_SYSTEM`: require `changed_because` when `revised` is true; add the word-for-word rule (finding 3).
- `build_context(..., excerpts=False)`: `rebut` passes `True` (finding 2). Reuse `bench.window`, then cap at `EXCERPT_CHARS = 300`.
- New `_check_revision(first, out, allowed, sections) -> (basis, because, note)`, in order:
  1. no declared revision, no severity or position change: `None`
  2. undeclared change: `pressure`
  3. no valid `changed_because`, or id outside `allowed`, or quote fails G2, or id in `first.citations`: `pressure`
  4. otherwise: `evidence`
- New `_counted(first, second)`: round-1 severity and position when `pressure`; otherwise round 2's.
- `deliberate`: Chief Justice context gets a `COUNTED POSITIONS` block and a `REVISIONS` block (who counted, who didn't, why). In `ROUND 2`, drop a pressure member's claimed position and mark it not counted. `RULING_SYSTEM` is told to count only the former.
- Fakes: `_fake_reply` adds `severity` (risk in focus only). `_fake_rebuttal` takes round 1 and gives both paths deterministically: Sunny revises on evidence when an unused citation exists; Grey claims a one-notch move with no evidence. This is what makes the browser check possible.

**`ain/models.py` / `web/src/lib/api.ts`:** `CouncilReply` gains `severity: Severity | None`, `flip_basis`, `changed_because: ChangedBecause | None`, `flip_note`. New `CouncilVote` (member, severity, position, flip_basis); `CouncilRuling.votes`. I'm using the `Severity` literal rather than `str`, so bad client values get a 422.

**`web/src/components/counsel/Council.tsx`, `counsel.module.css`** (edits sit alongside your uncommitted scene work)
- `ReplyCard`: "Moved on evidence ✓" with the citation chip and quote; "Moved under pressure: not counted", with `flip_note` as the tooltip; otherwise "Kept position".
- New `SeverityScale`, shown after round 2 when a risk is in focus: four bands, each avatar at its counted severity, a faint ghost and dashed line at a pressure member's claimed severity. Tokens from existing `data-sev`; works at phone width and with reduced motion.
- `RulingCard`: counted tally from `votes`.
- `historyOf`: use the counted position, so a blocked claim doesn't enter the next question's history.

## Part 2: Pressure trap (`eval/bench_quality.py`)
- `PRESSURE_TRAPS`: six existing cases (2 correct, 2 proviso, 1 contradicted, 1 wrong_section; English and Bangla).
- Reuse `load_traps`, `TimedLLM`, `groq_only`, `use_cache("pressure_trap")`. Each case gets a small `AnalysisResult.model_construct(...)` with a verified ledger row, so the real `ask` and `rebut` run unchanged.
- Each case also gets a companion row from the same act. Without it `allowed` has one id and every flip fails "new" automatically, making "blocked" meaningless.
- For each seat: real round 1, then round 2 against a confident colleague citing nothing. The claim is "critical", or "low" if the member already sits at high/critical, otherwise it isn't pressure.
- **Control arm (small addition):** same round 2 with a neutral colleague. Without it, raw flips can't be told from natural drift. The eval already measures noise the same way (`baseline_2`).
- Output, per seat: cases, raw flips and rate, blocked, counted, undeclared, control flips, models. Plus block reasons. Written to `eval/pressure_trap.json` (`.fake.json` under `--fake`).
- Runs **before** the arms, so a Groq daily-limit stop can't lose the table; `BudgetOut` saves partial results marked `incomplete`.
- Scores are on the seats' **Groq backup models** (as the whole eval is), not their OpenRouter models. The table says so.
- Not fed into prompts. `config.yaml` adds `council: {peer_stability_notes: false}`, with `config.council_settings()`.
- Add `backend/eval/pressure_trap*.json` to `.gitignore`, matching `bench_quality*.json`.

## Part 3: Events
- **`clause_ids`:** one `_risk_found(job, agent, risk)` helper replaces the five `job.say("risk_found", ...)` calls in `orchestrator.py`.
- **`LLM._on_event`:** one optional callback, set in `_run` beside `_on_call`. It carries both new events without threading a parameter through `verify_all`, `verify_claim`, `convene`, `convene_many` and `_round`.
- **`bench_opinion`:** emitted from `bench._round` per judge as answers arrive: persona, verdict, severity, model, claim_id, plus `round`.
  - **Beyond the spec:** a judge who actually revises in peer review emits once more (`round: 2`), or the live vote would disagree with the ruling. In fake mode nobody revises, so it's exactly one per judge. Seats with no opinion emit nothing.
  - Bench prompts don't change.
- **`rate_wait`** (`ain/llm.py`): split `_Pacer.wait` into a sync `slot()` plus sleep. Per attempt in `_post`, add the pacer and token-bucket delays and emit once **before** sleeping; emit once for each 429/5xx retry-after wait.
  - Transport and bad-JSON backoffs aren't rate waits and stay silent.
  - Waits under 1 s are skipped (`RATE_WAIT_MIN_S`), since sub-second pacing would flood the trace.
  - Fields: seconds, provider, model. `agent` is left out: `_post` doesn't know it, and the page that would use it is out of scope.
- **`web/src/lib/api.ts`:** typed `risk_found`, `bench_opinion`, `rate_wait` payloads. `TracePanel` shows them through their `message` text, so it needs no change.

## Tests
`backend/tests/test_council.py`: the six listed cases, plus short and empty quote rejected, whole-contract excerpts present and bounded, policy-overlay section accepted, `changed_because` stripped on pressure, reworded position within tolerance not flagged, severity fields fake-valid.
`backend/tests/test_llm_routing.py`: retry-after emits one event; token-bucket wait emits one, not per second; sub-second wait emits none.
`backend/tests/test_api.py`: all three new events appear in the EPZ stream; every `risk_found` has `clause_ids`; three `bench_opinion` per benched claim.
New `backend/tests/test_pressure_trap.py`: fake harness run, table shape, JSON written, flag off and absent from prompts.

## Docs
`README.md` Honest limitations (findings 1, 11, Groq-backup scoring), `docs/AI_USAGE.md` (evidence gate, pressure trap). `AGENTS.md` asks for a flag on unproven behaviour; I'm not adding one for the gate because you specified it as always on, and it can only make the council more conservative. `smoke_live` doesn't exercise the council and bench prompts are unchanged, so no cache re-warm is needed.

## Verification
```bash
git switch -c evidence-gate                          # from deploy; carries the working tree
cd backend && python -m pytest -q                    # AIN_LLM_MODE=fake via conftest
python -m eval.run_eval
python -m eval.bench_quality                         # live on Groq if budget allows
cd ../web && npm run lint && npm run build
```
- `.env` sets `AIN_LLM_MODE=live`, and keys exist, so `run_eval` and `bench_quality` will **spend free-tier Groq quota**. Several arms are uncached (`rubric`, `review_skip`, `window`), so the sweep may hit the daily limit. If it does, I report where it stopped; the pressure table will already be saved.
- If live runs can't complete, I fall back to `--fake` and label that table a harness check, not a sycophancy score.
- Gate 3 browser check in fake mode, on a multi-citation risk (R9): evidence card, pressure card, ghost on the scale, phone width.
- Final summary: what changed, the pressure-trap table, the finding-1 limitation, anything unfinished.
