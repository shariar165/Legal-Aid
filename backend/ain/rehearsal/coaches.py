"""The three coaches: the Virtual Bench seats with their lenses, one short hint each per worker turn.

Grounding follows the LLM Council (agents/council.py): each coach sees a CONTEXT block and may cite only the
citation_ids in it, and anything else is stripped. The allowed list for a turn is the tactic's curated `law` anchors
plus a few in-force sections retrieved for the tactic, as `council.extra_sections` retrieves them.

Regal states law, so his hint passes an evidence gate in code, never on the model's word: the one citation must be in
the allowed list (existence and applicability), its quote must match the section text (fidelity, the verifier's
threshold), the section must be in force (currency), and the judge must find that the section supports what Regal says
(entailment, `verifier.gate_entailment`). A hint that fails any gate loses its citation and says only that there is no
verified law on the point.
"""

from __future__ import annotations

import asyncio

from ain.agents.bench import BY_ID, model_name, window
from ain.agents.council import _cites, _quote_matches, _short, _strip_ids
from ain.agents.verifier import gate_currency, gate_entailment
from ain.llm import LLM
from ain.models import Claim, CoachHint, GateResult, RehearsalSetup, RehearsalTurn, Section
from ain.rehearsal import guard
from ain.rehearsal.tactics import Tactic
from ain.retrieval import get_corpus

HINT_CHARS = 220
SAY_CHARS = 160
SECTION_CHARS = 700
EXTRA_SECTIONS = 3
NO_LAW = {"bn": "এ বিষয়ে যাচাই করা আইন আমার কাছে নেই।", "en": "I have no verified law on this point."}

LENS = {
    "happy": "what the worker should ask for next, and one polite sentence they can say to the dalal",
    "proud": "what the law in the CONTEXT actually says about the dalal's line, read strictly",
    "gloomy": "the red flag in the dalal's line, and how lines like it are used to exploit workers, as the SOURCE describes",
}
FORMAT = {
    "happy": '{"text": "your hint", "say": "one polite sentence the worker can say, in the worker\'s voice", "citations": []}',
    "proud": '{"text": "your hint", "citation_id": "one citation_id from the CONTEXT", "quote": "a short phrase copied exactly from that section\'s TEXT"}',
    "gloomy": '{"text": "your hint", "citations": []}',
}
LANGUAGE = {
    "bn": "Write in simple, everyday Bangla (বাংলা) that a worker with little schooling can follow.",
    "en": "Write in plain, simple English.",
}

COACH_SYSTEM = """You are {name}, {title}, coaching a Bangladeshi worker who is practising a conversation with a recruiting
middleman (a "dalal") before paying anything. This is a training role-play.
Your lens: {lens}. Voice: {voice}
Give ONE short hint (at most 30 words). {language}
Rely ONLY on the CONTEXT; do not use outside knowledge of the law. Cite only citation_ids that appear in the CONTEXT,
and never write a citation_id or a section number in the hint text. Use no figures except ones in the CONTEXT's
section text or in the worker's own words. This is information, not legal advice.
Return JSON: {fmt}"""


def allowed_sections(tactic: Tactic, dalal_line: str, packs: set[str]) -> dict[str, Section]:
    """The tactic's own anchors, then up to EXTRA_SECTIONS in-force sections the retriever finds for it."""
    corpus = get_corpus()
    out: dict[str, Section] = {}
    for a in tactic.law:
        s = corpus.get(a.citation_id)
        if s and gate_currency(s).status != "fail":
            out[s.citation_id] = s
    query = f"{tactic.label.en} {tactic.label.bn} {dalal_line}"
    for s, _ in corpus.search(query, packs, EXTRA_SECTIONS * 3, False):
        if len(out) >= len(tactic.law) + EXTRA_SECTIONS:
            break
        if s.citation_id not in out and gate_currency(s).status != "fail":
            out[s.citation_id] = s
    return out


def _context(tactic: Tactic, turn: RehearsalTurn, sections: dict[str, Section], member: str) -> str:
    lines = [f"DALAL'S TACTIC: {tactic.label.en} ({tactic.label.bn})", f"DALAL SAID: {turn.dalal_line}"]
    lines.append(f"WORKER REPLIED: {turn.worker_reply or '(no reply yet)'}")
    if turn.action == "paid":
        lines.append("THE WORKER PRESSED: I paid the money.")
    elif turn.action == "gave_passport":
        lines.append("THE WORKER PRESSED: I handed over my passport.")
    if member == "gloomy":
        for src in tactic.sources:
            lines.append(f"SOURCE ({src['publisher']}, {src['year']}): {src['supports']}")
    lines.append("LAW YOU MAY CITE:")
    for s in sections.values():
        lines.append(f"[{s.citation_id}] {s.act_en}, s.{s.section} - {s.heading}\nTEXT: {_short(window(s.text, tactic.label.en, SECTION_CHARS), SECTION_CHARS)}")
    return "\n".join(lines)


