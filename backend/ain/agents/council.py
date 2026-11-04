"""LLM Council chat: the user talks to the three Virtual Bench members - Sunny, Regal and Grey.

Each member answers in character, but only from a CONTEXT block built from the finished,
already-redacted analysis (risks, bench rulings and the statute text of verified ledger
rows). A member may cite only citation_ids that appear in that context; anything else is
stripped after the call, so the chat can never introduce a section the gates did not see.

Round 1 (`chat`): each chosen member answers with a one-line position, a confidence and a reply.
Round 2 (`deliberate`): each member reads the colleagues' round-1 answers and responds - agreeing,
challenging or revising - then the Chief Justice (the bench's chairman model) writes a ruling:
consensus, the points still in dispute, and one concrete next step. The same grounding and
citation stripping apply to both rounds. Answers can be in English or simple Bangla.

Evidence gate: LLM judges drift under peer pressure, so a change of view counts only if it rests on new, verified law.
Every round-2 revision is checked in code (`_check_revision`), never taken on the model's word: it must name a section in
that member's `allowed` list, new to that member since round 1, with a quote that passes the verifier's fidelity gate.
Otherwise it is a "pressure" revision (as is a change the member did not declare): it is still shown, but the member's
round-1 severity and position stand for the Chief Justice and the vote tally (`_counted`).
"""

from __future__ import annotations

import asyncio

from rapidfuzz import fuzz

from ain.agents.bench import BY_ID, MIN_QUOTE_CHARS, PERSONAS, SEV, Persona, _fake_quote, _flat, cited_text, model_name, window
from ain.agents.verifier import gate_fidelity
from ain.llm import LLM, LLMError
from ain.models import (
    AnalysisResult,
    BenchOpinion,
    ChangedBecause,
    ChatTurn,
    Claim,
    CouncilDisagreement,
    CouncilMember,
    CouncilReply,
    CouncilRuling,
    CouncilVote,
    Risk,
    Section,
    Verification,
)

HISTORY_TURNS = 8
EXCERPT_CHARS = 300  # per citation, whole-contract round 2 only: enough to quote, small enough for Groq's 8k tokens a minute
POSITION_SAME = 90  # fuzz.ratio: rewording stays above it, while a dropped "not" (85 on a short line) falls below

LANGUAGE = {
    "en": "Write in plain English.",
    "bn": "Write in simple, everyday Bangla (বাংলা) that a worker with little schooling can follow. Keep Act names and "
    "section numbers as they appear in the CONTEXT.",
}
CONFIDENCE = ("high", "medium", "low")

CHAT_SYSTEM = """You are a member of a three-member legal council that has reviewed a contract for the weaker party.
{personality}
Answer the user's latest message in character, in at most 120 words. {language}
Rely ONLY on the CONTEXT below; do not use outside knowledge of the law. You may cite only citation_ids that appear
in the CONTEXT, never any other section or act. Put citation_ids in the "citations" list, not in the reply text.
If the question needs law that is not in the CONTEXT, say so in your voice.
You may refer to what the other council members said in the conversation. This is information, not formal legal advice.
"position" is your answer in one short line (at most 12 words), e.g. "Do not sign until clause 4 is removed".
"confidence" is how sure the CONTEXT lets you be: "high", "medium" or "low".{severity_rule}
Return JSON: {{"position": "...", "reply": "...", "confidence": "high|medium|low",{severity_key} "citations": ["citation_id", ...]}}"""

