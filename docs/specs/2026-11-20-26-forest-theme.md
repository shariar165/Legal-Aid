# Spec 26: Forest & Sand theme, dark mode, a more polished Counsel

## Context
The user wants the UI recoloured to match two reference images: **Forest Green `#1F3D2B`** and **Sand Beige `#E8DCC4`**.
The second image is a deep-green hero with fine grain, cream type, a translucent pill nav, and a cream pill as the
main button. They also want a dark mode that suits the UI, and a more professional Counsel workspace (`/counsel`).

Decisions (from the user):
- Scope of the polish: the Counsel workspace (top bar, Case Desk, Memo, Council tab frame, Checks, start, login).
  The pixel-art council scene keeps its look.
- Dark mode: **everywhere** (Citizen, Counsel, /docs). It follows the system setting, and a toggle overrides it.
- Gold → **Sand**: the main buttons on the green bar become sand pills with forest text. Gold stays only on the
  "said" ledger bar.

What exists already:
- `web/src/app/globals.css` is the single token source for Citizen and Counsel (spec 20). Modules read its tokens,
  and `citizen.module.css` has no hard-coded colours.
- `counsel.module.css` has about 50 hard-coded colours, `desk.module.css` 14 and `moneyHero.module.css` 3. Most are
  `#fff` on accent, `#fff` cards, and warn/bad border tints. These would break in dark mode.
- `docs.module.css` keeps its own `--d-*` tokens and already has the dark-mode pattern we will reuse:
  `@media (prefers-color-scheme: dark) :root:where(:not([data-theme="light"]))` plus `:root[data-theme="dark"]`.
  Nothing sets `data-theme` yet.
- `Charts.tsx` reads the CSS tokens at runtime, but it only re-reads them when `matchMedia` changes.
- Next 16 guide `node_modules/next/dist/docs/01-app/02-guides/preventing-flash-before-hydration.md`: an inline
  `<head>` script sets `data-theme` before first paint, with `suppressHydrationWarning` on `<html>`, and a
  `useLayoutEffect` in the toggle re-applies the theme after the dev Strict-Mode remount.
- The logo is generated: `web/scripts/build-logo.py` sets `TILE, CREAM, GOLD = "#0f4c3a", …`.
- Branch: `ledger-live` has no `web/` changes, so the work goes on a new branch **`forest-theme` off main**.

## Approach

### 1. Tokens: one palette, two themes (`globals.css`)
Rewrite the `:root` values with the new palette and **keep every token name**, so the modules need no rename.
Light theme (a sand-paper ground, forest ink):
- ground `--bg #F3EEE3`, `--card #FCFAF5`, `--subtle #EDE6D7`, `--paper #FFFDF8`, `--paper-line #E3D9C4`
- ink `--ink #17231B`, `--ink-2 #34433A`, `--muted #5C6559`, `--line #E2D9C8`, `--line-strong #CDBFA6`
- brand `--accent #1F3D2B`, `--accent-hover #16301F`, `--accent-tint #E3EADF`, `--deep #1F3D2B`,
  `--deep-line #3A5644`, `--on-deep #F2EBDD`, `--on-deep-muted #C3C7B4`
- new `--sand #E8DCC4`, `--sand-hover #F0E7D5`, `--sand-ink #1F3D2B`, `--on-accent` (light: `#FCFAF5`)
- new line tokens to replace the hard-coded borders: `--ok-line`, `--warn-line`, `--bad-line`, `--accent-line`
- status, severity and member colours keep their hues. Only the tints shift slightly warmer so they sit on sand.
- shadows tinted forest instead of neutral.

Dark theme (the reference hero: deep forest, cream type). The same two selectors as the docs page:
- `--bg #0E1812`, `--card #15221A`, `--subtle #1B2A20`, `--paper #19261D`, `--ink #ECE4D2` (sand-cream),
  `--muted #A29C8A`, `--line #26362B`, `--deep #12201A`
- `--accent #E8DCC4` (sand), `--on-accent #1F3D2B`, so dark-mode primary buttons are the sand pill from the
  reference. Links use a lighter sage, `#B5D0AE`.
- status, severity, member and ledger tints become dark, low-chroma fills with light ink (e.g. critical tint
  `#3A1B17` / ink `#F3A79C`). `--highlight` becomes a muted amber fill.
- `color-scheme: dark` so form controls and scrollbars follow.
- **Print always uses the light tokens** (`@media print` resets them), so the memo prints on white.

