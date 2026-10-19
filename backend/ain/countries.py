"""Destination-country registry (ain/countries.yaml): detection, packs, wage limits, help lines.

Bangla text is NFC-normalised on both sides before matching, and aliases match whole words
only (so "Oman" is not found inside "woman").
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import yaml

from ain import config
from ain.models import Destination, L10n

REGISTRY_FILE = config.BACKEND / "ain" / "countries.yaml"


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


BN_CHARS = "ঀ-৿"


def _word(alias: str) -> str:
    # \b does not work around Bangla combining marks, so use explicit "not a letter" lookarounds.
    # Bangla adds case endings to the name itself (সৌদি আরবে, মালয়েশিয়ায়), so only its start must be a boundary.
    body = re.escape(_nfc(alias.lower()))
    end = "" if re.search(f"[{BN_CHARS}]", alias) else rf"(?![\w{BN_CHARS}])"
    return rf"(?<![\w{BN_CHARS}]){body}{end}"


@dataclass(frozen=True)
class Country:
    code: str
    name: dict
    of: dict  # possessive: "Malaysia's" / "মালয়েশিয়ার"
    aliases: tuple[str, ...]
    currency: str
    currency_aliases: tuple[str, ...]
    pack: str
    label: str
    min_wage: dict | None
    deduction_cap: dict | None
    help: dict

    @property
    def pattern(self) -> re.Pattern[str]:
        return re.compile("|".join(_word(a) for a in (self.name["en"], *self.aliases)), re.I)


@lru_cache
def load_countries() -> tuple[Country, ...]:
    raw = yaml.safe_load(REGISTRY_FILE.read_text(encoding="utf-8"))
    return tuple(
        Country(**{**c, "aliases": tuple(c["aliases"]), "currency_aliases": tuple(c["currency_aliases"])})
        for c in raw
    )


def by_name(name: str | None) -> Country | None:
    """Look up a country by its English name, code or any alias (case-insensitive)."""
    if not name:
        return None
    key = _nfc(name.strip().lower())
    for c in load_countries():
        if key in {c.code.lower(), c.name["en"].lower(), _nfc(c.name["bn"])} | {_nfc(a.lower()) for a in c.aliases}:
            return c
    return None


def by_pack(pack: str) -> Country | None:
    return next((c for c in load_countries() if c.pack == pack), None)


def detect(text: str) -> Country | None:
    """The registry country mentioned most often in the text (ties go to the first mention)."""
    low = _nfc(text.lower())
    best: tuple[int, int, Country] | None = None
    for c in load_countries():
        hits = [m.start() for m in c.pattern.finditer(low)]
        if hits and (best is None or (len(hits), -hits[0]) > (best[0], best[1])):
            best = (len(hits), -hits[0], c)
    return best[2] if best else None


def currency_codes() -> dict[str, str]:
    """How contracts write each currency (lower-case) -> the code used in facts."""
    out: dict[str, str] = {}
    for c in load_countries():
        out[c.currency.lower()] = c.currency
        for a in c.currency_aliases:
            out[a.lower()] = c.currency
    return out


def as_destination(c: Country) -> Destination:
    return Destination(code=c.code, name=L10n(**c.name), of=L10n(**c.of), supported=True, law=c.label, help=L10n(**c.help))


def destination(name: str | None) -> Destination | None:
    """What the UI shows for a document's destination; unknown countries are flagged as not covered."""
    if not name or name.strip().lower() == "bangladesh":
        return None
    c = by_name(name)
    return as_destination(c) if c else Destination(name=L10n(en=name, bn=name))