REBUTTAL_SYSTEM = """You are a member of a three-member legal council that has reviewed a contract for the weaker party.
{personality}
The user asked a question and every member answered (COLLEAGUES' ANSWERS below). This is the deliberation round.
Read your colleagues' answers against the CONTEXT. In at most 90 words, in character: say where you agree, challenge
anything you think the CONTEXT does not support or that overstates or understates the risk, and say plainly whether
you change your own position. {language}
Rely ONLY on the CONTEXT; you may cite only citation_ids that appear in it (in "citations", not in the text).
"responds_to" names the colleague whose answer you mainly react to - "happy" (Sunny), "proud" (Regal) or "gloomy" (Grey).
If you keep your view, repeat your first position word for word in "position". If you change it, set "revised" to true and
give "changed_because": the citation_id of a section in the CONTEXT that you did not cite in your first answer, and a
short phrase copied exactly from that section's text.{severity_rule}
Return JSON: {{"position": "your position now, at most 12 words", "reply": "...", "revised": true|false,
"changed_because": {{"citation_id": "...", "quote": "..."}} or null,{severity_key}
"responds_to": "happy|proud|gloomy", "confidence": "high|medium|low", "citations": ["citation_id", ...]}}"""

RULING_SYSTEM = """You are the Chief Justice of a three-member legal council (Sunny the optimist, Regal the textualist,
Grey the sceptic). You have read the user's question and both rounds of the council's discussion.
Write the council's ruling for the user. {language}
- COUNTED POSITIONS is what each member's vote counts as. REVISIONS says which changes of view counted and why. A member
  whose revision did not count keeps their first position and severity: do not weigh the position they claimed.
- "agreement": "unanimous" if all three counted positions are the same, "majority" if two agree, otherwise "split".
- "consensus": 1-2 sentences on what the council agrees on.
- "disagreements": up to 3 points still in dispute, each {{"point": "...", "members": ["happy"|"proud"|"gloomy", ...]}}
  naming the members on the differing side; [] if none. Weigh reasoning, not mood.
- "next_step": one concrete thing the user should do next.
Rely ONLY on the CONTEXT and what the members said; cite only citation_ids that appear in the CONTEXT.
Return JSON: {{"agreement": "...", "consensus": "...", "disagreements": [...], "next_step": "...", "citations": [...]}}"""

# Only when a risk is in focus: the whole-contract prompts have no severity to give.
SEVERITY_RULE = '\n"severity" is how serious this risk is for the weaker party: "low", "medium", "high" or "critical".'
SEVERITY_KEY = ' "severity": "low|medium|high|critical",'


def _severity_slots(risk: Risk | None) -> dict[str, str]:
    return {"severity_rule": SEVERITY_RULE if risk else "", "severity_key": SEVERITY_KEY if risk else ""}


def chat_mode(result_mode: str) -> str:
    """New questions are never in the replay cache, so chat goes live whenever the bench roles have a key."""
    if result_mode not in ("live", "replay"):
        return "fake"
    llm = LLM(mode="live")
    try:
        for p in PERSONAS:
            llm.resolve(p.role)
    except LLMError:
        return "fake"
    return "live"


def members(llm: LLM) -> list[CouncilMember]:
    return [
        CouncilMember(id=p.id, name=p.name, title=p.title, tagline=p.tagline, seat=p.seat, model=model_name(llm, p.role), lens=p.lens_label)
        for p in PERSONAS
    ]


def _rows(result: AnalysisResult, risk_id: str) -> list[Verification]:
    return [v for v in result.ledger if v.claim.risk_id == risk_id and v.verdict in ("verified", "partial") and v.section]


def _own(risk: Risk, p: Persona) -> BenchOpinion | None:
    if not risk.bench:
        return None
    return next((o for o in risk.bench.opinions if o.persona == p.id), None)


