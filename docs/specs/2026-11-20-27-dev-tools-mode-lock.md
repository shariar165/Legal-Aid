# Spec 27: keep the scratchpad dev tools, lock `llm_mode`

## Context
1. **Tools at risk.** Four helper scripts from earlier sessions live only in Claude's temp scratchpad, which a reboot can wipe:
   - `shot.py`: headless Chrome over CDP, for screenshots and JS checks (the Gate 3 browser checks).
   - `citizen_js.py`: JS snippets that drive the Citizen page to its result screen and promise form.
   - `warm_clean.py`: deletes fallback answers from the LLM cache and re-warms a sample from the configured model.
   - `contrast.py`: WCAG contrast check of the `globals.css` tokens, light and dark (spec 26).

   They belong in the repo.
2. **Mode override hole.** `POST /api/analyze` takes an `llm_mode` form field (`api.py:348`) and passes it to the pipeline unchecked. On a replay or fake server, any client can send `llm_mode=live` and spend free quota, and there is no rate limit. Stored results have the same hole: `/promises/verify` and `/ablation` run with `LLM(mode=r.llm_mode)`, so a result saved by an earlier live run calls live models again.

**Decisions (user):**
- This change is the code lock only. Railway keeps running live (no `AIN_LLM_MODE` is set there), so on Railway today the lock changes nothing. It takes effect once the server runs in replay mode.
- Council chat stays as designed (`council.chat_mode`): it goes live when the bench roles have keys.

## Part A: commit the tools
Source: the newest copy of each file. `shot.py` comes from session `c973e933…`, because the `7612b034…` copy is older and lacks `--pre`/`--login`. `citizen_js.py` is the same in both sessions.

| File | Destination | Changes |
|---|---|---|
| `c973e933…/scratchpad/shot.py` | `web/scripts/check/shot.py` | `PROFILE` moves out of the repo to `Path(tempfile.gettempdir()) / "jukti-shot-profile"`. The docstring states that `--login` needs the local test account `desk-check@example.test` (example.test, a fake address) and needs `websockets`, which is already in `.venv` (17.2). |
| `c973e933…/scratchpad/citizen_js.py` | `web/scripts/check/citizen_js.py` | none |
| `730b3023…/scratchpad/contrast.py` | `web/scripts/check/contrast.py` | The css path defaults to `web/src/app/globals.css`, found relative to the script. It exits 1 when any pair fails, so it works as a check. |
| `c973e933…/scratchpad/warm_clean.py` | `backend/scripts/warm_clean.py` | The module-level code moves into `main()` under `if __name__ == "__main__"`. Behaviour stays the same. It runs as `python -m scripts.warm_clean <sample_id> [--dry]` from `backend/`. |

Docs:
- `AGENTS.md` "Commands": add one line each for `warm_clean`, `shot.py` and `contrast.py`.
- `.claude/skills/warm-cache/SKILL.md`: add one line on purging cached fallback answers with `scripts.warm_clean`.

Commit 1: `Dev tools: browser-check, contrast and cache-clean scripts`.

## Part B: lock `llm_mode`
- **`backend/ain/config.py`**:
  - Add `MODE_RANK = {"fake": 0, "replay": 1, "live": 2}`.
  - Add `allowed_mode(requested: str | None) -> str`. It returns the server mode (`llm_mode()`) when `requested` is empty or ranks higher than the server mode. Otherwise it returns `requested`. A request can lower the mode but never raise it.
- **`backend/ain/api.py` `analyze`**:
  - Keep the 400 for an unknown value.
  - Add a **403** when the requested mode ranks above the server mode: `"This server runs in {mode} mode; a request cannot raise it."`
  - Pass `config.allowed_mode(llm_mode)` to `run_pipeline`.
- **`backend/ain/api.py`** `verify_promises` (l.458) and `run_ablation` (l.491): use `LLM(mode=config.allowed_mode(r.llm_mode))`.
- **Unchanged:**
  - The council endpoints (user decision).
  - `smoke_live`, `warm_clean` and eval, which call `run_pipeline` directly and are not HTTP clients.
  - The web app, which never sends `llm_mode` (checked with grep of `web/src`).
- **Tests** in `backend/tests/test_api.py` (the server runs fake through conftest):
  - `llm_mode=live` and `llm_mode=replay` → 403, `fake` → 200.
  - With `monkeypatch.setenv("AIN_LLM_MODE", "replay")`, `allowed_mode` gives: `"live"` → `"replay"`, `"fake"` → `"fake"`, `None` → `"replay"`.
  - A saved result with `llm_mode="live"` on a fake server: `allowed_mode` gives fake for the ablation/verify paths.
- **README**:
  - The "LLM modes" section gets one sentence: the request field can only lower the mode (403 otherwise).
  - "Honest limitations" gets a new bullet: no per-user rate limit yet, and the demo backend runs live (cache first), so each new upload spends free quota.

Commit 2: `Lock llm_mode: a request can lower the server's mode, never raise it`.

Both commits go on a new branch `dev-tools-mode-lock` off `main`. No push, PR or Railway deploy unless the user asks. The spec is saved as `docs/specs/2026-11-20-27-dev-tools-mode-lock.md` (in commit 1).

## Verification
1. Run `cd backend && ..\.venv\Scripts\python -m pytest -q`. All tests must pass, new ones included.
2. Run `..\.venv\Scripts\python web\scripts\check\contrast.py`. It should print "all pass" and exit 0.
3. Run `python -m scripts.warm_clean rmg_epz --dry` with `AIN_LLM_MODE=replay`. This is replay only, with no network and no quota spent. It should run and print counts.
4. Gate 3 (fake mode):
   - Start the backend with `AIN_LLM_MODE=fake AIN_DENSE=0` and the web app with `npm run build && npm start`.
   - Run `web/scripts/check/shot.py snap / 1440 <scratchpad>/home.png`, then `citizen_js.py 0` through `shot.py eval`. The Citizen sample run must still reach its result, which proves both the moved tools and the unchanged UI path.
   - Check with curl that `POST /api/analyze` with `llm_mode=live` returns 403.
5. Gate 2 evals are not needed: no prompt, routing or bench flag changes.
