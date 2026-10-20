"""Adversarial Counsel: hunts for risks OUTSIDE the playbook.

Agentic RAG in three steps:
  1. hypothesise  - read the redacted clauses, the risks already found and what the playbook covers; propose new risks
                    (clause interactions, dangerous gaps, wrong-regime traps) with search queries in EN + BN
  2. retrieve     - run each query through hybrid retrieval, restricted to the routed law packs
  3. ground       - for each hypothesis, pick legal support ONLY from the retrieved citation_ids

Long documents are read map -> reduce: the clauses are packed into parts that fit one model call; each part is
hypothesised on its own and also returns a short digest of its material terms; one reduce call then merges the
parts' hypotheses and looks across the digests for interactions between clauses in different parts.

A hypothesis that only restates a playbook risk is dropped in code (and the drop is shown in the trace), so what
remains is genuinely off-playbook. Any citation_id not handed out by retrieval in step 2 is rejected before
verification: the model cannot cite from memory. Everything it proposes still goes through the 4 gates.
"""

from __future__ import annotations

import asyncio
import re

from ain.agents import bench, risk_analyst
from ain.llm import LLM, LLMError
from ain.models import Claim, Clause, DocFacts, L10n, Risk, RouteDecision, TraceEvent
from ain.retrieval import Corpus

CHUNK_CHARS = 8000  # one part of a long document per call: ~2-4k tokens, under Groq's free 8k tokens/minute
MAX_HYPOTHESES = 5
MAX_CANDIDATES = 8  # statute sections offered per hypothesis
CANDIDATE_CHARS = 1000  # of each section's text, windowed on the hypothesis (sub-sections, provisos kept whole)
GROUND_CHARS = 10000  # hypotheses are grounded in batches of about this size
# long documents: what each part may pass up to the reduce step, and the size of one reduce call before it splits
PART_HYPOTHESES = 4
DIGEST_ITEMS = 8
REDUCE_CHARS = 12000

SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
CAT_RANK = {"interaction": 0, "regime_conflict": 1, "absence": 2, "other": 3}

HYPOTHESIS_SYSTEM = """You are opposing counsel reviewing a contract for a Bangladeshi party. A rule-based playbook has
already flagged some risks (listed with their clause ids and findings), and its rule list shows what it covers.
Find up to 6 ADDITIONAL, non-obvious risks it missed. Each must be ONE of:
- "interaction": two or more clauses that are harmless alone but dangerous together. Name at least 2 clause_ids and
  explain the mechanism (what happens to the worker or party step by step).
- "absence": an important term that is MISSING, and why THIS contract's other clauses make the gap dangerous.
- "regime_conflict": a clause that cannot be performed, or is void, under mandatory law of the place it is performed.
Do NOT restate a flagged risk or anything a listed playbook rule covers, and do not give generic advice
("no clause on health insurance") unless a clause here makes that gap harmful.
Personal data is replaced by placeholders. Do not cite any law yet.
If the input says PART i OF n, you see only that part: also return "digest", the material terms of this part
(obligations, money, documents, termination, penalties, forum), at most 10 items of one line each.
Return JSON: {"hypotheses": [{"key": "h1", "title_en": "...", "title_bn": "...", "category": "interaction|absence|regime_conflict",
"severity": "critical|high|medium|low", "clause_ids": ["C7", "C12"], "finding": "what the contract says or omits",
"why_non_obvious": "...", "queries": ["Bangla search query in statutory wording", "English search query"]}],
"digest": [{"clause_id": "C7", "term": "one line"}]}
Most Bangladeshi statutes are in Bangla: ALWAYS give at least one query in formal statutory Bangla (e.g. "পাসপোর্ট আটকাইয়া রাখিলে")."""

REDUCE_SYSTEM = """You are opposing counsel finishing the review of a LONG contract that was read in parts. You get the risks
the playbook already flagged, the candidate hypotheses found in each part, and a digest of the material terms of every
part. Merge hypotheses that describe the same risk, drop any that restate a flagged risk, and ADD interactions between
clauses in DIFFERENT parts that only show up when the digests are read together (name the clause_ids from each part).
Return the best 5, most serious first, in the same schema (keep each hypothesis' queries; at least one in statutory Bangla):
{"hypotheses": [{"key": "...", "title_en": "...", "title_bn": "...", "category": "...", "severity": "...",
"clause_ids": [...], "finding": "...", "why_non_obvious": "...", "queries": [...]}]}"""

GROUND_SYSTEM = """You ground legal risks in statute text. For each hypothesis you get candidate statute sections, each with a
citation_id. Use ONLY citation_ids from the candidates; never invent one. For each hypothesis either drop it (if no candidate
supports it) or return claims: short legal propositions, each supported by ONE section, with an optional verbatim quote
copied exactly from that section's text.
Return JSON: {"risks": [{"key": "h1", "keep": true, "citizen_line_en": "...", "citizen_line_bn": "...", "action_en": "...",
"action_bn": "...", "mitigation_clause": "...", "claims": [{"citation_id": "...", "proposition": "...", "quote": "..."}]}]}"""


def _clause_block(clauses: list[Clause], redact) -> str:
    return "\n\n".join(f"[{c.id}] {redact(c.text)}" for c in clauses)


