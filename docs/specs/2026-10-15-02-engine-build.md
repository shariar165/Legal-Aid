# Ain Copilot (আইন কপাইলট): build the engine behind the existing UI, plus Counsel mode

## Context
- **The challenge:** a functional multi-agent prototype that ingests a raw legal document, finds **≥3 non-obvious compliance risks**, and produces a **verified memo citing real statutes**.
- **What exists today:** `web/` is a polished Next.js 16 / React 19 **citizen app** for migrant workers. It is Bangla-first and has 3 screens: Home → Analyzing → Result. It includes TTS, an OCR-confirm card and citation chips. **Everything is mock data:**
  - `web/src/lib/citizen/analysis.ts` holds `SAMPLE_RESULT`, with section numbers deliberately left as `__` so they must come from the verified pipeline;
  - the steps are timers;
  - the uploaded file is ignored.
- **What's missing:**
  - No backend.
  - `.venv` (Python 3.13) is empty.
  - The workspace is not a git repo.
- **Environment:**
  - No GPU, no Tesseract.
  - bdlaws.minlaw.gov.bd is reachable. Pages are **UTF-16**, and each section has its own URL (e.g. Contract Act s.27 = `/act-26/section-190.html`). A scrape test returned the real s.27 text.
  - OpenRouter and Groq APIs are reachable.
- **Decisions taken:**
  - Use **Groq for the main pipeline and OpenRouter for the Virtual Bench**.
  - Build **one engine with two lenses**: Citizen mode for the migrant contract and **Counsel mode** for the full memo. There are two hero documents: a Malaysia migrant contract and a Dhaka EPZ (Savar) RMG appointment letter plus an EU buyer agreement.
  - Use **local EasyOCR** so the raw photo never leaves the machine.
- **Feedback adopted:**
  - Build a vertical slice first.
  - Use about 12 core Acts.
  - Drop the case-law agent, Whisper, German LkSG and CourtListener.
  - Fix Gazipur → Dhaka EPZ (Savar).
  - Add an EPZ router test.
  - At least one demo risk must come from Adversarial Counsel *outside* the playbook.
  - Pre-cache OCR.
  - Run the PII Shield before any external call.
  - Keep the `citation_id`-only constraint, the 4-gate verifier, the ledger and the ablation.

## What will make us stand out (judge-facing features)
1. **Verification Ledger with live ❌ drops.** Every claim shows 4 gate results and a deep link to the official source. Claims that are dropped as hallucinations stay visible in the ledger.
2. **Virtual Bench (ভার্চুয়াল বেঞ্চ):**
   - 3 judges from different model families plus a Chief Justice.
   - The judges review each other anonymously.
   - The output is a **majority opinion plus a dissent**, and any dissent raises a ⚠ human-review flag.
   - The judges see only the retrieved statute text and the claim.
3. **Ablation split-screen.** "Plain LLM" vs "Ain Copilot" on the same document. The plain answer's citations go through *our* gates, and the screen shows how many fail.
4. **Valid abroad, void in BD.** A jurisdiction-clash badge on risks where a clause is fine under the template's home law but void under BD mandatory law.
5. **Wage Truth Calculator.** Deterministic code, no LLM: promised pay − deductions = real pay, compared with the minimum wage. It uses the salary the user confirmed on the existing OCR card (a human-in-the-loop step).
6. **Privacy receipt.** It shows exactly the redacted text that left the machine. The photo itself is never sent anywhere.
7. **Bangla negotiation letter.** A ready-to-send letter to the agency listing the clauses to fix with verified citations. It can be read aloud through the existing TTS.
8. **Live agent trace.** The Analyzing screen and Counsel mode are driven by real SSE agent events, not timers.

