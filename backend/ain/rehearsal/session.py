"""Runs one rehearsal: the dalal's line, the worker's reply, three coach hints, the next line; then the debrief.

Every step is a TraceEvent on an `orchestrator.Job`, so the API streams it over SSE exactly as it streams an analysis.
Everything the worker types goes through the PII Shield (one mapping per session) before any model sees it, and the
mapping is stored only inside the encrypted session file.

While `rehearsal.live` is false in config.yaml, every call is an offline stand-in, whatever AIN_LLM_MODE says.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field

from ain import config
from ain.agents.bench import model_name
from ain.agents.council import _cites, _short, _strip_ids
from ain.agents.pii import redact
from ain.llm import LLM
from ain.models import PromiseContacts, RehearsalDebrief, RehearsalSession, RehearsalSetup, RehearsalTurn, RubricItem, Section, WorkerAction
from ain.orchestrator import Job
from ain.rehearsal import coaches, dalal, guard, record, rubric, store, tactics
from ain.retrieval import get_corpus, nfc

AGENT = "Rehearsal Council"
CHIEF = "Rehearsal · Chief Justice"
NOTE_CHARS = 600
NAME_HINT = re.compile(
    nfc(r"(?:(?:আমার|ওনার|উনার|তার|তাঁর|এজেন্টের|দালালের|ভাইয়ের)\s+নাম\s+|(?:my|his|her) name is\s+)([^\s,।.!?]+(?:\s[^\s,।.!?]+)?)"),
    re.I,
)


def mode() -> str:
    """The quota lock: offline unless the rehearsal flag is on."""
    return config.llm_mode() if config.rehearsal_settings().get("live") else "fake"


# ---------------------------------------------------------------- PII


def force(mapping: dict[str, str], kind: str, value: str) -> str:
    """A placeholder for a value that is PII by definition (a contact field), detected or not."""
    value = " ".join(value.split())
    for ph, v in mapping.items():
        if v == value:
            return ph
    n = 1 + max((int(p.strip("[]").rsplit("_", 1)[1]) for p in mapping if p.startswith(f"[{kind}_")), default=0)
    ph = f"[{kind}_{n}]"
    mapping[ph] = value
    return ph


def clean(mapping: dict[str, str], text: str) -> str:
    """Known values first (so a name typed in the record is caught in a reply too), then 'my name is ...', then the
    PII Shield's own patterns. `mapping` is updated in place."""
    text = nfc(text or "")
    for ph, v in sorted(mapping.items(), key=lambda kv: -len(kv[1])):
        if v and len(v) >= 2:
            text = text.replace(v, ph)
    text = NAME_HINT.sub(lambda m: m.group(0).replace(m.group(1), force(mapping, "NAME", m.group(1))), text)
    r = redact(text, mapping)
    mapping.update(r.mapping)
    return r.text


def _clean_setup(mapping: dict[str, str], s: RehearsalSetup) -> RehearsalSetup:
    p = s.promises
    promises = p.model_copy(
        update={k: clean(mapping, getattr(p, k)) for k in ("salary", "total_cost", "job", "duration", "paid_so_far")}
        | {"extra": [clean(mapping, x) for x in p.extra if x.strip()]}
    )
    return s.model_copy(update={"job": clean(mapping, s.job), "promises": promises})


# ---------------------------------------------------------------- runner


@dataclass
class Runner:
    session: RehearsalSession
    job: Job
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    task: asyncio.Task | None = None

    @property
    def s(self) -> RehearsalSession:
        return self.session

    def llm(self) -> LLM:
        return LLM(mode=self.s.mode, on_call=self.s.outbound_calls.append)

    def say(self, type_: str, agent: str | None = None, message: str = "", **data) -> None:
        self.job.say(type_, agent, message, **data)

    def save(self) -> None:
        self.s.trace = list(self.job.events)
        store.save(self.s)


RUNNERS: dict[str, Runner] = {}


def _job_for(s: RehearsalSession) -> Job:
    job = Job(id=s.id, name="rehearsal")
    job.events = list(s.trace)
    job.status = "done" if s.status == "done" else "running"
    return job


