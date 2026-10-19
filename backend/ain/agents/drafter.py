"""Memo Drafter + citizen view.

The drafter writes IRAC analysis but may cite ONLY citation_ids that passed verification for
that risk. Anything else it emits is stripped and logged (the Critic's rule). The citizen
cards are assembled deterministically from verified risks - no free text reaches the worker
without a verified citation behind it.
"""

from __future__ import annotations

from ain.llm import LLM
from ain.models import (
    SEVERITY_ORDER,
    CitizenCard,
    CitizenCitation,
    CitizenView,
    DocFacts,
    L10n,
    Memo,
    MemoIssue,
    Risk,
    RouteDecision,
    TraceEvent,
    Verification,
    WageCalc,
)
from ain.naming import EN_TO_BN_DIGITS, label

DRAFT_SYSTEM = """You are a senior Bangladeshi lawyer writing a legal risk memorandum in IRAC form.
For each risk you get the finding and the VERIFIED legal propositions with their citation_ids.
Rules: cite ONLY the citation_ids listed under that risk; never mention any other statute or section number;
be precise and practical. Also write a 3-4 sentence executive summary in English, a 2-3 sentence summary in plain
Bangla, and a short, polite letter (Bangla and English) from the weaker party asking for the listed changes.
Return JSON: {"executive_summary": "...", "summary_bn": "...",
"issues": [{"risk_id": "R1", "issue": "...", "rule": "...", "application": "...", "conclusion": "...", "citation_ids": ["..."]}],
"letter_bn": "...", "letter_en": "..."}"""


def _bn(n: float | int) -> str:
    return f"{n:,.0f}".translate(EN_TO_BN_DIGITS)


def _good(ledger: list[Verification], risk_id: str) -> list[Verification]:
    return [v for v in ledger if v.claim.risk_id == risk_id and v.verdict in ("verified", "partial") and v.section is not None]


def _template_issue(r: Risk, good: list[Verification]) -> dict:
    return {
        "risk_id": r.id,
        "issue": f"{r.title.en}. {r.finding}",
        "rule": " ".join(v.claim.proposition for v in good),
        "application": f"{r.finding} {r.why_non_obvious}".strip(),
        "conclusion": f"Risk rated {r.severity}. {('Recommended clause: ' + r.mitigation_clause) if r.mitigation_clause else 'Seek amendment before signing.'}",
        "citation_ids": [v.claim.citation_id for v in good],
    }


def _template_letter(risks: list[Risk], ledger: list[Verification], migrant: bool) -> tuple[str, str]:
    to_en = "To the Recruiting Agency / Employer" if migrant else "To the Buyer"
    to_bn = "বরাবর, রিক্রুটিং এজেন্সি / নিয়োগকর্তা" if migrant else "বরাবর, ক্রেতা প্রতিষ্ঠান"
    en = [f"{to_en},", "", "Before signing, I request the following changes to the contract:"]
    bn = [to_bn, "", "চুক্তিতে সই করার আগে নিচের শর্তগুলো বদলানোর অনুরোধ করছি:"]
    for i, r in enumerate(risks[:5], 1):
        good = _good(ledger, r.id)
        cite = label(good[0].section) if good else None
        en.append(f"{i}. {r.action.en}" + (f" ({cite.en})" if cite else ""))
        bn.append(f"{str(i).translate(EN_TO_BN_DIGITS)}. {r.action.bn}" + (f" ({cite.bn})" if cite else ""))
    en += ["", "Thank you. I look forward to the corrected contract."]
    bn += ["", "ধন্যবাদ। সংশোধিত চুক্তির অপেক্ষায় রইলাম।"]
    return "\n".join(bn), "\n".join(en)


