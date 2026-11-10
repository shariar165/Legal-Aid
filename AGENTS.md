# AGENTS.md — working on Ain Copilot

Instructions for any coding agent (Claude Code, Cursor, Codex…) and for people. Read this before you change code.
`README.md` explains what the product does; this file explains how we build it.

## Layout
- `backend/` — FastAPI app (`ain/api.py`), orchestrator, agents (`ain/agents/`), LLM layer (`ain/llm.py`),
  model routing (`ain/config.yaml`), playbook (`ain/playbook/rules.yaml`), corpus pipeline (`corpus/`),
  evals (`eval/`), offline tests (`tests/`).
- `web/` — Next.js 16 app: citizen UI (`/`), Counsel workspace (`/counsel`), docs (`/docs`).
  `web/AGENTS.md` is written by `next dev`: this Next.js has breaking changes, so read
  `web/node_modules/next/dist/docs/` before writing frontend code.
- `docs/specs/` — the spec for each feature, written and approved before any code (see "Workflow").
- `docs/AI_USAGE.md` — how AI is used in the build (models, prompts, RAG, MCP, evals, guardrails).

## Hard rules (the product's promise depends on them)
1. **Never hand-type statute text or section numbers.** Law comes only from the corpus
   (`backend/corpus/processed/corpus.jsonl`), built by the scripts in `backend/corpus/`. A test checks that every
   playbook quote is verbatim.
2. **Agents may cite only `citation_id`s returned by retrieval.** Do not loosen this constraint, the 4-gate verifier
   (existence/applicability, fidelity, entailment, currency) or the drafter's stripping of unverified citations.
3. **No PII leaves the machine.** Text goes through `agents/pii.py` before any model call; `llm.py` blocks a payload
   that still holds an identifier. New outbound paths (MCP tools, webhooks) must redact the same way.
4. **OpenRouter = free models only**, with `data_collection: deny` (`config.validate` enforces it). Fall back to
   Groq visibly (`OutboundCall.fallback`), never silently.
5. **The bench verdict prompt is one neutral test, identical for all three judges.** Personas and lenses shape
   severity, reasoning and chat only.
6. **Bangla text is NFC-normalised before comparison** (`retrieval.nfc`).
7. **No demo document may name a real company.** `corpus/companies.yaml` quotes companies' own published
   documents only, never allegations.
8. Changing a prompt changes the LLM cache key. Re-warm the replay cache live (`python -m scripts.smoke_live`).

## Commands
```bash
cd backend && python -m pytest -q          # offline (fake LLM); must pass before every commit
python -m eval.run_eval                    # gold-set recall / precision / citation validity / ablation
python -m eval.run_eval --stop-on-quota    # live over several days: stops at OpenRouter's daily quota, never on a backup
python -m eval.bench_quality               # Virtual Bench trap set: a quota-saver flag stays off until this passes
python -m scripts.smoke_live --docs 1      # live keys: model check, cache warm-up, free-quota left
cd web && npm run lint && npm run build
```
Low-memory machine: start the backend with `AIN_DENSE=0`, and serve the UI with `npm run build && npm start`.

## Workflow (spec-driven, with review gates)
1. **Spec.** Each feature starts as a plan in Claude Code's plan mode: context, the approach, the files it touches,
   and how to verify it. The user approves it, and it is kept in `docs/specs/`.
2. **Build** against the spec. Reuse what exists (retrieval, verifier gates, calculator) instead of new logic.
3. **Gate 1: tests.** `pytest` passes offline. A new behaviour gets a test.
4. **Gate 2: evals.** A change to prompts, routing or bench flags must hold the gold set (`eval/run_eval`) and,
   for bench changes, the trap set (`eval/bench_quality`). The report comes before the commit.
5. **Gate 3: browser check** of the UI change (fake mode is enough), then commit.

## Style
- Match the surrounding code: comment density, naming, idiom. Python 3.13, type hints, Pydantic models in
  `ain/models.py`. Frontend: CSS modules, no UI kit.
- Behaviour that is not proven yet goes behind a flag in `config.yaml`, off by default.
- Keep the README's "Honest limitations" section true when you change behaviour.
