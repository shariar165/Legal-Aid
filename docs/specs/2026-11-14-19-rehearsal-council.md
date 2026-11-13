# Rehearsal Council (মহড়া · "আগে মহড়া, পরে টাকা")

Approved in plan mode on 2026-11-13. Branch `rehearsal`, cut from `evidence-gate` at 37e2bac.

## Why
OKUP's 2025 study of 114 complaints to BMET found:
- 75% of the workers had no written contract before they left;
- 80% were recruited through unlicensed sub-agents (dalals);
- the dealings were verbal and without receipts.

So the harm happens before any contract exists, in the conversation with the dalal. Ain today reads only contracts.

In Rehearsal Council, a prospective migrant worker, or an NGO trainer running pre-departure orientation, rehearses that conversation before paying anything. The three seats coach the worker on every turn. A debrief follows, with three parts:
- a deterministic readiness score;
- a checklist of questions to ask before paying;
- a dated Promise Record, checked against verified law.

## Constraints while the live eval is pending
- **The analysis pipeline is read-only.** That covers the adversary, playbook, verifier, risk analyst, calculator, router, corpus, gold set and eval scoring. This feature imports them and never changes them.
- **Fake mode only.** A new flag, `rehearsal.live: false` in `config.yaml`, makes every rehearsal call `LLM(mode="fake")`, even with `AIN_LLM_MODE=live`. A test checks this.
- **The eval comes first.** When the user says "go", the work in progress is committed on `rehearsal` and the eval plan on `evidence-gate` resumes.
- **The uncommitted step-3 corpus file stays unstaged.** That file is `backend/corpus/curate_intl.py`. Every commit names explicit paths.

## Flow
1. **Setup** (citizen mode, Bangla first). Every field is optional:
   - destination country (from `/api/countries`);
   - job;
   - what the agent has promised so far: salary, total cost, job, duration, and who keeps the passport;
   - whether the worker already paid anything.

   A contract photo is optional too. With one, the worker can start the existing full check (`/api/analyze`), and its job id is linked to the session. The rehearsal works with no contract at all.
2. **Bench.** It has three parts:
   - **The dalal seat**, an AI role-playing a recruiting sub-agent, with a neutral silhouette avatar (not one of the judge stickers).
     - It may use only the tactic the scheduler picks from `backend/ain/rehearsal/tactics.yaml`.
     - Guardrails in code replace any line that breaks the rules (see "Dalal guardrails").
   - **Three coaches**: the existing seats, with their lenses. Each worker turn gets one short hint per coach, in simple Bangla.
     - **Sunny (Remedies):** what to ask for, and a polite way to say it. The suggested line becomes a reply chip.
     - **Regal (Text):** what the law says. It gives verified citations only, through the evidence gate below.
     - **Grey (Enforcement):** the red flag, and how this line is used to exploit workers. Grey draws on the tactic's own source.
   - **The Chief Justice** writes the debrief note.
3. **Turns.** Each turn runs in this order:
   1. the dalal's line;
   2. the worker's reply (typed, or by voice: see "Privacy");
   3. the coach hints;
   4. the next dalal line.

   The worker can also press an explicit action button: "টাকা দিলাম" (I paid) or "পাসপোর্ট দিলাম" (I handed over the passport). A rehearsal runs 6–10 turns, and the worker can stop at any time.
4. **Debrief.**
   - **(a) Readiness score**, from the deterministic rubric below. It is never a model's opinion.
   - **(b) "টাকা দেওয়ার আগে যা জিজ্ঞেস করবেন"**, a checklist:
     - a fixed question for every rubric item that was missed or not tested;
     - the questions tied to the tactics that were played.
   - **(c) "প্রতিশ্রুতির লিখিত রেকর্ড"**, the Promise Record. This is a dated document with four parts:
     - every promise the worker says the agent made;
     - each promise checked against verified law, where the corpus covers it;
     - where to complain;
     - what Ain could not check.

     It downloads as DOCX (server side, `python-docx`). The PDF comes from a print-styled view in the browser, so Bangla text shapes correctly.
