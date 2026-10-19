"""Policy Check: does the contract break the employer's OWN policy?

The policy is either a handbook the user uploaded or the company's published policy from
corpus/companies.yaml. Its clauses are citable sections (POLICY-c3, CO-<SLUG>-2). A contradiction
becomes a risk whose claim quotes the policy, so the 4-gate verifier proves the policy really says
it (G2 fidelity) and that the proposition follows from it (G3) - the model cannot invent a promise.

Wording stays factual: "The employer's policy says X; this contract says Y." No other claims are
made about the company.
"""

from __future__ import annotations

import re
from datetime import date

from ain.agents.risk_analyst import load_rules
from ain.llm import LLM
from ain.models import Claim, Clause, L10n, Risk, Section

POLICY_PACK = "employer_policy"
POLICY_LABEL = "Employer's own policy (uploaded)"

SYSTEM = """You compare an employment contract with the employer's OWN policy (code of conduct, recruitment policy or
handbook). Personal data is replaced by placeholders. Find places where the contract breaks a promise the policy makes
to workers (fees, passports, wages, deductions, travel home, working hours, complaints, termination...).
Only report real contradictions. "policy_quote" must be copied EXACTLY, word for word, from ONE policy clause.
Return JSON: {"contradictions": [{"policy_clause_id": "P2", "contract_clause_ids": ["C3"], "policy_quote": "...",
"topic_en": "recruitment fees", "topic_bn": "নিয়োগ ফি", "finding": "what the contract says instead",
"severity": "critical|high|medium", "citizen_line_en": "...", "citizen_line_bn": "...", "action_en": "...", "action_bn": "..."}]}"""

