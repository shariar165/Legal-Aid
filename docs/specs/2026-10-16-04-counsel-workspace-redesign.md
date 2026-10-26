# Counsel mode redesign: professional, user-friendly workspace

## Context
Counsel mode (`/counsel` and `/counsel/[jobId]`) works, but it doesn't look professional. The causes found in the code:
- **Typography.** Headings use `--font-serif` (Noto Serif Bengali), and only the Bengali subset is loaded. English headings therefore fall back to the browser's Times. Body text uses Hind Siliguri, a Bengali-first face.
- **Cartoon council.** The avatars have rosy cheeks, a crown, a rain cloud and a tear. Messages appear as candy-coloured chat bubbles.
- **Glyphs instead of icons.** `✓ ⚠ ✕ →` are used as icons throughout (`format.ts` VERDICT_LABEL, RiskCard, Panels).
- **Messy CSS.** `counsel.module.css` (1,927 lines) is layered with overrides. `.topbar`, `.page` and `.sectionTitle` are each redefined later in the file, and colours are hard-coded (`#d9534a`, `#fbe1dc`, `#efb8b0`).
- **Layout.** Every view is one narrow column. There is no at-a-glance summary, the start page is a plain grid of cards, and the chat is a small box inside the page.

The user chose: **refined monogram badges** for the council, and a **full restructure + restyle**. Data, API calls, the citation_id-only constraint and the citizen UI stay untouched. The changes are front-end only, under `web/`.

## Approach

### 1. Foundation
- **New `web/src/app/counsel/layout.tsx`.** Load `Inter` (UI) and `Source_Serif_4` (headings) with `next/font/google` (variable fonts; check `node_modules/next/dist/docs/01-app/01-getting-started/13-fonts.md`, as AGENTS.md requires). Expose them as `--font-inter` / `--font-source-serif` on a wrapper `div`. The stacks fall back to Hind Siliguri, so Bangla (`lang="bn"`) text still renders: `--c-sans: var(--font-inter), var(--font-hind-siliguri), system-ui`.
- **New `web/src/components/counsel/Icons.tsx`.** A small inline-SVG icon set at 16–20px with `currentColor` and a 1.75 stroke: check, alert, x, download, printer, upload, file, scale, shield, send, chevron, external, copy, sun, cloud, users, sparkle. No new dependency.
- **Rewrite `counsel.module.css`** as one ordered file: tokens → shell → start → progress → report → risk card → contract → council → verification → print → responsive. Keep every class name the TSX uses (or rename it in the same change).
  - Scoped tokens on `.page`: cool off-white canvas (`#f6f7f5`), white cards, slate ink, hairline `--c-line`, two shadow levels, 8/12px radii, a 4px spacing scale, and the brand green kept as the accent.
  - Severity tokens: `--sev-critical/high/medium/low` plus `-tint` and `-ink` variants. These replace every hard-coded hex.
  - Persona tokens are kept, with muted accents (Sunny amber, Regal indigo, Grey slate).

### 2. App shell (`CounselApp.tsx`)
- **Header row.** Brand on the left. In the centre, a document pill (file icon, name, Replay/Offline chip). On the right, a primary **Download memo** button (icon) and a **Print** icon button with a tooltip.
- **Tab row.** Underline tabs with icons and count badges: Report (live risks), Contract (flagged clauses), Council, Verification (verified/claims). "How we checked" is renamed **Verification**, and its page title stays "How we checked this memo".
- **Loading view.** A centred card with a 4-step vertical stepper (icons, done/current/todo), a thin progress bar (`stepsDone.length / 4`), and the agent log in a collapsible section.
- **Error view.** A card with an alert icon, the message, and a "Start a new analysis" button.

### 3. Report view: two columns
- At `≥1024px`, a grid of `minmax(0,1fr) 300px`. The aside sticks below the header. On narrower screens it stacks above the risks as a compact summary.
- **Main column**
  - **Summary card:** kicker, serif title ("N risks need your attention"), severity count badges, executive summary, and the Bangla summary in a labelled inset ("বাংলা সারাংশ").
  - **Wage check card:** the existing figures as KPI tiles. The bar gets labels for take-home and legal minimum.
  - **Risk list.**
  - **Limits of this memo:** the existing `<details>`, restyled.
- **Aside, "At a glance"**
  - Stacked severity distribution bar.
  - Verified citations: `stats.verified` of `stats.claims`, with a link to Verification.
  - Laws applied: the route packs, with excluded ones struck through.
  - **Jump to risk:** a numbered list. Clicking an item reuses `go("report", "risk-…")`.
  - **Ask the council** button.

