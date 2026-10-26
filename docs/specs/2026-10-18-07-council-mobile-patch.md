# Apply "Make the Council mobile-friendly" patch

## Context
The user pasted a `git format-patch` commit (acb69be, "Make the Council mobile-friendly") produced in a cloud session (session_017Va1noWJR4DSsfMFcxuyFN). It cannot apply to this repo today:

- Local `main`, `llm-council` and `origin/*` all sit at `5570a44`; the patch's base blobs (`Council.tsx 6b739dc`, `CounselApp.tsx 68bbf45`, `counsel.module.css f2208c2`) don't exist locally (local blobs: `b7f52b8`, `2bc0c05`, `2c3bf91`).
- The patch styles/edits code that isn't here: deliberation + Chief Justice ruling (`exchanges`, `deliberateBar`, `rulingTitle`, `agreement`, `rulingConsensus`), EN/বাংলা answer switch (`langSwitch`, `language` state), `ReplyCard`/`Cites`, `msgMeta`, `msgPosition`, `quickRow`, `sevPill`. Local CSS is 3266 lines; the patch's hunk sits at line ~3916.

User decision: obtain the missing upstream commits first, then apply this patch unchanged.

## Steps
1. **User brings over the missing commits** (one of):
   - From the cloud session: push its branch to `origin` (e.g. `origin/llm-council` or a new branch), or
   - Export them as patches (`git format-patch 5570a44..<commit-before-acb69be>`) and share the files/paste.
2. **Integrate** (I do this once they exist):
   - `git fetch origin` → inspect `git log main..origin/<branch>`; fast-forward or create a local branch from it. Or `git am` the exported series onto `main` in order.
   - Confirm blob hashes of the 3 files now equal `6b739dc` / `68bbf45` / `f2208c2`.
3. **Apply the mobile patch**: save the pasted patch to the scratchpad, `git apply --check`, then `git am` it (keeps author, message, Co-Authored-By trailer). If any hunk conflicts, resolve by hand keeping the patch's intent.
4. Don't push unless asked.

## Verification
- `cd web && npx tsc --noEmit` and `npm run lint` (if configured), `npm run build` for a full Next.js 16 check.
- Backend `pytest` is unaffected (frontend-only change), but run it if the upstream commits touched `backend/`.
- Run the app (`run` skill / `npm run dev`), open a Counsel job's Council tab in Chrome at 390×844 and at desktop width:
  - phone: 4 equal member buttons (All/Sunny/Regal/Grey), topic + EN/বাংলা side by side, short intro, page-flow chat with sticky composer, avatar in card header, full-width "Hold a deliberation", vote pills with avatars, "Checks" tab label, no iOS zoom (16px inputs); new replies scroll into view above the composer.
  - desktop: layout unchanged, chat log still scrolls inside its own box.
