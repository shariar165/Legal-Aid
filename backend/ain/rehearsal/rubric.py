"""Readiness rubric: what the worker asked for, decided in code from their replies and their explicit actions.

No model reads the rubric or sets the score. Patterns live in rubric.yaml and run on the redacted reply, NFC-normalised,
lower-cased, with Bangla digits made ASCII.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from ain.agents.pii import BN_DIGITS
from ain.models import L10n, RehearsalTurn, RubricItem
from ain.retrieval import nfc

RUBRIC_FILE = Path(__file__).with_name("rubric.yaml")


@dataclass(frozen=True)
class Item:
    id: str
    label: L10n
    ask: L10n
    applies: str
    hit: tuple[re.Pattern[str], ...]
    negate: tuple[re.Pattern[str], ...]
    agree: tuple[re.Pattern[str], ...]
    refuse_action: str | None
    before_paying: bool
    weight: int


def _compile(patterns) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(nfc(p), re.I) for p in patterns or ())


@lru_cache
def items() -> tuple[Item, ...]:
    raw = yaml.safe_load(RUBRIC_FILE.read_text(encoding="utf-8"))["items"]
    return tuple(
        Item(
            id=i["id"], label=L10n(**i["label"]), ask=L10n(**i["ask"]), applies=i["applies"], hit=_compile(i.get("hit")),
            negate=_compile(i.get("negate")), agree=_compile(i.get("agree")), refuse_action=i.get("refuse_action"),
            before_paying=bool(i.get("before_paying")), weight=int(i.get("weight", 1)),
        )
        for i in raw
    )


def normalise(text: str) -> str:
    return " ".join(nfc(text).translate(BN_DIGITS).lower().split())


def asks(item: Item, reply: str) -> bool:
    t = normalise(reply)
    return bool(t) and any(p.search(t) for p in item.hit) and not any(p.search(t) for p in item.negate)


def hits(reply: str) -> list[str]:
    """The items this one reply asks for (shown to the worker as ticks after each turn)."""
    return [i.id for i in items() if i.hit and asks(i, reply)]


def _agrees_to_pay(item: Item, reply: str) -> bool:
    t = normalise(reply)
    return any(p.search(t) for p in item.agree)


def _first_paid(turns: list[RehearsalTurn]) -> int | None:
    pay = next(i for i in items() if i.id == "no_pay_on_spot")
    return next((t.n for t in turns if t.action == "paid" or _agrees_to_pay(pay, t.worker_reply)), None)


def _judge(item: Item, turns: list[RehearsalTurn]) -> tuple[str, int | None]:
    answered = [t for t in turns if t.worker_reply.strip() or t.action != "none"]
    if not answered:
        return "not_tested", None
    if item.applies.startswith("tactic:"):
        tactic = item.applies.split(":", 1)[1]
        start = next((t.n for t in turns if t.tactic_id == tactic), None)
        if start is None:
            return "not_tested", None
        answered = [t for t in answered if t.n >= start]
        if not answered:
            return "not_tested", None
    if item.refuse_action:
        bad = next((t.n for t in answered if t.action == item.refuse_action), None)
        if item.id == "no_pay_on_spot":
            bad = _first_paid(answered)
        if bad is not None:
            return "missed", bad
        if not item.hit:  # nothing to ask for: not doing it is the whole item
            return "met", None
    paid = _first_paid(turns) if item.before_paying else None
    for t in answered:
        if paid is not None and t.n >= paid:
            break
        if asks(item, t.worker_reply):
            return "met", t.n
    return "missed", paid


def score(turns: list[RehearsalTurn]) -> tuple[int, list[RubricItem]]:
    out: list[RubricItem] = []
    for item in items():
        status, n = _judge(item, turns)
        out.append(RubricItem(id=item.id, label=item.label, status=status, turn=n, weight=item.weight))
    counted = [r for r in out if r.status != "not_tested"]
    total = sum(r.weight for r in counted)
    met = sum(r.weight for r in counted if r.status == "met")
    return (round(100 * met / total) if total else 0), out


def checklist(results: list[RubricItem]) -> list[L10n]:
    """Questions to ask before paying: one for every item not met, then the rest, so the list is always complete."""
    by = {i.id: i for i in items()}
    first = [by[r.id].ask for r in results if r.status != "met"]
    rest = [by[r.id].ask for r in results if r.status == "met"]
    return [*first, *rest]
