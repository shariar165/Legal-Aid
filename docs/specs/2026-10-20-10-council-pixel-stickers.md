# Council pixel stickers (from Claude Design "Mood Stickers")

## Context
The user designed three animated pixel-art mood stickers in Claude Design (project `d715e3ba-…`, file `Mood Stickers.dc.html`): **Happy** (hops, twinkling sparkles, beating heart), **Proud** (puffs up, shining medal, eye glint) and **Gloomy** (sighs, a drifting rain cloud, a tear that drips). They map one-to-one onto the council personas `happy` (Remedies · Sunny), `proud` (Text · Regal) and `gloomy` (Enforcement · Grey). The council should use them instead of the S/R/G monogram badges.

User decisions:
- **Placement:** big animated stickers in the empty-chat "council is ready" state and on the "thinking" rows. Small static stickers replace the monogram avatar everywhere else (rail, replies, vote table, ruling disputes, risk cards, Council tab).
- **Colour:** each persona gets its own body colour, not the design's single terracotta.

`support.js` is only the Claude Design runtime (DCLogic, `<sc-for>`). Nothing from it is ported.

## Approach

### 1. New `web/src/components/counsel/PixelSticker.tsx`
Port the design's geometry logic as pure TS, with no React state, memoised once per persona at module level:
- Helpers copied from the design script: `hex`, `mix`, `grid`, `stamp`, `rowsToDots`, `dots`, `off`, `kernel`, `morph`. Keep the sprite constants verbatim: `BODY`, `SPROUT`, `WILT`, `CLOUD`, the face dot lists, `sparkle`, `row`, and the `moods()` layer lists with their offsets (3,3 / 3,9).
- Die-cut outline: dilate by `r+k`, then erode by `k`, with `r = 2` (the design default) and `k = 3`. The white outline fill and the `under` colours for animated layers work exactly as in `sticker()`.
- **Render as SVG, not box-shadow.** The design draws every cell as a box-shadow sized in px. That can't scale cleanly to 18–40px avatars, and it would put thousands of shadows on the page. Instead, emit one `<svg viewBox="0 0 W H" shape-rendering="crispEdges">` per sticker. Inside it, each colour becomes one `<path>` built from horizontal run-length rects (`M x y h n v 1 h -n z`), so there are about 10 paths for the base and 1–2 per layer. Each layer is a `<g>`.
- Palette is the design's `palette()` with `B` = persona body colour; `S`/`H` are derived with `mix()` as in the design. Body colours come from the design's own option swatches so they stay in the persona hues: happy `#E9B544` (amber), proud `#8F82E3` (indigo/violet), gloomy `#8C9AB0` (slate). The design's `gloom` mix is dropped because the slate body already carries it.
- Export `PixelSticker({ persona, size, animate, className })`. The SVG fits inside a `size × size` box (`preserveAspectRatio` meet). The motion class goes on the `<svg>` with `transform-origin: 50% 100%`. Each layer `<g>` gets `transform-box: view-box`, `transform-origin: {cx}px {cy}px` (the centroid in cell units, as the design computes it), a layer animation class, and inline `animationDuration`/`animationDelay`. Proud's glint layer (`hideStill`) always has `opacity: 0`; the animation overrides that while it runs, so it stays hidden when static or when the user prefers reduced motion.

### 2. Keyframes in `counsel.module.css` (motion section, ~line 4055)
Add classes `.stk` (plus `display:block`, drop-shadow filter), `.stkHop`/`.stkPuff`/`.stkSigh`, and layer classes `.stkTwinkle`/`.stkBeat`/`.stkShine`/`.stkGlint`/`.stkDrift`/`.stkFall`/`.stkDrip`. They live in CSS rather than inline styles because CSS Modules hash keyframe names. Copy the design's keyframes, with one change: the layer keyframes that translate by `%` (Drift ±50%, Fall −100%→150%, Drip −100%→200%) are rewritten in cell units (`-0.5px`, `-1px`→`1.5px`, `-1px`→`2px`). In the design, `%` referred to a 1-cell div; under `transform-box: view-box` 1px is 1 cell. The body keyframes (Hop/Puff/Sigh) keep `%` because they apply to the `<svg>` box, as in the design. The existing `prefers-reduced-motion` rule (`.page *` → `animation:none`) already covers the SVG children.

Small avatars use a subtle `drop-shadow(0 1px 0 rgba(43,29,24,.15))`. The hero size uses the design's double drop-shadow.

### 3. `Council.tsx` changes
- `CouncilAvatar({ persona, size, animate = false })` keeps its signature and `role="img"` + `aria-label`, but renders `<PixelSticker>` in a `.sticker` span instead of the initial + glyph. Remove `GLYPH` and the glyph span; `Icon` stays imported because it is used elsewhere.
- `CouncilFaces` stays the same API (used by `CounselApp.tsx:131,610` and `RiskCard.tsx:96`); it now overlaps the static stickers.
- **Empty chat** (`Council.tsx:422`): replace `<CouncilFaces size={40} />` with a new `CouncilStickers` row: three animated stickers at about 88px, tilted by the design's rotations (−5°, 3°, −2°), each captioned with its lens (`LENS[p]`) in the small-label style.
- **Thinking** (`Council.tsx:671`): `<CouncilAvatar persona={p} size={36} animate />`, so the member who is "thinking" hops, puffs or sighs while the request runs.

### 4. CSS cleanup in `counsel.module.css`
- Add `.sticker` (inline-grid, `flex:none`, no circle background). Use a new class rather than `.avatar`, because `.avatar` is defined twice (council at line 2189, account menu at line 3705) and the account rules would bleed in.
- Retarget `.faces .avatar…` (2223–2229) and `.councilCta .faces .avatar` (1677) to `.sticker`, and drop the circular ring shadow because the die-cut outline replaces it. Remove `.avGlyph` (2206). Keep the council `.avatar` rule only if something else still uses it; otherwise remove it.
- Add `.stickerRow`/`.stickerFig` for the empty-state hero, with flex wrap and gap, and make sure it fits phone width (≤640px: about 64px stickers).

## Files
- `web/src/components/counsel/PixelSticker.tsx` (new)
- `web/src/components/counsel/Council.tsx` (CouncilAvatar, CouncilStickers, empty state, Thinking)
- `web/src/components/counsel/counsel.module.css` (sticker + keyframe classes, faces/cta retarget, glyph removal)

## Verification
1. `cd web; npx tsc --noEmit` and `npm run lint`.
2. Run the backend in fake mode with `AIN_DENSE=0`, build with `npm run build`, and run `next start`, as in the memory notes about low RAM. Sign in with the QA account (`backend/.data/test_account.txt`), open a Counsel job, then use the Council tab with Claude in Chrome:
   - The empty state shows three animated stickers, and their animation matches the design (hop, sparkles, heart; puff, medal shine, glint; sigh, cloud drift, rain, tear drip).
   - Send a question to "Entire council". The thinking rows animate, then the replies show static stickers.
   - Check the vote table, the risk-card faces, and the Council tab faces at 18–28px: they are crisp, with no seams.
   - Phone width (375px): no horizontal scroll, and the hero row wraps.
   - Turn on reduced-motion emulation: everything is static and the proud glint is hidden.
3. Compare with `render_preview` of the design file to check visual parity.