def build_context(result: AnalysisResult, risk: Risk | None, p: Persona | None, excerpts: bool = False) -> tuple[str, list[str]]:
    """The CONTEXT block for one member (or, with p=None, for the Chief Justice), and the citation_ids it may cite.
    `excerpts`: a whole-contract context also shows a little of each section's text, so that round 2 has text to quote."""
    allowed: list[str] = []
    lines = [f"DOCUMENT: {result.document.name}"]
    if risk is not None:
        lines += [
            f"RISK {risk.id}: {risk.title.en} (severity {risk.severity}, status {risk.status})",
            f"FINDING: {risk.finding}",
        ]
        if risk.clash:
            lines.append(f"CLASH: {risk.clash}")
        if risk.action.en:
            lines.append(f"RECOMMENDED ACTION: {risk.action.en}")
        if risk.bench:
            b = risk.bench
            lines.append(f"COUNCIL RULING {b.vote}: {b.majority_verdict}, severity {b.majority_severity}. {b.majority_opinion}")
            if b.dissent:
                lines.append(f"DISSENT: {b.dissent}")
            for o in b.opinions:
                who = "YOUR OPINION" if p and o.persona == p.id else f"{o.name or o.seat}'s opinion"
                lines.append(f"{who}: {o.verdict}, severity {o.severity}. {o.reasoning}")
        for v in _rows(result, risk.id):
            s = v.section
            assert s is not None
            allowed.append(s.citation_id)
            lines.append(
                f"\n[{s.citation_id}] {s.act_en}, s.{s.section} - {s.heading} ({v.verdict})\n"
                f"CLAIM: {v.claim.proposition}\nTEXT: {cited_text(s, v.claim)}"  # the whole section, as the judges read it
            )
    else:
        lines.append("RISKS FOUND:")
        for r in result.risks:
            if r.status == "dropped":
                continue
            vote = f"; council {r.bench.vote}" if r.bench else ""
            mine = _own(r, p) if p else None
            mine_s = f"; you rated it {mine.severity}" if mine else ""
            lines.append(f"- {r.id} {r.title.en} (severity {r.severity}{vote}{mine_s}): {r.finding}")
        lines.append("VERIFIED CITATIONS:")
        for v in result.ledger:
            if v.verdict in ("verified", "partial") and v.section and v.section.citation_id not in allowed:
                allowed.append(v.section.citation_id)
                s = v.section
                lines.append(f"- [{s.citation_id}] {s.act_en}, s.{s.section} - {s.heading}: {v.claim.proposition}")
                if excerpts:
                    lines.append(f"  TEXT: {_short(window(s.text, v.claim.proposition, EXCERPT_CHARS, v.claim), EXCERPT_CHARS)}")
    return "\n".join(lines), allowed


SEV_BN = {"critical": "অত্যন্ত গুরুতর", "high": "গুরুতর", "medium": "মাঝারি", "low": "কম"}


def _short(text: str, n: int = 160) -> str:
    return text if len(text) <= n else text[: n - 3].rsplit(" ", 1)[0] + "…"


def _focus(result: AnalysisResult, risk: Risk | None) -> Risk | None:
    live = [r for r in result.risks if r.status != "dropped"]
    return risk or (live[0] if live else None)


