# Mood Fight as the council's deliberation loading scene

## Context
When the user clicks **Hold a deliberation**, the slow `councilDeliberate` call runs: the members rebut each other and the Chief Justice writes the ruling. During that wait the chat shows only three typing dots (`<Thinking>` at `web/src/components/counsel/Council.tsx:650`). The Claude Design project "Mood Fight" (d715e3ba-…) has a pixel-art brawl between the same three characters our stickers already use (Happy→Sunny, Proud→Regal, Gloomy→Grey). We'll turn it into a looping council-deliberation scene and play it for that wait.

The user's decisions:
- **Deliberation only.** Round-1 "asking" keeps the small dots.
- **New variant in Claude Design.** Mood Fight stays untouched. We add a council loop variant and port that to the app.

## Part 1: Design edit (Claude Design project d715e3ba-be01-4909-9ace-048193cb1479)
Call `get_claude_design_prompt` first (required before writes). Then write three new files and leave the existing ones unchanged:

1. **`council-fight.jsx`** builds on `window.MoodKit`, which `mood-fight.jsx` already exports (sprites, `charSprite`, `Pix/PixC/Char`, `big`, `tw`, `rnd`, `mix`). It holds a `CouncilFight` composition plus `window.CouncilFightRoot`. The changes from Mood Fight:
   - **Per-character colours.** Each fighter gets its app colour: happy `#E9B544`, proud `#8F82E3`, gloomy `#8C9AB0`. These come from `BODY_COLOR` in `PixelSticker.tsx:51`. The original used one `bodyColor` for everyone.
   - **No title or "ROUND 1".** The characters are already on stage, so the Title, Lineup and Round scenes are dropped. A short "DELIBERATING" tag can sit at the bottom, like the loaders' `Frame` label with animated dots.
   - **Neutral ending.** The KO beat ends with "RULING…" or a gavel/star instead of "GLOOMY WINS". Gloomy's grin can stay.
   - **Seamless loop.** The last scene returns everyone to their home positions and full HP, so the start of the loop is identical to the end of the previous pass.
   - **HUD.** The HP panels show the lens names REMEDIES / TEXT / ENFORCEMENT, matching the app's labels.
   - **Scenes.** `HappyAttack 3.2`, `ProudStrike 3.4`, `Brawl 3.2`, `Storm 3.6`, `Settle ~2.0`, about 15 s in total, with `OM_PLAYBACK` set to loop.
2. **`Council Deliberation.dc.html`** has the same shell as `Loader Tug of War.dc.html`: `x-import component-from-global-scope="CouncilFightRoot" from="./animations-v3.jsx ./mood-fight.jsx ./council-fight.jsx"`, a `label` prop that defaults to "DELIBERATING", and a camera-shake toggle.
3. Check it with `render_preview` at a few timestamps, including the loop seam. Share the page link with the user.

## Part 2: Port to the app
This follows the precedent in `PixelSticker.tsx`, which already ports "Mood Stickers.dc.html" to TypeScript.

**New `web/src/components/counsel/CouncilFight.tsx`** (client component):
- **Sprite kit.** Port the kit from `mood-fight.jsx` (`kernel/morph/makeSprite`, `BODY/SPROUT/WILT/CLOUD/SHADES/STAR/HEART/SPARK/BOLT/puffRows`, `FACES`, `charRows`) and the choreography from `council-fight.jsx`. Reuse `mix`, `hex`, `palette`, `kernel` and `morph` from `PixelSticker.tsx` instead of copying them. Export them from there; the palette needs the extra `D/d` puff colours added.
- **Engine.** This replaces `animations-v3.jsx`: an `rAF` loop holds `T = (now - t0) % total` in state, and a tiny local `Easing` (`easeInOutCubic`, `easeOutBack`, `easeOutExpo`) and `clamp` stand in for the originals. Cues are a constant object built from the scene list. None of the CompositionStage, export or timeline plumbing is needed.
- **Sizing.** The 1920×1080 stage is drawn inside a `ResizeObserver`-measured box and scaled with `transform: scale(w/1920)`, with `aspect-ratio: 16/9`, `max-width: 640px` and the full chat-column width on phones.
- **Accessibility.** The scene gets `role="img"` and `aria-label="The council is deliberating"`. Under `prefers-reduced-motion` the rAF loop is skipped: one static frame renders (all three standing, stickers' rest pose) with the label.
- **Font.** Add Silkscreen through `next/font/google` in `web/src/lib/fonts.ts` and expose it as a CSS variable used only by this scene. Read `node_modules/next/dist/docs/` for font usage first, as `web/AGENTS.md` asks.

**`Council.tsx`:**
- Line 650: `{x.status === "deliberating" && <Thinking members={x.members} />}` becomes `<DeliberationScene />`, which shows the fight plus a short caption ("The members are arguing it out; the Chief Justice will write the ruling"). Round 1 (line 632) keeps `<Thinking>`.
- Load `CouncilFight` with `next/dynamic` (`ssr: false`) so the sprite code stays out of the first bundle. The typing dots are the loading fallback.

**`counsel.module.css`:** add a `.fight` block (16:9 frame, rounded border matching `.ruling`, `overflow: hidden`, ink background) and add `.fight` to the existing `prefers-reduced-motion` block.

## Files
- Claude Design: `council-fight.jsx` and `Council Deliberation.dc.html` are new.
- `web/src/components/counsel/CouncilFight.tsx` is new.
- `web/src/components/counsel/PixelSticker.tsx` exports its shared helpers.
- `web/src/components/counsel/Council.tsx` swaps the deliberating state.
- `web/src/components/counsel/counsel.module.css` gets the frame styles.
- `web/src/lib/fonts.ts` adds Silkscreen.

## Verification
1. **Design:** `render_preview` of `Council Deliberation.dc.html` at T = 0, 5, 10 and 14.9 s confirms the colours, the label and that the loop seam matches.
2. **Static checks:** run `npm run lint` and `npx tsc --noEmit` in `web/`.
3. **In the app:** start the backend and `npm run dev` (via the `run` skill), analyse a sample contract, open the Council tab, ask with "Entire council", then click **Hold a deliberation**. The fight should loop until the ruling card replaces it, Round 1 should still show the dots, and the scene should scale on a phone-width viewport (Chrome tools).
4. Toggle reduced motion in DevTools rendering and check that a static frame shows.