# Offline / test mode: promises a policy commonly makes, matched against the playbook rule for the opposite term.
TOPICS = [
    dict(
        rule="PB-RECRUIT-FEE",
        policy=r"no (worker|employee|candidate|jobseeker)s?[^.]{0,40}(pay|be charged|bear)[^.]{0,60}(fee|cost)|(employer|company|group)[^.]{0,40}(bear|pay|cover|meet)s?[^.]{0,80}(recruit|placement|visa|agency)[^.]{0,40}(fee|cost|expense|charge)|zero[- ](fee|cost recruitment)|no recruitment fee",
        topic=L10n(en="recruitment fees", bn="নিয়োগ ফি"),
        citizen=L10n(
            en="The company's own policy says workers pay no recruitment fees, but this contract makes you pay them.",
            bn="কোম্পানির নিজের নীতিতেই বলা আছে কর্মী কোনো নিয়োগ ফি দেবে না, কিন্তু এই চুক্তি আপনার কাছ থেকে খরচ নিচ্ছে।",
        ),
        action=L10n(en="Show the agency the company's own policy and ask for the fee deduction to be removed.", bn="কোম্পানির নীতিটি এজেন্সিকে দেখিয়ে ফি কাটার শর্ত বাদ দিতে বলুন।"),
    ),
    dict(
        rule="PB-PASSPORT",
        policy=r"(not|never)[^.]{0,30}(hold|keep|retain|confiscate)[^.]{0,40}(passport|identity document)|(passport|identity document)s?[^.]{0,60}(remain|kept|stay)s?[^.]{0,30}(with|in the possession of) the (worker|employee)|keep their passports themselves|full custody of their (respective )?passports",
        topic=L10n(en="passports", bn="পাসপোর্ট"),
        citizen=L10n(
            en="The company's own policy says you keep your passport, but this contract lets them hold it.",
            bn="কোম্পানির নিজের নীতিতেই বলা আছে পাসপোর্ট আপনার কাছে থাকবে, কিন্তু চুক্তি বলছে তারা রেখে দেবে।",
        ),
        action=L10n(en="Point to the company's own passport rule and ask for this clause to be removed.", bn="কোম্পানির নিজের পাসপোর্ট নিয়মটি দেখিয়ে এই শর্ত বাদ দিতে বলুন।"),
    ),
    dict(
        rule="PB-RETURN-TICKET",
        policy=r"(return|homeward|repatriation)[^.]{0,40}(ticket|air ?fare|passage|travel|journey)[^.]{0,80}(employer|company)|(employer|company)[^.]{0,60}(bear|pay|provide|cover)s?[^.]{0,60}(return|repatriation)",
        topic=L10n(en="the ticket home", bn="দেশে ফেরার টিকিট"),
        citizen=L10n(
            en="The company's own policy says it pays for your ticket home, but this contract makes you pay.",
            bn="কোম্পানির নিজের নীতিতেই বলা আছে দেশে ফেরার টিকিট কোম্পানি দেবে, কিন্তু চুক্তিতে খরচ আপনার।",
        ),
        action=L10n(en="Ask for the company-paid return ticket from its own policy to be written into the contract.", bn="কোম্পানির নীতিমতো ফেরার টিকিট কোম্পানি দেবে, এটা চুক্তিতে লিখে নিন।"),
    ),
    dict(
        rule="PB-END-OF-SERVICE",
        policy=r"(end[- ]of[- ]service|gratuity|leaving indemnity)[^.]{0,80}(paid|pay|entitled|receive)|(receive|paid|entitled to)s?[^.]{0,40}(end[- ]of[- ]service|gratuity|leaving indemnity)",
        topic=L10n(en="the end-of-service gratuity", bn="চাকরি শেষের গ্র্যাচুইটি"),
        citizen=L10n(
            en="The company's own policy promises an end-of-service payment, but this contract takes it away.",
            bn="কোম্পানির নিজের নীতিতেই চাকরি শেষের পাওনা দেওয়ার কথা, কিন্তু চুক্তি তা কেড়ে নিচ্ছে।",
        ),
        action=L10n(en="Ask for the gratuity promised in the company's policy to be put back.", bn="কোম্পানির নীতিতে যে গ্র্যাচুইটির কথা আছে, তা চুক্তিতে ফিরিয়ে আনতে বলুন।"),
    ),
    dict(
        rule="PB-CLAIM-WAIVER",
        policy=r"(right to|may|can|free to)[^.]{0,40}(complain|raise (a )?grievance|report)[^.]{0,80}(without|no)[^.]{0,20}(retaliation|reprisal)",
        topic=L10n(en="the right to complain", bn="অভিযোগ করার অধিকার"),
        citizen=L10n(
            en="The company's own policy says you may complain without fear, but this contract bars complaints.",
            bn="কোম্পানির নিজের নীতিতেই নির্ভয়ে অভিযোগ করার অধিকার আছে, কিন্তু চুক্তি তা নিষেধ করছে।",
        ),
        action=L10n(en="Remind the agency that the company's own policy protects complaints.", bn="এজেন্সিকে মনে করিয়ে দিন, কোম্পানির নিজের নীতিই অভিযোগের অধিকার দেয়।"),
    ),
]

SENTENCE = re.compile(r"[^.!?।\n]+[.!?।]?")


def sections_from_clauses(clauses: list[Clause], name: str, source: str) -> list[Section]:
    """Turn an uploaded (already redacted) policy into citable, job-local sections POLICY-c1, POLICY-c2, ..."""
    today = date.today().isoformat()
    out = []
    for c in clauses:
        num = c.index + 1  # people count clauses from 1
        heading = re.sub(r"\s+", " ", c.text).strip()
        out.append(
            Section(
                citation_id=f"POLICY-c{num}", jurisdiction="EMPLOYER", act_key="POLICY", act=f"Employer policy: {name}",
                act_en=f"Employer policy: {name}", year=date.today().year, section=str(num),
                heading=heading[:80] + ("…" if len(heading) > 80 else ""), text=c.text,
                lang="bn" if re.search(r"[ঀ-৿]", c.text) else "en", url="", act_url="", source=source,
                retrieved_at=today, packs=[POLICY_PACK], kind="company_policy",
            )
        )
    return out


def _policy_ids(sections: list[Section]) -> dict[str, Section]:
    """Short ids the model sees for policy clauses: P1, P2, ... (contract clauses are C1, C2, ...)."""
    return {f"P{i + 1}": s for i, s in enumerate(sections)}


