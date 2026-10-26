# LLM Council with personalities: Happy, Proud, Gloomy

## Context
Today the "Virtual Bench" (`backend/ain/agents/bench.py`) is a 3-judge LLM council (`bench_a/b/c` on OpenRouter) plus a neutral Chief Justice (`chairman`). The judges are anonymous ("Justice A/B/C"), share one prompt, and the UI only shows them as read-only cards in the Counsel-mode "Virtual Bench" tab (`web/src/components/counsel/Panels.tsx` `BenchPanel`).

The user wants each council member to have its own personality, to be clearly visible in the UI, and to be something users can talk to. Decisions made:
- **The personality changes tone and how severe they rate a risk.** Happy leans lenient, Proud keeps to its first view, Gloomy leans harsh. All three still rule ONLY from the statute text. The bench rules stay the same: the median severity wins, and any dissent goes to human review.
- **Interaction:** a council chat. A question can go to all three at once (three in-character replies) or to one member picked from a selector.
- **Placement:** Counsel mode only (English). The "Virtual Bench" tab becomes "LLM Council", and member avatars also appear on risk cards.

## Personas (single source of truth, in `bench.py`)
| id | Name | Seat / role | Voice | Severity disposition | Review behaviour |
|---|---|---|---|---|---|
| `happy` | **Sunny** · the Happy AI | Justice A / `bench_a` | upbeat, encouraging, leads with the remedy/fix | on a genuinely borderline call, one notch lower; never denies a risk the text plainly shows | open to revising |
| `proud` | **Regal** · the Proud AI | Justice B / `bench_b` | confident, formal, quotes the text precisely, a bit grand | calls it exactly as the text reads | revises only if the text plainly proves it wrong |
| `gloomy` | **Grey** · the Gloomy AI | Justice C / `bench_c` | melancholy, worst-case, "this is how it goes wrong" | on a borderline call, one notch higher | revises reluctantly |

The Chief Justice stays neutral and has no persona.

## Backend

### 1. `backend/ain/agents/bench.py`: personas on the bench
- Replace `SEATS` with a `PERSONAS` list of small dicts/dataclass: `id, name, title ("the Happy AI"), seat ("Justice A"), role ("bench_a"), tagline, voice, disposition, review_stance`.
- `JUDGE_SYSTEM` / `REVIEW_SYSTEM` become templates: the existing evidence rules are kept word for word, and a `PERSONALITY:` paragraph is added from the persona (voice + disposition + review stance). The JSON contract stays the same.
- Peer review stays anonymised by seat label ("Justice B: …"), and model names never appear in review payloads (keeps `test_judges_see_only_statute_claim_and_redacted_finding` valid).
- The chair prompt receives opinions labelled `"Sunny (Justice A)"` etc. Dissent fallback text uses the persona name too.
- `_fake_opinion`: move the deterministic disagreement from Justice C to **Sunny/happy** (one notch lower on `valid_abroad_void_bd` / `regime_conflict`), which fits the Happy persona. Existing test expectations hold: labour risks are still unanimous 3–0, and the pipeline still surfaces a dissent.
- `_clean(...)` also sets `persona` and `name`.

### 2. `backend/ain/models.py`
- `BenchOpinion`: add `persona: str = ""` and `name: str = ""`. The defaults keep old `runs/*.json` loading.
- New models: `CouncilMember {id, name, title, tagline, seat, model}`, `ChatTurn {speaker: "user"|member_id, text}`, `CouncilChatRequest {message (1..1000 chars), members: list[id] (1–3), risk_id: str|None, history: list[ChatTurn] (server keeps last 8)}`, `CouncilReply {member, name, model, text, citations: list[str]}`, `CouncilChatResponse {replies}`.

### 3. New `backend/ain/agents/council.py`: talking to the members
- `members(llm) -> list[CouncilMember]` resolves each role's model (`llm.resolve`, or "(offline stand-in)" in fake mode, the same pattern as `bench.py:64`).
- `async chat(llm, result: AnalysisResult, req, corpus) -> list[CouncilReply]`:
  - **Context builder:** if `risk_id` is set, use that risk (title, redacted finding, severity, clash, the member's OWN bench opinion and the ruling/dissent) plus the verified/partial ledger rows for it with section text (trimmed ~1500 chars each). Otherwise use a compact digest of all live risks (id, title, severity, verdict, bench vote) and the verified citation ids with headings. Use only `result` fields, which are already redacted.
  - **System prompt:** persona voice; "you are a member of a legal council reviewing this contract; answer in character in ≤120 words; rely ONLY on the CONTEXT; you may cite only citation_ids listed in CONTEXT; if the question needs law not in CONTEXT, say so in character; never invent section numbers; no outside legal knowledge." Returns JSON `{"reply": "...", "citations": [...]}`.
  - **Group chats:** when several members are asked, they answer in parallel (`asyncio.gather`), independently. Each sees the shared history, so later turns can reference what the others said.
  - **Citation guard:** after the call, drop any citation not among the context's ids (keeps the project's citation_id-only rule), and replace the reply text if it is empty.
  - `temperature=0.7`, `max_tokens=600`, `task="council_chat"`, `agent=f"LLM Council · {name}"`.
  - **Fake replies:** deterministic, in character, filled from the risk/ruling (e.g. Sunny: "Good news first — …", Regal: "As the text of {cite} makes plain, …", Grey: "I fear …").