def chunks(clauses: list[Clause], budget: int = CHUNK_CHARS) -> list[list[Clause]]:
    """Pack whole clauses, in order, into parts of at most `budget` chars (a clause is never cut here; ingestion
    already splits any clause longer than MAX_CLAUSE_CHARS)."""
    parts: list[list[Clause]] = [[]]
    size = 0
    for c in clauses:
        if parts[-1] and size + len(c.text) > budget:
            parts.append([])
            size = 0
        parts[-1].append(c)
        size += len(c.text) + 8
    return [p for p in parts if p]


# ------------------------------------------------------------------ off-playbook filter

_STOP = {"the", "and", "with", "from", "that", "this", "for", "not", "any", "are", "has", "have", "its", "their", "contract",
         "clause", "worker", "workers", "employer", "shall", "will", "may", "without", "under", "into", "than", "which"}


def _terms(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in _STOP}


def duplicate_of(h: dict, known: list[Risk], rules: list[risk_analyst.Rule]) -> str | None:
    """The playbook risk or rule a hypothesis merely restates, or None when it is genuinely new.

    A hypothesis restates a flagged risk when it is about no clause beyond that risk's clauses AND shares at least half
    of the key words of that risk's title. An absence (or single-clause) hypothesis also restates an active playbook
    rule whose title it mostly repeats, even if the rule has not fired yet (fact rules run in parallel with this agent).
    """
    ids = set(h.get("clause_ids") or [])
    words = _terms(f"{h.get('title_en', '')} {h.get('finding', '')}")
    for k in known:
        kt = _terms(k.title.en)
        if kt and (not ids or ids <= set(k.clause_ids)) and len(kt & words) / len(kt) >= 0.5:
            return k.rule_id or k.id
    if h.get("category") == "absence" or len(ids) <= 1:
        head = _terms(h.get("title_en", ""))
        for rule in rules:
            rt = _terms(re.sub(r"\{\w+\}", " ", rule.title["en"]))
            # what the rule is about, in its own words: its title, its question and its fix
            about = rt | _terms(f"{rule.question} {rule.mitigation}")
            if (rt and len(rt & words) / len(rt) >= 0.5) or (len(head) >= 2 and len(head & about) / len(head) >= 0.6):
                return rule.id
    return None


def _clean(h: object) -> dict | None:
    """A model's hypothesis in a safe shape: string title and key, list-of-string clause ids and queries."""
    if not isinstance(h, dict) or not str(h.get("title_en") or "").strip():
        return None

    def strings(v: object) -> list[str]:
        items = v if isinstance(v, list) else [v] if v else []
        return [str(x).strip() for x in items if str(x).strip()]

    return {
        **h,
        "key": str(h.get("key") or "h").strip() or "h",
        "title_en": str(h["title_en"]).strip(),
        "clause_ids": strings(h.get("clause_ids")),
        "queries": strings(h.get("queries")),
        "finding": str(h.get("finding") or ""),
    }


def _rank(h: dict) -> tuple[int, int]:
    return SEV_RANK.get(h.get("severity"), 2), CAT_RANK.get(h.get("category"), 3)


# ------------------------------------------------------------------ deterministic stand-ins for offline/test mode

_BN = re.compile(r"[ঀ-৿]")


def _ids(clauses: list[Clause], pattern: str, n: int = 3) -> list[str]:
    return [c.id for c in clauses if re.search(pattern, c.text, re.I)][:n]


