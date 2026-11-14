# Where the Adversary loses risks, a gold set anchored on clauses, and two new playbook rules

Approved in chat on 2026-11-13, after a diagnosis of the live gold-set eval (spec 16). The diagnosis replayed the eval from the LLM cache with the eval-day routing: 0 cache misses, and the same call counts as the eval (74, 99, 57, 100, 7), so these are the eval's own answers.

## Diagnosis
- **Malaysia recall.** All three misses (return home, no forum, English-only terms) were never proposed by the live Adversary. It was not the playbook regex, OCR (the document is text), retrieval or the verifier. Offline, the hand-written stand-in always proposes them, which is why fake mode scored 100%.
  - The live Adversary proposed six other risks: Malaysian hours, rest days, termination notice and others.
  - The corpus has only three Malaysian sections (EA s.24, s.90B, the minimum wages order), so two of them could not be grounded on any law.
- **Saudi precision.** Four live risks matched nothing:
  - **R8** ("no medical insurance"): its own claim was refuted, and it survived on the return-ticket article that R4 already relies on.
  - **R10** (accommodation charge "violates a Saudi housing rule"): the housing claim was refuted, and it survived on the general wage-withholding article. Its clause C4 is the deduction-cap risk's, which the Adversary never saw.
  - **R9** (passport kept + complaint ban): real, and the gold set's "forum" keyword did not fit its wording.
  - **R11** (no notice period): rests on a voluntary code, and Saudi law supplies a default.
- **Off-playbook count.** Malaysia and EPZ each went 6 proposed, then 1 restated (correctly), then 2 never grounded, then 1 dropped by the verifier, leaving 2 live.
  - On EPZ, one grounding batch came back with no entry for both of its hypotheses.
  - The verifier drops were a voluntary code (Malaysia) and the Labour Act, which is switched off inside an EPZ.
  - The Adversary sees the text-rule risks but not the calculator's, which run in parallel.
- **The gold matcher.** It matched on keywords alone. "epz" is in most EPZ findings, and "committee" credited a worker-data risk with the grievance-committee finding, so EPZ's 92% was overstated.

## Decisions (the user's), in order
1. **Retry a grounding batch** that came back without some of its hypotheses: each missing one is asked again alone. A hypothesis the model did answer, even with `keep: false`, is not asked again.
2. **The calculator runs before the Adversary**, and its risks go to the Adversary as already covered, alongside the playbook risks. As a safety net after verification, an Adversary risk is withdrawn if it stands only on law that a playbook or calculator risk on an overlapping clause already cites.
3. **Gold matching is anchored on clauses.** A keyword finding needs every listed clause in the risk's `clause_ids`, plus a specific keyword. Each anchor carries an `at` phrase that its first clause must contain, so a renumbered document fails a test. R9 joins the Saudi gold set: a reviewer would call it correct, and it is not the forum finding. Corrected numbers are reported even where they drop.
4. **Live rerun of Malaysia, Saudi and EPZ**, then report.
5. **Malaysian Employment Act 1955 s.12, s.59 and s.60A**, from the official consolidated text with the 2022 amendments, verbatim, through `rebuild-corpus`. G4 must mark them in force.
6. **Playbook rules for (a) no paid return home and (b) no complaint or dispute forum**, each anchored on a verbatim section already in the corpus (OEMA 2013 / ILO); stop if none exists. English-only terms stay with the Adversary unless the corpus has a verbatim legal anchor for the language of the contract. The gold set then labels these as playbook risks.
7. No Adversary prompt change yet. All five documents rerun live at the end, across days for the quota, and the README numbers updated.

## Approach (steps 1–3)
- `ain/agents/adversary.py`:
  - `_unanswered(keys, answer)` finds the hypotheses a batch answer left out.
  - Missing ones from a multi-hypothesis batch are grounded again one at a time, which is a different prompt and so not the same cached answer. A trace event names them.
- `ain/orchestrator.py`:
  - The Adversary now starts after the calculator, with `text_risks + fact_risks` as known.
  - The calculator is deterministic. The only wait it adds is a person confirming a blurry salary from a photo.
- `ain/agents/critic.py` `restated_after_verification()`:
  - Takes only Adversary risks that are still live and have clauses.
  - Collects the citations each has a verified or partial claim on.
  - Withdraws one when those citations all appear among the standing citations of non-Adversary risks sharing a clause with it.
  - The orchestrator sets the risk to dropped and emits `hypothesis_dropped` from the Critic, so `run_eval`'s "restated" column counts it.
  - **Known limit:** R10 survived on Art. 61, which the deduction-cap risk does not cite, so this rule alone does not catch it. Fix 2's earlier filter may, since the Adversary now sees that risk. A looser rule, any adversary risk on a calculator clause, would also drop genuine risks such as Malaysia's insurance deduction.
- `eval/gold.yaml`, `eval/run_eval.py`: `clauses` and `at` on every keyword expectation, and `_match` requires the clauses. `--doc NAME` runs a subset and writes `last_eval.subset.json`, leaving the full report alone.