- **Which mode chat runs in:** if the job is `live` or `replay` and the provider has a key, run **live** (replay would only produce canned answers for new questions). Otherwise run fake. A helper picks the mode before building the `LLM`.

### 4. `backend/ain/api.py`
- `GET /api/council` returns `list[CouncilMember]`.
- `POST /api/jobs/{job_id}/council/chat` (`CouncilChatRequest` → `CouncilChatResponse`): uses `_result_or_409`, validates member ids and `risk_id` (404/422), and catches `PIILeakError` → **422** "Your message contains personal identifiers (phone/NID/…); please remove them." The existing PII guard in `llm.json` already scans `user`. Append the call records to `result.privacy.outbound_calls` and save the run file the way `run_ablation` does (`api.py:208-210`), so the Privacy tab stays truthful.

## Frontend (Counsel mode)

### 5. `web/src/lib/api.ts`
- `BenchOpinion` gets `persona`, `name`. Add the `CouncilMember`, `ChatTurn` and `CouncilReply` types and `api.council()` / `api.councilChat(jobId, body)`, following the existing `json<T>()` helper. Surface the 422 detail text as the error.

### 6. New `web/src/components/counsel/Council.tsx`
- `PERSONA_STYLE` map: accent colour + avatar for each persona id (amber/Sunny, violet/Regal, slate-blue/Grey).
- `CouncilAvatar({persona, size})`: a small inline-SVG face (smile, raised chin with a crown, droopy brows with a rain-cloud), so it does not depend on emoji.
- `CouncilPanel({result, focus, onFocusChange})` replaces `BenchPanel`:
  1. **Members row:** three cards with the avatar, name, "the Happy AI", tagline, model, and a vote summary across benched risks ("sided with majority 3/4 · dissented on R2"). Each card has a "Talk to Sunny" button.
  2. **Rulings:** the existing per-risk bench case UI (moved from `BenchPanel`), with seat labels replaced by avatar + name. "Revised after review", the vote, the majority opinion and the dissent stay.
  3. **Chat:** target chips `[All three] [Sunny] [Regal] [Grey]`, an optional "About: All risks / R1 … Rn" select, 3 suggested prompts ("Should I sign this?", "What should I negotiate first?", "Why do you disagree with the others?"), a message list (user bubble right; member bubbles left in accent colour, with avatar and citation chips that link to `section.url` from the ledger), a typing indicator for each pending member, an input with Enter-to-send, and error text. History stays in component state, and the last 8 turns are sent.
- When there is no benched risk, the members row and chat still render (the members just have no votes yet).

### 7. Wiring
- `CounselApp.tsx`: tab `bench` → `council`, labelled "LLM Council". `Workspace` holds the `councilFocus {member?, riskId?}` state and an `openCouncil(member?, riskId?)` that switches the tab and pre-fills the chat target.
- `RiskCard.tsx`: in the `benchMini` block, show the three mini avatars with each member's severity vote (dissenter outlined) and an "Ask the council about this" button calling the new `onAskCouncil` prop.
- Toolbar: a compact 3-avatar "Council" button that opens the tab, so the members are visible without hunting for the tab.
- `counsel.module.css`: styles for members, avatars, chat bubbles, chips and typing dots, reusing the existing `--card/--line/--green/--amber/--red` tokens and adding 3 persona accent tokens. Check that the 340px side pane and the mobile single-column layout fit.
- `Panels.tsx`: remove `BenchPanel` once it has moved.
- Before writing the client code, check the Next 16 docs in `web/node_modules/next/dist/docs/` (per `web/AGENTS.md`). These are plain client components, so little should change.

### 8. Small touch-ups
- `export.py`: name the dissenting member in the memo ("Dissent (Grey, the Gloomy AI): …"); this comes for free from the dissent text.
- `eval/run_eval.py` and `scripts/smoke_live.py` need no change. Optionally make the smoke test send one council chat call when live.

## Tests (`backend/tests`, offline fake LLM)
- `test_bench.py`: keep the 3 tests, updating the seat assertion to also check `{o.persona} == {"happy","proud","gloomy"}`. Add tests that the persona paragraph is in each judge's system prompt and that the persona names do not leak model names.
- New `test_council.py`:
  - `members` returns 3 entries in order.
  - Chat to all three returns 3 replies in character (fake).
  - Chat to a single member returns 1 reply.
  - Citations not in the context are stripped (override via `RecordingLLM`).
  - The context contains only the redacted finding and selected-risk sections.
- `test_api.py`: the chat endpoint gives 200 on a finished job, 422 for a message with a phone number (PII guard), 422 for an unknown member, and 409 for an unfinished job.

## Verification
1. `cd backend && ..\.venv\Scripts\python -m pytest` — all green offline.
2. `uvicorn ain.api:app --port 8000` (from `backend/`) + `cd web && npm run dev`. Run the `rmg_epz` and `migrant_text` samples with `llm_mode=fake`, then open `/counsel/<job>`:
   - The toolbar shows the 3 avatars, and risk cards show per-member votes, including Sunny's dissent on the clash risk.
   - In the LLM Council tab, "All three" returns 3 distinct in-character replies, a single member returns 1, the risk selector changes the context, and a message containing a phone number shows the PII error.
   - The Privacy tab lists the council chat calls.
3. With keys in `.env`: run one job with `llm_mode=live` and check that the personalities read distinctly, that citations only reference ledger sections, and that `npm run lint` / `tsc` pass.
4. Use the `run` skill / Chrome to screenshot the council tab at desktop and mobile widths.