def _fake_hypotheses(clauses: list[Clause], facts: DocFacts, route: RouteDecision, text: str, known: list[Risk]) -> dict:
    low = text.lower()
    packs = route.pack_ids
    hyps = []
    flagged = {r.rule_id for r in known}
    if (
        "bd_migration" in packs
        and "PB-RETURN-TICKET" not in flagged  # the playbook already raised it under the destination country's law
        and not re.search(r"return (air|ticket|flight|passage|journey)|ফেরত আসিবার খরচ", low)
        and re.search(r"terminate", low)
    ):
        hyps.append(
            {
                "key": "h1", "title_en": "Contract is silent on the cost of the return journey", "title_bn": "দেশে ফেরার খরচ কে দেবে, চুক্তিতে লেখা নেই",
                "category": "absence", "severity": "high", "clause_ids": _ids(clauses, r"terminate|air ticket|travel"),
                "finding": "The employer may terminate at any time without notice, but the contract never says who pays for the worker's return to Bangladesh.",
                "why_non_obvious": "Each clause looks ordinary; together, termination-at-will plus silence on return travel can strand the worker abroad.",
                "queries": ["বিদেশ হইতে ফেরত আসিবার খরচ কর্মসংস্থান চুক্তি", "employment contract must state cost of travel abroad and return"],
            }
        )
    if re.search(r"penalty", low) and re.search(r"withhold", low) and "bd_migration" in packs:
        hyps.append(
            {
                "key": "h2", "title_en": "Exit penalty plus withheld wages amounts to debt bondage", "title_bn": "চাকরি ছাড়লে জরিমানা ও বেতন আটকানো: ঋণ-দাসত্বের ঝুঁকি",
                "category": "interaction", "severity": "critical", "clause_ids": _ids(clauses, r"penalty|withhold|recruitment"),
                "finding": "A worker who leaves early must repay recruitment costs plus a fixed penalty, and unpaid wages may be withheld until the sum is paid.",
                "why_non_obvious": "Read separately these look like ordinary breach terms; combined with recruitment-cost deductions they lock the worker in.",
                "queries": ["জবরদস্তি বা দাসত্বমূলক শ্রম ঋণ-দাস", "forced labour debt bondage offence punishment"],
            }
        )
    if "bd_epz" in packs and re.search(r"trade union|multiple unions|collective", low):
        hyps.append(
            {
                "key": "h3", "title_en": "Buyer's multi-union clause cannot be performed inside an EPZ", "title_bn": "ইপিজেডে একাধিক ট্রেড ইউনিয়নের শর্ত পালন করা সম্ভব নয়",
                "category": "regime_conflict", "severity": "high", "clause_ids": _ids(clauses, r"union|representation|participation", 2),
                "finding": "The supply agreement requires recognising multiple trade unions; the factory is in Dhaka EPZ, where workers organise through a single Workers' Welfare Association.",
                "why_non_obvious": "The clause reads as standard human-rights language, but it sets the supplier up for a breach it cannot cure, giving the buyer an immediate termination right (clause 9).",
                "queries": ["শ্রমিক কল্যাণ সমিতি একের অধিক গঠন করা যাইবে না", "ট্রেড ইউনিয়ন গঠন করার অধিকার", "workers welfare association EPZ only one per industrial unit"],
            }
        )
    if (
        "sa_labour" in packs
        and re.search(r"passport[^.]{0,80}(custody|hand over|deposit|keep|retain)|hand over his passport", low)
        and re.search(r"worker shall (pay|bear)[^.]{0,80}(iqama|residence permit)", low)
    ):
        hyps.append(
            {
                "key": "h4", "title_en": "Passport held by the employer while the worker must renew his own iqama", "title_bn": "পাসপোর্ট মালিকের কাছে, অথচ ইকামা নবায়নের দায় কর্মীর",
                "category": "interaction", "severity": "critical", "clause_ids": _ids(clauses, r"passport[^.]{0,80}(custody|hand over|deposit|keep|retain)|hand over his passport|iqama"),
                "finding": "The employer keeps the passport for the whole term, yet the worker must pay to renew the iqama and work permit every year.",
                "why_non_obvious": "Renewal needs the passport the employer holds; if the iqama lapses the worker becomes irregular, cannot change job or leave, and depends entirely on the employer.",
                "queries": ["residence permit iqama renewal fees borne by employer", "foreign worker free to return home identity documents not retained", "অভিবাসী কর্মীর দেশে ফিরিয়া আসিবার অধিকার"],
            }
        )
    if "bd_migration" in packs and re.search(r"shall not (file|bring|lodge) any (complaint|claim|case)", low) and re.search(r"governed by the laws? of", low):
        hyps.append(
            {
                "key": "h5", "title_en": "Foreign governing law plus a ban on complaints in Bangladesh leaves no forum", "title_bn": "বিদেশি আইন আর দেশে অভিযোগ নিষেধ: কোথাও অভিযোগের জায়গা থাকে না",
                "category": "interaction", "severity": "high", "clause_ids": _ids(clauses, r"complaint|governed by"),
                "finding": "The contract is governed only by the destination country's law and forbids any complaint to BMET, the mission or a Bangladeshi court.",
                "why_non_obvious": "Each clause looks like a routine choice of law; together they try to cut the worker off from every Bangladeshi remedy, although the recruiting agency in Dhaka stays jointly liable.",
                "queries": ["রিক্রুটিং এজেন্ট এবং নিয়োগকারী যৌথ ও পৃথকভাবে দায়ী", "কর্মসংস্থান চুক্তি লঙ্ঘনের অভিযোগ সরকারের নিকট উত্থাপন", "migrant worker complaint against recruiting agent breach of employment contract"],
            }
        )
    body = " ".join(c.text for c in clauses)
    if "bd_migration" in packs and re.search(r"পড়িয়া ও বুঝিয়া|পড়িয়া|বুঝিয়া", text) and len(_BN.findall(body)) < 0.2 * len(body):
        hyps.append(
            {
                "key": "h6", "title_en": "Bangla 'read and understood' line, but every term is in English only", "title_bn": "বাংলায় 'পড়ে ও বুঝে সই', অথচ সব শর্ত শুধু ইংরেজিতে",
                "category": "interaction", "severity": "medium", "clause_ids": _ids(clauses, r"[ঀ-৿]{3,}.*স্বাক্ষর|পড়িয়া|বুঝিয়া", 2),
                "finding": "The only Bangla clause is a declaration that the worker read and understood all terms; the terms themselves are in English.",
                "why_non_obvious": "The declaration looks protective, but it is used to prove consent to terms the worker may not be able to read.",
                "queries": ["written contracts in a language that the worker can understand", "কর্মসংস্থান চুক্তি ভাষা কর্মী বুঝিতে পারে"],
            }
        )
    if "bd_epz" in packs and re.search(r"participation committee", low):
        hyps.append(
            {
                "key": "h7", "title_en": "Grievances go only to a committee that EPZ law dissolves", "title_bn": "অভিযোগ শুধু এমন কমিটিতে, যা ইপিজেড আইনে বিলুপ্ত হয়ে যায়",
                "category": "absence", "severity": "medium", "clause_ids": _ids(clauses, r"participation committee|grievance", 2),
                "finding": "The appointment letter sends grievances only to the participation committee and says nothing about the worker's own written grievance procedure.",
                "why_non_obvious": "In an EPZ the participation committee exists only until a Workers' Welfare Association is formed; with the buyer pushing for worker organisation, the only grievance route named can vanish, while the 30-day statutory grievance clock keeps running.",
                "queries": ["অংশগ্রহণকারী কমিটি স্বয়ংক্রিয়ভাবে বিলুপ্ত", "অভিযোগ লিখিত আকারে রেজিস্ট্রি ডাকযোগে মালিকের নিকট", "EPZ worker grievance procedure written complaint"],
            }
        )
    if "bd_epz" in packs and re.search(r"maternity", low) and re.search(r"terminate[^.]{0,80}notice", low):
        hyps.append(
            {
                "key": "h9", "title_en": "Termination on notice could be used to dismiss a pregnant worker", "title_bn": "নোটিশে ছাঁটাইয়ের শর্ত দিয়ে গর্ভবতী কর্মীকে বাদ দেওয়ার ঝুঁকি",
                "category": "interaction", "severity": "high", "clause_ids": _ids(clauses, r"terminate[^.]{0,80}notice|maternity", 2),
                "finding": "Either party may end the job on 30 days' notice, and the letter grants only 12 weeks of maternity leave; nothing protects a pregnant worker from a notice timed before delivery.",
                "why_non_obvious": "Each term looks routine; together they let an employer avoid maternity benefit with a short notice, which the EPZ Act does not allow.",
                "queries": ["মহিলা শ্রমিকের চাকরির অবসানে বাধা প্রসূতি কল্যাণ সুবিধা বঞ্চিত", "EPZ dismissal of woman worker before delivery maternity benefit"],
            }
        )
    return {"hypotheses": hyps}