5. **Every screen** shows "সিদ্ধান্তে সহায়তা, আইনি পরামর্শ নয়" (decision support, not legal advice) and the existing help pathways: the helpdesk button and the destination's `help` line from `countries.yaml`.

## No unsourced numbers
A figure is shown only if it is one of these:
- the worker's own input;
- verbatim text of an in-force corpus section, such as OEMA s.31's penalty or s.41's 30 working days;
- a `countries.yaml` minimum wage, which `tests/test_countries.py` already ties to its section.

OEMA s.21 only lets the Government set a ceiling on migration cost "by order". That order is not in the corpus, so the Promise Record shows no ceiling. It says the corpus does not hold the order and tells the worker to ask BMET for the current figure in writing.

## Tactic sourcing rules
Each tactic in `tactics.yaml` has:
- `id`, `label {bn, en}`, `example_bn` (one Bangla line, with no digits and no names);
- `source {title, publisher, year, url, locator, supports}`. Here `locator` is a page, section or chapter, and `supports` is a short paraphrase of what the source documents;
- `tests`: the rubric items this tactic probes;
- `counter_of`: the rubric items that make the scheduler pick it as a reaction;
- `grey_flag_bn` and `sunny_ask_bn`: the offline fallbacks for the two coaches;
- optional `law: [{citation_id, quote}]`. As with playbook anchors, every quote is a verbatim substring of an in-force corpus section, and a test enforces it.

The sources must be ones I can actually open and read (WebFetch, with no user data in the request). They are reports by recognised publishers, such as ILO, IOM, OKUP, RMMRU, TIB, Human Rights Watch or Amnesty International. A source has to describe the tactic itself, not just recruitment abuse in general. If no source I can open documents a tactic, the tactic is left out and listed under "Unverified tactics" below.

Candidate tactics:
- pay today or the visa goes;
- no receipt needed;
- everyone pays this much;
- give me your passport for processing;
- the contract comes later, at the airport;
- inflated salary and overtime talk;
- "free visa";
- mortgage the land or take a loan;
- the licence is the big office's business;
- tell no one or you lose the seat.

### Dalal guardrails (`ain/rehearsal/guard.py`, all in code)
A dalal line is replaced by the tactic's `example_bn`, and a `guardrail` event names the reason, if it has any of these:
- a legal claim: আইন, ধারা, section, act, law, বৈধ, অবৈধ, legal, or a citation-id pattern. The dalal never states legal facts.
- an insult, from a curated bn/en list.
- a real name:
  - anything `pii.find_pii` finds;
  - a name from `companies.yaml`;
  - an agency-style suffix: ওভারসিজ, ট্রাভেলস, এজেন্সি, Overseas, Travels, International, Ltd, Limited.
- a number the worker did not give in setup or a reply, so the dalal cannot invent "official" figures.
- a `tactic_id` that is not the scheduled one, or a line that is empty or too long.

The agent's real name and phone, if the worker types them into the Promise Record, never reach the dalal or any model.

## Coaches and the evidence gate
**Allowed list for a turn.** It is built the same way as `council.extra_sections`:
- the tactic's `law` anchors;
- plus `get_corpus().search(...)` over `bd_migration` and the destination's pack, with repealed law excluded;
- filtered by `verifier.gate_currency`.

**Regal** returns `{text, citation_id, quote}`. Its hint is kept only if every gate passes:
1. **Existence and applicability:** the citation is in the allowed list.
2. **Fidelity:** the quote passes the verifier's threshold (`council._quote_matches`).
3. **Currency:** `gate_currency` passes.
4. **Entailment:** `verifier.gate_entailment` finds that the section supports Regal's text. Offline, this uses `fake_entailment`.

On any failure, the citation is stripped and the hint becomes "এ বিষয়ে যাচাই করা আইন আমার কাছে নেই" ("I have no verified law on this"). A `citation_dropped` event records which gate failed.

**Sunny and Grey** may cite only the allowed list. Any other citation is stripped, the way council chat does it. Hints are capped at about 220 characters.

## Readiness rubric (`ain/rehearsal/rubric.yaml`, `rubric.py`)
The rubric reads only:
- the worker's NFC-normalised, redacted replies;
- the explicit actions.

