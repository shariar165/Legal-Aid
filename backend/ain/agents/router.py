"""Jurisdiction Router: decides which law packs apply, and which are switched OFF.

Deterministic rules decide first (they are what the tests pin down, e.g. EPZ => the BEPZ
Labour Act 2019 replaces the Labour Act 2006). An LLM then reads the *redacted* text to
fill facts the regexes missed; it may add packs but can never re-enable an excluded one.
"""

from __future__ import annotations

from ain import countries
from ain.llm import LLM
from ain.models import DocFacts, PackDecision, RouteDecision

PACK_LABELS = {
    "bd_contract": "Contract Act 1872 · Stamp Act 1899 · CPC 1908",
    "bd_labour": "Bangladesh Labour Act 2006 (as amended 2026)",
    "bd_epz": "Bangladesh EPZ Labour Act 2019",
    "bd_migration": "Overseas Employment & Migrants Act 2013 · Trafficking Act 2026",
    "ilo": "ILO Conventions C29 · C95 · C181",
    "bd_fx": "FER Act 1947 · Bangladesh Bank GFET 2018",
    "eu_dd": "EU CSDDD (Directive 2024/1760)",
    "bd_data": "Personal Data Protection Act 2026",
    "eu_data": "EU GDPR (Regulation 2016/679)",
    "std_recruitment": "Fair-recruitment standards: ILO General Principles · Employer Pays Principle · RBA Code (voluntary, not law)",
    **{c.pack: c.label for c in countries.load_countries()},  # one labour-law pack per destination country
}

FACTS_SYSTEM = """You extract facts from a contract for a legal-risk engine.
Personal identifiers have been replaced by placeholders like [NAME_1]; never guess them.
Return ONLY a JSON object with these keys (null when unknown):
doc_type ("employment"|"commercial"|"mixed"|"lease"|"other"), destination_country (country where the worker will work, if abroad from Bangladesh),
is_epz (true only if the workplace is inside a Bangladesh Export Processing Zone), epz_name, is_export_contract, mentions_eu_buyer,
mentions_personal_data, governing_law, salary_amount (number), salary_currency, payment_terms_days (days after shipment),
notice_days (employer termination notice), maternity_days (total maternity leave in days)."""


def decide(facts: DocFacts, text_lower: str) -> RouteDecision:
    packs: list[PackDecision] = []
    excluded: list[PackDecision] = []

    def add(pack: str, reason: str) -> None:
        if pack not in {p.pack for p in packs}:
            packs.append(PackDecision(pack=pack, label=PACK_LABELS[pack], reason=reason))

    add("bd_contract", "General contract law applies to every agreement made in or performed from Bangladesh.")

    abroad = facts.destination_country and facts.destination_country != "Bangladesh"
    if abroad or "recruiting agency" in text_lower or "রিক্রুটিং" in text_lower:
        add("bd_migration", f"Overseas employment of a Bangladeshi worker{' in ' + facts.destination_country if abroad else ''} through a recruiting agency.")
        add("ilo", "International labour standards on forced labour, wage protection and recruitment fees.")
        add("std_recruitment", "Voluntary fair-recruitment standards that many foreign employers and buyers have signed up to.")
    country = countries.by_name(facts.destination_country)
    if country:
        add(country.pack, f"Place of work is {country.name['en']}; its labour law governs the job itself.")

    employs_in_bd = facts.doc_type in ("employment", "mixed") and not abroad
    if employs_in_bd:
        if facts.is_epz:
            zone = facts.epz_name or "an Export Processing Zone"
            add("bd_epz", f"Workplace is inside {zone}; the BEPZ Labour Act 2019 governs EPZ establishments.")
            excluded.append(
                PackDecision(
                    pack="bd_labour",
                    label=PACK_LABELS["bd_labour"],
                    reason=f"Switched OFF: workplace is in {zone}. The BEPZ Labour Act 2019 applies instead and s.3 gives it overriding effect.",
                )
            )
        else:
            add("bd_labour", "Employment in Bangladesh outside any EPZ: the Labour Act 2006 applies.")

    if facts.is_export_contract:
        add("bd_fx", "Export of goods from Bangladesh: export proceeds must be repatriated under FX regulation.")
    if facts.mentions_eu_buyer and ("due diligence" in text_lower or "csddd" in text_lower or "code of conduct" in text_lower):
        add("eu_dd", "An EU buyer imposes human-rights due diligence obligations through the contract.")
    if facts.mentions_personal_data:
        add("bd_data", "Workers' personal data is processed or transferred.")
        if facts.mentions_eu_buyer:
            add("eu_data", "Personal data flows to a party in the European Union.")
    return RouteDecision(packs=packs, excluded=excluded)


def _fake_facts(facts: DocFacts) -> dict:
    return {}


async def refine_facts(llm: LLM, facts: DocFacts, redacted_text: str) -> DocFacts:
    """Fill gaps the regexes left, using the redacted text only."""
    data = await llm.json(
        role="fast",
        system=FACTS_SYSTEM,
        user=redacted_text[:12000],
        task="facts",
        agent="Jurisdiction Router",
        fake=lambda: _fake_facts(facts),
    )
    merged = facts.model_copy()
    for key in ("destination_country", "epz_name", "governing_law", "salary_currency"):
        if getattr(merged, key) is None and isinstance(data.get(key), str) and data[key].strip():
            setattr(merged, key, data[key].strip())
    country = countries.by_name(merged.destination_country)  # "KSA", "Dubai" -> the registry's name
    if country:
        merged.destination_country = country.name["en"]
    for key in ("salary_amount", "payment_terms_days", "notice_days", "maternity_days"):
        val = data.get(key)
        if getattr(merged, key) is None and isinstance(val, (int, float)) and val > 0:
            setattr(merged, key, float(val) if key == "salary_amount" else int(val))
    for key in ("is_export_contract", "mentions_eu_buyer", "mentions_personal_data"):
        if data.get(key) is True:
            setattr(merged, key, True)
    if merged.doc_type == "unknown" and data.get("doc_type"):
        merged.doc_type = str(data["doc_type"])
    # EPZ status is only accepted from the LLM when the text actually names a zone (guards against hallucinated EPZ)
    if data.get("is_epz") is True and not merged.is_epz and ("epz" in redacted_text.lower() or "processing zone" in redacted_text.lower()):
        merged.is_epz = True
    return merged