## Architecture
```
upload / sample ─► [1] Ingestion (PyMuPDF | python-docx | EasyOCR bn+en, cached) → clauses + facts (+ OCR confidence)
                 ─► [2] PII Shield (regex + labelled-field heuristics, BN+EN) → placeholders + privacy receipt
                 ─► [3] Jurisdiction Router (rules + LLM confirm) → law packs; EPZ ⇒ BEPZ Labour Act 2019 replaces Labour Act 2006
                 ─► [4] Statute Researcher (hybrid BM25 + multilingual-e5-small, recursive cross-ref follow) → citation_ids
                 ─► [5] Risk Analyst (YAML playbook, per clause)   ┐ parallel
                 ─► [6] Adversarial Counsel (cross-clause / absence / off-playbook; proposes only) ┘
                 ─► [7] Calculator (wage math; waits for HITL OCR confirmation of salary)
                 ─► [8] Citation Verifier: G1 existence · G2 quote fidelity (rapidfuzz ≥90) · G3 entailment · G4 currency
                        └─ G3 + severity on high/critical → [9] Virtual Bench (OpenRouter) ; else single Groq judge
                 ─► [10] Drafter (cites ONLY verified citation_ids; IRAC memo, BN summary, citizen cards, mitigation clauses, letter)
                 ─► [11] Critic (rejects any unverified claim; ≤2 loops) → result + ledger + trace
```
- **Orchestration:** a small custom async orchestrator, `ain/orchestrator.py`, with typed Pydantic state. Each agent emits events (`agent_start`, `agent_done`, `risk_found`, `claim_verified`, `claim_dropped`, `bench_vote`, `ocr_check`, `done`) onto a per-job queue that is streamed as SSE. It is easier to test and trace than LangGraph.
- **LLM layer (`ain/llm.py`):**
  - Groq and OpenRouter both use the OpenAI-compatible API through `httpx`.
  - Each role (`fast`, `reasoner`, `judge`, `bench_judge_a/b/c`, `chairman`) maps to a provider and model in `config.yaml`. Model IDs are verified against live `/models` during the build.
  - JSON-mode outputs are validated by Pydantic.
  - Calls go through a `diskcache` cache and `tenacity` 429 backoff.
  - Modes are `live | replay (cache-only) | fake` (fake is for tests).
  - Every external call goes through `pii.assert_clean()`. OpenRouter calls send `provider.data_collection: "deny"`.
- **Corpus record:** `{citation_id, jurisdiction, act, year, section, heading, text, lang, url, source, retrieved_at, status, amended_by}`. Example ID: `BD-CONTRACT-1872-s27`.

## Corpus (~12 core sources, committed so the demo works offline)
- **BD, scraped from bdlaws with a polite, cached scraper that decodes UTF-16:**
  - Contract Act 1872
  - Labour Act 2006
  - BEPZ Labour Act 2019
  - Overseas Employment and Migrants Act 2013
  - Prevention and Suppression of Human Trafficking Act 2012
  - Stamp Act 1899
  - FERA 1947
  - Arbitration Act 2001
  - CPC 1908 (s.44A)
- **International, as curated verbatim excerpts with official URLs fetched during the build:**
  - ILO C029, C095 (wage deductions), C181 Art.7 (no fees to workers)
  - Malaysia Employment Act 1955 (deductions), Passports Act 1966 (passport retention), the current Minimum Wages Order
  - EU CSDDD 2024/1760, GDPR Art.44–46
  - BB GFET export-repatriation rule
- **Rule:** no section number or statute text is written by hand. Every playbook anchor must resolve to scraped or fetched text, and a test enforces this.

## Repo layout (new `backend/`, existing `web/`)
- **`backend/ain/`**
  - `config.py`, `config.yaml`, `llm.py`, `models.py`, `orchestrator.py`, `api.py` (FastAPI)
  - `export.py` (DOCX memo)
  - `agents/`: `ingestion.py`, `pii.py`, `router.py`, `research.py`, `risk_analyst.py`, `adversary.py`, `calculator.py`, `verifier.py`, `bench.py`, `drafter.py`, `critic.py`, `ablation.py`
  - `retrieval.py`
  - `playbook/*.yaml`
- **`backend/corpus/`**: `scrape_bdlaws.py`, `curated/*.json`, `processed/corpus.jsonl`, `build_index.py`
- **`backend/demo/`**:
  - `migrant_my_contract` (BN+EN text → generated photo/PDF for OCR)
  - `rmg_dhaka_epz` (appointment letter + buyer agreement)
  - `control_clean` (legal clauses only, to test precision)
  - `ocr_cache/`
- **`backend/eval/`**: `gold.yaml`, `run_eval.py` (recall/precision, citation validity, drop rate, latency, ablation)
- **`backend/tests/`**: pytest
- **Root:** `requirements.txt` (pinned), `.env.example` (`GROQ_API_KEY`, `OPENROUTER_API_KEY`), `.gitignore`, `README.md`

## API (FastAPI on :8000, CORS for :3000)
- `POST /api/analyze` takes multipart `file` or `sample_id` and returns `{job_id}`.
- `GET /api/jobs/{id}/events` streams SSE.
- `POST /api/jobs/{id}/confirm` takes `{field, value}` and resumes the Calculator.
- `GET /api/jobs/{id}/result` returns the citizen view, the memo, the ledger, the bench, the trace and the privacy receipt.
- `GET /api/jobs/{id}/memo.docx` downloads the memo.
- `POST /api/jobs/{id}/ablation` runs the plain-LLM comparison.
- `GET /api/samples`, `GET /api/corpus/{citation_id}`, `GET /api/health`.

