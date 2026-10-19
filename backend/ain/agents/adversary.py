"""Adversarial Counsel: hunts for risks OUTSIDE the playbook.

Agentic RAG in three steps:
  1. hypothesise  - read the redacted clauses and the risks already found; propose new risks
                    (clause interactions, missing terms, wrong-regime traps) with search queries in EN + BN
  2. retrieve     - run each query through hybrid retrieval, restricted to the routed law packs
  3. ground       - for each hypothesis, pick legal support ONLY from the retrieved citation_ids

Any citation_id not handed out by retrieval in step 2 is rejected before verification:
the model cannot cite from memory. Everything it proposes still goes through the 4 gates.
"""

from __future__ import annotations

import re

from ain.llm import LLM
from ain.models import Claim, Clause, DocFacts, L10n, Risk, RouteDecision, TraceEvent
from ain.retrieval import Corpus

HYPOTHESIS_SYSTEM = """You are opposing counsel reviewing a contract for a Bangladeshi party. A rule-based playbook has
already flagged some risks (listed). Find up to 3 ADDITIONAL, non-obvious risks it missed: clauses that are harmless alone
but dangerous together, important terms that are MISSING, or terms that collide with mandatory local law.
Personal data is replaced by placeholders. Do not cite any law yet.
Return JSON: {"hypotheses": [{"key": "h1", "title_en": "...", "title_bn": "...", "category": "interaction|absence|regime_conflict|other",
"severity": "critical|high|medium|low", "clause_ids": ["C7"], "finding": "what the contract says or omits",
"why_non_obvious": "...", "queries": ["Bangla search query in statutory wording", "English search query"]}]}
Most Bangladeshi statutes are in Bangla: ALWAYS give at least one query in formal statutory Bangla (e.g. "পাসপোর্ট আটকাইয়া রাখিলে")."""

GROUND_SYSTEM = """You ground legal risks in statute text. For each hypothesis you get candidate statute sections, each with a
citation_id. Use ONLY citation_ids from the candidates; never invent one. For each hypothesis either drop it (if no candidate
supports it) or return claims: short legal propositions, each supported by ONE section, with an optional verbatim quote
copied exactly from that section's text.
Return JSON: {"risks": [{"key": "h1", "keep": true, "citizen_line_en": "...", "citizen_line_bn": "...", "action_en": "...",
"action_bn": "...", "mitigation_clause": "...", "claims": [{"citation_id": "...", "proposition": "...", "quote": "..."}]}]}"""


def _clause_block(clauses: list[Clause], redact) -> str:
    return "\n\n".join(f"[{c.id}] {redact(c.text)}" for c in clauses)


# ------------------------------------------------------------------ deterministic stand-ins for offline/test mode