def get(sid: str) -> Runner | None:
    r = RUNNERS.get(sid)
    if r is None:
        s = store.load(sid)
        if s is None:
            return None
        r = RUNNERS[sid] = Runner(session=s, job=_job_for(s))
    return r


def forget(sid: str) -> None:
    RUNNERS.pop(sid, None)
    store.delete(sid)


def _packs(setup: RehearsalSetup) -> set[str]:
    return record.route(setup).pack_ids


def create(user_id: str, setup: RehearsalSetup) -> Runner:
    sid = store.new_id()
    mapping: dict[str, str] = {}
    s = RehearsalSession(id=sid, created_at=time.time(), setup=_clean_setup(mapping, setup), mode=mode(), mapping=mapping)
    store.record(user_id, sid)
    r = RUNNERS[sid] = Runner(session=s, job=Job(id=sid, name="rehearsal"))
    least, most = tactics.turn_limits()
    llm = r.llm()
    r.say(
        "rehearsal_started", AGENT, "Rehearsal started", mode=s.mode, min_turns=least, max_turns=most,
        coaches=coaches.models(llm), dalal_model=model_name(llm, config.rehearsal_settings().get("roles", {}).get("dalal", "reasoner")),
    )
    r.save()
    return r


async def open_turn(r: Runner) -> None:
    """The dalal's next line, or the debrief when the scheduler has nothing left."""
    nxt = tactics.schedule(r.s.setup, r.s.turns)
    if nxt is None:
        await finish(r)
        return
    tactic = tactics.by_id()[nxt]
    line, reason = await dalal.line(r.llm(), tactic, r.s.setup, r.s.turns)
    turn = RehearsalTurn(n=len(r.s.turns) + 1, tactic_id=tactic.id, dalal_line=line, guardrail=reason)
    r.s.turns.append(turn)
    if reason:
        r.say("guardrail", dalal.AGENT, f"Replaced the dalal's line: {reason}", turn=turn.n, reason=reason)
    r.say("dalal_line", dalal.AGENT, line, turn=turn.n, tactic_id=tactic.id, label=tactic.label.model_dump())
    r.save()


def pending(r: Runner) -> RehearsalTurn | None:
    t = r.s.turns[-1] if r.s.turns else None
    return t if t and not t.worker_reply and t.action == "none" and not t.hints else None


async def answer(r: Runner, reply: str, action: WorkerAction) -> None:
    turn = pending(r)
    assert turn is not None
    turn.worker_reply = clean(r.s.mapping, reply)
    turn.action = action
    turn.hits = rubric.hits(turn.worker_reply)
    r.say("worker_turn", AGENT, turn.worker_reply, turn=turn.n, action=action, hits=turn.hits)
    tactic = tactics.by_id()[turn.tactic_id]
    sections = await asyncio.to_thread(coaches.allowed_sections, tactic, turn.dalal_line, _packs(r.s.setup))
    llm = r.llm()
    turn.hints = await coaches.coach_all(llm, tactic, turn, sections, r.s.setup)
    for h in turn.hints:
        r.say("coach_hint", f"Rehearsal · {h.name}", h.text, turn=turn.n, hint=h.model_dump())
        if h.member == "proud" and h.dropped:
            r.say("citation_dropped", f"Rehearsal · {h.name}", f"Regal's citation failed the {h.dropped} gate", turn=turn.n, gate=h.dropped)
    r.say("turn_done", AGENT, f"Turn {turn.n} done", turn=turn.n, hits=turn.hits)
    r.save()
    await open_turn(r)


# ---------------------------------------------------------------- debrief

CHIEF_SYSTEM = """You are the Chief Justice of a three-member council (Sunny, Regal and Grey) that coached a Bangladeshi
worker through a rehearsal of a conversation with a recruiting middleman (a "dalal"). Write a short, warm debrief for
the worker (at most 80 words). {language}
- Say what they did well and the one or two things to do differently, from RUBRIC RESULTS only. Do not invent results.
- Do not give or mention any score or number. Do not state law beyond the VERIFIED LAW below; cite only its ids.
- End with one concrete next step before paying anything.
Return JSON: {{"note": "...", "citations": ["citation_id", ...]}}"""