No model is involved. Each item has `hit` and `negate` patterns, in Bangla, English and Banglish, and a weight.

| Item | Met when | Applies |
|---|---|---|
| `receipt` | A reply asks for a receipt (রসিদ, রশিদ, রিসিট, receipt…) and is not negated ("রসিদ লাগবে না"). | always |
| `written_contract_first` | A reply asks for a written contract before any "টাকা দিলাম" action. | always |
| `licence` | A reply asks whether the agency is licensed or registered (লাইসেন্স, নিবন্ধন, RL, BMET…). | always |
| `kept_passport` | No "পাসপোর্ট দিলাম" action, and a reply refuses or asks why. | only if the passport tactic was played |
| `total_cost_in_writing` | A reply asks for the total cost in writing. | always |
| `no_pay_on_spot` | No "টাকা দিলাম" action, and no reply agreeing to pay now. | always |

Score = the weights of the items met ÷ the weights of the items that apply × 100. Every item is shown as met, missed or not tested, with the turn where it was decided.

## Promise Record and the law checks (`record.py`, `promise_checks.yaml`)
Each promise or fact maps to `Claim`s: a `citation_id` and a verbatim `quote` from the corpus, plus a plain proposition that names no section number. The section labels are rendered from the corpus (`naming.label`).

Every claim goes through `verifier.verify_claim(..., use_bench=False)`, with a `RouteDecision` for `bd_migration` plus the country pack. Only verified and partial rows are shown. Dropped rows are listed as "যাচাই হয়নি, দেখানো হয়নি" (not verified, not shown).

| Promise or fact | Law checks |
|---|---|
| The agent or employer keeps the passport | OEMA s.31(গ), plus the destination's `PB-PASSPORT` `pack_anchors`, read from `playbook/rules.yaml` |
| No written contract yet | OEMA s.22(1) |
| Recruited through a sub-agent | OEMA s.9(1) and s.14A |
| Money taken on a promise of a job, or an inflated salary | OEMA s.31(খ) and (ঘ) |
| Total cost | OEMA s.21 (a ceiling can be set by order; no figure) |
| Salary | the destination minimum wage, only where `countries.yaml` has one with a citation |

**Where to complain.** Each pathway is quoted verbatim and passes the same gates:
- OEMA s.41: a complaint to the Government, investigated within 30 working days;
- s.28: a civil suit for compensation;
- s.43: recovery of money taken illegally;
- s.27: legal aid;
- s.29(1): help from the Bangladesh Mission once abroad.

The request named s.29 as a complaint pathway. It is the right to return home and to the Mission's help, so it is listed for that. s.41 is the complaint section.