# digest tags the offline reduce step understands (a live model reads the digests' prose instead)
_DIGEST_TAGS = {
    "passport_retained": r"passport[^.]{0,100}(deposit|custody|retain|keep|surrender)",
    "exit_penalty": r"abscond|leaves? the (worksite|employment)[^.]{0,160}(pay|damages|penalty)",
}


def _fake_digest(clauses: list[Clause]) -> list[dict]:
    out = []
    for c in clauses:
        for tag, pat in _DIGEST_TAGS.items():
            if re.search(pat, c.text, re.I):
                out.append({"clause_id": c.id, "term": c.text[:120].replace("\n", " "), "tag": tag})
    return out


def _fake_map(part: list[Clause], facts: DocFacts, route: RouteDecision, known: list[Risk]) -> dict:
    text = "\n".join(c.text for c in part)
    return {**_fake_hypotheses(part, facts, route, text, known), "digest": _fake_digest(part)}


def _fake_reduce(hyps: list[dict], digests: list[list[dict]]) -> dict:
    out = list(hyps)
    tagged = {d["tag"]: (i, d["clause_id"]) for i, part in enumerate(digests) for d in part if d.get("tag")}
    if {"passport_retained", "exit_penalty"} <= tagged.keys() and tagged["passport_retained"][0] != tagged["exit_penalty"][0]:
        out.insert(
            0,
            {
                "key": "h8", "title_en": "Passport retention plus an absconding penalty traps the worker", "title_bn": "পাসপোর্ট আটকে রাখা আর পালানোর জরিমানা মিলে কর্মী আটকা পড়েন",
                "category": "interaction", "severity": "critical", "clause_ids": [tagged["passport_retained"][1], tagged["exit_penalty"][1]],
                "finding": "One part lets the employer keep the passport; a schedule far later makes a worker who leaves without permission pay a large penalty as an 'absconder'.",
                "why_non_obvious": "The two terms sit in different parts of a long document; only read together do they show the menace of a penalty used to keep a worker who cannot leave.",
                "queries": ["জবরদস্তি বা দাসত্বমূলক শ্রম ঋণ-দাস", "forced or compulsory labour menace of any penalty"],
            },
        )
    return {"hypotheses": out[:MAX_HYPOTHESES]}


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
            {"citation_id": "ILO-CEACR-C029-2021-FL", "proposition": "The ILO Committee of Experts, in its 2021 observation on Bangladesh, urged the Government to ensure that all workers are fully protected from abusive practices and working conditions that amount to forced labour.", "quote": "fully protected from abusive practices and working conditions that amount to forced labour"},
        ],
    },
    "h3": {
        "citizen_line_en": "The buyer asks for something the EPZ law does not allow.", "citizen_line_bn": "ক্রেতা এমন শর্ত দিয়েছে যা ইপিজেড আইনে করা যায় না।",
        "action_en": "Rewrite the clause around the EPZ Workers' Welfare Association.", "action_bn": "শর্তটি ইপিজেড শ্রমিক কল্যাণ সমিতি অনুযায়ী লিখুন।",
        "mitigation_clause": "The Supplier shall respect workers' freedom of association to the extent permitted by the Bangladesh EPZ Labour Act 2019, including recognising and engaging in good faith with the Workers' Welfare Association; non-performance caused by mandatory EPZ law shall not be a breach.",
        "claims": [
            {"citation_id": "BD-EPZLABOUR-2019-s100", "proposition": "Under the Bangladesh EPZ Labour Act 2019 s.100, not more than one Workers' Welfare Association may be formed in an industrial unit in a zone.", "quote": "একের অধিক শ্রমিক কল্যাণ সমিতি গঠন করা যাইবে না"},
            {"citation_id": "BD-EPZLABOUR-2019-s94", "proposition": "Under the Bangladesh EPZ Labour Act 2019 s.94(1), workers of an industrial unit in a zone have the right to form and join a Workers' Welfare Association.", "quote": None},
            {"citation_id": "ILO-CEACR-C087-2023-EPZ", "proposition": "The ILO Committee of Experts, in its 2023 observation on Bangladesh, found that many provisions of the EPZ Labour Act still need to be repealed or substantially amended to conform with Convention No. 87, so a buyer's freedom-of-association clause can collide with the law the supplier must follow.", "quote": "an exceptionally large number of provisions still need to be repealed or substantially amended to ensure the conformity of the ELA with the Convention"},
            # The Labour Act's trade-union section is the reflex citation; the router switched that Act off for EPZ.
            {"citation_id": "BD-LABOUR-2006-s176", "proposition": "Under Bangladesh Labour Act 2006 s.176, workers have the right to form and join trade unions of their own choosing.", "quote": None},
        ],
    },
    "h4": {
        "citizen_line_en": "Your boss keeps your passport, but you must renew your iqama yourself. If it lapses you become illegal.", "citizen_line_bn": "পাসপোর্ট মালিকের কাছে, কিন্তু ইকামা নবায়ন আপনাকে করতে হবে। মেয়াদ গেলে আপনি অবৈধ হয়ে যাবেন।",
        "action_en": "Ask that the employer pays and arranges the iqama renewal, and that you keep your own passport.", "action_bn": "ইকামা নবায়ন মালিক করবে ও খরচ দেবে, আর পাসপোর্ট আপনার কাছে থাকবে, এটা লিখে নিন।",
        "mitigation_clause": "The Employer shall obtain and renew the Worker's iqama and work permit at its own cost before expiry. The Worker shall keep his own passport at all times.",
        "claims": [
            {"citation_id": "SA-LABOR-2005-a40", "proposition": "Under Saudi Labor Law Art. 40(1), the employer bears the fees of the residence permit (iqama) and work permit, their renewal and the fines for late renewal.", "quote": "the fees of the residence permit (Iqama) and work permit together with their renewal and the fines resulting from their delay"},
            {"citation_id": "STD-ILO-FAIR-2019-p12", "proposition": "Under the ILO fair-recruitment principles (para. 12), migrant workers should be free to terminate their employment and return to their country.", "quote": "Workers should be free to terminate their employment and, in the case of migrant workers, to return to their country."},
        ],
    },
    "h5": {
        "citizen_line_en": "The contract tries to stop you complaining anywhere. The agency in Dhaka is still responsible.", "citizen_line_bn": "চুক্তি আপনাকে কোথাও অভিযোগ করতে দিতে চায় না। তবু ঢাকার এজেন্সি দায়ী থাকে।",
        "action_en": "Keep a copy of the contract. You can still complain to the government against the agency.", "action_bn": "চুক্তির কপি রাখুন। এজেন্সির বিরুদ্ধে সরকারের কাছে অভিযোগ করতে পারবেন।",
        "mitigation_clause": "Nothing in this Contract limits the Worker's right to complain to BMET, the Bangladesh mission or any court, and the Recruiting Agency remains jointly and severally liable with the Employer.",
        "claims": [
            {"citation_id": "BD-OEMA-2013-s22", "proposition": "Under OEMA 2013 s.22(2), the recruiting agent is treated as the foreign employer's representative and is jointly and severally liable with the employer under the contract.", "quote": "যৌথ ও পৃথকভাবে দায়ী থাকিবেন"},
            {"citation_id": "BD-OEMA-2013-s41", "proposition": "Under OEMA 2013 s.41(1), without prejudice to the right to sue, an aggrieved person may complain to the government against any person, including a recruiting agent, for breach of the employment contract.", "quote": "কর্মসংস্থান চুক্তি লঙ্ঘনের অভিযোগসহ সংশ্লিষ্ট অন্য যে কোন অভিযোগ উত্থাপন করিতে পারিবে"},
        ],
    },
    "h6": {
        "citizen_line_en": "You sign that you understood everything, but the rules are only in English.", "citizen_line_bn": "আপনি সই করছেন যে সব বুঝেছেন, অথচ শর্তগুলো শুধু ইংরেজিতে।",
        "action_en": "Ask for a full Bangla copy before you sign.", "action_bn": "সই করার আগে পুরো চুক্তির বাংলা কপি চান।",
        "mitigation_clause": "This Contract is executed in Bangla and English; the Worker has received the Bangla text in advance of departure, and in case of doubt the version more favourable to the Worker prevails.",
        "claims": [
            {"citation_id": "STD-ILO-FAIR-2019-p8", "proposition": "Under the ILO fair-recruitment principles (para. 8), a migrant worker's written contract should be in a language the worker can understand and be provided well before departure.", "quote": "written contracts should be in a language that the worker can understand"},
        ],
    },
    "h7": {
        "citizen_line_en": "Your only complaint route is a committee that can disappear.", "citizen_line_bn": "আপনার অভিযোগের একমাত্র পথ এমন কমিটি, যা বিলুপ্ত হয়ে যেতে পারে।",
        "action_en": "Send any complaint in writing to the employer within 30 days, by registered post.", "action_bn": "যেকোনো অভিযোগ ৩০ দিনের মধ্যে লিখে রেজিস্ট্রি ডাকে মালিককে পাঠান।",
        "mitigation_clause": "You may raise any grievance in writing with the Company under section 28 of the Bangladesh EPZ Labour Act 2019, and through the Workers' Welfare Association or, where none exists, the participation committee.",
        "claims": [
            {"citation_id": "BD-EPZLABOUR-2019-s122", "proposition": "Under the EPZ Labour Act 2019 s.122(1), a participation committee may be formed only where no Workers' Welfare Association executive council exists, and it is dissolved automatically once one is formed.", "quote": "অংশগ্রহণকারী কমিটি স্বয়ংক্রিয়ভাবে বিলুপ্ত হইবে"},
            {"citation_id": "BD-EPZLABOUR-2019-s28", "proposition": "Under the EPZ Labour Act 2019 s.28(1), a worker with a grievance must send it in writing to the employer within 30 days of learning of its cause.", "quote": "৩০ (ত্রিশ) দিনের মধ্যে অভিযোগটি লিখিত আকারে রেজিস্ট্রি ডাকযোগে মালিকের নিকট প্রেরণ করিবেন"},
        ],
    },
    "h8": {
        "citizen_line_en": "They keep your passport and fine you if you leave. That is a sign of forced labour.", "citizen_line_bn": "পাসপোর্ট আটকে রাখে আর চলে গেলে জরিমানা করে। এটা জোরপূর্বক শ্রমের লক্ষণ।",
        "action_en": "Do not sign. Ask for both clauses to be removed, or call the labour wing.", "action_bn": "সই করবেন না। দুটি শর্ত বাদ দিতে বলুন, বা শ্রম উইং-এ ফোন করুন।",
        "mitigation_clause": "The Worker keeps his passport. A Worker who leaves the employment owes no penalty, damages or recruitment cost; only wages and benefits earned are settled.",
        "claims": [
            {"citation_id": "ILO-C029-a2", "proposition": "Under ILO C29 Art. 2(1), forced labour is work exacted from a person under the menace of any penalty and for which the person has not offered himself voluntarily.", "quote": "exacted from any person under the menace of any penalty"},
            {"citation_id": "BD-TRAFFICKING-2026-s9", "proposition": "Under the Trafficking Act 2026 s.9, compelling a person to provide labour or services, or holding a person in debt bondage, is an offence punishable with 5 to 12 years' rigorous imprisonment.", "quote": "ঋণ-দাস করিয়া রাখেন"},
            {"citation_id": "ILO-CEACR-C029-2021-FL", "proposition": "The ILO Committee of Experts, in its 2021 observation on Bangladesh, urged the Government to ensure that all workers are fully protected from abusive practices and working conditions that amount to forced labour.", "quote": "fully protected from abusive practices and working conditions that amount to forced labour"},
        ],
    },
    "h9": {
        "citizen_line_en": "If you get pregnant, a notice cannot take away your maternity pay.", "citizen_line_bn": "গর্ভবতী হলে নোটিশ দিয়ে আপনার প্রসূতি সুবিধা কেড়ে নেওয়া যায় না।",
        "action_en": "Keep proof of your pregnancy date. A notice in the 6 months before delivery does not cancel your maternity benefit.", "action_bn": "গর্ভধারণের তারিখের প্রমাণ রাখুন। প্রসবের আগের ৬ মাসে নোটিশ দিলেও প্রসূতি সুবিধা বাতিল হয় না।",
        "mitigation_clause": "No notice of termination shall be given to a woman worker during the six months before or eight weeks after delivery except for sufficient cause, and her maternity benefit shall be paid in full in any case.",
        "claims": [
            {"citation_id": "BD-EPZLABOUR-2019-s34", "proposition": "Under the EPZ Labour Act 2019 s.34, if the employer gives notice ending a woman worker's job within 6 months before or 8 weeks after delivery without sufficient cause, she is not deprived of the maternity benefit she would otherwise have received.", "quote": "উহা হইতে তিনি বঞ্চিত হইবেন না"},
        ],
    },
}