def _fake_note(items: list[RubricItem], language: str) -> dict:
    met = [i for i in items if i.status == "met"]
    missed = [i for i in items if i.status == "missed"]
    if language == "en":
        good = f"Well done: {', '.join(i.label.en.lower() for i in met)}." if met else "You finished the rehearsal, and that is the first step."
        fix = f" Next time: {', '.join(i.label.en.lower() for i in missed[:2])}." if missed else ""
        return {"note": f"{good}{fix} Before you pay anything, ask every question on the list below and keep the written record.", "citations": []}
    good = f"ভালো করেছেন: {', '.join(i.label.bn for i in met)}।" if met else "মহড়া শেষ করেছেন, এটাই প্রথম ধাপ।"
    fix = f" পরের বার খেয়াল রাখুন: {', '.join(i.label.bn for i in missed[:2])}।" if missed else ""
    return {"note": f"{good}{fix} টাকা দেওয়ার আগে নিচের প্রশ্নগুলো জিজ্ঞেস করুন আর লিখিত রেকর্ড রাখুন।", "citations": []}


def _verified_law(r: Runner) -> dict[str, Section]:
    corpus = get_corpus()
    ids = dict.fromkeys(c for t in r.s.turns for h in t.hints if h.member == "proud" for c in h.citations)
    return {c: s for c in ids if (s := corpus.get(c))}


async def finish(r: Runner) -> None:
    if r.s.status == "done":
        return
    score, items = rubric.score(r.s.turns)
    checklist = rubric.checklist(items)
    law = _verified_law(r)
    language = r.s.setup.language
    lines = [f"- {i.label.en}: {i.status.replace('_', ' ')}" for i in items]
    played = [tactics.by_id()[t.tactic_id].label.en for t in r.s.turns]
    user = (
        f"TACTICS THE DALAL USED: {', '.join(played) or 'none'}\n\nRUBRIC RESULTS:\n" + "\n".join(lines) + "\n\nVERIFIED LAW:\n"
        + ("\n".join(f"[{c}] {s.act_en}, s.{s.section} - {s.heading}" for c, s in law.items()) or "(none)")
    )
    llm = r.llm()
    fallback = _fake_note(items, language)
    role = config.rehearsal_settings().get("roles", {}).get("debrief", "chairman")
    out = await llm.json(
        role=role, system=CHIEF_SYSTEM.format(language=coaches.LANGUAGE[language]), user=user, task="rehearsal_debrief",
        agent=CHIEF, fake=lambda: fallback, temperature=0.3, max_tokens=500,
    )
    note = _short(_strip_ids(str(out.get("note") or "").strip(), list(law)), NOTE_CHARS)
    if not note or guard.numbers(note):  # the score is the rubric's; the note gives no figures at all
        note, out = fallback["note"], fallback
    r.s.debrief = RehearsalDebrief(score=score, items=items, checklist=checklist, note=note, citations=_cites(out, list(law)), model=model_name(llm, role))
    r.say("debrief", CHIEF, note, debrief=r.s.debrief.model_dump())
    contacts = r.s.record.contacts if r.s.record else PromiseContacts()
    r.s.record = await record.build(llm, r.s.setup, contacts)
    r.say("record_ready", AGENT, "Promise Record ready", rows=len(r.s.record.rows), paths=len(r.s.record.paths))
    r.s.status = "done"
    r.job.status = "done"
    r.save()
    await r.job._notify()


CONTACT_KINDS = {"agent_name": "NAME", "agent_phone": "PHONE", "agency_name": "ORG", "place": "PLACE"}


def set_contacts(r: Runner, contacts: PromiseContacts) -> PromiseContacts:
    """Contact fields become placeholders whatever the PII Shield detects; notes go through the Shield."""
    m = r.s.mapping
    out = PromiseContacts(**{k: force(m, kind, v) if v.strip() else "" for k, kind in CONTACT_KINDS.items() if (v := getattr(contacts, k)) is not None})
    out.notes = clean(m, contacts.notes) if contacts.notes.strip() else ""
    return out