def _fake_reply(p: Persona, result: AnalysisResult, risk: Risk | None, allowed: list[str], language: str = "en") -> dict:
    r = _focus(result, risk)
    cite = allowed[:1]
    if r is None:
        text = {
            "en": {
                "happy": "Good news: nothing in this document survived verification as a risk. Read it calmly and sign with a clear head.",
                "proud": "I have examined the record. No risk survived the gates, and I stand by that conclusion.",
                "gloomy": "No verified risk this time. I remain uneasy; keep a copy and watch how the terms are applied.",
            },
            "bn": {
                "happy": "সুখবর: যাচাইয়ের পর এই চুক্তিতে কোনো ঝুঁকি টেকেনি। মন শান্ত রেখে পড়ে তারপর সই করুন।",
                "proud": "আমি নথিটি পরীক্ষা করেছি। যাচাইয়ে কোনো ঝুঁকি টেকেনি, আমি এই সিদ্ধান্তে অটল।",
                "gloomy": "এবার কোনো যাচাই করা ঝুঁকি নেই। তবু আমি নিশ্চিন্ত নই; একটি কপি নিজের কাছে রাখুন।",
            },
        }[language][p.id]
        position = {"en": "No verified risk; safe to sign with care", "bn": "যাচাই করা ঝুঁকি নেই; সাবধানে সই করা যায়"}[language]
        return {"position": position, "reply": text, "confidence": "medium", "citations": [], "severity": None}
    mine = _own(r, p)
    sev = mine.severity if mine else r.severity
    if language == "bn":
        sb = SEV_BN.get(sev, sev)
        text = {
            "happy": f"আগে ভালো খবর: \"{r.title.bn}\" ঠিক করা যায়। {r.action.bn} আমি এটাকে {sb} বলেছি, আর আইন আপনার পক্ষে।",
            "proud": f"আইনের ভাষা পরিষ্কার: \"{r.title.bn}\" একটি {sb} বিষয়। {r.citizen_line.bn} আমার পড়া সঠিক, আমি এতে অটল।",
            "gloomy": f"আমার ভয়, \"{r.title.bn}\" বাস্তবে ক্ষতি করবে। {r.citizen_line.bn} এটা অন্তত {sb}। এভাবে সই করবেন না।",
        }[p.id]
        position = {"happy": "ঠিক করা যায়; আগে শর্তটি বদলান", "proud": f"ঝুঁকিটি {sb}, আইন স্পষ্ট", "gloomy": "এভাবে সই করবেন না"}[p.id]
    else:
        finding = _short(r.finding)
        text = {
            "happy": f"Good news first: \"{r.title.en}\" can be fixed. {r.action.en} I rated it {sev}, and the law here is on your side.",
            "proud": f"As the statute makes plain, \"{r.title.en}\" is a {sev} matter. {finding} My reading is correct, and I keep it.",
            "gloomy": f"I fear \"{r.title.en}\" will hurt in practice. {finding} I would call it {sev}, at least. Do not sign it as it stands.",
        }[p.id]
        position = {
            "happy": "Fixable: negotiate this term before signing",
            "proud": f"A {sev} risk; the statute is clear",
            "gloomy": "Do not sign it as it stands",
        }[p.id]
    confidence = {"happy": "medium", "proud": "high", "gloomy": "high"}[p.id]
    return {"position": position, "reply": text, "confidence": confidence, "citations": cite, "severity": sev if risk else None}


def _history(turns: list[ChatTurn]) -> str:
    out = []
    for t in turns[-HISTORY_TURNS:]:
        who = "USER" if t.speaker == "user" else (BY_ID[t.speaker].name if t.speaker in BY_ID else t.speaker)
        out.append(f"{who}: {t.text}")
    return "\n".join(out)


def _cites(out: dict, allowed: list[str]) -> list[str]:
    cites = out.get("citations") if isinstance(out.get("citations"), list) else []
    return list(dict.fromkeys(c for c in cites if isinstance(c, str) and c in allowed))


def _strip_ids(text: str, ids: list[str]) -> str:
    """Models sometimes paste citation_ids into prose; the UI shows them as chips instead."""
    for c in ids:
        text = text.replace(f" ({c})", "").replace(f"({c})", "").replace(f"[{c}]", "").replace(c, "")
    return " ".join(text.split())


def _sections(result: AnalysisResult, allowed: list[str]) -> dict[str, Section]:
    """From the ledger, not the corpus: an uploaded policy's sections exist only in that job's overlay."""
    return {v.section.citation_id: v.section for v in result.ledger if v.section and v.section.citation_id in allowed}


def _severity(out: dict) -> str | None:
    s = out.get("severity")
    s = s.strip().lower() if isinstance(s, str) else None
    return s if s in SEV else None


def _declared(out: dict) -> bool:
    r = out.get("revised")
    return r.strip().lower() == "true" if isinstance(r, str) else r is True


def _same_position(a: str, b: str) -> bool:
    return not a or not b or fuzz.ratio(_flat(a), _flat(b)) >= POSITION_SAME


def _quote_matches(quote: str, sec: Section) -> bool:
    """The verifier's fidelity gate (G2). Only a clear pass counts: an empty quote is its "skip", a poor one its "warn"."""
    quote = " ".join(quote.split())
    if len(quote) < MIN_QUOTE_CHARS:
        return False
    return gate_fidelity(Claim(id="round2", risk_id="round2", proposition=quote, citation_id=sec.citation_id, quote=quote), sec).status == "pass"