## Corrected eval-day numbers (the same answers, new matching)
| Document | Old matching | New matching | Why |
|---|---|---|---|
| Malaysia | recall 67%, precision 71% | **56%, 71%** | "penalty"/"exit" had credited a risk not about the C8 exit penalty |
| Saudi | 78%, 64% | **80%, 73%** | R9 added and found; R2 lost its "iqama" credit (it is about fees in C4, not the renewal in C6) |
| EPZ | 92%, 91% | **75%, 82%** | union and grievance were both credited to R6 (worker data); neither risk was really raised live |
| Long MSA | 73%, 88% | 73%, 88% | unchanged |
Offline (fake mode) on the new matching: Saudi 90% (the stand-in never proposes R9), long MSA 73% (the stand-in picks other clauses on the long document). The offline numbers are regression checks, not a benchmark.

## Files
`ain/agents/adversary.py`, `ain/agents/critic.py`, `ain/orchestrator.py`, `eval/gold.yaml`, `eval/run_eval.py`, `tests/test_adversary_funnel.py`, `tests/test_run_eval.py`, `.gitignore`.

## Verification (steps 1–3)
- `tests/test_adversary_funnel.py` (7 tests):
  - an empty multi-hypothesis batch is regrounded one at a time and loses nothing;
  - `keep: false` is not asked again;
  - the Adversary's prompt lists every calculator risk;
  - the R8 shape is withdrawn, while R7 (same article, its own clause) and R9 (one law of its own) stay;
  - playbook and unverified risks are never withdrawn;
  - a withdrawn risk is dropped and traced.
- Mutations: six, removing the retry, retrying everything, hiding the calculator risks, not dropping, the subset test and the clause test. All were caught.
- `tests/test_run_eval.py`: every anchor clause exists and contains its `at` phrase. Pointing the absconding anchor at C149 ("Sleeping on duty") fails it. A keyword finding needs its clause; a subset run leaves the full report alone.
- `pytest`: 309 passed.
- Live rerun (step 4): see below.

## Live rerun of Malaysia, Saudi and EPZ (step 4, 2026-11-14)
Fixes 1, 2 and 5, before the corpus and rule changes below, with dense retrieval on, as on the eval day. `--stop-on-quota`; the run finished in one go (exit 0).

| Document | Eval day, new matching | Rerun | Off-playbook (adv / restated) |
|---|---|---|---|
| Malaysia | 56%, 71% | **56%, 100%** | 0 / 3 |
| Saudi | 80%, 73% | **80%, 80%** | 4 / 1 |
| EPZ | 75%, 82% | **83%, 100%** | 1 / 1 |

- Every memo citation was verified, and the plain-LLM ablation was 0 of 40.
- Precision rose on all three. The safety net withdrew restated Adversary risks, three of them on Malaysia.
- Malaysia's recall did not move. The return-home, forum and English-only findings were still not raised live, which is what steps 5 and 6 address.
- **Backup models answered some bench calls.** OpenRouter rate-limited Sunny's Gemma 4 31B upstream (27 failed after retries), so bench calls went to backups: 15 of 80 calls on Malaysia, 22 of 104 on Saudi and 10 of 65 on EPZ. Most went to GPT-OSS 120B, the Chief Justice's family. These are design fallbacks, flagged per call, but this rerun's bench is partly not the configured one.
- The report (`eval/last_eval.subset.json`, gitignored) was overwritten by a later offline `--doc` run and rebuilt from the live run's printed results.

## Step 5: Malaysian Employment Act s.12, s.59, s.60A (2026-11-14)
- Built through `rebuild-corpus`: 1157 to 1160 sections.
- The three new sections are in force (G4), have no page furniture, and only those three were encoded.
- No existing section changed. `pytest` passed 309.

## Step 6: PB-RETURN-COST and PB-NO-FORUM (2026-11-14)
- **PB-RETURN-COST.**
  - It covers destinations where PB-RETURN-TICKET does not fire (the rule excludes the five Gulf packs), so Malaysia gets it.
  - It uses the same triggers and absence patterns as PB-RETURN-TICKET.
  - Anchor: OEMA s.22(1) ("বিদেশে গমন এবং বিদেশ হইতে ফেরত আসিবার খরচ"), plus the Employer Pays Principle under `std_recruitment`.
- **PB-NO-FORUM.**
  - It fires on a complaint ban that names BMET, Bangladesh, the mission or a court, read with a foreign governing-law clause.
  - Anchors: OEMA s.28 and s.29(1).
  - Its question asks whether the clauses together leave no forum.
- All four quotes are verbatim (`test_corpus`). English-only terms stay with the Adversary.
- **Gold set.** Malaysia's return finding is now `{rule: PB-RETURN-COST}`, and the forum finding is `{rule: PB-NO-FORUM}` in Malaysia, Saudi and the long MSA.
- **Offline stand-in.** It no longer proposes the return or forum hypotheses once PB-RETURN-COST or PB-NO-FORUM has fired, as it already did for PB-RETURN-TICKET. Without that, the forum finding was reported twice: the Adversary's version rests on s.22 and s.41, so the restated-risk net could not catch it. No live prompt changed.
- **The user's decision:** `min_adversary` is 2 for Malaysia and Saudi, because the findings moved to the playbook rather than being lost. EPZ and the MSA keep 3. The test reads each document's own bar.
- **Offline results.**

  | Document | Recall | Precision |
  |---|---|---|
  | Malaysia | 100% | 100% |
  | Saudi | 90% | 100% |
  | EPZ | 100% | 100% |
  | MSA | 100% | 100% |

  The control has no risk. Every document meets its bar, and `pytest` passed 309.
- **Next (step 7):** all five documents live, over several days for the quota, then the README numbers.