def _fake_ground(keys: list[str]) -> dict:
    return {"risks": [{"key": k, "keep": True, **FAKE_GROUNDING[k]} for k in keys if k in FAKE_GROUNDING]}


# ------------------------------------------------------------------ agent


def _known_block(known: list[Risk], rules: list[risk_analyst.Rule]) -> str:
    flagged = "\n".join(f"- {r.rule_id or r.id} [{', '.join(r.clause_ids)}] {r.title.en}: {r.finding[:200]}" for r in known) or "- (none)"
    covered = "\n".join(f"- {r.id}: {re.sub(r'\{\w+\}', '…', r.title['en'])}" for r in rules) or "- (none)"
    return f"ALREADY FLAGGED:\n{flagged}\nPLAYBOOK RULES (already covered, do not repeat):\n{covered}"


async def _hypothesise(llm: LLM, clauses, facts, route, known, rules, redact, full_text: str, emit) -> list[dict]:
    head = (
        f"FACTS: country={facts.destination_country} epz={facts.is_epz} governing_law={facts.governing_law}\n"
        f"LAW PACKS: {', '.join(sorted(route.pack_ids))}\n{_known_block(known, rules)}"
    )
    parts = chunks(clauses)
    if len(parts) == 1:
        try:
            hyp = await llm.json(
                role="reasoner",
                system=HYPOTHESIS_SYSTEM,
                user=f"{head}\n\nCLAUSES:\n{_clause_block(clauses, redact)}",
                task="adversary_hypotheses",
                agent="Adversarial Counsel",
                fake=lambda: _fake_hypotheses(clauses, facts, route, full_text, known),
                temperature=0.3,
            )
        except LLMError as e:  # the playbook's findings still stand; say that this agent could not run
            emit(TraceEvent(t=0, type="agent_progress", agent="Adversarial Counsel", message=f"Could not run: {str(e)[:160]}", data={"skipped": True}))
            return []
        return [h for h in hyp.get("hypotheses") or [] if isinstance(h, dict)]

    # map: each part on its own, plus a digest of its material terms
    emit(TraceEvent(t=0, type="agent_progress", agent="Adversarial Counsel", message=f"Long document: reading {len(parts)} parts separately, then across parts", data={"parts": len(parts), "clauses": len(clauses)}))

    async def read_part(i: int, p: list[Clause]) -> dict:
        try:
            return await llm.json(
                role="reasoner",
                system=HYPOTHESIS_SYSTEM,
                user=f"{head}\n\nPART {i + 1} OF {len(parts)} (clauses {p[0].id}-{p[-1].id}):\n{_clause_block(p, redact)}",
                task="adversary_map",
                agent="Adversarial Counsel",
                fake=lambda: _fake_map(p, facts, route, known),
                temperature=0.3,
                max_tokens=3000,
            )
        except LLMError as e:  # one unreadable part must not sink the whole analysis; the trace says what was skipped
            emit(TraceEvent(t=0, type="agent_progress", agent="Adversarial Counsel", message=f"Part {i + 1} of {len(parts)} could not be read: {str(e)[:160]}", data={"part": i + 1, "skipped": True}))
            return {}

    answers = await asyncio.gather(*(read_part(i, p) for i, p in enumerate(parts)))
    by_part: list[list[dict]] = []
    titles: set[str] = set()
    keys: set[str] = set()
    digests: list[list[dict]] = []
    for i, a in enumerate(answers):
        digests.append([d for d in (a.get("digest") or []) if isinstance(d, dict)][:DIGEST_ITEMS])
        mine = []
        for h in map(_clean, a.get("hypotheses") or []):
            if h is None or h["title_en"].lower() in titles:
                continue  # the same risk seen from two parts
            titles.add(h["title_en"].lower())
            key = h["key"]
            if key in keys:  # models number each part h1, h2, ... from scratch
                key = f"p{i + 1}{key}"
            keys.add(key)
            mine.append({**h, "key": key})
        by_part.append(sorted(mine, key=_rank)[:PART_HYPOTHESES])
    found = [h for part in by_part for h in part]
    try:
        out = await _reduce(llm, head, by_part, digests)
    except LLMError as e:
        emit(TraceEvent(t=0, type="agent_progress", agent="Adversarial Counsel", message=f"Cross-part review failed, keeping each part's own findings: {str(e)[:160]}", data={"skipped": True}))
        out = []
    return out or found  # a reduce that returns nothing keeps the parts' own hypotheses