def _fake(contract: list[Clause], short: dict[str, Section]) -> dict:
    rules = {r.id: r for r in load_rules()}
    found = []
    for t in TOPICS:
        pats = [re.compile(p, re.I | re.S) for p in rules[t["rule"]].trigger.get("regex", [])]
        hits = [c.id for c in contract if any(p.search(c.text) for p in pats)]
        if not hits:
            continue
        for pid, sec in short.items():
            m = re.search(t["policy"], sec.text, re.I | re.S)
            if not m:
                continue
            quote = next((s.group(0).strip() for s in SENTENCE.finditer(sec.text) if s.start() <= m.start() < s.end()), m.group(0))
            found.append(
                {
                    "policy_clause_id": pid, "contract_clause_ids": hits[:2], "policy_quote": quote,
                    "topic_en": t["topic"].en, "topic_bn": t["topic"].bn, "severity": "high",
                    "finding": "",
                    "citizen_line_en": t["citizen"].en, "citizen_line_bn": t["citizen"].bn,
                    "action_en": t["action"].en, "action_bn": t["action"].bn,
                }
            )
            break
    return {"contradictions": found}


async def run(
    llm: LLM, contract: list[Clause], sections: list[Section], redact, start: int, source_label: str = "own policy"
) -> tuple[list[Risk], list[Claim]]:
    """`sections` are the policy's clauses (uploaded or published); `source_label` names them in findings."""
    if not sections:
        return [], []
    short = _policy_ids(sections)
    policy_block = "\n\n".join(f"[{pid}] {s.text}" for pid, s in short.items())
    contract_block = "\n\n".join(f"[{c.id}] {redact(c.text)}" for c in contract)
    data = await llm.json(
        role="reasoner",
        system=SYSTEM,
        user=f"EMPLOYER POLICY ({source_label}):\n{policy_block}\n\nCONTRACT:\n{contract_block}",
        task="policy_check",
        agent="Policy Check",
        fake=lambda: _fake(contract, short),
    )
    contract_ids = {c.id for c in contract}
    risks: list[Risk] = []
    claims: list[Claim] = []
    n = start
    for item in data.get("contradictions", [])[:6]:
        sec = short.get(str(item.get("policy_clause_id")))
        quote = str(item.get("policy_quote") or "").strip()
        if sec is None or not quote:
            continue  # nothing to verify against: never show an unsupported "the policy says"
        rid = f"R{n}"
        ids = [i for i in item.get("contract_clause_ids") or [] if i in contract_ids]
        where = f"clause {ids[0]}" if ids else "the contract"
        topic = L10n(en=str(item.get("topic_en") or "a policy promise"), bn=str(item.get("topic_bn") or item.get("topic_en") or "নীতির প্রতিশ্রুতি"))
        claim = Claim(
            id=f"{rid}.1", risk_id=rid, citation_id=sec.citation_id, quote=quote, origin="policy",
            proposition=f"The employer's {source_label} states: \"{quote}\"",
        )
        risks.append(
            Risk(
                id=rid, origin="policy", category="policy_contradiction",
                severity=item.get("severity") if item.get("severity") in ("critical", "high", "medium") else "high",
                title=L10n(en=f"Contract breaks the employer's own policy on {topic.en}", bn=f"{topic.bn}: চুক্তি কোম্পানির নিজের নীতি ভাঙছে"),
                clause_ids=ids,
                finding=f"The employer's {source_label} says: “{quote}” This contract ({where}) says otherwise. {str(item.get('finding') or '').strip()}".strip(),
                why_non_obvious="The employer has already promised better terms in its own policy, which gives the worker or their lawyer strong leverage to get this clause changed.",
                citizen_line=L10n(
                    en=str(item.get("citizen_line_en") or f"The company's own policy promises better terms on {topic.en} than this contract."),
                    bn=str(item.get("citizen_line_bn") or f"{topic.bn} নিয়ে কোম্পানির নিজের নীতি এই চুক্তির চেয়ে ভালো শর্ত দেয়।"),
                ),
                action=L10n(
                    en=str(item.get("action_en") or "Show the agency the company's own policy and ask for this clause to match it."),
                    bn=str(item.get("action_bn") or "কোম্পানির নীতিটি এজেন্সিকে দেখিয়ে শর্তটি নীতির মতো করতে বলুন।"),
                ),
                mitigation_clause=f"Amend {where} so that it matches the Employer's own policy: “{quote}”",
                claim_ids=[claim.id],
            )
        )
        claims.append(claim)
        n += 1
    return risks, claims
