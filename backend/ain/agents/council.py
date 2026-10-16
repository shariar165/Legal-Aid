"""LLM Council chat: the user talks to the three Virtual Bench members - Sunny, Regal and Grey.

Each member answers in character, but only from a CONTEXT block built from the finished,
already-redacted analysis (risks, bench rulings and the statute text of verified ledger
rows). A member may cite only citation_ids that appear in that context; anything else is
stripped after the call, so the chat can never introduce a section the gates did not see.
"""

from __future__ import annotations

import asyncio

from ain.agents.bench import BY_ID, PERSONAS, Persona, model_name
from ain.llm import LLM, LLMError
from ain.models import AnalysisResult, BenchOpinion, ChatTurn, CouncilMember, CouncilReply, Risk, Verification

HISTORY_TURNS = 8
SECTION_CHARS = 1500

CHAT_SYSTEM = """You are a member of a three-member legal council that has reviewed a contract for the weaker party.
{personality}
Answer the user's latest message in character, in at most 120 words of plain English.
Rely ONLY on the CONTEXT below; do not use outside knowledge of the law. You may cite only citation_ids that appear
in the CONTEXT, never any other section or act. If the question needs law that is not in the CONTEXT, say so in your voice.
You may refer to what the other council members said in the conversation. This is information, not formal legal advice.
Return JSON: {{"reply": "...", "citations": ["citation_id", ...]}}"""


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
        CouncilMember(id=p.id, name=p.name, title=p.title, tagline=p.tagline, seat=p.seat, model=model_name(llm, p.role))
        for p in PERSONAS
    ]


def _rows(result: AnalysisResult, risk_id: str) -> list[Verification]:
    return [v for v in result.ledger if v.claim.risk_id == risk_id and v.verdict in ("verified", "partial") and v.section]


def _own(risk: Risk, p: Persona) -> BenchOpinion | None:
    if not risk.bench:
        return None
    return next((o for o in risk.bench.opinions if o.persona == p.id), None)


def build_context(result: AnalysisResult, risk: Risk | None, p: Persona) -> tuple[str, list[str]]:
    """The CONTEXT block for one member, and the citation_ids it may cite."""
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
                who = "YOUR OPINION" if o.persona == p.id else f"{o.name or o.seat}'s opinion"
                lines.append(f"{who}: {o.verdict}, severity {o.severity}. {o.reasoning}")
        for v in _rows(result, risk.id):
            s = v.section
            assert s is not None
            allowed.append(s.citation_id)
            lines.append(
                f"\n[{s.citation_id}] {s.act_en}, s.{s.section} - {s.heading} ({v.verdict})\n"
                f"CLAIM: {v.claim.proposition}\nTEXT: {s.text[:SECTION_CHARS]}"
            )
    else:
        lines.append("RISKS FOUND:")
        for r in result.risks:
            if r.status == "dropped":
                continue
            vote = f"; council {r.bench.vote}" if r.bench else ""
            mine = _own(r, p)
            mine_s = f"; you rated it {mine.severity}" if mine else ""
            lines.append(f"- {r.id} {r.title.en} (severity {r.severity}{vote}{mine_s}): {r.finding}")
        lines.append("VERIFIED CITATIONS:")
        for v in result.ledger:
            if v.verdict in ("verified", "partial") and v.section and v.section.citation_id not in allowed:
                allowed.append(v.section.citation_id)
                s = v.section
                lines.append(f"- [{s.citation_id}] {s.act_en}, s.{s.section} - {s.heading}: {v.claim.proposition}")
    return "\n".join(lines), allowed


def _fake_reply(p: Persona, result: AnalysisResult, risk: Risk | None, allowed: list[str]) -> dict:
    live = [r for r in result.risks if r.status != "dropped"]
    r = risk or (live[0] if live else None)
    cite = allowed[:1]
    if r is None:
        text = {
            "happy": "Good news: nothing in this document survived verification as a risk. Read it calmly and sign with a clear head.",
            "proud": "I have examined the record. No risk survived the gates, and I stand by that conclusion.",
            "gloomy": "No verified risk this time. I remain uneasy; keep a copy and watch how the terms are applied.",
        }[p.id]
        return {"reply": text, "citations": []}
    mine = _own(r, p)
    sev = mine.severity if mine else r.severity
    ref = f" ({cite[0]})" if cite else ""
    finding = r.finding if len(r.finding) <= 160 else r.finding[:157].rsplit(" ", 1)[0] + "…"
    text = {
        "happy": f"Good news first: \"{r.title.en}\" can be fixed. {r.action.en} I rated it {sev}, and the law here{ref} is on your side.",
        "proud": f"As the text{ref} makes plain, \"{r.title.en}\" is a {sev} matter. {finding} My reading is correct, and I keep it.",
        "gloomy": f"I fear \"{r.title.en}\" will hurt in practice. {finding} I would call it {sev}, at least. Do not sign it as it stands.",
    }[p.id]
    return {"reply": text, "citations": cite}


def _history(turns: list[ChatTurn]) -> str:
    out = []
    for t in turns[-HISTORY_TURNS:]:
        who = "USER" if t.speaker == "user" else (BY_ID[t.speaker].name if t.speaker in BY_ID else t.speaker)
        out.append(f"{who}: {t.text}")
    return "\n".join(out)


async def ask(llm: LLM, result: AnalysisResult, p: Persona, message: str, risk: Risk | None, history: list[ChatTurn]) -> CouncilReply:
    context, allowed = build_context(result, risk, p)
    convo = _history(history)
    user = f"CONTEXT:\n{context}\n\n" + (f"CONVERSATION SO FAR:\n{convo}\n\n" if convo else "") + f"USER'S LATEST MESSAGE: {message}"
    out = await llm.json(
        role=p.role,
        system=CHAT_SYSTEM.format(personality=p.personality()),
        user=user,
        task="council_chat",
        agent=f"LLM Council · {p.name}",
        fake=lambda: _fake_reply(p, result, risk, allowed),
        temperature=0.7,
        max_tokens=600,
    )
    cites = out.get("citations") if isinstance(out.get("citations"), list) else []
    citations = list(dict.fromkeys(c for c in cites if isinstance(c, str) and c in allowed))
    text = str(out.get("reply") or "").strip() or _fake_reply(p, result, risk, allowed)["reply"]
    return CouncilReply(member=p.id, name=p.name, model=model_name(llm, p.role), text=text[:1500], citations=citations)


async def chat(llm: LLM, result: AnalysisResult, message: str, member_ids: list[str], risk: Risk | None, history: list[ChatTurn]) -> list[CouncilReply]:
    chosen = [p for p in PERSONAS if p.id in member_ids]
    return list(await asyncio.gather(*(ask(llm, result, p, message, risk, history) for p in chosen)))

