# Ain Copilot — AI Depth Score audit + extra-marks plan

## Context
The hackathon's "AI Detail Usage" form scores the build out of 110 (plus Data Lifecycle, tunneling, /docs).
Goal: (1) map what Ain Copilot *already* uses to each form section, with honest evidence from the repo, and
(2) add the few missing pieces that earn the most extra points for the least risk. Rule: only claim what the code
really does — judges can verify, and the README already stresses honesty.

## Part 1 — What we already use (evidence in repo)

| Form section (max) | What to tick / write | Evidence | Est. now |
|---|---|---|---|
| Prompt Usage (10) | Role prompting (judge, Chief Justice, opposing counsel, IRAC lawyer), persona lenses, strict JSON contracts, stepwise mechanism reasoning, map→reduce prompts, prompts are cache-keyed (changing prompt = new key), test that verdict prompt is identical for all judges | `agents/*.py` `*_SYSTEM`, `tests/test_bench.py` | 8–10 |
| Token Optimization (10) | Disk LLM response cache (replay mode = 0 tokens), JSON mode, cheap-model routing (`fast` 20B vs `reasoner` 120B), request batching (`batch_bench`), context trimming (`statute_window`), map→reduce digests for long docs, review-skip on agreement, token-bucket TPM pacing, `reasoning_effort: low` | `ain/llm.py`, `ain/config.yaml` | 8–10 |
| ↳ tools list | ✔ Structured outputs/JSON mode · ✔ Cheap-model routing · ✔ Request batching · ✔ Sliding-window/context trimming · ✔ Rolling summary memory (map→reduce digests) · add "diskcache exact-match LLM cache" | | |
| Models (15) | ✔ ChatGPT/OpenAI (GPT-OSS 120B/20B) · ✔ Qwen (3.8 27B) · ✔ Claude (Claude Code built it) · add Gemma 4 (Google), dots.3 (rednote), Xing 4.0, multilingual-e5-small | `config.yaml` | 15 |
| How & why (5) | role table from README "Models" section | README | 5 |
| Retrieval & RAG (12) | ✔ Naive RAG · ✔ Hybrid search (BM25 + e5 dense, RRF) · ✔ Agentic RAG (Adversary multi-query) · ✔ Query rewriting (bilingual EN/BN queries) · ✔ Corrective RAG (4-gate verifier + Critic re-anchoring) | `ain/retrieval.py`, `agents/adversary.py`, `verifier.py`, `critic.py` | 12 |
| RAG details (5) | 1,157 sections, section-level chunks w/ deep links, e5-small embeddings in `.npy`, BM25 over NFC Bangla tokens, citation_id-only constraint, MRR 0.75 vs 0.19 | README corpus section | 5 |
| **MCP (20)** | **Nothing in the product.** Dev-time only: Claude in Chrome, Claude Design (mood stickers / council fight came from a Claude Design project), Claude Docs | — | **0–4** |
| Open-source (8) | FastAPI, sentence-transformers, rank-bm25, EasyOCR, PyMuPDF, python-docx, RapidFuzz, diskcache, BeautifulSoup/lxml, Next.js/React, argon2, cryptography | `requirements.txt` | 8 |
| Agent orchestration (7) | Custom asyncio multi-agent pipeline (10+ agents), SSE event trace, 3-judge bench + peer review + Chief Justice, council deliberation rounds, provider fallback chains | `orchestrator.py`, `bench.py`, `council.py` | 6–7 |
| Fine-tuning (5) | none | — | 0 |
| Evaluation (7) | Gold set (recall/precision/citation validity/drop rate), 38-pair bench trap set, LLM-as-judge entailment, plain-chatbot ablation, retrieval MRR, 169 offline tests | `eval/`, `tests/` | 7 |
| Guardrails (6) | PII Shield + outbound PII guard (422), citation_id-only, 4-gate verifier, citation stripping, free-only + `data_collection: deny`, CSRF, argon2, Fernet at rest | `agents/pii.py`, `llm.py`, `auth.py`, `vault.py` | 6 |
| Frontend AI builders (5) | Claude Design (add as "other"), Claude Code; ask user if Cursor/v0/Artifacts were used | memory | 1–2 |
| Workflow automation (4, n8n +2) | none | — | 0 |
| Local LLMs (8, Ollama +2) | none (EasyOCR + e5 run locally but are not LLMs) | — | 0 |
| Agentic frameworks | custom (no framework) | — | — |
| AI-DLC | Claude Code plan files (spec-first), persistent memory (= memory-bank pattern), `web/AGENTS.md`; plans → tests → eval gate before commit | `~/.claude/plans/*.md` | partial |
| /docs module | not built | — | 0 |
| Data lifecycle | scraping bdlaws (httpx+bs4, UTF-16), official PDFs, OCR, user uploads, synthetic long doc; JSON/JSONL/YAML/PDF/DOCX/images/HTML; Pydantic; SQLite + encrypted files + diskcache; REST+SSE+OpenAPI; DOCX export | `corpus/`, `ingestion.py` | good, no viz |
| Tunneling | HF Spaces deploy, no tunnel | — | 0 |

**Estimated current score ≈ 80–90 / 110. Biggest holes: MCP (20), Local LLM (8), Workflow (4+2), Fine-tune (5), /docs, visualization.**

## Part 2 — What to add (user picked: MCP, /docs+charts, n8n, AI-DLC+answers; local LLM skipped; UI tools = Claude Design + Claude Code)