async def draft(
    llm: LLM, doc_name: str, facts: DocFacts, route: RouteDecision, risks: list[Risk], ledger: list[Verification], wage: WageCalc | None, emit
) -> tuple[Memo, L10n]:
    live = sorted([r for r in risks if r.status != "dropped"], key=lambda r: SEVERITY_ORDER[r.severity])
    migrant = "bd_migration" in route.pack_ids
    allowed = {r.id: {v.claim.citation_id for v in _good(ledger, r.id)} for r in live}

    blocks = []
    for r in live:
        props = "\n".join(f"   - <{v.claim.citation_id}> {v.claim.proposition}" for v in _good(ledger, r.id))
        blocks.append(f"{r.id} [{r.severity}] {r.title.en}\n FINDING: {r.finding}\n WHY NON-OBVIOUS: {r.why_non_obvious}\n VERIFIED LAW:\n{props}\n SUGGESTED CLAUSE: {r.mitigation_clause}")
    if wage:
        blocks.append(f"WAGE: promised {wage.currency} {wage.promised:,.0f}; deductions {wage.monthly_deductions:,.0f}/month ({wage.pct_deducted}%); in hand {wage.net:,.0f}.")

    letter_bn, letter_en = _template_letter(live, ledger, migrant)

    def fake() -> dict:
        crit = sum(1 for r in live if r.severity in ("critical", "high"))
        return {
            "executive_summary": f"The document contains {len(live)} verified compliance risks, {crit} of them high or critical. "
            + " ".join(f"{r.title.en}." for r in live[:3])
            + " Each conclusion below rests only on statute text that passed all verification gates.",
            "summary_bn": f"চুক্তিতে {_bn(len(live))}টি যাচাইকৃত ঝুঁকি পাওয়া গেছে, এর মধ্যে {_bn(crit)}টি গুরুতর। সই করার আগে এগুলো ঠিক করান।",
            "issues": [_template_issue(r, _good(ledger, r.id)) for r in live],
            "letter_bn": letter_bn,
            "letter_en": letter_en,
        }

    data = await llm.json(role="reasoner", system=DRAFT_SYSTEM, user="\n\n".join(blocks) or "No risks.", task="draft_memo", agent="Memo Drafter", fake=fake, max_tokens=4000)

    issues: list[MemoIssue] = []
    seen: set[str] = set()
    for item in data.get("issues", []):
        rid = item.get("risk_id")
        if rid not in allowed or rid in seen:
            continue
        cited = [c for c in item.get("citation_ids", []) if c in allowed[rid]]
        stray = [c for c in item.get("citation_ids", []) if c not in allowed[rid]]
        if stray:
            emit(TraceEvent(t=0, type="critic", agent="Critic", message=f"Stripped unverified citation(s) {', '.join(stray)} from the memo for {rid}", data={"risk_id": rid, "stripped": stray}))
        r = next(x for x in live if x.id == rid)
        issues.append(
            MemoIssue(
                risk_id=rid, heading=r.title.en, issue=str(item.get("issue", "")), rule=str(item.get("rule", "")),
                application=str(item.get("application", "")), conclusion=str(item.get("conclusion", "")),
                citation_ids=cited or sorted(allowed[rid]), mitigation_clause=r.mitigation_clause,
            )
        )
        seen.add(rid)
    for r in live:  # the model skipped a risk: fall back to the deterministic IRAC
        if r.id not in seen:
            t = _template_issue(r, _good(ledger, r.id))
            issues.append(MemoIssue(heading=r.title.en, mitigation_clause=r.mitigation_clause, **t))
    issues.sort(key=lambda i: SEVERITY_ORDER[next(r.severity for r in live if r.id == i.risk_id)])

    excluded = " ".join(p.reason for p in route.excluded)
    caveats = [
        "Decision support, not legal advice. Consult a licensed advocate before acting.",
        "Statute text is the consolidated text retrieved from official sources on the date shown in the ledger.",
    ]
    if any(v.verdict == "partial" for v in ledger):
        caveats.append("Items marked partial rely on amended provisions or paraphrases; check the cited source.")
    if any(r.bench and r.bench.human_review for r in live):
        caveats.append("The Virtual Bench flagged at least one risk for human review (the judges disagreed on the verdict or on its severity, or a judge gave no opinion).")
    memo = Memo(
        title=f"Legal Risk Memorandum - {doc_name}",
        prepared_for="Migrant worker and caseworker" if migrant else "Supplier management",
        executive_summary=str(data.get("executive_summary") or fake()["executive_summary"]),
        summary_bn=str(data.get("summary_bn") or fake()["summary_bn"]),
        jurisdiction_note="Applicable law: " + "; ".join(p.label for p in route.packs) + (f". {excluded}" if excluded else "."),
        issues=issues,
        caveats=caveats,
    )
    return memo, L10n(bn=str(data.get("letter_bn") or letter_bn), en=str(data.get("letter_en") or letter_en))


