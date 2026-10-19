"""Risk Analyst: runs the YAML playbook over the clauses.

Each rule is a hypothesis with a trigger (regex on clauses, absence in the document, or a
deterministic fact check). Regex hits are confirmed by an LLM reading only the candidate
clause(s); fact checks need no LLM. The legal propositions attached to a risk come from the
rule's anchors (citation_ids into the corpus); the verifier still checks every one of them.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from functools import lru_cache

import yaml

from ain import config, countries
from ain.llm import LLM
from ain.models import Claim, Clause, DocFacts, L10n, Risk, RouteDecision, WageCalc
from ain.naming import EN_TO_BN_DIGITS

CHECK_SYSTEM = """You are a careful contract lawyer. You get ONE question and the text of one or more contract clauses
(personal data is replaced by placeholders). Answer ONLY from the clause text.
Return JSON: {"applies": true|false, "clause_ids": ["C3", ...], "finding": "one or two sentences quoting or describing what the clause says"}"""


@dataclass
class Rule:
    id: str
    category: str
    severity: str
    packs: list[str]
    title: dict
    trigger: dict
    question: str
    citizen_line: dict
    action: dict
    mitigation: str = ""
    why_non_obvious: str = ""
    clash: str | None = None
    exclude_packs: list[str] = field(default_factory=list)
    anchors: list[dict] = field(default_factory=list)
    anchors_by_pack: dict[str, list[dict]] = field(default_factory=dict)
    pack_anchors: dict[str, list[dict]] = field(default_factory=dict)  # routed pack (a destination country, standards) -> extra anchors

    def active(self, packs: set[str]) -> bool:
        return bool(set(self.packs) & packs) and not set(self.exclude_packs) & packs

    def anchors_for(self, packs: set[str]) -> list[dict]:
        base = self.anchors
        if self.anchors_by_pack:
            base = []
            for pack in ("bd_epz", "bd_labour"):  # EPZ regime first: it overrides the Labour Act
                if pack in packs and pack in self.anchors_by_pack:
                    base = self.anchors_by_pack[pack]
                    break
        # the host country's law applies on top of Bangladesh law and ILO standards
        return base + [a for pack, group in self.pack_anchors.items() if pack in packs for a in group]


@lru_cache
def load_rules() -> list[Rule]:
    rules: list[Rule] = []
    for path in sorted(config.PLAYBOOK_DIR.glob("*.yaml")):
        for raw in yaml.safe_load(path.read_text(encoding="utf-8")):
            rules.append(Rule(**raw))
    return rules


# ------------------------------------------------------------------ fact checks (deterministic)


def _notice_short(facts: DocFacts, wage: WageCalc | None) -> str | None:
    if facts.notice_days is not None and facts.notice_days < 120:
        return f"The document gives {facts.notice_days} days' notice of termination; the statutory minimum for a permanent worker is 120 days."
    return None


def _maternity_short(facts: DocFacts, wage: WageCalc | None, packs: set[str]) -> str | None:
    if facts.maternity_days is None:
        return None
    required = 112 if "bd_epz" in packs else 120
    if facts.maternity_days < required:
        regime = "8 weeks before + 8 weeks after delivery (EPZ Labour Act)" if "bd_epz" in packs else "60 days before + 60 days after delivery (Labour Act as amended 2026)"
        return f"The document grants {facts.maternity_days} days ({facts.maternity_days // 7} weeks) of maternity leave; the statute requires {required} days: {regime}."
    return None


def _payment_long(facts: DocFacts, wage: WageCalc | None) -> str | None:
    if facts.payment_terms_days is not None and facts.payment_terms_days > 120:
        return f"Invoices are payable {facts.payment_terms_days} days after shipment, beyond the four-month (about 120-day) repatriation period."
    return None


def _below_min(facts: DocFacts, wage: WageCalc | None) -> str | None:
    if wage and wage.below_minimum:
        return f"Basic salary is {wage.currency} {wage.promised:,.0f} per month, {wage.currency} {wage.shortfall:,.0f} below the {wage.currency} {wage.minimum_wage:,.0f} minimum wage."
    return None


def _over_cap(facts: DocFacts, wage: WageCalc | None) -> str | None:
    if wage and wage.over_cap:
        return (
            f"Monthly deductions total {wage.currency} {wage.monthly_deductions:,.0f} ({wage.pct_deducted}% of the salary); "
            f"the worker keeps {wage.currency} {wage.net:,.0f}. The legal cap is {wage.deduction_cap_pct:.0f}%."
        )
    return None


def run_fact_check(name: str, facts: DocFacts, wage: WageCalc | None, packs: set[str]) -> str | None:
    if name == "maternity_short":
        return _maternity_short(facts, wage, packs)
    return {"notice_short": _notice_short, "payment_terms_long": _payment_long, "below_min_wage": _below_min, "deduction_over_cap": _over_cap}[name](facts, wage)


FACT_CLAUSE_HINTS = {
    "notice_short": r"notice",
    "maternity_short": r"maternity|প্রসূতি",
    "payment_terms_long": r"payment|days after",
    "below_min_wage": r"salary|wage|বেতন",
    "deduction_over_cap": r"deduct",
}


# ------------------------------------------------------------------ helpers


class _Blanks(dict):
    def __missing__(self, key: str) -> str:  # leave unknown {placeholders} as they are
        return "{" + key + "}"


def _placeholders(packs: set[str], wage: WageCalc | None) -> dict[str, _Blanks]:
    """Values for {country}, {country_of}, {currency}, {min_wage} and {cap} in rule texts, per language."""
    country = next((c for c in countries.load_countries() if c.pack in packs), None)
    out = {}
    for lang in ("en", "bn"):
        vals = _Blanks()
        if country:
            vals.update(country=country.name[lang], country_of=country.of[lang], currency=country.currency)
            if country.min_wage:
                vals["min_wage"] = f"{country.min_wage['amount']:,}"
            if country.deduction_cap:
                cap = f"{country.deduction_cap['pct']}"
                vals["cap"] = cap.translate(EN_TO_BN_DIGITS) if lang == "bn" else cap
        if wage and wage.currency:
            vals["currency"] = wage.currency
        out[lang] = vals
    return out


def _l10n(texts: dict, vals: dict[str, _Blanks]) -> L10n:
    return L10n(**{lang: text.format_map(vals[lang]) for lang, text in texts.items()})


def _risk_from_rule(
    rule: Rule, n: int, finding: str, clause_ids: list[str], packs: set[str], wage: WageCalc | None = None
) -> tuple[Risk, list[Claim]]:
    rid = f"R{n}"
    vals = _placeholders(packs, wage)
    claims = [
        Claim(id=f"{rid}.{i + 1}", risk_id=rid, proposition=a["proposition"], citation_id=a["citation_id"], quote=a.get("quote"), origin="playbook")
        for i, a in enumerate(rule.anchors_for(packs))
    ]
    risk = Risk(
        id=rid,
        rule_id=rule.id,
        origin="calculator" if rule.trigger.get("fact") in ("below_min_wage", "deduction_over_cap") else "playbook",
        category=rule.category,
        title=_l10n(rule.title, vals),
        severity=rule.severity,  # type: ignore[arg-type]
        clause_ids=clause_ids,
        finding=finding,
        why_non_obvious=rule.why_non_obvious.format_map(vals["en"]),
        citizen_line=_l10n(rule.citizen_line, vals),
        action=_l10n(rule.action, vals),
        mitigation_clause=rule.mitigation.format_map(vals["en"]),
        clash=rule.clash,
        claim_ids=[c.id for c in claims],
    )
    return risk, claims


def _matching_clauses(rule: Rule, clauses: list[Clause]) -> list[Clause]:
    pats = [re.compile(p, re.I | re.S) for p in rule.trigger.get("regex", [])]
    return [c for c in clauses if any(p.search(c.text) for p in pats)]


def _missing_term(rule: Rule, clauses: list[Clause]) -> list[Clause]:
    """For an `absent` trigger: the clauses to show the LLM when NO clause has the protective term, else []."""
    if not rule.trigger.get("absent"):
        return []
    text = "\n".join(c.text for c in clauses)
    if any(re.search(p, text, re.I | re.S) for p in rule.trigger["absent"]):
        return []
    hint = re.compile(rule.trigger.get("hint", "."), re.I)
    return [c for c in clauses if hint.search(c.text)][:3] or clauses[:1]


async def _confirm(llm: LLM, rule: Rule, hits: list[Clause], redact, absence: bool = False) -> tuple[bool, list[str], str]:
    body = "\n\n".join(f"[{c.id}] {redact(c.text)}" for c in hits)
    first = redact(hits[0].text).replace("\n", " ")

    excerpt = first if len(first) <= 220 else first[:217].rsplit(" ", 1)[0].rstrip(",;:") + "…"

    def fake() -> dict:
        finding = rule.trigger.get("absent_finding") if absence else None
        return {"applies": True, "clause_ids": [c.id for c in hits], "finding": finding or f"Clause {hits[0].id}: “{excerpt}”"}

    data = await llm.json(
        role="reasoner",
        system=CHECK_SYSTEM,
        user=f"QUESTION: {rule.question}\n\nCLAUSES:\n{body}",
        task=f"risk_check:{rule.id}",
        agent="Risk Analyst",
        fake=fake,
    )
    ids = [i for i in data.get("clause_ids") or [] if any(c.id == i for c in hits)] or [hits[0].id]
    return bool(data.get("applies")), ids, str(data.get("finding") or "").strip() or fake()["finding"]


# ------------------------------------------------------------------ public API


async def run_text_rules(llm: LLM, clauses: list[Clause], route: RouteDecision, redact, start: int = 1) -> tuple[list[Risk], list[Claim]]:
    """Regex- and absence-triggered rules, confirmed by the LLM in parallel."""
    packs = route.pack_ids
    jobs = []
    for rule in load_rules():
        if not rule.active(packs) or not {"regex", "absent"} & rule.trigger.keys() or not rule.anchors_for(packs):
            continue
        if hits := _matching_clauses(rule, clauses):
            jobs.append((rule, hits, False))
        elif missing := _missing_term(rule, clauses):
            jobs.append((rule, missing, True))
    results = await asyncio.gather(*(_confirm(llm, rule, hits, redact, absence) for rule, hits, absence in jobs))
    risks: list[Risk] = []
    claims: list[Claim] = []
    n = start
    for (rule, _, _), (applies, ids, finding) in zip(jobs, results):
        if not applies:
            continue
        risk, cl = _risk_from_rule(rule, n, finding, ids, packs)
        risks.append(risk)
        claims += cl
        n += 1
    return risks, claims


def run_fact_rules(facts: DocFacts, wage: WageCalc | None, clauses: list[Clause], route: RouteDecision, start: int) -> tuple[list[Risk], list[Claim]]:
    packs = route.pack_ids
    risks: list[Risk] = []
    claims: list[Claim] = []
    n = start
    for rule in load_rules():
        name = rule.trigger.get("fact")
        if not name or not rule.active(packs) or not rule.anchors_for(packs):
            continue
        finding = run_fact_check(name, facts, wage, packs)
        if not finding:
            continue
        hint = re.compile(FACT_CLAUSE_HINTS[name], re.I)
        ids = [c.id for c in clauses if hint.search(c.text)][:2]
        risk, cl = _risk_from_rule(rule, n, finding, ids, packs, wage)
        risks.append(risk)
        claims += cl
        n += 1
    return risks, claims
