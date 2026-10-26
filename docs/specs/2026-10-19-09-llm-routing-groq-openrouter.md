# Plan: professional LLM setup (Groq + free-only OpenRouter)

## Context
The user added a Groq key and an OpenRouter key, and wants the system's models set up properly, with **only free models on OpenRouter**. The page they linked (OpenRouter's "Claude Code integration") covers pointing the Claude Code CLI at OpenRouter. It doesn't apply to this app, which calls OpenAI-compatible `/chat/completions` from `backend/ain/llm.py`. Live checks on 2026-10-19 found:

- **Keys are in the wrong file.** They are in `.env.example`, which git tracks; no `.env` exists. Not committed yet.
- **Groq retired 3 of the 4 configured models.** `llama-3.1-8b-instant`, `qwen/qwen3-32b` and `llama-3.3-70b-versatile` no longer exist. Still available: `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`.
- **All 4 OpenRouter roles point at paid models** (claude-haiku, gemini, deepseek, gpt-5.4-mini).
- **OpenRouter key limits:** `is_free_tier: true`, **50 free-model requests/day**, about 20 requests/min. One bench costs 7 calls (3 opinions + 3 reviews + chair), so one analysis can need about 30 calls.
- **`data_collection: deny` (kept, per user choice) blocks** the Nvidia Nemotron and Poolside free endpoints with 404 "Free model training".
- **Under deny, these were probed and work:** `dots-studio/dots-3-note-preview:free` (AtlasCloud, about 9 s, reasoning-heavy), `xingchen-agi/xing4.0-29b-a4b:free` (Phala), and `openrouter/free` (routed to dots-3). `google/gemma-4-31b-it:free` and `gemma-4-26b` pass the policy filter but often return upstream 429s. `thinkingmachines/inkling:free` is only for agent harnesses (403).
- **User decisions:** keep strict deny; when OpenRouter quota or rate limits run out, **fall back to Groq** and mark the fallback visibly.

## Changes

### 1. Secrets
- Create root `.env` with the two keys plus `AIN_LLM_MODE=live`, keeping the other lines from `.env.example`.
- Restore `.env.example` to blank placeholders (`git checkout -- .env.example`).
- `.env` is already gitignored (`.gitignore`).

### 2. `backend/ain/config.yaml`: model routing as the single source of truth
Move the hard-coded `FALLBACKS` dict out of `llm.py` and give every role an ordered chain:
```yaml
roles:
  fast:     {provider: groq, model: openai/gpt-oss-20b,  backup: {provider: openrouter, model: xingchen-agi/xing4.0-29b-a4b:free}}
  reasoner: {provider: groq, model: openai/gpt-oss-120b, backup: {provider: openrouter, model: dots-studio/dots-3-note-preview:free}}
  judge:    {provider: groq, model: qwen/qwen3.8-27b,    backup: {provider: openrouter, model: google/gemma-4-31b-it:free}}   # different family from the gpt-oss drafter
  plain:    {provider: groq, model: openai/gpt-oss-120b} # ablation baseline uses the SAME model as the reasoner, so the comparison isolates the pipeline
  bench_a:  {provider: openrouter, model: google/gemma-4-31b-it:free,           fallbacks: [google/gemma-4-26b-a4b-it:free, openrouter/free], backup: {provider: groq, model: qwen/qwen3.8-27b}}     # Sunny
  bench_b:  {provider: openrouter, model: dots-studio/dots-3-note-preview:free, fallbacks: [openrouter/free],                                  backup: {provider: groq, model: openai/gpt-oss-120b}}  # Regal
  bench_c:  {provider: openrouter, model: xingchen-agi/xing4.0-29b-a4b:free,    fallbacks: [openrouter/free],                                  backup: {provider: groq, model: openai/gpt-oss-20b}}   # Grey
  chairman: {provider: openrouter, model: openrouter/free,                      fallbacks: [dots-studio/dots-3-note-preview:free],             backup: {provider: groq, model: openai/gpt-oss-120b}}
providers:
  groq:       {base_url: ..., key_env: GROQ_API_KEY, rpm: 30}
  openrouter: {base_url: ..., key_env: OPENROUTER_API_KEY, rpm: 18, free_only: true,
               reasoning: {effort: low, exclude: true}}
```
This gives three judge families (Google, rednote, Xingchen) plus a routed chairman.

