# Apply the "Council upgrade + mobile" patch series

## Context
The user pasted a two-commit `git format-patch` series (from [a teammate], 18 Oct 2026):
1. **Upgrade the LLM Council and polish the UI**: council replies get a position and a confidence level, Bangla answers, a deliberation round with a Chief Justice ruling (`POST /api/jobs/{id}/council/deliberate`), in-place OCR salary confirmation in Counsel mode, a "New analysis" button, a severity filter, and SVG icons in the citizen app.
2. **Make the Council mobile-friendly**: a phone layout at ≤640px.

The goal is to land both commits on `main` with their authorship and messages intact, then confirm the tests, lint and build pass.

## Pre-checks (done, read-only)
- HEAD is `5570a44` and the working tree is clean.
- The pre-image blob hash of all 15 touched files matches the `index <old>..` lines in the patch exactly, so it should apply with no fuzz or conflicts.
- Everything the patch depends on is already in the repo:
  - icons: `camera`, `copy`, `external`, `arrowRight`, `users`, `check`;
  - CSS tokens and classes: `--warn-tint`, `--bad-ink`, `--sv-tint`, `--acc`, `.faces`, `.views`, `.count`, `.secondaryBtn`, `.linkBtn`, `.insetLabel`;
  - test helpers: `RecordingLLM(overrides=…)` in `backend/tests/conftest.py`, and `_benched` and `find_pii` in `test_council.py`;
  - frontend: `api.confirm` and `OcrCheck` in `web/src/lib/useAnalysis.ts`.
- `.venv` and `web/node_modules` are present.

## Steps
1. Save the pasted patch text verbatim (both commits, as one mbox) to the scratchpad:
   `C:\Users\Acer\AppData\Local\Temp\claude\D--Ai-congress-laywer\43ad5b52-dc1b-420a-8eee-7b8e33c4b541\scratchpad\council-upgrade.mbox`
2. Dry run: `git apply --check` on that file.
3. Apply: `git am --keep-cr <file>` on `main`. This creates the 2 commits and keeps the original author, dates, messages and Co-Authored-By trailers. If it fails, run `git am --abort`, use `git am -3`, and report back.
4. Do not push. The user hasn't asked for that.

## Files changed by the patch
- Backend:
  - `backend/ain/agents/council.py`: `rebut`, `deliberate`, `_reply`, `_strip_ids`, Bangla fakes;
  - `backend/ain/models.py`: `CouncilRuling`, `CouncilDeliberateRequest`/`Response`, new `CouncilReply` fields;
  - `backend/ain/api.py`: the new deliberate endpoint, plus the `_council_risk` and `_save_council_calls` helpers;
  - `backend/ain/agents/risk_analyst.py`: word-boundary excerpt.
- Tests: `backend/tests/test_council.py` (5 new) and `backend/tests/test_api.py` (deliberation checks).
- Web:
  - `web/src/components/counsel/{Council.tsx, CounselApp.tsx, Icons.tsx, counsel.module.css}`
  - `web/src/lib/api.ts`
  - `web/src/components/citizen/{HomeScreen.tsx, citizen.module.css}`
  - `web/next.config.ts`
- `README.md`

## Verification
- `cd backend && ..\.venv\Scripts\python -m pytest -q`: expect **59 passed**, the number the commit message claims.
- `cd web && npm run lint && npm run build`: should come out clean (the TS types for `CouncilReply`/`CouncilRuling` must line up with the components).
- `git log --oneline -3` should show the two new commits on top of `5570a44`.
- Optional manual check (`/run`):
  - open `/counsel` and pick a sample;
  - in Council, ask the whole council a question, then press "Hold a deliberation";
  - switch to বাংলা;
  - narrow the window to ≤640px to see the phone layout.