## Privacy
- **Before any model call.** Every worker reply, setup field and promise goes through `pii.redact`, with one mapping per session. `llm.py`'s outbound guard still applies.
- **The Promise Record's contact fields** (the agent's name and phone, the agency name) are stored only as placeholders. Their mapping lives inside the encrypted session and never reaches a model.
- **Storage.** The session is stored only encrypted (`vault`), at `RUNS_DIR/rehearsal-{id}.json.enc`. Ownership is a `rehearsals` table in the accounts DB, with `ON DELETE CASCADE` to users.
- **Deletion.** Account erasure and the guest purge both call `store.purge_orphans()`, which deletes every session file that no longer has a row.
- **DOCX export.** It puts the real values back in, on the server the user runs, as the memo export does.
- **Voice** (the user's choice): use on-device bn-BD recognition (`processLocally`) where the browser offers it. Otherwise the mic stays off until the worker taps a plain notice that the audio goes to Google's servers and agrees. Typing is the default. Every transcript goes through the PII Shield like typed text.

## Data model (appended to `ain/models.py`)
- `PromisedTerms`: salary, total_cost, job, duration, passport_keeper (me, agent, employer or unsure), paid_so_far, and extra free-text items.
- `RehearsalSetup`: country, job, promises, has_contract, linked `job_id`, language.
- `CoachHint`: member, text, `say` (Sunny only), citations, gates (Regal only), dropped.
- `RehearsalTurn`: n, tactic_id, dalal_line, guardrail, worker_reply (redacted), action, hints.
- `RubricItem`: id, label, status, turn, weight.
- `RehearsalDebrief`: score, items, checklist, note, citations.
- `PromiseRow`: field, promised, checks (`Verification`s).
- `ComplaintPath`: citation_id, label, quote, url.
- `PromiseRecord`: created_at, contact placeholders, rows, paths, unverified.
- `RehearsalSession`: id, created_at, setup, turns, status, debrief, record, mapping (stored encrypted only), mode, outbound calls.

## API and SSE (`ain/api.py`, all behind `require_principal` and an ownership check)
- `POST /api/rehearsals` takes `RehearsalSetup`, returns `{id}`, and starts turn 1.
- `GET /api/rehearsals/{id}` returns the session, redacted, with no mapping.
- `GET /api/rehearsals/{id}/events` streams SSE `trace` events, in the format `/jobs/{id}/events` uses (a reused `orchestrator.Job`):
  - `rehearsal_started`, `dalal_line`, `guardrail`, `worker_turn`;
  - `coach_hint` ×3, `citation_dropped`, `turn_done`;
  - `debrief`, `record_ready`, then `end`.
- `POST /api/rehearsals/{id}/turns` takes `{reply, action}` and returns 202. The work streams on SSE.
- `POST /api/rehearsals/{id}/finish` runs the debrief.
- `PUT /api/rehearsals/{id}/record` saves the contact fields and edited promises.
- `GET /api/rehearsals/{id}/record.docx` downloads the Promise Record.
- `DELETE /api/rehearsals/{id}` deletes the session.

## Models in live mode (later, when the user says so)
- The coaches keep their seats: Sunny on `bench_a` and Regal on `bench_b` (both OpenRouter), and Grey on `bench_c` (Groq).
- The dalal runs on `reasoner` (Groq), and the debrief on `chairman` (Groq).
- That costs about 2 OpenRouter requests per turn, or up to 20 for a 10-turn rehearsal, out of 50 a day. This must be weighed before `rehearsal.live` is turned on.
- The Promise Record's entailment checks are the same claims every time, so after the first live run they are cache hits.

## Out of scope
- Contract OCR inside the rehearsal: a photo uses the existing full check instead.
- An English-first UX: English is the secondary language.
- Trainer dashboards and group sessions.
- Live mode.
- Changes to the analysis pipeline or its prompts, so `eval/run_eval` is not run for this feature.

## Files
- **Backend:**
  - `backend/ain/rehearsal/`: `tactics.yaml`, `rubric.yaml`, `promise_checks.yaml`, `tactics.py`, `guard.py`, `dalal.py`, `coaches.py`, `rubric.py`, `record.py`, `store.py`, `session.py`;
  - `ain/models.py` and `ain/api.py` (additions only);
  - `ain/config.yaml` and `ain/config.py` (the `rehearsal` flag);
  - `tests/test_rehearsal_*.py`.
- **Web:**
  - `src/app/rehearsal/page.tsx`;
  - `src/components/rehearsal/*`;
  - `src/lib/rehearsal/*`;
  - `src/lib/citizen/useDictation.ts`;
  - an entry card in `HomeScreen.tsx`.
- **Docs:** this spec, `docs/specs/README.md`, the README (feature and "Honest limitations"), `docs/AI_USAGE.md`.

## Verification
1. `cd backend && python -m pytest -q` passes offline. It includes the tests for:
   - tactic sourcing;
   - dalal guardrails;
   - coach citations within the allowed list;
   - rubric scoring on scripted transcripts;
   - PII redaction in the Promise Record;
   - DOCX export;
   - the fake-mode lock;
   - ownership.
2. `cd web && npm run lint && npm run build`.
3. Browser check in fake mode at phone width. Run a 6-turn session and confirm:
   - a guardrail fires;
   - Regal shows a verified OEMA chip;
   - stopping early gives a debrief that matches the rubric by hand;
   - the DOCX and the print PDF hold the name, and the trace does not.

## Unverified tactics
To be filled during stage 2: every candidate tactic for which no source I could open documents the tactic.