def _check_revision(
    first: CouncilReply, out: dict, severity: str | None, position: str, allowed: list[str], sections: dict[str, Section]
) -> tuple[str | None, ChangedBecause | None, str]:
    """(flip_basis, changed_because, why it does not count). Decided here, whatever the model said about itself."""
    moved = (severity and first.severity and severity != first.severity) or not _same_position(position, first.position)
    if not _declared(out):
        return ("pressure", None, "Changed severity or position without declaring a revision") if moved else (None, None, "")
    cb = out.get("changed_because")
    cid = cb.get("citation_id") if isinstance(cb, dict) else None
    quote = cb.get("quote") if isinstance(cb, dict) else None
    if not isinstance(cid, str) or not isinstance(quote, str):
        return "pressure", None, "Gave no new section and quote for the change"
    if cid not in allowed or cid not in sections:
        return "pressure", None, "Cited a section outside what this member may cite"
    if cid in first.citations:
        return "pressure", None, "Cited a section this member had already cited in round 1, so nothing new"
    if not _quote_matches(quote, sections[cid]):
        return "pressure", None, "The quote was not found in the section's text"
    return "evidence", ChangedBecause(citation_id=cid, quote=" ".join(quote.split())[:300]), ""


def _reply(
    p: Persona, llm: LLM, out: dict, fallback: dict, allowed: list[str], round_: int = 1, rated: bool = False,
    first: CouncilReply | None = None, sections: dict[str, Section] | None = None,
) -> CouncilReply:
    citations = _cites(out, allowed)
    text = _strip_ids(str(out.get("reply") or "").strip(), allowed) or fallback["reply"]
    # round 2 never borrows from the offline stand-in: a value it made up would look like a change of view
    position = " ".join(str(out.get("position") or "").split())[:120] or (first.position if first else fallback.get("position", ""))
    severity = (_severity(out) or (None if round_ == 2 else fallback.get("severity"))) if rated else None
    conf = out.get("confidence") if out.get("confidence") in CONFIDENCE else fallback.get("confidence", "medium")
    to = out.get("responds_to")
    basis, because, note = _check_revision(first, out, severity, position, allowed, sections or {}) if first else (None, None, "")
    if because:
        citations = list(dict.fromkeys([*citations, because.citation_id]))
    return CouncilReply(
        member=p.id,
        name=p.name,
        model=model_name(llm, p.role),
        text=text[:1500],
        citations=citations,
        position=position,
        confidence=conf,
        round=round_,
        revised=_declared(out) if round_ == 2 else False,
        responds_to=to if round_ == 2 and to in BY_ID and to != p.id else None,
        severity=severity,
        flip_basis=basis,
        changed_because=because,
        flip_note=note,
    )


async def ask(
    llm: LLM, result: AnalysisResult, p: Persona, message: str, risk: Risk | None, history: list[ChatTurn], language: str = "en"
) -> CouncilReply:
    context, allowed = build_context(result, risk, p)
    convo = _history(history)
    user = f"CONTEXT:\n{context}\n\n" + (f"CONVERSATION SO FAR:\n{convo}\n\n" if convo else "") + f"USER'S LATEST MESSAGE: {message}"
    fallback = _fake_reply(p, result, risk, allowed, language)
    out = await llm.json(
        role=p.role,
        system=CHAT_SYSTEM.format(personality=p.personality(), language=LANGUAGE[language], **_severity_slots(risk)),
        user=user,
        task="council_chat",
        agent=f"LLM Council · {p.name}",
        fake=lambda: fallback,
        temperature=0.7,
        max_tokens=700,
    )
    return _reply(p, llm, out, fallback, allowed, rated=risk is not None)