### 4. Risk card (`RiskCard.tsx`)
- **Header:** "Risk 1" number, severity badge, and a "Lawyer review advised" flag (shield icon) when `bench.human_review` is set. Below it, the serif title and the Bangla subtitle.
- **Body:** the finding, then a **Recommended action** callout (green-tinted, check icon).
- **Legal basis:** citation chips. Verified chips show a check icon; partial ones show an amber alert icon. External links get an external-link icon.
- **Council line:** three mini monogram badges, "Council 3–0" and the majority line.
- **Actions:** "Discuss with council" (primary-outline) and "Details" (with a chevron that rotates).
- **Details:** sections with consistent small-caps headings (In the contract, Why it's easy to miss, Valid abroad / void in BD, Suggested replacement clause with a Copy icon button, Council vote, Legal analysis). Legal analysis is shown as a two-column IRAC table.

### 5. Contract view
- The document renders as a paper sheet: white, a max width of about 72ch, and serif body text.
- Clause numbers sit in a left gutter. A flagged clause gets a severity left rule, a faint tint and an inline badge ("High · Unlawful deductions →").
- A sticky toolbar holds the legend and a segmented control: **All clauses (n) | Flagged only (m)**. It replaces the checkbox.

### 6. Council view (`Council.tsx`)
- **`CouncilAvatar` → monogram badge.** A circle with the persona tint, a 1px accent ring and the initial (S / R / G) in semibold. A tiny corner glyph (sun / shield / cloud) sits on a white disc. The component keeps the same `{persona, size}` props, so `MemberVotes`, `CouncilFaces` and RiskCard keep working. `CouncilFaces` becomes overlapping badges with white rings.
- **Layout at `≥1024px`:** a `280px | 1fr` grid.
  - **Left rail, "Who answers":** a vertical list. "Entire council" comes first, then each member: badge, name, title, tagline, and the model id in small mono text. Selection uses a radio list with `aria-checked` and a selected background plus accent rule. Below the list, a **Topic** select (whole contract / each risk).
  - **Right, the conversation panel** (height about `calc(100dvh - header - 48px)`, minimum 520px):
    - **Header:** "Asking *Entire council* about *the whole contract*".
    - **Messages:** member replies render as cards (badge, name · title, text, citation chips) rather than bubbles. User messages are right-aligned, compact and in neutral ink.
    - **Empty state:** three suggested questions as cards with a sparkle icon.
    - **Composer:** pinned at the bottom. An auto-growing textarea with a send icon button inside the frame. Enter sends and Shift+Enter adds a new line, as today. The disclaimer sits underneath.
  - **Mobile:** the rail collapses to a horizontal segmented member strip above the chat.
- **Below, "How the council voted":** an accordion table with columns Risk | Sunny | Regal | Grey | Outcome ("Unanimous", or "Grey dissented"). It expands to the majority opinion plus each member's reasoning, the revised note and the model. The "Ask about this risk" button is kept.
- **Unchanged:** all state and logic (`send`, history trimming, error handling, the `api.council()` fetch).

### 7. Verification view (`Panels.tsx` + Checks in CounselApp)
- **KPI tiles:** neutral cards with a coloured dot or indicator rather than full tint blocks.
- **Sub-tabs:** become a segmented control.
- **Ledger rows:** cards. The header holds the claim id, citation link and verdict badge (icon + text). Gate chips become "Existence ✓"-style chips with icons, and the legend is shown once.
- **`format.ts`:** `VERDICT_LABEL` becomes plain words. The components render the icons.
- **Trace:** a monospace log table. Ablation keeps the two-column comparison with the new tokens. Privacy keeps its tables, restyled.

### 8. Start page (`CounselStart.tsx`)
- **Hero:** kicker "Counsel mode", serif title, a one-line lead, and three trust points with icons:
  - "Every citation checked against the statute book"
  - "Personal details hidden before any AI sees the text"
  - "Reviewed by a three-model council"
- **Upload dropzone panel:** a large dashed area with an upload icon, "Drop a contract here or browse", and the accepted formats. It adds `onDragOver`/`onDragLeave`/`onDrop`, which call the existing `go(() => api.analyzeFile(f), "upload")`, and shows a busy state.
- **"Or try a sample":** cards with a kind badge (Sample / Phone photo), the English and Bangla titles, the subtitle and an arrow.
- **"How it works":** a 3-step strip: Upload → Verified analysis → Memo & council.

### 9. Print and accessibility
- Print rules are kept: memo only, so the header, aside, actions and council are hidden, and risk details stay intact.
- Focus rings, ARIA roles and `prefers-reduced-motion` are kept. All text/background pairs must meet WCAG AA.

## Files
- **New:** `web/src/app/counsel/layout.tsx`, `web/src/components/counsel/Icons.tsx`
- **Rewrite:** `web/src/components/counsel/counsel.module.css`
- **Edit:** `CounselApp.tsx`, `CounselStart.tsx`, `Council.tsx`, `RiskCard.tsx`, `Panels.tsx`, `format.ts` (all in `web/src/components/counsel/`)
- **Reuse as-is:** `useAnalysis` / `STEP_ORDER` (`web/src/lib/useAnalysis.ts`), `api` + types (`web/src/lib/api.ts`), `citeLabel`, `money`, `SEVERITY_*` (`format.ts`), and the global tokens in `globals.css` (not modified, so the citizen UI is unaffected).

## Verification
1. `cd web && npx tsc --noEmit && npm run lint && npm run build`
2. Start the backend offline: `cd backend && $env:AIN_LLM_MODE='fake'; ..\.venv\Scripts\python -m uvicorn ain.api:app --port 8000`. The web dev server is already up on :3000.
3. In Chrome, check `/counsel` at 1440px and 390px: dropzone (click and drag-drop), then start a sample.
4. Check every view:
   - Loading stepper.
   - Report: aside sticky, jump links scroll to the right card, Details toggle, Copy.
   - Contract: segmented filter, clause → risk link.
   - Council: pick a member and topic, send a suggested prompt, citation chips link out, the error path shows (type a phone number), the votes accordion works.
   - Verification: all four sub-tabs, including running the ablation.
5. Print preview of the Report shows the memo only.
6. Confirm `/` (citizen UI) looks unchanged.
7. `cd backend && pytest` still passes (no backend changes expected).