## Frontend changes (`web/`, following existing CSS tokens in `globals.css` and module patterns)
- **`src/lib/api.ts`:** a typed client using `NEXT_PUBLIC_API_URL`, defaulting to `http://localhost:8000`.
- **`src/lib/citizen/useAnalysis.ts`:** an EventSource hook. The types in `analysis.ts` stay as the contract, and `SAMPLE_RESULT` is removed from runtime use.
- **`CitizenApp.tsx`:** holds the real job state and an error/offline screen.
- **`HomeScreen.tsx`:** adds "Try a sample contract" chips.
- **`AnalyzingScreen.tsx`:** steps map from real agent events (read / redact / match / verify). The OCR card is driven by the `ocr_check` event, and it POSTs `/confirm`.
- **`ResultScreen.tsx`:**
  - real cards with filled section numbers and verified/partial status;
  - a new **wage card** and a **letter** card (copy, share, listen);
  - a "Full legal memo →" link to Counsel mode;
  - new strings go in `i18n.ts`.
- **New `src/app/counsel/[jobId]/page.tsx` + `src/components/counsel/*` (desktop layout):**
  - document pane with a clause risk heatmap;
  - memo pane (IRAC risks, severity, clash badge, bench majority/dissent ⚠);
  - tabs: **Ledger**, **Bench**, **Trace**, **Ablation**, **Privacy**;
  - DOCX export and print CSS.
- Before writing any new Next code, read `web/node_modules/next/dist/docs/` as `AGENTS.md` requires (Next 16 with `cacheComponents` enabled).

## Build order (vertical slice first)
1. **Setup.**
   - Run `git init` at the root with a `.gitignore` covering `.venv`, `.env`, caches and `.next`.
   - Install dependencies into `.venv`: fastapi, uvicorn, pydantic, httpx, python-multipart, sse-starlette, pymupdf, python-docx, easyocr + CPU torch, sentence-transformers, rank-bm25, rapidfuzz, pyyaml, diskcache, tenacity, python-dotenv, beautifulsoup4, lxml, pytest, pytest-asyncio, Pillow.
   - Pin the versions in `requirements.txt` and add `.env.example`.
   - Ask you to fill in `.env`.
2. **Corpus.** Scrape the BD Acts, curate the international excerpts, build the index, and commit. Sanity checks:
   - "restraint of trade" must return Contract Act s.27;
   - "retain passport" must return the passport anchors.
3. **Vertical slice.**
   - Pipeline: text/PDF ingestion → PII → router → retrieval → playbook risks → verifier (G1, G2, G4 + single-judge G3) → drafter → API.
   - Wire the citizen UI end to end on the migrant sample, and add tests.
4. **Depth.** Adversarial Counsel, Virtual Bench, critic loop, Calculator with HITL confirmation, EasyOCR with cache, and the SSE trace. Add the EPZ hero doc.
5. **Counsel mode UI.** Ledger, bench, trace, heatmap, privacy receipt, DOCX export, and the letter.
6. **Proof.**
   - Build the ablation and the eval harness.
   - Pre-warm the demo cache with live keys.
   - Write `README.md` with run instructions and a 3-minute demo script.
   - Commit at each milestone.

## Verification
- **pytest (fake LLM, offline):**
  - corpus integrity: every playbook anchor resolves, and the text is non-empty with a valid URL;
  - retrieval sanity;
  - PII: passport, NID and +880 phone numbers are redacted, the round-trip works, and the FakeLLM recorded **no PII in any outbound payload**;
  - **router: an EPZ doc gets the BEPZ Labour Act and never Labour Act 2006 s.26/46; a non-EPZ doc gets the Labour Act; a Malaysia doc gets the MY + OEMA + ILO packs**;
  - each verifier gate fails on its own bad case: fake ID, misquote, "contradicts", repealed section;
  - bench majority/dissent aggregation, and judge payloads contain only the statute text and the claim;
  - calculator math;
  - the drafter rejects an unknown `citation_id`;
  - E2E on both hero docs: ≥3 risks, 100% of memo citations verified, ≥1 ❌ dropped claim, ≥1 risk from the adversary that is not in the playbook;
  - API flow through TestClient: analyze → SSE → confirm → result → docx.
- **Eval:** `python -m eval.run_eval` prints recall, precision, citation validity, drop rate and latency, plus the ablation numbers.
- **Live smoke test with real keys:** `scripts/smoke_live.py` runs both hero docs through Groq and OpenRouter and warms the cache.
- **Frontend:** `npm run lint` and `npm run build` must pass. Then start both servers and drive both flows in Chrome:
  - Citizen: sample → steps → OCR confirm → result → listen → memo link;
  - Counsel: ledger links open the correct bdlaws section, bench dissent shows ⚠, the ablation runs, and the DOCX downloads.