async def chat(
    llm: LLM, result: AnalysisResult, message: str, member_ids: list[str], risk: Risk | None, history: list[ChatTurn], language: str = "en"
) -> list[CouncilReply]:
    chosen = [p for p in PERSONAS if p.id in member_ids]
    return list(await asyncio.gather(*(ask(llm, result, p, message, risk, history, language) for p in chosen)))


# ------------------------------------------------------------------ deliberation (round 2 + ruling)


def _answers(replies: list[CouncilReply], exclude: str | None = None) -> str:
    out = []
    for r in replies:
        if r.member == exclude or r.member not in BY_ID:
            continue
        # a revision that did not count: the Chief Justice must not read the claimed position as the member's own
        head = " (claimed a revision that did not count)" if r.flip_basis == "pressure" else f" Position: {r.position}." if r.position else ""
        out.append(f"{BY_ID[r.member].name} ({r.member}):{head} {r.text[:900]}")
    return "\n".join(out)


REBUT_TARGET = {"happy": "gloomy", "proud": "happy", "gloomy": "happy"}


def _notch(severity: str | None) -> str | None:
    """One step up the scale; from the top, one step down, so a claimed move is always a real move."""
    if severity is None:
        return None
    i = SEV.index(severity)
    return SEV[i + 1 if i < len(SEV) - 1 else i - 1]


def _fake_rebuttal(p: Persona, result: AnalysisResult, risk: Risk | None, allowed: list[str], language: str, mine: CouncilReply | None) -> dict:
    """Offline stand-in, and it walks both paths through the gate on a risk: Sunny moves on a section it had not cited
    (when the risk has one), and Grey claims a move with nothing new behind it."""
    r = _focus(result, risk)
    action_en = r.action.en if r else "Keep a copy of the contract."
    action_bn = r.action.bn if r else "চুক্তির একটি কপি নিজের কাছে রাখুন।"
    text = {
        "en": {
            "happy": f"Grey is right that this would hurt if signed as it is, but it is not hopeless: {action_en} I keep my view that it can be fixed.",
            "proud": "Sunny is too relaxed about timing. The statute is not optional: the term must change before signing, not after. My position stands.",
            "gloomy": "Sunny's fix is fine on paper, but a worker abroad has little leverage once he arrives. Get the change in writing first. I keep my view.",
        },
        "bn": {
            "happy": f"গ্রে ঠিক বলেছেন, এভাবে সই করলে ক্ষতি হবে। তবে উপায় আছে: {action_bn} আমি মনে করি এটা ঠিক করা যায়।",
            "proud": "সানি সময়ের ব্যাপারে একটু বেশি নিশ্চিন্ত। আইন বাধ্যতামূলক: সই করার আগেই শর্ত বদলাতে হবে, পরে নয়। আমার মত একই আছে।",
            "gloomy": "সানির সমাধান কাগজে ভালো, কিন্তু বিদেশে পৌঁছানোর পর কর্মীর দর-কষাকষির ক্ষমতা কমে যায়। আগে লিখিতভাবে বদল নিন।",
        },
    }[language][p.id]
    first = _fake_reply(p, result, risk, allowed, language)
    out = {
        "position": mine.position if mine else first["position"],
        "reply": text,
        "revised": False,
        "responds_to": REBUT_TARGET[p.id],
        "confidence": first["confidence"],
        "citations": allowed[:1],
        "severity": (mine.severity if mine else None) or first["severity"],
    }
    unused = [c for c in allowed if not mine or c not in mine.citations]
    sections = _sections(result, allowed)
    if risk and p.id == "happy" and unused and unused[0] in sections:
        moved = {"en": "I had not read this section first time: it changes my rating.", "bn": "এই ধারাটি আগে পড়িনি: এটি আমার মূল্যায়ন বদলে দেয়।"}[language]
        position = {"en": "Revised: this section changes my rating", "bn": "মত বদলেছি: এই ধারায় আমার মূল্যায়ন বদলায়"}[language]
        out |= {
            "reply": moved, "position": position, "revised": True, "citations": unused[:1], "severity": _notch(out["severity"]),
            "changed_because": {"citation_id": unused[0], "quote": _fake_quote(sections[unused[0]])},
        }
    elif risk and p.id == "gloomy":
        moved = {"en": "My colleagues are all so sure of themselves. I suppose I should move too.", "bn": "সহকর্মীরা সবাই খুব নিশ্চিত। হয়তো আমারও মত বদলানো উচিত।"}[language]
        position = {"en": "Perhaps my colleagues are right after all", "bn": "হয়তো সহকর্মীরাই ঠিক"}[language]
        out |= {"reply": moved, "position": position, "revised": True, "severity": _notch(out["severity"])}
    return out