def citizen_view(route: RouteDecision, risks: list[Risk], ledger: list[Verification], wage: WageCalc | None, letter: L10n, procedural: list[Verification]) -> CitizenView:
    live = sorted([r for r in risks if r.status != "dropped"], key=lambda r: SEVERITY_ORDER[r.severity])

    def cites(risk_ids: list[str], extra: list[Verification] | None = None) -> list[CitizenCitation]:
        out: dict[str, CitizenCitation] = {}
        rows = [v for v in ledger if v.claim.risk_id in risk_ids] + (extra or [])
        for v in rows:
            if v.verdict in ("verified", "partial") and v.section and v.claim.citation_id not in out:
                out[v.claim.citation_id] = CitizenCitation(name=label(v.section), status="verified" if v.verdict == "verified" else "partial", citation_id=v.claim.citation_id, url=v.section.url)
        return list(out.values())

    cards: list[CitizenCard] = []
    top = [r for r in live if r.origin != "policy"][:4]  # contradictions with the employer's policy get their own card
    cards.append(
        CitizenCard(
            kind="danger",
            title=L10n(bn="বিপদ কী", en="What is the danger"),
            lines=[r.citizen_line for r in top] or [L10n(bn="বড় কোনো বিপদ পাওয়া যায়নি।", en="No serious danger was found.")],
            citations=cites([r.id for r in top]),
        )
    )
    broken = [r for r in live if r.origin == "policy"]
    if broken:
        cards.append(
            CitizenCard(
                kind="policy",
                title=L10n(bn="কোম্পানির নিজের নীতি ভাঙছে", en="Breaks the company's own policy"),
                lines=[r.citizen_line for r in broken[:4]],
                citations=cites([r.id for r in broken[:4]]),
            )
        )
    if wage:
        pay_lines = [
            L10n(bn=f"কথা দেওয়া বেতন: {wage.currency} {_bn(wage.promised)}", en=f"Promised salary: {wage.currency} {wage.promised:,.0f}"),
            L10n(bn=f"প্রতি মাসে কাটা হবে: {wage.currency} {_bn(wage.monthly_deductions)} ({_bn(round(wage.pct_deducted))}%)", en=f"Cut every month: {wage.currency} {wage.monthly_deductions:,.0f} ({wage.pct_deducted:.0f}%)"),
        ]
        if wage.minimum_wage:
            pay_lines.append(L10n(bn=f"আইনে ন্যূনতম বেতন: {wage.currency} {_bn(wage.minimum_wage)}", en=f"Legal minimum wage: {wage.currency} {wage.minimum_wage:,.0f}"))
        pay_ids = [r.id for r in live if r.rule_id in ("PB-MIN-WAGE", "PB-DEDUCTION-CAP")]
        cards.append(
            CitizenCard(
                kind="pay",
                title=L10n(bn="আপনার হাতে আসল বেতন", en="Your real pay"),
                big=L10n(bn=f"{wage.currency} {_bn(wage.net)} / মাস", en=f"{wage.currency} {wage.net:,.0f} / month"),
                lines=pay_lines,
                citations=cites(pay_ids),
            )
        )
    actions: list[L10n] = []
    for r in top:
        if r.action.en not in {a.en for a in actions}:
            actions.append(r.action)
    if "bd_migration" in route.pack_ids:
        actions.append(L10n(bn="বিদেশ যাওয়ার আগে BMET অফিসে চুক্তিটি দেখান।", en="Show the contract at a BMET office before going abroad."))
    cards.append(CitizenCard(kind="todo", title=L10n(bn="কী করবেন", en="What to do"), lines=actions[:4], citations=cites([r.id for r in top], procedural)))
    if "bd_migration" in route.pack_ids:
        cards.append(
            CitizenCard(
                kind="deadline",
                title=L10n(bn="শেষ তারিখ", en="Deadline"),
                big=L10n(bn="ফ্লাইটের আগে", en="Before your flight"),
                lines=[L10n(bn="BMET ছাড়পত্র নেওয়ার আগেই চুক্তি ঠিক করান। পরে বদলানো কঠিন।", en="Fix the contract before you get BMET clearance. It is hard to change later.")],
                citations=cites([], procedural),
            )
        )
    elif "bd_fx" in route.pack_ids and any(r.rule_id == "PB-EXPORT-PROCEEDS" for r in live):
        cards.append(
            CitizenCard(
                kind="deadline",
                title=L10n(bn="শেষ তারিখ", en="Deadline"),
                big=L10n(bn="শিপমেন্টের ৪ মাসের মধ্যে", en="Within 4 months of shipment"),
                lines=[L10n(bn="প্রতিটি চালানের পুরো রপ্তানি মূল্য ৪ মাসের মধ্যে দেশে আনতে হবে।", en="Full export proceeds of every shipment must reach Bangladesh within four months.")],
                citations=cites([r.id for r in live if r.rule_id == "PB-EXPORT-PROCEEDS"]),
            )
        )
    danger = sum(1 for r in live if r.severity in ("critical", "high"))
    return CitizenView(dangerCount=danger, cards=cards, letter=letter)