Every text/background pair is checked against WCAG AA (4.5:1 for body text, 3:1 for large text and UI parts) with
a small script in the scratchpad. Any value that fails is adjusted before commit.

### 2. Theme switch (no flash)
- `web/src/app/layout.tsx`: an inline `<head>` script reads `localStorage["jukti-theme"]` (`light`, `dark`, or none
  meaning system) and sets `data-theme` on `<html>`. Add `suppressHydrationWarning` on `<html>`. `themeColor`
  becomes a light/dark media pair (`#1F3D2B` / `#0E1812`).
- New `web/src/components/shared/ThemeToggle.tsx` (client): one icon button that cycles System → Light → Dark.
  It has an `aria-label` naming the current state, and its `useLayoutEffect` re-applies the stored theme (from the
  Next guide). Add `sun`, `moon` and `monitor` glyphs to `shared/Icons.tsx`.
- Placement: Counsel top bar `.actions` (CounselApp, CounselStart, AuthForm), Citizen `HomeScreen` top bar beside
  the language toggle (bilingual label), and the /docs header.
- `docs/Charts.tsx`: also re-read the tokens when `data-theme` changes (a `MutationObserver` on `<html>`).

### 3. Remove hard-coded colours
In `counsel.module.css`, `desk.module.css` and `moneyHero.module.css`, swap each literal for a token:
`#fff` text on accent → `var(--on-accent)` (or `--on-deep` on the bar), `#fff`/`#fbfdfc`/`#fafbfa` fills →
`--card`/`--subtle`, `#f3dca6`/`#f5c7c1`/`#a6d9bf`/`#cfe3d8` borders → the new `--*-line` tokens, `#05603a` →
`--ok-ink`, white-alpha hovers on the bar → `color-mix(in srgb, var(--on-deep) 8%, transparent)`.
The code block at `#151c18` stays dark in both themes. Print-only `#fff` stays.
`docs.module.css` `--d-*` values are moved onto the same palette (light and dark), so /docs matches.
The `CouncilFight.tsx` and `PixelSticker.tsx` pixel art is left as it is. Only its frame and background use tokens.

### 4. Counsel polish (in the style of the reference, CSS only, no new UI kit)
- **Top bar**: forest `--deep` with a very faint SVG-noise grain (one inline data-URI `background-image`, opacity
  ~4%). The brand stays at left. Actions become pill buttons (`--r-pill`), and the primary action (Download memo) is
  the sand pill.
- **View tabs** (Case Desk / Memo / Council / Checks): the underline tabs become a pill segment group. The active
  tab is a translucent cream pill (`color-mix(var(--on-deep) 14%)`), like the reference nav. Counts become small
  sand badges.
- **Start page hero** (`CounselStart`): a forest band with grain, the cream headline in the serif face at
  `--fs-40` with tighter tracking, the trust items as small outlined pills (like "→ Monthly drops"), and the
  dropzone as a sand-bordered card under the band.
- **Surfaces**: cards on sand ground with `--line` hairlines and the forest-tinted `--shadow-2`. Section titles get
  consistent weight and tracking. Chips and badges become pills. Focus rings use the sand colour on green and forest
  on sand.
- The Case Desk hero (`MoneyHero`) keeps its layout. Its colours come from tokens, so it follows the theme.

### 5. Logo
`web/scripts/build-logo.py`: `TILE = "#1f3d2b"`, `CREAM` and `GOLD` → sand `#e8dcc4`. Run the script to regenerate
`logo-paths.ts` and `icon.svg`, and never edit the paths by hand.

## Files
- `web/src/app/globals.css`, `web/src/app/layout.tsx`
- `web/src/components/shared/ThemeToggle.tsx` (new), `shared/Icons.tsx`, `shared/moneyHero.module.css`
- `web/src/components/counsel/counsel.module.css`, `counsel/desk/desk.module.css`, `CounselApp.tsx`,
  `CounselStart.tsx`, `AuthForm.tsx` (toggle and tab markup only)
- `web/src/components/citizen/HomeScreen.tsx` (toggle), `citizen.module.css` (toggle style only)
- `web/src/components/docs/docs.module.css`, `docs/Charts.tsx`, `web/src/app/docs/page.tsx` (toggle)
- `web/scripts/build-logo.py` → regenerated `brand/logo-paths.ts`, `app/icon.svg`
- `docs/specs/2026-11-20-26-forest-theme.md` (this plan + what was done), screenshots in `docs/design/theme-*.png`

