"""The dalal seat: an AI role-playing a recruiting sub-agent, limited to the one tactic the scheduler hands it.

It sees only that tactic, its curated example line, the redacted setup and the last few redacted turns. Its line then
goes through guard.check_dalal; a line that breaks a rule is replaced by the tactic's example line.
"""

from __future__ import annotations

from ain import config
from ain.llm import LLM
from ain.models import RehearsalSetup, RehearsalTurn
from ain.rehearsal import guard
from ain.rehearsal.tactics import Tactic

HISTORY = 4
AGENT = "Rehearsal · Dalal"

DALAL_SYSTEM = """You play a recruiting sub-agent (a "dalal") in a TRAINING ROLE-PLAY for a Bangladeshi worker who wants
to work abroad. The worker is practising how to stay safe before paying anything. Speak one short line (at most 2
sentences) in everyday spoken Bangla, in the voice of a friendly but pushy middleman.
Rules you must follow:
- Use ONLY the TACTIC given below. Put its id in "tactic_id". Stay close to the EXAMPLE LINE's meaning.
- Never state anything about the law, rules, government rates, courts or crimes, true or false.
- Never insult or threaten the worker.
- Never name any real or invented person, agency or company. Never give a phone number.
- Use no figures except ones the worker already gave (in SETUP or the conversation).
- React naturally to the worker's last reply, but do not give in: keep the tactic's pressure.
Return JSON: {"tactic_id": "...", "line": "..."}"""


def _setup_block(setup: RehearsalSetup) -> str:
    p = setup.promises
    rows = [
        ("country", setup.country or ""), ("job", setup.job or p.job), ("salary promised", p.salary), ("total cost asked", p.total_cost),
        ("duration", p.duration), ("passport is with", p.passport_keeper), ("paid so far", p.paid_so_far),
    ]
    return "\n".join(f"- {k}: {v}" for k, v in rows if v and v != "unsure")


def _history(turns: list[RehearsalTurn]) -> str:
    out = []
    for t in turns[-HISTORY:]:
        out.append(f"DALAL: {t.dalal_line}")
        if t.worker_reply:
            out.append(f"WORKER: {t.worker_reply}")
    return "\n".join(out)


def allowed_numbers(setup: RehearsalSetup, turns: list[RehearsalTurn]) -> set[str]:
    p = setup.promises
    text = " ".join([p.salary, p.total_cost, p.duration, p.paid_so_far, p.job, setup.job, *p.extra, *(t.worker_reply for t in turns)])
    return guard.numbers(text)


async def line(llm: LLM, tactic: Tactic, setup: RehearsalSetup, turns: list[RehearsalTurn]) -> tuple[str, str]:
    """(the line shown, why the model's own line was replaced or '')."""
    user = (
        f"TACTIC {tactic.id}: {tactic.label.en} ({tactic.label.bn})\nEXAMPLE LINE: {tactic.example_bn}\n\n"
        f"SETUP (what the worker says the dalal promised so far):\n{_setup_block(setup) or '- nothing yet'}\n\n"
        + (f"CONVERSATION SO FAR:\n{_history(turns)}\n" if turns else "This is the opening line.\n")
    )
    out = await llm.json(
        role=config.rehearsal_settings().get("roles", {}).get("dalal", "reasoner"),
        system=DALAL_SYSTEM,
        user=user,
        task="rehearsal_dalal",
        agent=AGENT,
        fake=lambda: {"tactic_id": tactic.id, "line": tactic.example_bn},
        temperature=0.8,
        max_tokens=300,
    )
    said = " ".join(str(out.get("line") or "").split())
    reason = guard.check_dalal(said, out.get("tactic_id") if isinstance(out.get("tactic_id"), str) else None, tactic.id, allowed_numbers(setup, turns))
    return (tactic.example_bn, reason) if reason else (said, "")
