# Fixing the weaknesses judges could catch: Adversary depth, long context, scope, case law, hosting, docs

## Context
A review found six weak spots that judges could press on:
1. **"Non-obvious" is mostly rule-matching.** In the offline eval the Adversary contributes only 2, 0 and 1 risks (MY, SA, EPZ). The live cache is worse: `gpt-oss-120b` hypotheses are shallow and repeat the playbook ("No clause on minimum wage", "No health insurance", "Missing return ticket" when PB-RETURN-TICKET already fired). Causes in `backend/ain/agents/adversary.py`:
   - the prompt passes only the *titles* of known risks;
   - it is capped at 3 hypotheses;
   - nothing in code rejects duplicates;
   - grounding shows only `s.text[:700]` of each candidate section, so support further into the section is never seen.
2. **No long-context handling.** The Adversary sends every clause in one call. Groq's free tier allows about 8k tokens per minute, so a 20–30 page document hits 413/429 errors. `ingestion.segment()` splits only on top-level numbers, so sub-clauses ("12.3") make giant clauses.
3. **Narrow domain**, not stated up front.
4. **No case law**: the corpus holds only statutes and standards.
5. **No hosted demo.** The README commands are Windows-only.
6. **Docs drift.** The README says 129 tests (the real count is 150). `web/README.md` is still the create-next-app boilerplate.

The user chose: one Docker image on Hugging Face Spaces, ILO CEACR observations as the case-law layer, and a fictional long contract for testing.

---

## 1. Adversary: ≥3 genuinely off-playbook risks per hero doc (live)
File: `backend/ain/agents/adversary.py`
- **Richer context.** Pass the known risks as `rule_id · clause_ids · finding`, not titles. Also pass a list of the playbook's rule ids with their one-line title (from `risk_analyst.load_rules()`), so the model knows what is already covered.
- **Stronger prompt.** Ask for up to 6 hypotheses. Each must be one of these:
  - (a) an **interaction**: it must name ≥2 clause_ids and the mechanism;
  - (b) an **absence**: it must name the missing term *and* why this contract makes the gap dangerous;
  - (c) a **regime conflict**.
  
  Generic "missing X" items and anything a listed rule already covers are forbidden. Keep the bilingual query requirement.
- **Code-side duplicate filter** (new `_novel(h, known, rules)`). Drop a hypothesis when its clause_ids are a subset of one known risk's clause_ids *and* its title or finding shares the key terms of that risk's rule (token overlap ≥ 0.5, a simple set check). Also drop absence hypotheses for which a playbook `absent` rule exists in the active packs. Each drop is emitted as a trace event ("duplicate of PB-…"), so the ledger stays honest.
- **Keep the top 5** by severity, then by category (interaction > regime_conflict > absence).
- **Grounding sees the real text.** Replace `s.text[:700]` with `bench.cited_text(section, query=h["finding"])`, which is already the anchored window used by the judges, capped per candidate (~1,500 chars via `bench.window`). Max candidates per hypothesis: 6.
- **Fake mode.** Add deterministic SA hypotheses so the offline eval shows ≥3 Adversary risks on every hero doc, with groundings whose citation_ids and quotes come from the corpus (never hand-typed; quotes checked by an existing-style corpus test):
  - **SA**: passport custody (cl.4) + the worker paying the iqama renewal (cl.5) → the worker falls into irregular status and cannot leave;
  - **SA**: governing-law Saudi Arabia (cl.9) + a ban on complaints to BMET or the Embassy (cl.8) → the worker has no forum in either country;
  - **SA**: return ticket at the worker's cost (cl.6) + no end-of-service award (cl.7) → stranded with no money to get home.
  - **MY and EPZ**: add one more each, so every hero doc reaches 3.
- **Eval** (`backend/eval/gold.yaml`, `run_eval.py`):
  - add `min_adversary: 3` per hero doc and keyword expectations for the new off-playbook risks;
  - add a `novel` metric: Adversary risks whose `_novel` check passed;
  - print both in the table.