def _reduce_block(by_part: list[list[dict]], digests: list[list[dict]]) -> str:
    cand = "\n".join(
        f"- key={h['key']} [{', '.join(h['clause_ids'])}] ({h.get('category')}, {h.get('severity')}) {h['title_en']}: {h['finding'][:240]} QUERIES: {' | '.join(q[:120] for q in h['queries'][:2])}"
        for part in by_part
        for h in part
    ) or "- (none)"
    digest = "\n".join(
        f"PART {i + 1}: " + "; ".join(f"[{d.get('clause_id')}] {str(d.get('term', ''))[:110]}" for d in part) for i, part in enumerate(digests)
    )
    return f"CANDIDATE HYPOTHESES FROM THE PARTS:\n{cand}\n\nDIGEST OF EVERY PART:\n{digest}"


async def _reduce(llm: LLM, head: str, by_part: list[list[dict]], digests: list[list[dict]]) -> list[dict]:
    """Merge the parts' hypotheses and look across their digests. If that would not fit one call (a very long
    document), reduce each half first and then the two halves' results: a recursive decomposition whose every call
    stays under Groq's per-minute token budget, while each level still sees a digest of every part below it."""
    block = _reduce_block(by_part, digests)
    if len(block) > REDUCE_CHARS and len(by_part) > 2:
        mid = len(by_part) // 2
        left, right = await asyncio.gather(_reduce(llm, head, by_part[:mid], digests[:mid]), _reduce(llm, head, by_part[mid:], digests[mid:]))
        # one level up each half is a single "part": its merged hypotheses and the first items of each digest below it
        halves = [[d for part in digests[:mid] for d in part[:3]], [d for part in digests[mid:] for d in part[:3]]]
        return await _reduce(llm, head, [[c for c in map(_clean, left) if c], [c for c in map(_clean, right) if c]], halves)
    flat = [h for part in by_part for h in part]
    merged = await llm.json(
        role="reasoner",
        system=REDUCE_SYSTEM,
        user=f"{head}\n\n{block[: REDUCE_CHARS + 4000]}",
        task="adversary_reduce",
        agent="Adversarial Counsel",
        fake=lambda: _fake_reduce(flat, digests),
        temperature=0.2,
        max_tokens=3000,
    )
    return [h for h in merged.get("hypotheses") or [] if isinstance(h, dict)] or flat


