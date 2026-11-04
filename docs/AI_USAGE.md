# AI usage: answers for the "AI Detail Usage" form

One section per form section. **Tick** = the boxes to select. **Paste** = text for the free-text field. Everything
here is checkable in the repo, and the evidence is listed under each answer. Don't tick anything this file doesn't
list: judges can verify.

---

## Prompt usage (/10)

**Paste:**
Every agent has a role prompt with a strict JSON output contract: fact extractor, playbook checker, opposing counsel
(the Adversary), statute grounder, entailment verifier, three bench judges, the Chief Justice, the IRAC memo drafter,
and the council members for chat and deliberation. Patterns we used:
- **Role prompting with personas and reasoning lenses.** The three judges reason through different lenses: Remedies
  (Sunny), Text (Regal) and Enforcement (Grey). The lens shapes severity, reasoning and voice, but the entailment
  test itself is one neutral instruction, word-for-word identical for all three judges. A unit test enforces that, so
  personality can never change what the law is read to say.
- **Grounded, closed-book prompts.** Judges see only the statute text and the claim ("decide ONLY from the statute
  text provided"), and must quote the phrase they rely on; in batched mode the quote is checked in code.
- **Stepwise reasoning where it matters.** The Adversary must spell out the mechanism (what happens to the worker,
  step by step) and name at least 2 interacting clauses, a gap, or a regime conflict. It also gets the playbook's
  findings and rule list, so it doesn't repeat them.
- **Multi-round deliberation.** Anonymised peer review (judges see the others' opinions as "Justice A/B"), then a
  ruling that records the majority, any dissent and the points still in dispute.
- **Map → reduce prompts** for long contracts: each part gets a hypothesis prompt plus a digest of its material
  terms; a reduce prompt looks across the digests for clause interactions far apart in the document.
- **Iteration and versioning.** Prompts live as constants in each agent module under git. The LLM cache key
  includes the full messages, so every prompt edit is a new version that must be re-warmed and re-evaluated. Bench
  prompt changes go through the 38-case trap set (`eval/bench_quality.py`) before their flag is turned on.
- **Evidence-gated revisions.** LLM judges change their answers under peer pressure, even when the argument is empty, so
  in the council's round 2 a change of view counts only if code confirms it rests on new law: a section the member may
  cite, not cited in its round 1, with a quote passing the verifier's G2. Otherwise round 1 stands for the Chief Justice
  and the tally. The prompts ask only for the format, so they do not coach the behaviour the pressure trap measures.

Evidence: `backend/ain/agents/*.py` (`*_SYSTEM` constants), `tests/test_bench.py`, `eval/bench_traps.yaml`.

## Token optimization (/10)

**Paste:**
Everything runs on free tiers (Groq ~8k tokens/min per model; OpenRouter 50 free requests/day), so tokens and
requests are the constraint we designed around:
- **Response cache.** Every model answer is stored on disk (diskcache), keyed by provider + model + messages +
  temperature. Replay mode serves the whole demo from cache at 0 tokens, and the Docker image ships the warmed cache.
- **Cheap-model routing.** GPT-OSS 20B for fact extraction and routing, 120B only for reasoning and drafting;
  deterministic code wherever a model isn't needed (the wage calculator, quote fidelity by fuzzy match, citation
  existence and currency checks).
- **Structured outputs.** JSON mode on every call (with a fallback for models that reject it) means no retries
  over prose parsing.
- **Context trimming.** Statutes over 8,000 characters are windowed on the cited sub-section, the quote, the
  definitions and every proviso. Grounding reads each candidate section windowed on the hypothesis.
- **Map → reduce digests** for long contracts instead of sending the whole document every call.
- **Request savers behind eval-gated flags:** batching up to 4 claims per judge call, skipping peer review when all
  three judges already agree, and a tighter statute window. Each stays off until the trap-set eval shows it changes
  no answer.
- **Pacing instead of failing.** A token bucket keeps calls under Groq's per-minute budget, re-synced from Groq's
  `x-ratelimit-remaining-tokens` header. A daily-quota 429 trips a breaker to the backup provider instead of retrying.

**Tick:** Structured outputs / JSON mode · Cheap-model routing · Request batching · Sliding-window / context
trimming · Rolling summary memory (map→reduce digests) · **Add:** "Exact-match LLM response cache (diskcache) +
offline replay mode" · "Token-bucket rate pacing from provider headers".
(Don't tick the providers' prompt caching or LLMLingua: we don't use them.)

## LLMs / models used (/15)

**Tick:** ChatGPT (OpenAI's open-weight **GPT-OSS 120B / 20B**, via Groq) · Qwen (**Qwen 3.8 27B**, via Groq) ·
Claude (**development**: the code was written with Claude Code). **Add:** Google **Gemma 4 31B / 26B** ·
rednote **dots.3** · Xingchen **Xing 4.0 29B** · **multilingual-e5-small** (embeddings) · **EasyOCR** (bn + en).
(Not Gemini, Llama, Grok, Mistral, DeepSeek or Kimi: don't tick them.)

## How & why did you use these LLMs? (/5)

**Paste:**
Different families check each other, so no model grades its own work. GPT-OSS 120B (Groq) does risk analysis,
adversarial counsel and drafting; GPT-OSS 20B does fast fact extraction. Qwen 3.8 27B is the single-judge
entailment verifier: a different family from the drafter. The Virtual Bench seats three judges from three more
families on OpenRouter's free tier (Gemma 4, dots.3, Xing 4.0), and their fallback chains never overlap, so no two
judges share a model. GPT-OSS 120B is the Chief Justice. Every role has a backup on the other provider, and a
fallback is marked in the trace. The ablation baseline is deliberately the reasoner's own model with one prompt and
no tools, so the comparison measures the pipeline, not the model. multilingual-e5-small gives cross-lingual dense
retrieval on CPU; EasyOCR reads phone photos locally so they never leave the machine. Claude (Claude Code) was the
pair programmer for the whole build.

## Retrieval & RAG (/12)

**Tick:** Naive RAG · Hybrid Search (Keyword + Vector) · Agentic RAG / Multi-step Retrieval · Corrective RAG (CRAG)
· Query Rewriting / HyDE. (Not a vector DB: vectors are an in-memory numpy matrix. No reranker, no Graph RAG.)

## RAG architecture details (/5)

**Paste:**
Corpus: 1,157 verbatim sections (38 acts and documents). Bangladesh law is scraped section by section from
bdlaws.minlaw.gov.bd (UTF-16 pages) with deep links. ILO conventions, EU law, Bangladesh Bank rules, the labour law
of 8 destination countries, fair-recruitment standards, companies' own policies and 3 ILO CEACR observations are cut
verbatim from official PDF/HTML/DOCX sources. Each section is one chunk (the natural legal unit), with status (in
force / amended / repealed), what superseded it, and its law pack. Retrieval is hybrid: BM25 over NFC-normalised
Bangla + English tokens, plus intfloat/multilingual-e5-small dense vectors (embeddings.npy, rebuilt incrementally),
fused by reciprocal rank (k=60), filtered by the law packs the Jurisdiction Router chose (EPZ documents swap the
Labour Act for the BEPZ Labour Act). The Adversary does agentic multi-query retrieval in both languages, with a
round-robin share of candidates per query. Bangla BM25 queries beat English-only dense search for cross-lingual
recall (MRR 0.75 vs 0.19, measured during development), so every search is bilingual. Corrective step: agents may cite only citation_ids that
retrieval returned; each claim then passes 4 gates (existence and applicability, quote fidelity, entailment by a
different model family, currency), and the Critic re-anchors a citation to repealed law onto its replacement and
re-verifies it. A section's own cross-references ("section 28", "ধারা ১২৫") are followed to pull in linked sections.

## MCP (/20)

**Tick:** "We built and/or used MCP servers / clients in this build".

**Built: `ain-copilot` MCP server** (`backend/ain/mcp_server.py`, official `mcp` Python SDK 2.3, `MCPServer`)
- **6 tools:** `search_law`, `get_section`, `verify_citation` (the 4 gates), `wage_truth`, `analyze_contract` (the full
  pipeline), `list_countries`.
- **2 resources:** `ain://corpus/{citation_id}` (template) and `ain://playbook/rules`. **1 prompt:** `review_contract`.
- **2 transports:** stdio (`python -m ain.mcp_server`, registered for Claude Code in `.mcp.json`) and streamable HTTP
  at `POST /api/mcp` (stateless, JSON responses, so it works through the Next.js proxy in the hosted container),
  behind a bearer token with a Host allow-list against DNS rebinding.
- **Guardrails carried over:** text containing an identifier is refused, and the server reuses the engine's
  retrieval, gates and calculator unchanged.
- **Reuse:** any MCP client can use the verified-law engine, e.g. Claude Desktop, Claude Code while editing the
  playbook, or another NGO's agent.
- Tests: `backend/tests/test_mcp.py` (in-process client, PII refusal, HTTP 401 without the token, 200 with it).

**Used during the build (MCP clients in Claude Code):**
- **Claude in Chrome** MCP: browser checks of every UI change, e.g. the /docs page's charts, tooltips and layout.
- **Claude Design** MCP: the council's pixel "mood stickers" and the deliberation scene were designed in a Claude
  Design project and ported to React/SVG from there.

## Open-source tools & libraries (/8)

**Paste:**
FastAPI + Uvicorn + sse-starlette (API and live agent event stream) · Pydantic (every model, request and result
schema) · httpx (provider calls, with our own retry, fallback and pacing logic) · sentence-transformers + PyTorch CPU (multilingual-e5
embeddings) · rank-bm25 (keyword retrieval) · NumPy (vector search) · EasyOCR (local Bangla + English OCR) ·
PyMuPDF (PDF text and corpus curation) · python-docx (DOCX input and memo export) · RapidFuzz (quote-fidelity gate) ·
diskcache (LLM response cache) · argon2-cffi + cryptography/Fernet (passwords, encryption at rest) · PyYAML (playbook,
countries, routing) · the official MCP Python SDK (our MCP server) · pytest (229 offline tests) · Next.js 16 + React
19 (UI) · Recharts (charts on /docs) · n8n (workflow automation) · Docker (one-container deploy).

## Agent frameworks & orchestration (/7)

**Paste:**
A custom asyncio multi-agent orchestrator, no framework. A pipeline of 10+ agents: Ingestion → PII Shield →
Jurisdiction Router → Risk Analyst ‖ Adversarial Counsel ‖ Wage Calculator (parallel) → Policy Check → Citation
Verifier → Virtual Bench (3 judges + Chief Justice, peer review, quorum rules, graceful judge failure) → Critic →
Memo Drafter. It includes a human-in-the-loop pause (confirm a blurry OCR salary), and after the run an LLM Council
(chat, then deliberation rounds, then a ruling). Every step emits server-sent events, so the UI shows real agent
activity. Each role has a routing chain: primary → same-provider fallbacks → cross-provider backup, with circuit
breakers and per-model concurrency limits. Tool use is constrained: agents can only cite ids from the retrieval tool.

## Fine-tuning / adaptation (/5)

Leave blank. We didn't fine-tune; the free-tier, CPU-only setup made retrieval plus verification the better
investment.

## Evaluation & quality measurement (/7)

**Paste:**
1. **Gold set** (`eval/run_eval.py`, 5 documents including a clean control): recall and precision against expected
   risks, the share of memo citations verified, drop rate, off-playbook count (≥3 per hero document), and per-document
   must-cite / must-not-cite checks (e.g. a Saudi contract never relies on Malaysian law).
2. **Ablation:** the same model with one plain prompt and no tools; its citations go through the same 4 gates, so the
   gap measures the pipeline, not the model. (Quote numbers from a live run only: the committed run uses the fake
   LLM, whose plain-chatbot answers are canned.)
3. **LLM-as-judge:** entailment is judged by a different model family, and for high/critical claims by a 3-judge
   bench with dissent and human-review flags.
4. **Bench trap set** (`eval/bench_quality.py`, 38 adversarial claim/statute pairs: exceptions, provisos, wrong
   regime): every quota-saving or ruling flag must leave verdicts unchanged and keep severity within one notch for
   ≥90% of opinions before it's enabled.
   The same run includes the **pressure trap** (`eval/pressure_trap.json`): on six traps each seat meets a colleague who
   is certain and cites nothing, and we measure its raw flip rate, how many flips the gate blocked, and a neutral-colleague
   control. This is our sycophancy score per seat; it is not fed into any prompt.
5. **229 offline pytest tests** with a deterministic fake LLM, run on every change, including bilingual retrieval
   tests (a Bangla query must find the Bangla statute).
Honest note: the gold set covers our own seeded documents, so it's a regression check, not a benchmark.

## Guardrails, safety & privacy (/6)

**Paste:**
PII Shield redacts names, passport, NID, phone, address and date of birth before any model call. The LLM layer
blocks any payload that still holds an identifier (HTTP 422 in chat; MCP tools refuse too). OCR runs locally.
OpenRouter calls send `data_collection: deny` and use free endpoints only (enforced at config load). Hallucination
control: agents may cite only retrieved citation_ids; 4 verification gates; the drafter and council strip any
unverified id, including from the prose. Output validation with Pydantic schemas. Out-of-scope documents get an
"outside Ain's focus" label instead of a pretend review. Accounts: argon2id, hashed HttpOnly session tokens,
Origin-checked CSRF, rate limits, owner-only access (404), Fernet encryption at rest, and user erasure.

## Frontend AI / visual app builders

**Tick / add:** Claude Design (add as "other") · Claude Code (add as "other").
**Paste:** The council's animated pixel mood stickers and the deliberation fight scene were designed in Claude Design
and ported to React/SVG. The rest of the UI (citizen mode, Counsel workspace, /docs) was written in Claude Code
sessions from approved specs, then checked in the browser with the Claude in Chrome MCP. Nearly all frontend code
was AI-written and human-reviewed.

## Workflow automation (+1 each, n8n bonus +2)

**Tick:** n8n.
**Paste:** Self-hosted n8n (Docker, `automation/n8n/`). (1) **Law freshness watch**, daily: calls
`/api/corpus/freshness`, which re-reads each Bangladesh act on bdlaws, diffs it section by section against our corpus,
and alerts the team with the changed citation ids and the rebuild commands (or an "incomplete" alert if the site is
down). (2) **Analysis digest**, by webhook: the backend posts a count-only summary when an analysis finishes, and n8n
alerts on any critical risk or human-review flag. The backend logic is unit-tested and the workflows' JavaScript was
run in Node. Import the two workflows into a running n8n once before claiming they're live.

## Local / on-device LLMs

Leave blank (no local LLM runtime). Under "anything else" mention that the models which see the raw document run
locally: EasyOCR for photos and multilingual-e5 for embeddings, both on CPU.

## Agentic frameworks used

Leave the list blank and add "Custom asyncio orchestrator (no framework)". Don't tick LangGraph or CrewAI.

## AI Development Lifecycle (AI-DLC)

**Tick:** Claude Skills · AGENTS.md spec · **Add:** "Claude Code plan mode: spec-driven development".
**Paste:** Each feature started as a plan written in Claude Code's plan mode: context, chosen approach, files to touch,
how to verify. The user approved it before any code was written; all 13 are in `docs/specs/`. Shared rules for any
coding agent are in `AGENTS.md` (`CLAUDE.md` points to it): never hand-type statute text, cite only retrieved ids, no
PII leaves the machine, free-only OpenRouter. Project skills (`.claude/skills/rebuild-corpus`, `warm-cache`) hold the
repeatable procedures. Persistent agent memory carries decisions across sessions. Review gates before every commit:
offline tests → gold-set and trap-set evals for prompt or routing changes (the eval report before the commit) →
browser check of UI changes.

## Live /docs module

**Tick:** Yes. The live page is `/docs`: pitch, architecture, AI stack, MCP, evaluation, safety, build process and
limitations, plus live tiles and Recharts charts read from `/api/health` and `/api/metrics` (corpus by law pack,
model routing, cache size, MCP tools, last eval run).

## Anything else?

**Paste:** Things we think are unusual: (1) a **4-gate citation verifier** where dropped claims stay visible in a
ledger; (2) a **cross-family Virtual Bench** whose personas change tone and severity but provably not the legal test;
(3) **regime switching**: an EPZ factory turns off the Labour Act and a Labour Act citation fails the applicability
gate; (4) **repealed-law healing**: a 2012 Act citation is re-anchored to the 2026 Act and re-verified; (5)
**"valid abroad, void in Bangladesh"** clash badges; (6) a fully **free-tier** stack with visible fallbacks; (7) the
verified-law engine is open to any agent over **MCP**.

---

# Data lifecycle & engineering

1. **Data sources.** Tick: Public web (scraping) · Open datasets (government and ILO publications) · User uploads ·
   Internal (own DB) · Synthetic (the fictional ~25-page contract and the blurred sample photo). List: bdlaws.minlaw.gov.bd;
   ILO NORMLEX and ILO tradefordecentwork compilation; EU Publications Office CELLAR; Bangladesh Bank; WIPO Lex,
   FAOLEX, Malaysia AGC, Singapore Statutes Online, LLOC Bahrain, Decree.om, embassy translations; companies' own
   published policy PDFs.
2. **Acquisition.** Tick: Web scrapers (polite urllib scraper, 1 s delay, raw-page cache) · AI extraction (LLM fact
   extraction to a JSON schema) · Bulk upload (PDF/DOCX/TXT/photo) · OCR (EasyOCR, bn + en, cached by file hash) ·
   Automated flows (n8n daily freshness watch, job webhooks) · MCP servers for data access (our own server exposes the
   corpus).
3. **Formats and parsing.** JSON, JSONL, YAML, PDF, HTML/XHTML, images, DOCX, Markdown. Parsers: PyMuPDF,
   python-docx, zipfile+regex for DOCX sources, regex HTML parsing of UTF-16 bdlaws pages, EasyOCR, LLM JSON mode.
   Cleaning: NFC normalisation of Bangla, PDF header/footer and page-number removal, clause segmentation at numbered
   sub-clauses/schedules/annexes, table cell extraction, duplicate-hypothesis filtering, PII redaction. Validation:
   Pydantic models, config validation (free-only models), tests that every playbook quote is verbatim in its source.
4. **Storage.** Relational: SQLite (accounts, sessions, job ownership). Cache/KV: diskcache (LLM answers). Files:
   Fernet-encrypted analysis results; JSONL corpus; NumPy embedding matrix with per-row keys for incremental rebuilds.
5. **Visualization.** Tick: Recharts. Corpus-by-pack and per-document risk and claim charts on /docs, with hover
   tooltips, a legend and a table view for each, and light and dark palettes; in-app severity-tinted contract view and
   verification ledger.
6. **Insights.** Tick: LLM inference / RAG · Rule engine (YAML playbook, arithmetic wage calculator) · Statistical
   analysis (eval metrics). Delivered as an in-app report, citizen cards read aloud in Bangla, an IRAC memo (DOCX),
   a letter to the recruiting agency, and n8n alerts.
7. **Pipelines.** An event-driven asyncio orchestrator with SSE streaming; n8n cron (daily freshness) and webhooks
   (job digests); corpus build scripts (fetch → curate → build → embed).
8. **Outbound.** REST + SSE API (FastAPI, OpenAPI schema), MCP server (stdio + streamable HTTP), webhook digests, DOCX
   export.
9. **Open-source stack.** See "Open source tools" above.
10. **Quality and governance.** Corpus integrity tests; the currency gate (in force / amended / repealed) and the daily
    freshness diff; PII redaction with an outbound guard; encryption at rest; per-owner access; 7-day guest purge;
    account erasure; a privacy receipt per analysis listing every outbound call; agent trace; cost: free tiers only,
    cache, pacing, eval-gated quota savers.

**Tunneling:** none used (the hosted demo is a Docker image on Hugging Face Spaces). Leave blank.