## Verification
1. `cd web && npm run lint && npm run build` pass.
2. `cd backend && python -m pytest -q` still passes. No backend change is expected, so this is a sanity check.
3. Contrast script: every text/background pair in both themes is AA or better.
4. `grep` shows no hex/rgba colour left in `counsel.module.css`, `desk.module.css` or `moneyHero.module.css`,
   except the code block, print rules and noise data-URI.
5. Browser check in fake mode (`AIN_LLM_MODE=fake`, backend with `AIN_DENSE=0`, `npm run build && npm start`), at
   1440 and 390 wide, light and dark:
   - Counsel start, a sample analysis → Case Desk, Memo, Council, Checks, and login.
   - Citizen home → result. /docs, including its charts.
   - The toggle cycles System/Light/Dark, survives reload with no flash, and follows the OS when on System.
   - Print preview of the memo is light while dark mode is on.
   - Screenshots saved to `docs/design/theme-*.png`.
6. Commit on `forest-theme`. Push or open a PR only when the user asks.

## Done
- **Tokens** (`globals.css`): the light palette is in `:root`, and the dark values are written once in
  `:root[data-theme="dark"]` inside `@media screen`, so the memo always prints light. New tokens: `--on-accent`,
  `--link`/`--link-hover`, `--sand`/`--sand-hover`/`--sand-ink`, `--on-deep-hover`/`--on-deep-active`,
  `--accent-line`, `--ok-line`/`--warn-line`/`--bad-line`, `--highlight-ink`, `--grain` and `--shadow-up`.
- **Contrast** (scratchpad script, WCAG): every text pair passes AA in both themes, including ink/muted on
  every ground, on-accent on accent, status and severity ink on tints, member ink on tints, and sand-ink on sand.
  Severity colours pass 3:1 as UI parts. `--line-strong` hairlines stay decorative at about 1.75:1, as before
  (#c9d0ca on white).
- **Switch**: `lib/theme.ts` holds the logic and the inline script. `data-theme` always holds the resolved value,
  and "system" follows the OS live. `ThemeSync` in the root layout handles the dev remount. `ThemeToggle` cycles
  System → Light → Dark, with an English or Bangla label. It sits in the Counsel bar (app, start, login), on the
  Citizen home beside বাংলা/EN, and in the /docs header. `docs/Charts.tsx` re-reads its colours through a
  `MutationObserver` on `data-theme`.
- **No hard-coded colours** left in counsel, desk, moneyHero or citizen CSS, except the pixel stickers'
  drop-shadows, the redacted code block, the print `#fff`, the error pink on the forest band and the hatch on
  free bars. Text on `--ink` or status backgrounds uses `--card`, so it flips with the theme. The Citizen
  subtitles on accent buttons and the play button were fixed for dark.
- **Gold → sand**: the Counsel bar's main button, the file chip, active tab counts, focus rings, the desk
  language toggle, tags, the on-band button, and the money hero's "paper" bar. Gold remains on the "said" bar and
  on the hero's headline loss figure, which is a data highlight.
- **Counsel polish**: the bar has grain. Buttons are pills. The section tabs are a pill group with a translucent
  cream active pill, and `--header-h` stays 108/100. The start page has a full-width forest hero band with grain
  and a sand glow, a centred cream serif headline and pill trust items, and the dropzone card overlaps the band.
- **Logo**: `build-logo.py --recolour OUT_DIR` moves the built mark onto the palette (tile #1f3d2b, balance
  #e8dcc4) without re-shaping the glyph. The outlines were checked byte-identical to spec 22. `apple-icon.png` was
  rebuilt with `raster-logo.mjs`, and `favicon.ico` was rebuilt as 16/32/48 PNG entries, as before.

## Checked
- `npm run lint` and `npm run build` pass. `pytest` offline: 358 passed (main base).
- Browser, fake mode, 1440 wide: Counsel start (light and dark), Case Desk (light and dark), Memo, Council and
  Checks (dark), sign-in (dark), Citizen home (dark), /docs (dark). After a reload the theme is still applied
  (`data-theme` is set by the head script). The chart grid swaps `#26362b` ↔ `#e6decd` with the toggle. A throwaway
  local test account was used and then deleted with `DELETE /api/auth/me`.
- **Not checked**: the 390-wide layouts. The Chrome window would not resize and the app correctly refuses
  iframes, so the phone header (50 + 44 + 6 = 100px) is checked by arithmetic only. Print preview was not opened;
  the dark block is `@media screen` only. No `docs/design/theme-*.png` screenshots were saved.
