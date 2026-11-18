# Rename to যুক্তি · Jukti, with a new logo

## Context
The user is renaming the product from "আইন কপাইলট · Ain Copilot" to **যুক্তি** (*reason, reasoned argument*),
spelled **Jukti** in Latin script (agreed). The rename is **brand only** (agreed): every name a user, a judge or an MCP
client sees changes. Internal identifiers stay the same so Railway, Vercel and existing MCP configs keep working:
the `ain` Python package, `AIN_*` env vars, the `ain-copilot` MCP server id and `.mcp.json` key, `ain://` resource URIs,
`ain-copilot.vercel.app`, the Docker image tag and CSS hooks like `data-side="ain"`.
The product also needs a real logo in place of the current "আ" letter tile and the default Next.js `favicon.ico`.

Saved as spec `docs/specs/2026-11-18-22-jukti-rename.md` once approved.

## Logo: "the matra is the beam"
- **Idea.** Bengali script hangs every letter from a headline, the *matra* (মাত্রা). In the mark, the matra of **যু**
  runs past the letter and becomes the beam of a balance with two small pans. That is a reasoned weighing of both
  sides, which is what the product does to a contract. It also stays a Bangla monogram, the pattern the UI already uses.
- **Colours.** These come from the existing tokens: tile `--accent` #0f4c3a, letter `--paper` #fffdf8, beam and pans
  `--gold` #f5c443.
- **Outlined, not typed.** The glyphs are shaped with HarfBuzz from **Noto Serif Bengali Bold** (OFL; the UI already
  loads it) and turned into SVG paths, so the mark renders the same with no font installed.
  A one-off script in `web/scripts/build-logo.py` does this (`pip install fonttools uharfbuzz` in a scratch venv; the
  TTF is downloaded from the google/fonts repo). It writes:
  - `web/src/app/icon.svg`: the tile mark, which Next serves as the favicon.
  - `web/src/app/apple-icon.png` (180 px) and `web/src/app/favicon.ico` (16/32/48), rasterised from the SVG with the
    `sharp` already in `web/node_modules`, then packed into the .ico with Pillow.
  - `web/src/components/brand/logo-paths.ts`: the path data, used by a small `<Logo />` component.
- **Small sizes.** At 16 px the glyph drops out and the mark keeps only the tile, beam and pans (a separate
  `simple` path set), so the favicon stays legible.
- **Review.** A logo sheet (mark at 16/32/64/180 px, light and dark, beside the wordmark) is published as a private
  artifact for the user to see before anything is wired into the UI.

## Rename (user-visible strings)
The pattern: "আইন কপাইলট" → "যুক্তি", "Ain Copilot" → "Jukti", and "Ain" used as a product name → "Jukti"
(for example "outside Ain's focus" → "outside Jukti's focus"). The word **আইন** meaning *law* in legal text, the
playbook and the corpus is left alone; only the product name changes.

- **Web UI.** `web/src/app/layout.tsx` (title; keep the `themeColor`), the page `metadata` titles (login, signup,
  counsel, `[jobId]`, docs), `web/src/lib/citizen/i18n.ts` (`brand`, `brandMark` → `যু`), and the `desk/i18n.ts` rate
  note. In `AuthForm.tsx`, `CounselStart.tsx`, `CounselApp.tsx` and `citizen/HomeScreen.tsx`, the brand text,
  aria-labels and the `brandMark` span become `<Logo size={36} />`. The `.brandMark` CSS loses its letter styling
  and keeps only its size. The `Panels.tsx` label and the `CounselApp` "Outside Ain's focus" chip are renamed too.
  The docs page (`docs/page.tsx`) gets its heading, description and prose renamed; its MCP JSON snippet keeps the
  `ain-copilot` key.
- **Backend (strings only).** These are the `api.py` docstring and FastAPI title, the `mcp_server.py` docstring,
  `title=` and playbook-resource docstring (`name="ain-copilot"` stays), the `export.py` DOCX header and footer, the
  OpenRouter `X-Title` in `llm.py`, the `router.py` scope note (en and bn), the `ablation.py` docstring, and the
  `rules.yaml` header comment.
  - The DOCX download filename `ain-copilot-memo-*.docx` becomes `jukti-memo-*.docx`. This is a user-visible
    file name, so it counts as brand.
  - The `router.py` scope note, the `X-Title` header and the MCP title are part of the prompt or replay-cache path
    only if they reach a model. Before editing, check with `grep` whether the scope note is inside any LLM prompt.
    If any prompt text changes, AGENTS.md rule 8 applies: re-warm the cache with `python -m scripts.smoke_live`
    (to be flagged to the user, not run without keys).
- **Docs.** README (title line, prose, the HF Spaces `title:`; Docker and URL commands stay as they are), `web/README.md`,
  `docs/AI_USAGE.md`, the AGENTS.md and CLAUDE.md headings, both `.claude/skills/*/SKILL.md` descriptions, and the
  comments in `Dockerfile` and `backend/Dockerfile.lite`. Each says once "formerly Ain Copilot; internal ids keep
  `ain`" so the remaining `ain` names make sense. Old specs in `docs/specs/` are history and are not rewritten.
- **Memory.** The project memory entry is updated with the new name and the brand-only rule.

## Tests
- Grep `backend/tests` and `backend/eval` for asserted brand strings (none were found by the first grep) and update
  any that turn up.
- (Built as assertions in the existing `tests/test_api.py` DOCX flow and `tests/test_router.py`, so no extra pipeline run.)
  Offline checks: the DOCX export header contains "Jukti", the download filename
  starts with `jukti-memo-`, and the router's scope note (bn and en) has no "Ain Copilot" or "আইন কপাইলট".

## Verification
1. `cd backend && python -m pytest -q` passes.
2. `git grep -n -i "ain copilot\|আইন কপাইলট"` returns only old specs, the "formerly" notes and internal ids.
3. `cd web && npm run lint && npm run build` passes.
4. Browser check in fake mode (`AIN_DENSE=0`, `npm start`) of `/`, `/counsel`, `/login` and `/docs`: the new logo
   shows in each header, the tab title and favicon change, and Bangla and English both work. Take screenshots.
5. Run Gate 2 evals only if a prompt string changed (see the router note above).
6. Commit on `case-desk`: "Rename to যুক্তি · Jukti, with a new logo". Do not push unless asked.
