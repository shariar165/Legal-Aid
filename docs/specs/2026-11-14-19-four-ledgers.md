# Four Ledgers (চার খাতা), backend v1

Approved in plan mode on 2026-11-14. Branch `four-ledgers` off `evidence-gate`.

## Context
A migrant worker is often told one thing by the agent (কথা), signs another (কাগজ), is paid a third (টাকা), and the law
says a fourth (আইন). Ain checks the paper against the law, but it does not record what the worker was told. This
feature adds a per-term ledger that sets the four cells side by side and types every mismatch.

v1 covers কথা, কাগজ and আইন. The টাকা cell (payslip) stays in the model and is always empty until the next spec. The
ledger is deterministic and makes no model call. Its law cells come only from claims the 4-gate verifier already
passed. A gap between what was said and the paper on pay or benefits becomes a normal playbook Risk anchored on
OEMA 2013 s.31(ঘ), and it goes through the verifier like any other risk.

## Decisions to confirm on approval
1. **Field name.** `AnalysisResult.ledger` already exists: it is the citation ledger (`list[Verification]`) that
   the drafter, council and UI read. The new field is **`four_ledgers: FourLedgers | None`**, so nothing that reads
   the citation ledger breaks.
2. **`PB-PROMISE-GAP` severity is `medium`.** The gap rests on what the worker reports, not on proof of fraud.
   `medium` also keeps the Virtual Bench off (it sits on `critical`/`high` only), so the claim gets the same
   single-judge entailment check at analyze time and on a later `/promises` call. A `high` severity would need the
   bench, which means model calls, on `/promises`, and the spec rules those out.
3. **Recomputing with no model call.** When the flag is on and the rule is active (`bd_migration` routed), the
   analysis always verifies the rule's anchor claim once. It does this as a standing claim `L1` (risk_id `"L"`,
   like the procedural `P` claims), unless the risk already fired with its own claim. `/promises` then reuses that
   stored `Verification` for an identical claim (same citation_id, proposition and quote). If there is none, or it
   was dropped, no risk is created: the mismatch still shows, with the law cell marked `not_verified`.
4. **Break-even when currencies match.** If the cost paid and the monthly pay are in the same currency, no rate is
   needed. If they differ, break-even is computed only with a user-entered rate. The same rule applies to the
   salary comparison between what was said and the paper.
5. **The memo is not redrafted on `/promises`.** Redrafting would need a model call. `four_ledgers`, the risk list
   and the stats are updated. `four_ledgers.memo_includes_promises` says whether the memo saw them.

## Approach

### 1. Models (`ain/models.py`)
- `ExchangeRate{currency: str, per: str, value: float > 0, source: Literal["user-entered"] = "user-entered"}`,
  meaning 1 `per` = `value` `currency` (e.g. 1 RM = 27.5 BDT).
- `Promises` (structured only, every field optional):
  - `salary_amount` / `salary_currency`, `no_deductions: bool | None`
  - `recruitment_cost_paid` / `recruitment_cost_currency`, `hours_per_day`
  - `ticket_paid_by` / `passport_kept_by: Literal["worker","employer","agency"] | None`
  - `contract_months`, `said_on: date | None`, `note: str` (max 1000, stored redacted), `exchange_rate: ExchangeRate | None`
- `LedgerCell{value: str, amount, currency, clause_id, source: Literal["worker","contract","payslip","law"]}`
- `LawCell{status: Literal["verified","partial","not_verified","none"], citation_ids, risk_id, proposition}`
- `Mismatch{type: Literal["said_vs_paper","paper_vs_law","paid_vs_paper"], detail: L10n, risk_id: str | None}`
- `LedgerRow{term, said, paper, paid (always None in v1), law: LawCell, mismatches, severity: Severity | None, risk_id}`
- `ClaimLine{label: L10n, amount, currency, citation_id, risk_id, basis: str}`
- `ClaimValue{lines, total, currency, label: L10n}`. The label reads "computed under the cited law, not a
  prediction of any award", in Bangla and English.
- `PromiseGap{monthly, months, total, currency, label: L10n}`. It is kept apart from `ClaimValue` and never added
  to its total.
