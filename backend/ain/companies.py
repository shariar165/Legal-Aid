"""Registry of employers' published policies (corpus/companies.yaml): which company a contract names.

Company names are not personal data, so they are matched on the original text. Only whole-word
aliases count, and the longest alias wins ("IOI Plantation" before "IOI").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

import yaml

from ain import config

REGISTRY_FILE = config.BACKEND / "corpus" / "companies.yaml"
STALE_AFTER_DAYS = 365


@dataclass(frozen=True)
class Company:
    slug: str
    name: str
    aliases: tuple[str, ...]
    country: str
    sector: str
    document: str
    published: str
    policy_url: str

    @property
    def pack(self) -> str:
        return f"co_{self.slug}"

    @property
    def label(self) -> str:
        return f"{self.name}: published policy ({self.document}, {self.published})"

    @property
    def source_label(self) -> str:
        """How findings name the policy: 'The employer's published policy (...) says ...'."""
        return f"published policy ({self.document}, as published {self.published})"


@lru_cache
def load_companies() -> tuple[Company, ...]:
    if not REGISTRY_FILE.exists():
        return ()
    fields = Company.__dataclass_fields__
    return tuple(
        Company(**{k: (tuple(v) if k == "aliases" else str(v)) for k, v in c.items() if k in fields})
        for c in yaml.safe_load(REGISTRY_FILE.read_text(encoding="utf-8"))
    )


def detect(text: str) -> Company | None:
    """The registry company the contract names, if any (the longest matching alias wins)."""
    best: tuple[int, Company] | None = None
    for c in load_companies():
        for alias in (c.name, *c.aliases):
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text, re.I) and (best is None or len(alias) > best[0]):
                best = (len(alias), c)
    return best[1] if best else None


def is_stale(retrieved_at: str, today: date | None = None) -> bool:
    """A published policy we fetched more than a year ago may have changed: the UI asks to re-check it."""
    try:
        return ((today or date.today()) - date.fromisoformat(retrieved_at)).days > STALE_AFTER_DAYS
    except ValueError:
        return True
