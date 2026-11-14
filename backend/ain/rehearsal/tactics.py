"""The dalal's tactics (tactics.yaml) and the deterministic scheduler that picks one per turn.

The model never chooses a tactic: `schedule` does, from the base order and from what the worker's last reply asked for,
and the dalal may only voice the tactic it is given (guard.py checks).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from ain import config
from ain.models import L10n, RehearsalSetup, RehearsalTurn

TACTICS_FILE = Path(__file__).with_name("tactics.yaml")
SOURCE_KEYS = ("title", "publisher", "year", "url", "locator", "supports")


@dataclass(frozen=True)
class LawAnchor:
    citation_id: str
    quote: str


@dataclass(frozen=True)
class Tactic:
    id: str
    label: L10n
    example_bn: str
    source: dict
    tests: tuple[str, ...]
    counter_of: tuple[str, ...]
    sunny_ask_bn: str
    sunny_say_bn: str
    grey_flag_bn: str
    regal_bn: str
    law: tuple[LawAnchor, ...]
    also_source: dict | None = None

    @property
    def sources(self) -> list[dict]:
        return [self.source, *([self.also_source] if self.also_source else [])]


@lru_cache
def _raw() -> dict:
    return yaml.safe_load(TACTICS_FILE.read_text(encoding="utf-8"))


@lru_cache
def load() -> tuple[Tactic, ...]:
    out = []
    for t in _raw()["tactics"]:
        out.append(
            Tactic(
                id=t["id"], label=L10n(**t["label"]), example_bn=t["example_bn"].strip(), source=dict(t["source"]),
                tests=tuple(t.get("tests") or ()), counter_of=tuple(t.get("counter_of") or ()),
                sunny_ask_bn=t["sunny_ask_bn"], sunny_say_bn=t["sunny_say_bn"], grey_flag_bn=t["grey_flag_bn"], regal_bn=t["regal_bn"],
                law=tuple(LawAnchor(**a) for a in t.get("law") or ()), also_source=dict(t["also_source"]) if t.get("also_source") else None,
            )
        )
    return tuple(out)


def by_id() -> dict[str, Tactic]:
    return {t.id: t for t in load()}


def order() -> list[str]:
    return list(_raw()["order"])


def turn_limits() -> tuple[int, int]:
    s = config.rehearsal_settings()
    return int(s.get("min_turns", 6)), int(s.get("max_turns", 10))


def schedule(setup: RehearsalSetup, turns: list[RehearsalTurn]) -> str | None:
    """The next tactic, or None when the rehearsal is over.

    A tactic is played once. If the worker's last reply asked for an item that an unplayed tactic counters (asked for
    a receipt -> "no receipt needed"), that tactic comes next; otherwise the base order continues. A worker who said the
    passport is with them, or who has a contract already, still hears the passport and contract tactics: the point is
    to rehearse the answer."""
    _, most = turn_limits()
    if len(turns) >= most:
        return None
    played = {t.tactic_id for t in turns}
    left = [t for t in order() if t not in played]
    if not left:
        return None
    if turns:
        asked = set(turns[-1].hits)
        tactics = by_id()
        reaction = next((t for t in left if asked & set(tactics[t].counter_of)), None)
        if reaction:
            return reaction
    return left[0]