## 2. Long context: map → reduce Adversary, safe segmentation, TPM pacing
- **Segmentation** (`backend/ain/agents/ingestion.py`):
  - extend `CLAUSE_START` to sub-clauses `\d{1,2}\.\d{1,2}` and "Schedule"/"Annex" headings;
  - split any clause over ~2,500 chars at paragraph breaks;
  - strip repeated page headers, footers and bare page numbers from PDF text.
  
  Existing tests must still pass (hero docs segment unchanged).
- **Chunked Adversary** (in `adversary.py`; no new module):
  - `_chunks(clauses, budget_chars)` packs whole clauses into chunks of about 9k chars (~3k tokens);
  - every chunk call also gets a **document outline**: each clause's id + its first ~80 chars, so the model can name cross-chunk interactions;
  - **Map**: hypothesise per chunk (same prompt);
  - **Reduce**: one call over all chunk hypotheses (titles, clause_ids, findings only) merges duplicates, adds cross-chunk interactions it sees via the outline, and returns the top 5. This is the recursive decomposition step.
  - Short docs (one chunk) skip the reduce, so hero docs make the same number of calls as today.
- **TPM pacing** (`backend/ain/llm.py` + `config.yaml`):
  - add an optional provider `tpm` (Groq: 8000);
  - extend the `_pacer` with a token bucket that estimates tokens as `chars/3` (Bangla counts as `chars/2`) plus `max_tokens`, and waits before posting;
  - treat Groq **413 "Request too large"** as `_RouteFailed`, so the existing cross-provider backup runs instead of a hard error.
- **Fixture**: `backend/demo/docs/long_migrant_msa.txt`, a fictional, ~25–30 page manpower supply + employment agreement. It holds:
  - definitions and schedules;
  - sub-clauses;
  - the hero risky clauses scattered from page 3 to page 24;
  - **one cross-chunk trap**: the passport clause sits in Part 3 and the "absconding" penalty in Schedule 4.
  
  It names no real company or person, and the README says so.
- **Tests** (`backend/tests/test_long_context.py`, offline/fake):
  - segmentation of the long doc gives no clause over the cap;
  - every Adversary call's user payload stays under the chunk budget;
  - the reduce step receives the hypotheses of every chunk;
  - the cross-chunk trap is found and verified;
  - the pipeline completes with ≥3 risks.
- **Live check**: `scripts/smoke_live.py --doc long_migrant_msa.txt` (a new `--doc` flag) records time, calls, tokens and any 413/429 errors. Run it once live and put the numbers in the README.