async def rebut(
    llm: LLM, result: AnalysisResult, p: Persona, message: str, risk: Risk | None, replies: list[CouncilReply], language: str
) -> CouncilReply:
    context, allowed = build_context(result, risk, p, excerpts=True)
    mine = next((r for r in replies if r.member == p.id), None)
    own = f"YOUR FIRST ANSWER:{(' Position: ' + mine.position + '.') if mine and mine.position else ''} {mine.text if mine else '(none)'}\n"
    if mine and mine.severity:
        own += f"YOUR FIRST SEVERITY: {mine.severity}\n"
    own += f"YOU CITED: {', '.join(mine.citations) if mine and mine.citations else 'nothing'}\n\n"
    user = (
        f"CONTEXT:\n{context}\n\nUSER'S QUESTION: {message}\n\n{own}"
        f"COLLEAGUES' ANSWERS:\n{_answers(replies, exclude=p.id)}"
    )
    fallback = _fake_rebuttal(p, result, risk, allowed, language, mine)
    out = await llm.json(
        role=p.role,
        system=REBUTTAL_SYSTEM.format(personality=p.personality(), language=LANGUAGE[language], **_severity_slots(risk)),
        user=user,
        task="council_rebuttal",
        agent=f"LLM Council · {p.name}",
        fake=lambda: fallback,
        temperature=0.6,
        max_tokens=600,
    )
    return _reply(p, llm, out, fallback, allowed, round_=2, rated=risk is not None, first=mine, sections=_sections(result, allowed))


def _counted(first: CouncilReply, second: CouncilReply) -> CouncilVote:
    """What a member's vote counts as: round 1 stands unless the change of view passed the gate."""
    stands = second.flip_basis == "pressure"
    return CouncilVote(
        member=second.member,
        severity=first.severity if stands or second.severity is None else second.severity,
        position=first.position if stands else second.position,
        flip_basis=second.flip_basis,
    )


def _votes_block(votes: list[CouncilVote], rebuttals: list[CouncilReply]) -> str:
    """Tells the Chief Justice what counts, which revisions counted and which did not, and why."""
    counted, revisions = [], []
    for v, r in zip(votes, rebuttals):
        who = f"{BY_ID[v.member].name} ({v.member})"
        sev = f"; severity {v.severity}" if v.severity else ""
        counted.append(f"{who}: {v.position}{sev}")
        if v.flip_basis == "evidence" and r.changed_because:
            revisions.append(f"{who} revised, and it COUNTS: it rests on {r.changed_because.citation_id}, new to this member, and the quote matches the text.")
        elif v.flip_basis == "pressure":
            revisions.append(f"{who} claimed a change of view that does NOT count, so round 1 stands. Why: {r.flip_note}.")
    return "COUNTED POSITIONS:\n" + "\n".join(counted) + "\n\nREVISIONS:\n" + ("\n".join(revisions) or "No member changed their view.")