### Feasibility check (done in plan mode)
| Item | Verdict | Why |
|---|---|---|
| AI-DLC files + answers | **Easy**, do first | docs only, no code risk |
| MCP server | **Easy–medium**, do second | `mcp` SDK not installed yet but pure-Python, deps (httpx, pydantic, starlette, uvicorn, sse-starlette) already in venv; all tool logic already exists |
| /docs + Recharts | **Medium**, do third | Next 16 / React 19.3; recharts 3.x supports React 19; FastAPI's own `/docs` is on :8000 and Next only proxies `/api/*`, so no route clash |
| n8n | **Medium, cut first if short on time** | Docker 29 present, ~1.3 GB free RAM — enough to run n8n briefly for a check, not alongside backend+dense. Keep n8n thin: logic lives in a backend endpoint |

Execution order = table order. Stop and report after each item; if n8n gets hard (RAM, Docker), ship only the
backend endpoint + workflow JSON and say it was not run end-to-end.
Do not touch the uncommitted CouncilFight work on branch `deploy`; new work goes in new files.

## Part 2b — Details (in execution order: 5/6 → 1 → 2 → 3)

### 1. Ain MCP server — up to +20 (highest value)
New `backend/ain/mcp_server.py` using the official `mcp` Python SDK (FastMCP), reusing existing functions — no new logic:
- tools: `search_law(query, packs?, k)` → `Corpus.search`; `get_section(citation_id)` → `Corpus.get`; `verify_citation(citation_id, proposition, quote?)` → the verifier gates; `wage_truth(gross, deductions, country)` → `agents/calculator.py`; `analyze_contract(text, country?)` → `orchestrator.run_pipeline` (returns risks + verified ledger, PII-redacted); `list_countries` → `countries.py`.
- resources: `corpus://{citation_id}` statute text; `playbook://rules`.
- prompt: `review_contract` template.
- transports: stdio (`python -m ain.mcp_server`, for Claude Desktop / Claude Code `.mcp.json`) + streamable HTTP mounted at `/api/mcp` in `ain/api.py` (so it passes through the Next proxy on HF Spaces), with `stateless_http=True, json_response=True` to avoid SSE buffering in the proxy; bearer token `AIN_MCP_TOKEN` required on HTTP, and HTTP disabled when it is unset.
- add `mcp` (pinned) to `requirements.txt`; confirm the starlette version it pulls is compatible with fastapi 0.143.
- `wage_truth` builds `DocFacts`/`RouteDecision` from args and calls `calculator.compute`; `verify_citation` builds a `Claim` and calls `verifier.verify_claim` with the router's default route.
- PII guard stays on every tool input; fake mode works offline.
- `tests/test_mcp.py`: list tools, call `search_law`/`get_section`/`verify_citation` in-process.
- Also document the MCP servers *used* in dev (Claude in Chrome for browser QA, Claude Design for UI assets, Claude Docs).

### 2. Live `/docs` page (recommended by the form) + charts
`web/src/app/docs/page.tsx`: pitch + architecture diagram + AI-usage answers + **live** panel from `/api/health` and a new `/api/metrics` (corpus size by pack, last eval numbers from a committed `eval/results.json`, LLM cache hit counts). Add **Recharts** for eval/ablation bar charts (ticks a Visualization box). Check FastAPI's own `/docs` stays under `/api` so routes don't clash.

### 3. n8n workflow — +3 (n8n +1, bonus +2)
Self-hosted n8n (Docker) with 2 exported workflows committed in `automation/n8n/`:
- **Law freshness watch** (cron daily): re-fetch bdlaws pages for the corpus acts → hash diff → if changed, alert + open an issue ("re-run curate/build"). Fits the currency gate story.
- **Job digest webhook**: backend POSTs a redacted summary on job completion (`AIN_WEBHOOK_URL`, off by default) → n8n → email/Sheet log.

n8n detail: the freshness logic is a backend endpoint `GET /api/corpus/freshness` (re-fetch each corpus act's bdlaws page, hash, compare with the stored hash, return changed acts). The n8n workflow is just Schedule → HTTP Request → IF changed → notify (webhook/email). Run with `docker run -p 5678:5678 n8nio/n8n`, import, trigger once, then stop it.

### 4. Local LLM — skipped (user decision; not enough RAM)

### 5. AI-DLC artifacts — cheap, ticks "AGENTS.md spec" + "Claude Skills"
Root `AGENTS.md`/`CLAUDE.md` with project conventions (citation_id-only, never hand-type statute text, run pytest before commit), `docs/specs/` with the Claude Code plan files that drove each feature, and a project skill in `.claude/skills/` (e.g. `warm-cache`, `rebuild-corpus`).

### 6. Ready-to-paste form answers
`docs/AI_USAGE.md`: one honest paragraph per form section (Part 1 table expanded), reused by the /docs page.

Frontend-builder answer: tick Claude Design + Claude Code only (user confirmed).

### Not recommended
Fine-tuning (5 pts) — no GPU, machine OOMs on embedding rebuild; LangGraph/CrewAI rewrite just for a checkbox; LLMLingua — adds dependency for marginal gain. Tunneling: optional one-liner (cloudflared quick tunnel to show the MCP endpoint to judges) if wanted.

## Verification
- `cd backend && python -m pytest -q` (all existing + new MCP tests pass offline).
- MCP: `npx @modelcontextprotocol/inspector python -m ain.mcp_server` → list/call tools; add to Claude Code via `.mcp.json` and call `search_law`.
- `/docs`: `npm run build && npm start`, open `/docs`, check live panel + charts in light/dark and phone width.
- n8n: import JSON, trigger manually, confirm diff/alert node output.
- Docker image still builds and serves `/`, `/counsel`, `/docs`, `/api/health`.