## 3. Domain: pitch it as a focused niche
- **Router** (`backend/ain/agents/router.py`): when `doc_type` is commercial/lease/other with no employment or migrant pack, set `RouteDecision.scope_note` (a new optional field in `models.py`). It reads: "Ain is built for employment and migrant-worker contracts; only general Contract Act / foreign-exchange checks ran."
- **UI**: show `scope_note` as a banner in the Counsel Report and the citizen result. Read it via `api.ts` types and the existing `Panels.tsx` / `ResultScreen.tsx` notice styles.
- **README**: a new "Scope" paragraph at the top: the employment and migrant-labour niche, why it was chosen (Bangladesh's 1M+ migrants a year; the RMG sector), and what a commercial NDA or lease gets today.

## 4. Case law: ILO CEACR observations ("supervisory" pack)
- **Fetch**: `corpus/fetch_intl.py` downloads the official NORMLEX pages of CEACR observations on Bangladesh: C29 (forced labour), C87, C98 and C81. The newest observation for each, plus one on migrant recruitment if one exists.
- **Cut**: `corpus/curate_intl.py` cuts verbatim paragraphs by marker, the same as the existing ILO excerpts (it fails loudly on a missing marker). The new `Section.kind="supervisory"` carries the observation year and convention.
- **Use**:
  - add pack `ilo_supervisory` (always routed for BD documents, like the standards pack);
  - add `pack_anchors` on 2–3 rules (PB-PASSPORT, PB-RECRUIT-FEE, EPZ union) whose quotes are copied from the curated text by a test, never typed;
  - the Adversary may retrieve from it.
- **Gates**: a G4 currency message for supervisory text ("interpretive, not binding; observation of YEAR"). The UI badge reuses the "voluntary standard" badge style, labelled *ILO supervisory, interpretive*.
- **Rebuild**: fetch_intl → curate_intl → build_corpus → `python -m ain.retrieval`. Re-encode with `batch_size=1`, because a full rebuild runs out of memory on this machine.
- **README**: case law = ILO supervisory observations only. Court judgments (BD HC/AD, CourtListener, CAP) are listed as future work.

## 5. Hosted demo: one Docker image on HF Spaces
- `Dockerfile` (repo root):
  - Python 3.13-slim with CPU torch, `requirements.txt` and Node 22;
  - `npm ci && npm run build` in `web/`;
  - `start.sh` runs `uvicorn ain.api:app --port 8000` and `next start -p 7860`.
- **Same origin.** `web/next.config.ts` gets `rewrites()` that send `/api/:path*` to `http://127.0.0.1:8000/api/:path*` when `AIN_INTERNAL_API` is set. `api.ts` then uses `NEXT_PUBLIC_API_URL=""` (relative). Cookies stay first-party, and `AIN_CORS` is the Space origin.
- **SSE risk.** Check that the Next rewrite streams `/events` without buffering. If it buffers, add `X-Accel-Buffering: no` and `Cache-Control: no-transform` on the SSE response in `api.py`.
- **Space config**:
  - secrets `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `AIN_DATA_KEY`, `AIN_COOKIE_SECURE=1`;
  - `AIN_DENSE=0` is optional; with 16 GB RAM, dense can stay on;
  - the OCR cache ships in the image.
  
  The default mode is `live`, with the warmed replay cache baked in as the starting cache, so hero docs are instant and quota-free.
- **Data.** `backend/.data` and `runs/` live in `/data` (persistent storage if enabled; otherwise ephemeral, and the README says so).
- **Cross-platform docs.** Linux/macOS commands go next to the Windows ones, plus `docker build -t ain . && docker run -p 7860:7860 --env-file .env ain`.
- **Deploying is outward-facing.** I prepare everything, then ask before pushing to a Space (the user creates the Space and its secrets).

## 6. Small doc fixes
- README: replace the hard-coded "129 offline tests" with the real count after these changes. Update the test list (long-context, supervisory, scope).
- `web/README.md`: replace the boilerplate with a short project-specific guide: what `/` and `/counsel` are, env vars, dev/build commands, and the same-origin proxy.

---

## Order of work
1 (Adversary) → 2 (long context) → 6 → 3 → 4 (corpus rebuild) → 5 (Docker).

Each step ends with `pytest -q` passing. Per the user's standing rule, the eval report comes before any commit.

## Verification
- `cd backend && ..\.venv\Scripts\python -m pytest -q`: all old + new tests pass in fake mode.
- `AIN_LLM_MODE=fake python -m eval.run_eval`: every hero doc has `adv ≥ 3`, recall/precision unchanged at 100%, and the long doc completes.
- **Live**:
  - `python -m eval.run_eval` once on Groq: record per doc the Adversary count, the novel count, and drops (the prompt change invalidates the adversary cache keys, so re-warm with `smoke_live`);
  - then `smoke_live --doc long_migrant_msa.txt`: no 413, and the timing is recorded.
  
  Watch the Groq quota (about 200k tokens/day per model): this may span two days.
- `python -m eval.bench_quality --keep` is not affected (bench prompts are unchanged); spot-check only.
- **Browser** (`next start`, `AIN_DENSE=0` locally):
  - Saudi sample shows ≥3 *Adversarial Counsel* risks;
  - an NDA upload shows the scope banner;
  - a CEACR citation shows the "ILO supervisory, interpretive" badge.
- **Docker**: `docker build` and `docker run` locally, then the full citizen and Counsel flow at `localhost:7860`, including login (cookie), SSE progress and DOCX download.
- `cd web && npm run lint && npm run build`.