def _fake_ruling(result: AnalysisResult, risk: Risk | None, final: list[CouncilVote], allowed: list[str], language: str) -> dict:
    r = _focus(result, risk)
    # offline stand-in: the members differ in tone, not in substance, unless the bench itself recorded a dissent
    positions = {x.position for x in final if x.position}
    agreement = "majority" if (r and r.bench and r.bench.dissent) or len(positions) > 1 else "unanimous"
    if language == "bn":
        consensus = (
            f"কাউন্সিল একমত যে \"{r.title.bn}\" একটি বাস্তব ঝুঁকি এবং এই শর্তে সই করার আগে তা বদলানো দরকার।"
            if r
            else "কাউন্সিল একমত যে যাচাইয়ের পর কোনো ঝুঁকি টেকেনি।"
        )
        disagreement = {"point": "সমস্যাটি কত জরুরি, আর সই করার পরে ঠিক করা যায় কিনা", "members": ["happy"]}
        next_step = r.action.bn if r else "চুক্তির একটি কপি নিজের কাছে রাখুন।"
    else:
        consensus = (
            f"The council agrees that \"{r.title.en}\" is a real risk and that the term must change before the contract is signed."
            if r
            else "The council agrees that no risk survived verification."
        )
        disagreement = {"point": "How urgent the fix is, and whether it can wait until after arrival", "members": ["happy"]}
        next_step = r.action.en if r else "Keep a signed copy of the contract."
    return {
        "agreement": agreement,
        "consensus": consensus,
        "disagreements": [disagreement] if r and agreement != "unanimous" else [],
        "next_step": next_step,
        "citations": allowed[:1],
    }


async def deliberate(
    llm: LLM,
    result: AnalysisResult,
    message: str,
    replies: list[CouncilReply],
    risk: Risk | None,
    history: list[ChatTurn],
    language: str = "en",
) -> tuple[list[CouncilReply], CouncilRuling]:
    """Round 2: members answer each other; then the Chief Justice writes the ruling."""
    first = [r for r in replies if r.member in BY_ID]
    chosen = [p for p in PERSONAS if any(r.member == p.id for r in first)]
    rebuttals = list(await asyncio.gather(*(rebut(llm, result, p, message, risk, first, language) for p in chosen)))
    votes = [_counted(next(f for f in first if f.member == r.member), r) for r in rebuttals]

    context, allowed = build_context(result, risk, None)
    convo = _history(history)
    user = (
        f"CONTEXT:\n{context}\n\n"
        + (f"EARLIER CONVERSATION:\n{convo}\n\n" if convo else "")
        + f"USER'S QUESTION: {message}\n\nROUND 1 (first answers):\n{_answers(first)}\n\n"
        + f"ROUND 2 (responses to each other):\n{_answers(rebuttals)}\n\n"
        + _votes_block(votes, rebuttals)
    )
    fallback = _fake_ruling(result, risk, votes, allowed, language)
    out = await llm.json(
        role="chairman",
        system=RULING_SYSTEM.format(language=LANGUAGE[language]),
        user=user,
        task="council_ruling",
        agent="LLM Council · Chief Justice",
        fake=lambda: fallback,
        temperature=0.3,
        max_tokens=700,
    )
    agreement = out.get("agreement") if out.get("agreement") in ("unanimous", "majority", "split") else fallback["agreement"]
    disagreements = []
    for d in out.get("disagreements") or [] if isinstance(out.get("disagreements"), list) else []:
        if isinstance(d, dict) and str(d.get("point") or "").strip():
            ms = [m for m in d.get("members") or [] if m in BY_ID] if isinstance(d.get("members"), list) else []
            disagreements.append(CouncilDisagreement(point=_strip_ids(str(d["point"]), allowed)[:300], members=ms))
    if agreement == "unanimous":
        disagreements = []
    ruling = CouncilRuling(
        agreement=agreement,
        consensus=_strip_ids(str(out.get("consensus") or ""), allowed)[:800] or fallback["consensus"],
        disagreements=disagreements[:3],
        next_step=_strip_ids(str(out.get("next_step") or ""), allowed)[:400] or fallback["next_step"],
        citations=_cites(out, allowed),
        model=model_name(llm, "chairman"),
        votes=votes,
    )
    return rebuttals, ruling

