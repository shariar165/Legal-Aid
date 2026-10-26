---
name: warm-cache
description: Warm Ain Copilot's LLM replay cache with live Groq/OpenRouter calls after prompts, model ids or hero documents change, staying inside the free quota. Use before a demo or a Docker/HF Spaces build.
---

# Warm the LLM replay cache

The cache key covers the provider, model, messages, temperature and task, so a prompt edit makes old entries
unreachable. Replay mode (`AIN_LLM_MODE=replay`) only uses this cache, so the demo then runs offline at 0 tokens.

1. Check the keys are in the root `.env` (`GROQ_API_KEY`, `OPENROUTER_API_KEY`). Never print them.
2. From `backend/`: `python -m scripts.smoke_live --docs 1`. It checks every model id against the providers'
   `/models` lists, runs one hero document and prints the OpenRouter free quota left. OpenRouter allows 50 free
   requests a day; a full bench costs 6.
3. Repeat with `--doc <name>` for each remaining hero document, checking the quota between runs. Stop when the quota
   is low and continue after UTC midnight.
4. Report per document: clauses, off-playbook risks, dropped restatements, calls, fallbacks and time. Say plainly if
   any seat fell back to Groq.