def _fallback(tactic: Tactic, member: str) -> dict:
    if member == "happy":
        return {"text": tactic.sunny_ask_bn, "say": tactic.sunny_say_bn, "citations": []}
    if member == "proud":
        a = tactic.law[0] if tactic.law else None
        return {"text": tactic.regal_bn, "citation_id": a.citation_id, "quote": a.quote} if a else {"text": NO_LAW["bn"], "citation_id": None, "quote": None}
    return {"text": tactic.grey_flag_bn, "citations": []}


async def regal_gate(llm: LLM, text: str, cid: object, quote: object, sections: dict[str, Section], worker_words: str) -> tuple[list[GateResult], str]:
    """(gates, why the citation is dropped or ''). The four verifier gates, decided here."""
    if not isinstance(cid, str) or cid not in sections:
        return [GateResult(gate="existence", status="fail", detail="Cited a section outside the law shown for this turn.")], "existence"
    sec = sections[cid]
    gates = [GateResult(gate="existence", status="pass", detail=f"{sec.act_en} s.{sec.section} is in the allowed list for this turn.")]
    if not isinstance(quote, str) or not _quote_matches(quote, sec.text):
        gates.append(GateResult(gate="fidelity", status="fail", detail="The quote was not found in the section's text."))
        return gates, "fidelity"
    gates.append(GateResult(gate="fidelity", status="pass", detail="The quote matches the official text."))
    currency = gate_currency(sec)
    if currency.status == "fail":
        return [*gates, currency], "currency"
    if guard.unsourced_numbers(text, sec.text, worker_words):
        return [*gates, GateResult(gate="entailment", status="fail", detail="The hint gives a figure that is not in the section.")], "entailment"
    claim = Claim(id="rehearsal-regal", risk_id="rehearsal", proposition=text, citation_id=cid, quote=" ".join(quote.split()))
    entail = await gate_entailment(llm, claim, sec)
    gates += [entail, currency]
    return gates, "" if entail.status == "pass" else "entailment"


async def coach(llm: LLM, member: str, tactic: Tactic, turn: RehearsalTurn, sections: dict[str, Section], setup: RehearsalSetup) -> CoachHint:
    p = BY_ID[member]
    lang = setup.language
    out = await llm.json(
        role=p.role,
        system=COACH_SYSTEM.format(name=p.name, title=p.title, lens=LENS[member], voice=p.voice, language=LANGUAGE[lang], fmt=FORMAT[member]),
        user=f"CONTEXT:\n{_context(tactic, turn, sections, member)}",
        task="rehearsal_coach",
        agent=f"Rehearsal · {p.name}",
        fake=lambda: _fallback(tactic, member),
        temperature=0.5,
        max_tokens=400,
    )
    allowed = list(sections)
    worker_words = " ".join([turn.worker_reply, setup.promises.salary, setup.promises.total_cost, setup.promises.paid_so_far, setup.promises.duration])
    text = _short(_strip_ids(str(out.get("text") or "").strip(), allowed), HINT_CHARS)
    hint = CoachHint(member=member, name=p.name, lens=p.lens_label, text=text)
    if member == "proud":
        gates, dropped = await regal_gate(llm, text, out.get("citation_id"), out.get("quote"), sections, worker_words)
        hint.gates = gates
        if dropped or not text:
            hint.text, hint.citations, hint.dropped = NO_LAW[lang], [], dropped or "empty"
        else:
            hint.citations = [str(out["citation_id"])]
        return hint
    fallback = _fallback(tactic, member)
    if not text or guard.unsourced_numbers(text, worker_words, *(s.text for s in sections.values())):
        hint.text, hint.dropped = fallback["text"], "model hint unusable" if not text else "gave a figure with no source"
    hint.citations = _cites(out, allowed)
    if member == "happy":
        say = _short(" ".join(str(out.get("say") or "").split()), SAY_CHARS)
        if not say or guard.unsourced_numbers(say, worker_words):
            say = fallback["say"]
        hint.say = say
    return hint


async def coach_all(llm: LLM, tactic: Tactic, turn: RehearsalTurn, sections: dict[str, Section], setup: RehearsalSetup) -> list[CoachHint]:
    return list(await asyncio.gather(*(coach(llm, m, tactic, turn, sections, setup) for m in ("happy", "proud", "gloomy"))))


def models(llm: LLM) -> dict[str, str]:
    return {m: model_name(llm, BY_ID[m].role) for m in ("happy", "proud", "gloomy")}