### 3. `backend/ain/config.py`
- Extend `RoleConfig` with `fallbacks: tuple[str, ...]` and `backup: RoleConfig | None`.
- Extend `ProviderConfig` with `rpm`, `free_only` and `reasoning`.
- **Free-only guard:** when `config.yaml` loads, raise if any OpenRouter model (primary, fallbacks or backup) is not `*:free` or `openrouter/free`. This enforces "free only" in code, not just by convention.

### 4. `backend/ain/llm.py`
- **`resolve(role)`** returns an ordered candidate list: primary, then backup. A candidate is skipped when its provider has no key or is tripped.
- **Per-provider circuit breaker:** an OpenRouter 429 whose body mentions the daily free-model limit (`free-models-per-day`) marks the provider exhausted until the next UTC midnight. Calls then go straight to the Groq backup instead of burning the 6 retries.
- **Per-provider pacing:** a small async limiter shared across jobs (module-level, like `_cache`) keeps calls at or under `rpm`. This sits on top of the existing `Semaphore(6)` and retry/`retry-after` loop.
- **OpenRouter request body:**
  - send `models: [primary, *fallbacks]` for native fallback routing on upstream 429s and outages;
  - keep `provider.data_collection: "deny"`;
  - add the `reasoning` block from config;
  - read the **actual** model from the response's `model` field.
- **Empty or truncated content** (reasoning used up the budget) is treated as a failure, so the next candidate is tried.
- **Groq:** keep `reasoning_format: hidden` for `qwen/*` and `reasoning_effort: low` for `gpt-oss`.
- **Cache:** keep the existing key per (provider, requested model). On lookup, check each candidate in order, so `replay` mode also finds answers that a fallback produced.
- **`_post`** returns `(data, model_used)`.
- **`OutboundCall`** (`backend/ain/models.py`) gets `fallback: bool = False`. It records the provider and model actually used.

### 5. Bench and council labels
`bench.model_name()` (`backend/ain/agents/bench.py:190`) uses the new `resolve()`'s first live candidate. Seat labels in the Council and bench opinions then show the Groq model when OpenRouter is tripped. No other changes to `bench.py` or `council.py`: personas and prompts stay as they are.

### 6. Privacy receipt UI
- `web/src/components/counsel/Panels.tsx` and `web/src/lib/api.ts`: add `fallback?: boolean` to the call type.
- Add a small "fallback" tag in the per-model receipt row.

### 7. `backend/scripts/smoke_live.py`
- Validate primaries, fallbacks and backups against the live `/models` lists.
- Print the OpenRouter free-quota `used/limit/remaining` from `GET /api/v1/key` before and after the run.
- Add `--docs N` so a quota-limited day can warm one hero doc at a time.

### 8. Docs
- README "Models" table (`README.md:56-65`) and the Bench row (`README.md:22`): replace Claude/Gemini/DeepSeek/GPT with the new models.
- Note the free tier: 50 requests/day. A one-time $10 credit purchase raises this to 1000/day and still keeps every call on free models.
- Note the Groq fallback.
- `test_bench.py:62` checks for old model names in prompts. Generalise it to "no model id from config appears in the review prompt".

## Tests
- Add `tests/test_llm_routing.py` (offline, using mocked `httpx` transport) to cover:
  - the free-only guard rejects a paid OpenRouter id;
  - a daily-quota 429 trips the breaker, and the next call goes to the Groq backup with `fallback=True`;
  - the OpenRouter body carries `models`, `data_collection: deny` and `reasoning`;
  - an empty-content response moves on to the next candidate;
  - replay finds an answer cached under the backup.
- `cd backend && ..\.venv\Scripts\python -m pytest`: the whole suite stays offline and green.

## Verification
1. Run `pytest`; everything passes.
2. Run `python -m scripts.smoke_live --docs 1`. Every role should be OK against the live `/models`, one hero doc should run live, and the quota line should be printed. Check the trace for `openrouter/<model>:free` on bench calls.
3. Start the backend with `AIN_DENSE=0` and the web app with `next start`, per the low-RAM note in memory. Run one analysis, open Counsel, then check the privacy receipt and the Council seat models.
4. Run `git status` to confirm `.env` is untracked and `.env.example` has no keys.