def _fake_hypotheses(clauses: list[Clause], facts: DocFacts, route: RouteDecision, text: str, known: list[Risk]) -> dict:
    low = text.lower()
    hyps = []
    flagged = {r.rule_id for r in known}
    if (
        "bd_migration" in route.pack_ids
        and "PB-RETURN-TICKET" not in flagged  # the playbook already raised it under the destination country's law
        and not re.search(r"return (air|ticket|flight|passage|journey)|ফেরত আসিবার খরচ", low)
    ):
        ids = [c.id for c in clauses if re.search(r"terminate|air ticket|travel", c.text, re.I)][:3]
        hyps.append(
            {
                "key": "h1", "title_en": "Contract is silent on the cost of the return journey", "title_bn": "দেশে ফেরার খরচ কে দেবে, চুক্তিতে লেখা নেই",
                "category": "absence", "severity": "high", "clause_ids": ids,
                "finding": "The employer may terminate at any time without notice, but the contract never says who pays for the worker's return to Bangladesh.",
                "why_non_obvious": "Each clause looks ordinary; together, termination-at-will plus silence on return travel can strand the worker abroad.",
                "queries": ["বিদেশ হইতে ফেরত আসিবার খরচ কর্মসংস্থান চুক্তি", "employment contract must state cost of travel abroad and return"],
            }
        )
    if re.search(r"penalty", low) and re.search(r"withhold", low) and "bd_migration" in route.pack_ids:
        ids = [c.id for c in clauses if re.search(r"penalty|withhold|recruitment", c.text, re.I)][:3]
        hyps.append(
            {
                "key": "h2", "title_en": "Exit penalty plus withheld wages amounts to debt bondage", "title_bn": "চাকরি ছাড়লে জরিমানা ও বেতন আটকানো: ঋণ-দাসত্বের ঝুঁকি",
                "category": "interaction", "severity": "critical", "clause_ids": ids,
                "finding": "A worker who leaves early must repay recruitment costs plus RM 5,000, and unpaid wages may be withheld until paid.",
                "why_non_obvious": "Read separately these look like ordinary breach terms; combined with recruitment-cost deductions they lock the worker in.",
                "queries": ["জবরদস্তি বা দাসত্বমূলক শ্রম ঋণ-দাস", "forced labour debt bondage offence punishment"],
            }
        )
    if "bd_epz" in route.pack_ids and re.search(r"trade union|multiple unions|collective", low):
        ids = [c.id for c in clauses if re.search(r"union|representation|participation", c.text, re.I)][:2]
        hyps.append(
            {
                "key": "h3", "title_en": "Buyer's multi-union clause cannot be performed inside an EPZ", "title_bn": "ইপিজেডে একাধিক ট্রেড ইউনিয়নের শর্ত পালন করা সম্ভব নয়",
                "category": "regime_conflict", "severity": "high", "clause_ids": ids,
                "finding": "The supply agreement requires recognising multiple trade unions; the factory is in Dhaka EPZ, where workers organise through a single Workers' Welfare Association.",
                "why_non_obvious": "The clause reads as standard human-rights language, but it sets the supplier up for a breach it cannot cure, giving the buyer an immediate termination right (clause 9).",
                "queries": ["শ্রমিক কল্যাণ সমিতি একের অধিক গঠন করা যাইবে না", "ট্রেড ইউনিয়ন গঠন করার অধিকার", "workers welfare association EPZ only one per industrial unit"],
            }
        )
    return {"hypotheses": hyps}


