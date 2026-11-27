"""Who is bound by an international instrument: Bangladesh and the destination country (spec 29 step 2.1).

`corpus/ratifications.yaml` is a fact table, not statute text: one row per ILO convention in the corpus and per
country (Bangladesh and every destination in countries.yaml), checked against NORMLEX. A convention binds a state
only once it has ratified it; a claim resting on one that neither party ratified is an international standard,
persuasive but not binding. The note is added to Gate 1's detail and shown as a badge; no gate decision changes.
"""

from __future__ import annotations

import re
from functools import cache

import yaml

from ain import config, countries
from ain.models import L10n, PartyRatification, Ratification

TABLE_FILE = config.BACKEND / "corpus" / "ratifications.yaml"
BD = "BD"
BD_NAME = L10n(en="Bangladesh", bn="বাংলাদেশ")
INSTRUMENT = re.compile(r"^ILO-(C\d{3})$")  # ILO-C181 -> C181; supervisory comments (ILO-CEACR-…) are not instruments


@cache
def table() -> dict[str, dict]:
    return yaml.safe_load(TABLE_FILE.read_text(encoding="utf-8"))["instruments"]


def instrument(act_key: str) -> str | None:
    m = INSTRUMENT.match(act_key)
    return m.group(1) if m else None


def parties(destination_code: str | None) -> list[str]:
    """The states whose ratification matters for a document: Bangladesh, and the country where the job is."""
    return [BD] + ([destination_code] if destination_code and destination_code != BD else [])


def _name(code: str) -> L10n:
    if code == BD:
        return BD_NAME
    c = next(c for c in countries.load_countries() if c.code == code)
    return L10n(en=c.name["en"], bn=c.name["bn"])


def _join(names: list[str], word: str) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} {word} {names[-1]}"


def _note(yes: list[L10n], no: list[L10n]) -> L10n:
    if not no:
        return L10n(en=f"Ratified by {_join([n.en for n in yes], 'and')}.", bn=f"{_join([n.bn for n in yes], 'ও')} অনুসমর্থন করেছে।")
    if not yes:
        return L10n(en=f"Not ratified by {_join([n.en for n in no], 'or')}: an international standard (persuasive), not binding law here.",
                    bn=f"{_join([n.bn for n in no], 'বা')} অনুসমর্থন করেনি: এটি আন্তর্জাতিক মানদণ্ড, এখানে বাধ্যতামূলক আইন নয়।")
    return L10n(en=f"Ratified by {_join([n.en for n in yes], 'and')}; not by {_join([n.en for n in no], 'or')}.",
                bn=f"{_join([n.bn for n in yes], 'ও')} অনুসমর্থন করেছে; {_join([n.bn for n in no], 'বা')} করেনি।")


def status(act_key: str, codes: list[str]) -> Ratification | None:
    """Who has ratified the instrument behind `act_key`; None for national law or a country not in the table."""
    inst = instrument(act_key)
    rows = table().get(inst) if inst else None
    if not rows or any(c not in rows["countries"] for c in codes):
        return None
    ps = [PartyRatification(country=c, name=_name(c), ratified=bool(rows["countries"][c]["ratified"]),
                            date=rows["countries"][c].get("date")) for c in codes]
    return Ratification(instrument=inst, title=rows["title"], url=rows["url"], parties=ps,
                        persuasive=not any(p.ratified for p in ps),
                        note=_note([p.name for p in ps if p.ratified], [p.name for p in ps if not p.ratified]))