def _ground_batches(candidates: dict[str, dict]) -> list[list[str]]:
    batches: list[list[str]] = [[]]
    size = 0
    for key, c in candidates.items():
        n = sum(len(s["text"]) for s in c["shown"]) + 400
        if batches[-1] and size + n > GROUND_CHARS:
            batches.append([])
            size = 0
        batches[-1].append(key)
        size += n
    return [b for b in batches if b]


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
    rules = [r for r in risk_analyst.load_rules() if r.active(route.pack_ids)]
    raw = await _hypothesise(llm, clauses, facts, route, known, rules, redact, full_text, emit)

    # keep only what is genuinely off-playbook, most serious first
    hypotheses: list[dict] = []
    keys: set[str] = set()
    for h in map(_clean, raw):
        if h is None or not h["queries"]:
            continue
        while h["key"] in keys:  # grounding answers are matched back by key, so keys must be unique
            h["key"] += "x"
        keys.add(h["key"])
        dup = duplicate_of(h, known, rules)
        if dup:
            emit(TraceEvent(t=0, type="hypothesis_dropped", agent="Adversarial Counsel", message=f"{h['title_en']}: restates playbook {dup}", data={"duplicate_of": dup, "title": h["title_en"]}))
            continue
        hypotheses.append(h)
    hypotheses = sorted(hypotheses, key=_rank)[:MAX_HYPOTHESES]
    if not hypotheses:
        return [], [], []

    # retrieval: the only source of citable ids. Search the routed packs AND the excluded ones, so the
    # model can be tempted by the wrong regime - the verifier must catch it, which the ledger shows.
    search_packs = route.pack_ids | {p.pack for p in route.excluded}
    candidates: dict[str, dict] = {}
    allowed: set[str] = set()
    for h in hypotheses:
        per_query = []
        for q in h["queries"][:3]:
            hits = []
            for sec, _ in corpus.search(q, packs=search_packs, k=5):
                hits.append(sec)
                hits += corpus.cross_refs(sec, limit=1)  # recursive: follow "section N" references
            per_query.append(hits)
        # take the queries' results in turn, so each angle (Bangla statute, English, standards) gets a place
        found = [hits[i] for i in range(max(map(len, per_query), default=0)) for hits in per_query if i < len(hits)]
        uniq = list({s.citation_id: s for s in found}.values())[:MAX_CANDIDATES]
        # the grounding model reads each candidate windowed on this hypothesis, not just its first lines
        focus = f"{h['title_en']} {h.get('finding', '')}"
        shown = [{"section": s, "text": bench.window(s.text, focus, CANDIDATE_CHARS)} for s in uniq]
        candidates[h["key"]] = {"hypothesis": h, "sections": uniq, "shown": shown}
        allowed |= {s.citation_id for s in uniq}
        emit(TraceEvent(t=0, type="retrieval", agent="Adversarial Counsel", message=f"{h['title_en']}: {len(uniq)} candidate sections", data={"queries": h["queries"][:3], "hits": [s.citation_id for s in uniq]}))

    # successor provisions of repealed acts are always offered, so a careful model can pick the law in force
    for cid in list(allowed):
        sec = corpus.get(cid)
        if sec and sec.superseded_by:
            succ = corpus.get(f"{sec.superseded_by}-s{sec.section}")
            if succ:
                allowed.add(succ.citation_id)

    def ground_input(keys: list[str]) -> str:
        out = []
        for key in keys:
            c = candidates[key]
            h = c["hypothesis"]
            secs = "\n".join(f"  <{x['section'].citation_id}> {x['section'].act_en} s.{x['section'].section} ({x['section'].heading}) [status: {x['section'].status}]: {x['text']}" for x in c["shown"])
            out.append(f"HYPOTHESIS {key}: {h['title_en']}\nFINDING: {h.get('finding', '')}\nCANDIDATES:\n{secs}")
        return "\n\n".join(out)

    async def ground(keys: list[str]) -> dict:
        try:
            return await llm.json(
                role="reasoner",
                system=GROUND_SYSTEM,
                user=ground_input(keys),
                task="adversary_ground",
                agent="Adversarial Counsel",
                fake=lambda: _fake_ground(keys),
                max_tokens=3500,
            )
        except LLMError as e:  # these hypotheses stay unproven and are not shown; the others still go on
            emit(TraceEvent(t=0, type="agent_progress", agent="Adversarial Counsel", message=f"Could not ground {', '.join(keys)}: {str(e)[:160]}", data={"skipped": keys}))
            return {}

    answers = await asyncio.gather(*(ground(keys) for keys in _ground_batches(candidates)))

    risks: list[Risk] = []
    claims: list[Claim] = []
    rejected: list[dict] = []
    n = start
    for g in (g for a in answers for g in a.get("risks", [])):
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