FAKE_GROUNDING = {
    "h1": {
        "citizen_line_en": "The contract does not say who pays for your ticket home.", "citizen_line_bn": "দেশে ফেরার টিকিটের খরচ কে দেবে, চুক্তিতে লেখা নেই।",
        "action_en": "Ask for the employer to pay the return ticket, in writing.", "action_bn": "ফেরার টিকিট মালিক দেবে, এটা লিখে নিন।",
        "mitigation_clause": "The Employer shall bear the cost of the Worker's return air passage to Bangladesh on completion or any earlier termination of this Contract, other than for proven gross misconduct.",
        "claims": [
            {"citation_id": "BD-OEMA-2013-s22", "proposition": "Under OEMA 2013 s.22(1), the employment contract must state the migrant worker's salary, accommodation, term of work, compensation for death or injury, and the cost of travel abroad and return.", "quote": "বিদেশে গমন এবং বিদেশ হইতে ফেরত আসিবার খরচ"},
            {"citation_id": "BD-OEMA-2013-s22", "proposition": "Under OEMA 2013 s.22(2), the recruiting agent is treated as the foreign employer's representative and is jointly and severally liable with the employer under the contract.", "quote": "যৌথ ও পৃথকভাবে দায়ী থাকিবেন"},
        ],
    },
    "h2": {
        "citizen_line_en": "If you leave early you must pay a big penalty and your wages can be held back.", "citizen_line_bn": "আগে চাকরি ছাড়লে বড় জরিমানা দিতে হবে আর বেতন আটকে রাখা হতে পারে।",
        "action_en": "Do not sign an exit penalty. Ask for it to be removed.", "action_bn": "চাকরি ছাড়ার জরিমানার শর্তে সই করবেন না।",
        "mitigation_clause": "The Worker may resign on giving one month's notice. No penalty or recruitment cost shall be recoverable from the Worker, and wages earned shall be paid in full on termination.",
        "claims": [
            # A typical model cites the 2012 Act it was trained on; the currency gate catches that it was repealed.
            {"citation_id": "BD-TRAFFICKING-2012-s9", "proposition": "Compelling a person to provide labour or services through debt bondage, force or any kind of pressure is an offence punishable with rigorous imprisonment of 5 to 12 years.", "quote": None},
        ],
    },
    "h3": {
        "citizen_line_en": "The buyer asks for something the EPZ law does not allow.", "citizen_line_bn": "ক্রেতা এমন শর্ত দিয়েছে যা ইপিজেড আইনে করা যায় না।",
        "action_en": "Rewrite the clause around the EPZ Workers' Welfare Association.", "action_bn": "শর্তটি ইপিজেড শ্রমিক কল্যাণ সমিতি অনুযায়ী লিখুন।",
        "mitigation_clause": "The Supplier shall respect workers' freedom of association to the extent permitted by the Bangladesh EPZ Labour Act 2019, including recognising and engaging in good faith with the Workers' Welfare Association; non-performance caused by mandatory EPZ law shall not be a breach.",
        "claims": [
            {"citation_id": "BD-EPZLABOUR-2019-s100", "proposition": "Under the Bangladesh EPZ Labour Act 2019 s.100, not more than one Workers' Welfare Association may be formed in an industrial unit in a zone.", "quote": "একের অধিক শ্রমিক কল্যাণ সমিতি গঠন করা যাইবে না"},
            {"citation_id": "BD-EPZLABOUR-2019-s94", "proposition": "Under the Bangladesh EPZ Labour Act 2019 s.94(1), workers of an industrial unit in a zone have the right to form and join a Workers' Welfare Association.", "quote": None},
            # The Labour Act's trade-union section is the reflex citation; the router switched that Act off for EPZ.
            {"citation_id": "BD-LABOUR-2006-s176", "proposition": "Under Bangladesh Labour Act 2006 s.176, workers have the right to form and join trade unions of their own choosing.", "quote": None},
        ],
    },
}


def _fake_ground(keys: list[str]) -> dict:
    return {"risks": [{"key": k, "keep": True, **FAKE_GROUNDING[k]} for k in keys if k in FAKE_GROUNDING]}


# ------------------------------------------------------------------ agent