- `BreakEven{months: float | None, cost, monthly_net, currency, rate: ExchangeRate | None, note: str}`
- `FourLedgers{promises, rows, claim_value, promise_gap, break_even, memo_includes_promises}`
- `DocFacts`, new fields filled by regex only:
  - `contract_months`, `hours_per_day`
  - `ticket_paid_by` and `passport_held_by: Literal["worker","employer"] | None`
- `AnalysisResult.four_ledgers: FourLedgers | None = None`.

### 2. Paper facts (`ain/agents/ingestion.py` `extract_facts`)
Four deterministic regexes, in the style of `notice_days`:
- term: `(\d+)` years or months near "period", "term" or "মেয়াদ" (3 years → 36)
- hours: `(\d+) hours per day`
- ticket: who "shall bear" the "ticket"
- passport: surrender/custody/keep, giving `employer`; "Worker shall retain", giving `worker`

**Cache key: unchanged.** `router.FACTS_SYSTEM` is not edited, and no prompt serialises `DocFacts` (the only
facts reaching prompts are `adversary.py:407`'s destination, governing law and EPZ). With the flag off, every
prompt is byte-identical, so the replay cache needs no re-warm. With the flag on and promises given, the new
`PB-PROMISE-GAP` risk enters the Adversary's and drafter's inputs, so those runs miss the cache. The standing `L1`
claim adds one judge call. Re-warm (`warm-cache`) only before a live demo that uses promises.

### 3. Playbook rule `PB-PROMISE-GAP` (`ain/playbook/rules.yaml`)
- Rule settings:
  - `packs: [bd_migration]`, `severity: medium`, `category: deception`
  - `trigger: {fact: promise_gap}`
- One anchor, `BD-OEMA-2013-s31`.
  - The quote comes from s.31(ঘ) and is copied with the MCP `get_section` tool at build time, never typed. The
    section was fetched while writing this plan: (ঘ) is the clause on fraudulently promising higher pay, allowances
    and benefits to induce migration.
  - The proposition says that inducing someone to migrate, or to contract for migration, by fraudulently promising
    higher pay, allowances and benefits is an offence (up to 5 years and a fine of at least Tk 1 lakh).
- Citizen and action text are worded as "what you were told differs from the paper", not as an accusation.
- `test_corpus.py` already checks that the quote is verbatim.

`ain/agents/risk_analyst.py`:
- `run_fact_check` and `run_fact_rules` take `promises: Promises | None = None`.
- `promise_gap` returns a finding when `ledger.pay_benefit_gaps(facts, wage, promises)` is non-empty. That covers
  salary said > paper, "no deductions" said while the paper deducts, and the employer said to pay the ticket while
  the paper says the worker. Hours, term and passport are mismatches in the ledger but are not pay or benefits, so
  they do not count here (the passport already has `PB-PASSPORT`).
- Add `FACT_CLAUSE_HINTS["promise_gap"]`.

### 4. `ain/agents/ledger.py` (new; deterministic, no LLM, no corpus lookups)
- `pay_benefit_gaps(facts, wage, promises) -> list[str]`, shared with the rule above.
- `build(facts, wage, clauses, risks, ledger, promises, memo_includes_promises) -> FourLedgers`
- Rows: `salary`, `deductions`, `recruitment_cost`, `hours_per_day`, `ticket`, `passport`, `contract_months`.
  - The paper cell's `clause_id` comes from a per-term hint regex over the redacted clauses.
  - A row is emitted when it has a said or a paper cell.
- **Law cell**, from the linked risk only:
  - The link is first by `rule_id`:
    - salary → PB-MIN-WAGE; deductions → PB-DEDUCTION-CAP; recruitment_cost → PB-RECRUIT-FEE; passport → PB-PASSPORT
    - said_vs_paper on salary, deductions or ticket → PB-PROMISE-GAP
  - Otherwise the link is a live risk whose `clause_ids` hold the row's paper clause.
  - The cell lists that risk's claims with verdict `verified` (or `partial`, so marked) in the citation ledger.
  - If the risk is dropped, or none of its claims passed, the cell is `not_verified` with no citations.
  - With no linked risk the cell is `none`.
  - It never looks up a section by itself, so this adds no new citation path.
- **Mismatches**:
  - `said_vs_paper`: compare what was said with the paper. Amounts are compared only in the same currency or
    through a user rate.
  - `paper_vs_law`: only when the linked risk is live and its law cell is verified or partial.
  - `paid_vs_paper` is in the type and never produced.
  - Row severity is the worst linked-risk severity, or `low` for a said_vs_paper gap that has no risk.
- **Claim value** (arithmetic; each line needs a claim with verdict `verified`, and is dropped otherwise):
  - **Minimum-wage shortfall** = `wage.shortfall × months`, cited on `wage.minimum_wage_citation`, only if the
    PB-MIN-WAGE risk's claim on that id is verified.
    - Months come from the paper `contract_months`, or from the said value if the paper has none.
    - `basis` records which.
  - **Recruitment costs taken from wages** = Σ deductions whose label matches recruit/visa/agency (`amount × months`).
    - It is cited on the PB-RECRUIT-FEE risk's first verified claim on a `kind == "law"` section, with the
      destination-country anchor first and ILO next.
  - `total` = sum of the lines, in the wage currency.
- **Promise gap** = (said salary − paper salary) × months, shown on its own and labelled as the worker's account.
- **Break-even** = cost paid ÷ `wage.net`. The cost is converted only through the user's rate when the currencies
  differ, and the rate is returned marked `user-entered`. With no wage, net ≤ 0, or a missing rate, the result is
  `months=None` and a note explains why.

### 5. Orchestrator (`ain/orchestrator.py`)
- `run_pipeline(..., promises: Promises | None = None)`. The note is redacted right away with the job's `mapping`,
  so the same identifier keeps the same placeholder, and its redactions are added to `privacy`. The raw note is
  never put on the Job or the trace.
- `run_fact_rules(..., promises=promises)`.
- When `config.ledger_enabled()` is on and PB-PROMISE-GAP is active but did not fire, its anchors become standing
  claims `L1…`. They are verified with `verifier.verify_all(llm, corpus, route, [], …)`, added to `full_ledger`, and
  kept out of the citizen view's procedural list.
- After the Critic, `ledger.build(...)` runs and adds an `agent_done` event from "Four Ledgers".
- New `recompute_ledger(result, promises) -> FourLedgers`, which uses no LLM object at all:
  1. Redact the note. Placeholder counters continue from `result.privacy.redactions` through a sentinel mapping,
     and the receipt is updated.
  2. Remove any earlier PB-PROMISE-GAP risk and its rows in the citation ledger.
  3. Rerun the `promise_gap` fact check. If it fires, build the risk with `risk_analyst._risk_from_rule`, numbered
     after the highest `R` id.
  4. Attach verifications through the new `verifier.reuse(claim, ledger)`, which copies an identical stored claim's
     gates. If nothing can be reused, no risk is created.
  5. Rebuild `four_ledgers` with `memo_includes_promises=False`, update the stats, and call `save_result`.

### 6. API (`ain/api.py`)
- `POST /api/analyze`:
  - New `promises: str | None = Form(None)`, parsed with `Promises.model_validate_json`.
  - An invalid value gets 422. Promises sent while `ledger.enabled` is off get 400.
- `POST /api/jobs/{job_id}/promises` (`owned_job`):
  - The body is `Promises`; the handler calls `recompute_ledger` and returns `FourLedgers`.
  - 404 when the flag is off (as the automation endpoint does), 409 while the job is still running.

### 7. Config
- `config.yaml`: `ledger: {enabled: false}` with a comment pointing to this spec.
- `config.py`: `ledger_enabled()`, which reads `_raw().get("ledger", {})`.

### 8. Demo fixture
`backend/demo/promises/migrant_text.json`, fictional:
- RM 1,800 salary, "no deductions": yes
- BDT 450,000 recruitment cost paid, 8 hours a day
- employer pays the ticket, worker keeps the passport, 36 months
- `said_on` 2026-08-01
- a note containing a fake phone number and an "Mr …" name, so redaction shows
- rate 1 RM = 27.5 BDT, marked as a demo value the user would type

`SAMPLES["migrant_text"]` gets `"promises_file"`. With the flag on, the sample run loads it.

### 9. README
- Feature row: Four Ledgers, behind a flag.
- "Honest limitations":
  - Promises are typed by the user, not read from chats or voice notes.
  - The টাকা ledger (payslips) is not built yet.
  - Hours and ticket rows have no law cell unless a verified risk sits on that clause.
  - The claim value is arithmetic under the cited law, not a forecast.
  - A `/promises` update does not redraft the memo.
  - No exchange rate is built in.

Not in this spec: payslip OCR, ILO indicator map, fee ceilings, complaint file, frontend, council, MCP
`analyze_contract`.

## Files
- New: `ain/agents/ledger.py`, `tests/test_ledger.py`, `demo/promises/migrant_text.json`, `docs/specs/2026-11-14-19-four-ledgers.md`
- Edited:
  - `ain/models.py`, `ain/agents/ingestion.py`, `ain/agents/risk_analyst.py`, `ain/agents/verifier.py` (`reuse`)
  - `ain/orchestrator.py`, `ain/api.py`, `ain/config.yaml`, `ain/config.py`, `ain/playbook/rules.yaml`, `README.md`

## Verification
`tests/test_ledger.py`, in fake mode, with `config.ledger_enabled` monkeypatched to on:
1. **Malaysia sample with the fixture promises.** Expected rows and mismatches:

   | Row | Said | Paper | Law | Mismatch |
   |---|---|---|---|---|
   | salary | RM 1,800 | RM 1,200 | RM 1,700, MY-MWO-2024-p3 | said_vs_paper + paper_vs_law |
   | deductions | none | RM 650 (54.2%) | 50% cap | said_vs_paper + paper_vs_law |
   | recruitment_cost | | RM 3,000 from wages | | paper_vs_law |
   | hours | 8 | 12 | | said_vs_paper |
   | ticket | employer | worker | | said_vs_paper |
   | passport | | | PB-PASSPORT | said_vs_paper + paper_vs_law |
   | contract_months | 36 | 36 | | none |

   Also checked:
   - A PB-PROMISE-GAP risk exists, with a verified OEMA s.31 claim.
   - The claim value is RM 18,000 + RM 3,000 = RM 21,000.
   - The promise gap is RM 21,600, separate from that total.
   - Break-even ≈ 29.8 months, with the rate marked `user-entered`.
2. **No promises.** Every `said` is None, only `paper_vs_law` appears, there is no PB-PROMISE-GAP risk, and the
   standing L1 claim is in the citation ledger.
3. **Unverified risk.** With PB-MIN-WAGE's verification set to dropped, the salary law cell is `not_verified` with
   no citations, there is no paper_vs_law, and there is no minimum-wage claim line.
4. **No rate**, with BDT cost and an RM wage: `break_even.months is None`, and the promise-gap amount is still
   computed in RM.
5. **PII in the note.** The stored note holds `[PHONE_n]`/`[NAME_n]`, no raw digits or name, and the counts are
   added to the privacy receipt.
6. **`/promises` recompute** through TestClient, with `LLM.json` monkeypatched to raise:
   - the call succeeds
   - `privacy.outbound_calls` is unchanged
   - the PB-PROMISE-GAP risk appears, reusing the L1 verification
7. **Flag off.** `four_ledgers` is None, promises on analyze get 400, and `/promises` gets 404.
8. Unit tests for the four new DocFacts regexes on the Malaysia sample: 36, 12, worker, employer.

Then:
- `cd backend && python -m pytest -q`: the full suite passes, including `test_corpus` verbatim quotes.
- `python -m eval.run_eval` in fake mode, to show the gold set holds with the flag off.
- Report the results before any commit. No browser gate, since there is no UI change.

## Changes during the build (2026-11-14)
1. **`paper_vs_law` comes only from a rule-mapped risk.** At first the ticket row linked through its clause to
   `PB-RETURN-COST`, which is about the trip home, so it was flagged "against the cited law" for the ticket out. A
   risk linked only through its clause now fills the law cell but raises no mismatch. The ticket row in
   Verification is therefore `said_vs_paper` only. Law cells also list statutes before voluntary codes.
2. **`PB-PROMISE-GAP` is gated on the flag (`flag: ledger.enabled` in the rule, `Rule.active`).** The Adversary's
   prompt lists every active rule, so an always-active rule changed its prompt, and its cache key, on the three
   migration documents even with the flag off. It would also have let the Adversary drop hypotheses as restating
   it. With the gate, the outbound prompts of all five gold documents hash identically to `evidence-gate` (fake
   mode), and `test_the_promise_rule_is_in_no_prompt_while_the_flag_is_off` checks the gate.