async def run(
    llm: LLM,
    corpus: Corpus,
    clauses: list[Clause],
    facts: DocFacts,
    route: RouteDecision,
    known: list[Risk],
    redact,
    full_text: str,
    start: int,
    emit,
) -> tuple[list[Risk], list[Claim], list[dict]]:
    known_titles = "\n".join(f"- {r.title.en}" for r in known) or "- (none)"
    hyp = await llm.json(
        role="reasoner",
        system=HYPOTHESIS_SYSTEM,
        user=f"FACTS: country={facts.destination_country} epz={facts.is_epz} governing_law={facts.governing_law}\n"
        f"LAW PACKS: {', '.join(sorted(route.pack_ids))}\nALREADY FLAGGED:\n{known_titles}\n\nCLAUSES:\n{_clause_block(clauses, redact)}",
        task="adversary_hypotheses",
        agent="Adversarial Counsel",
        fake=lambda: _fake_hypotheses(clauses, facts, route, full_text, known),
        temperature=0.3,
    )
    hypotheses = [h for h in hyp.get("hypotheses", [])[:3] if h.get("queries")]
    if not hypotheses:
        return [], [], []

    # retrieval: the only source of citable ids. Search the routed packs AND the excluded ones, so the
    # model can be tempted by the wrong regime - the verifier must catch it, which the ledger shows.
    search_packs = route.pack_ids | {p.pack for p in route.excluded}
    candidates: dict[str, dict] = {}
    allowed: set[str] = set()
    for h in hypotheses:
        found = []
        for q in h["queries"][:3]:
            for sec, _ in corpus.search(q, packs=search_packs, k=5):
                found.append(sec)
                for ref in corpus.cross_refs(sec, limit=1):  # recursive: follow "section N" references
                    found.append(ref)
        uniq = list({s.citation_id: s for s in found}.values())[:8]
        candidates[h["key"]] = {"hypothesis": h, "sections": uniq}
        allowed |= {s.citation_id for s in uniq}
        emit(TraceEvent(t=0, type="retrieval", agent="Adversarial Counsel", message=f"{h['title_en']}: {len(uniq)} candidate sections", data={"queries": h["queries"][:3], "hits": [s.citation_id for s in uniq]}))

    # successor provisions of repealed acts are always offered, so a careful model can pick the law in force
    for cid in list(allowed):
        sec = corpus.get(cid)
        if sec and sec.superseded_by:
            succ = corpus.get(f"{sec.superseded_by}-s{sec.section}")
            if succ:
                allowed.add(succ.citation_id)

    ground_input = []
    for key, c in candidates.items():
        h = c["hypothesis"]
        secs = "\n".join(f"  <{s.citation_id}> {s.act_en} s.{s.section} ({s.heading}) [status: {s.status}]: {s.text[:700]}" for s in c["sections"])
        ground_input.append(f"HYPOTHESIS {key}: {h['title_en']}\nFINDING: {h['finding']}\nCANDIDATES:\n{secs}")
    grounded = await llm.json(
        role="reasoner",
        system=GROUND_SYSTEM,
        user="\n\n".join(ground_input),
        task="adversary_ground",
        agent="Adversarial Counsel",
        fake=lambda: _fake_ground(list(candidates)),
        max_tokens=3500,
    )

    risks: list[Risk] = []
    claims: list[Claim] = []
    rejected: list[dict] = []
    n = start
    for g in grounded.get("risks", []):
        c = candidates.get(g.get("key"))
        if not c or not g.get("keep", True):
            continue
        h = c["hypothesis"]
        rid = f"R{n}"
        rclaims = []
        for i, cl in enumerate(g.get("claims", [])):
            cid = str(cl.get("citation_id", "")).strip()
            if cid not in allowed and cid not in {s.citation_id for s in c["sections"]}:
                rejected.append({"risk": h["title_en"], "citation_id": cid, "reason": "not returned by retrieval - cannot be cited"})
                continue
            rclaims.append(Claim(id=f"{rid}.{i + 1}", risk_id=rid, proposition=str(cl.get("proposition", "")), citation_id=cid, quote=cl.get("quote") or None, origin="adversary"))
        if not rclaims:
            continue
        sev = h.get("severity", "medium") if h.get("severity") in ("critical", "high", "medium", "low") else "medium"
        risks.append(
            Risk(
                id=rid,
                rule_id=None,
                origin="adversary",
                category=h.get("category", "other"),
                title=L10n(en=h["title_en"], bn=h.get("title_bn") or h["title_en"]),
                severity=sev,
                clause_ids=[i for i in h.get("clause_ids", []) if any(cl.id == i for cl in clauses)],
                finding=h.get("finding", ""),
                why_non_obvious=h.get("why_non_obvious", ""),
                citizen_line=L10n(en=g.get("citizen_line_en") or h["title_en"], bn=g.get("citizen_line_bn") or h.get("title_bn") or h["title_en"]),
                action=L10n(en=g.get("action_en") or "Ask a lawyer to review this clause.", bn=g.get("action_bn") or "এই শর্তটি আইনজীবীকে দেখান।"),
                mitigation_clause=g.get("mitigation_clause", ""),
                clash="Lawful under the buyer's home law, but it cannot be performed under Bangladesh's mandatory EPZ regime." if h.get("category") == "regime_conflict" else None,
                claim_ids=[cl.id for cl in rclaims],
                confidence=0.7,
            )
        )
        claims += rclaims
        n += 1
    return risks, claims, rejected
