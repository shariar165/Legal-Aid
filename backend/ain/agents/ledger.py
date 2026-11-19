"""Four Ledgers (চার খাতা): for each contract term, what the worker was TOLD (কথা), what the PAPER says (কাগজ),
what was PAID (টাকা) and what the LAW says (আইন). Plain comparisons and arithmetic, no LLM.

* The law cell is read only from claims the 4-gate verifier already passed for a risk on that term (or for the
  calculator's own citation). This module never looks up a section itself: an unverified risk leaves the cell
  `not_verified` and empty.
* The টাকা cell waits for the payslip spec and is always empty.
* Money is never converted with a rate of our own: only with one the user typed, returned marked "user-entered".
* Every string a person reads is in Bangla and English (spec 20). Bangla counts use Bangla digits; money is written
  `RM 1,200` in both, as on the contract.
"""

from __future__ import annotations

import re

from ain import countries
from ain.agents.ingestion import _cur
from ain.models import (
    SEVERITY_ORDER,
    BreakEven,
    Claim,
    ClaimLine,
    ClaimProjection,
    Clause,
    ContractTerm,
    Deduction,
    DocFacts,
    ExchangeRate,
    FourLedgers,
    L10n,
    LawCell,
    LedgerCell,
    LedgerRow,
    Mismatch,
    NetStep,
    PromiseGap,
    Promises,
    Risk,
    Verification,
    WageCalc,
)

PROMISE_RULE = "PB-PROMISE-GAP"
# the playbook rule whose verified claims fill each term's law cell, and the only risks that can make a paper_vs_law
# mismatch. Other terms show the law of a live risk on their clause, without a mismatch: a risk on the same clause
# can be about another part of it (the travel clause's risk is about the trip home, not the ticket out).
RULE_FOR = {"salary": "PB-MIN-WAGE", "deductions": "PB-DEDUCTION-CAP", "recruitment_cost": "PB-RECRUIT-FEE", "hours_per_day": "PB-HOURS",
            "passport": "PB-PASSPORT"}
PAY_BENEFIT_TERMS = ("salary", "deductions", "ticket")  # a said_vs_paper gap on these is the PB-PROMISE-GAP risk
TERMS = ("salary", "deductions", "recruitment_cost", "hours_per_day", "ticket", "passport", "contract_months")
# where the paper cell's clause is found when ingestion did not record one (fact_clauses covers the four regex facts)
TERM_HINTS = {
    "salary": r"salary|wage|বেতন|মজুরি",
    "deductions": r"deduct|কর্তন",
    "recruitment_cost": r"recruit|agency cost|placement|নিয়োগ",
    "hours_per_day": r"hours",
    "ticket": r"ticket|air ?fare",
    "passport": r"passport|পাসপোর্ট",
    "contract_months": r"\bperiod\b|\bterm\b|\bduration\b|মেয়াদ",
}
RECRUIT_RE = re.compile(r"recruit|visa|agency|placement|levy|iqama|নিয়োগ", re.I)
BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")

PAID_BY = {
    "worker": L10n(en="the worker pays", bn="কর্মী দেবে"),
    "employer": L10n(en="the employer pays", bn="মালিক দেবে"),
    "agency": L10n(en="the agency pays", bn="এজেন্সি দেবে"),
}
KEPT_BY = {
    "worker": L10n(en="the worker keeps it", bn="কর্মীর নিজের কাছে থাকবে"),
    "employer": L10n(en="the employer keeps it", bn="মালিকের কাছে থাকবে"),
    "agency": L10n(en="the agency keeps it", bn="এজেন্সির কাছে থাকবে"),
}
# a short name for the law each playbook rule rests on (a topic, not a statement of the law: the verbatim quote and
# the citation say what the law is)
LAW_TITLE = {
    "PB-MIN-WAGE": L10n(en="Minimum wage", bn="ন্যূনতম মজুরি"),
    "PB-DEDUCTION-CAP": L10n(en="Limit on deductions", bn="কর্তনের আইনি সীমা"),
    "PB-RECRUIT-FEE": L10n(en="Recruitment costs", bn="নিয়োগের খরচ"),
    "PB-PASSPORT": L10n(en="Keeping the worker's passport", bn="কর্মীর পাসপোর্ট আটকে রাখা"),
    "PB-HOURS": L10n(en="Limit on working hours", bn="কাজের সময়ের আইনি সীমা"),
    "PB-RETURN-COST": L10n(en="The trip home", bn="দেশে ফেরার খরচ"),
    "PB-RETURN-TICKET": L10n(en="The trip home", bn="দেশে ফেরার খরচ"),
    "PB-CLAIM-WAIVER": L10n(en="The right to complain or sue", bn="অভিযোগ ও মামলার অধিকার"),
    "PB-NO-FORUM": L10n(en="A place to bring complaints", bn="অভিযোগ জানানোর জায়গা"),
}
# the promise gap rests on what the worker reports: the section may apply, it is never shown as a proven offence
PROMISE_TITLE = L10n(
    en="May fall under the cited section on false promises of pay and benefits",
    bn="বেতন-সুবিধার মিথ্যা আশ্বাস নিয়ে উল্লেখিত ধারার আওতায় পড়তে পারে",
)
TERM_LABEL = {
    "user": L10n(en="Term confirmed by user", bn="মেয়াদ ব্যবহারকারী নিশ্চিত করেছেন"),
    "contract": L10n(en="Term read from the contract", bn="মেয়াদ চুক্তি থেকে পড়া"),
    "worker": L10n(en="Term the worker was told (none on paper)", bn="মেয়াদ কর্মীকে যা বলা হয়েছিল (কাগজে নেই)"),
}

CLAIM_LABEL = L10n(
    en="Projected over the contract term at the rate on paper, under the cited law. Not money owed, and not a prediction of any award.",
    bn="চুক্তির পুরো মেয়াদ ও কাগজে লেখা হার ধরে, উল্লেখিত আইনের অধীনে প্রক্ষেপিত হিসাব। এটি বকেয়া টাকা নয়, কোনো রায়ের পূর্বাভাসও নয়।",
)
BREAK_EVEN_ASSUMPTION = L10n(
    en="A minimum: it assumes the whole take-home pay on paper is sent home, with nothing spent on food, phone or anything else.",
    bn="এটি সর্বনিম্ন সময়: ধরে নেওয়া হয়েছে কাগজে লেখা হাতে-পাওয়া পুরো বেতন দেশে পাঠানো হবে, খাবার, ফোন বা অন্য কিছুতে কোনো খরচ ছাড়াই।",
)
GAP_LABEL = L10n(
    en="What you were told minus what the contract says, over the contract term. This is your account of the promise, not an amount the law awards.",
    bn="আপনাকে যা বলা হয়েছিল তা থেকে চুক্তির অঙ্ক বাদ দিয়ে, চুক্তির পুরো মেয়াদে। এটি প্রতিশ্রুতি নিয়ে আপনার বিবরণ, আইন নির্ধারিত পাওনা নয়।",
)


# ------------------------------------------------------------------ money and numbers


def _money(amount: float, currency: str) -> str:
    return f"{currency} {amount:,.0f}"


def _bn(n: float | int) -> str:
    """A count in Bangla digits: 12 -> ১২, 54.2 -> ৫৪.২."""
    return (f"{int(n)}" if float(n).is_integer() else f"{n:g}").translate(BN_DIGITS)


def _per_month(amount: float, currency: str) -> L10n:
    m = _money(amount, currency)
    return L10n(en=f"{m} a month", bn=f"মাসে {m}")


def convert(amount: float, frm: str | None, to: str | None, rate: ExchangeRate | None) -> float | None:
    """`amount` in `frm` as `to`: as is when the currencies match, else only through the user's rate."""
    if not frm or not to:
        return None
    frm, to = _cur(frm), _cur(to)
    if frm == to:
        return amount
    if rate is None:
        return None
    per, cur = _cur(rate.per), _cur(rate.currency)
    if (frm, to) == (cur, per):  # 1 per = value cur
        return amount / rate.value
    if (frm, to) == (per, cur):
        return amount * rate.value
    return None


def _said_salary(facts: DocFacts, promises: Promises) -> float | None:
    """The promised salary in the paper's currency, when it can be compared."""
    if promises.salary_amount is None or facts.salary_amount is None:
        return None
    return convert(promises.salary_amount, promises.salary_currency or facts.salary_currency, facts.salary_currency, promises.exchange_rate)


def contract_term(facts: DocFacts, promises: Promises | None) -> ContractTerm | None:
    """The months the projection runs over, and where they came from: the user, the paper, or (none on paper) what the
    worker was told."""
    if facts.contract_months:
        source = "user" if facts.contract_months_confirmed else "contract"
        return ContractTerm(months=facts.contract_months, source=source, clause_id=facts.fact_clauses.get("contract_months"), label=TERM_LABEL[source])
    if promises and promises.contract_months:
        return ContractTerm(months=promises.contract_months, source="worker", label=TERM_LABEL["worker"])
    return None


def _months(facts: DocFacts, promises: Promises | None) -> tuple[int | None, str]:
    term = contract_term(facts, promises)
    return (term.months, term.label.en) if term else (None, "")


# ------------------------------------------------------------------ told vs paper


def pay_benefit_gaps(facts: DocFacts, wage: WageCalc | None, promises: Promises | None) -> list[str]:
    """Where the paper gives less pay or fewer benefits than the worker was told. Shared with the PB-PROMISE-GAP rule
    (these lines become the risk's finding, in the memo's English)."""
    if promises is None:
        return []
    out = []
    said = _said_salary(facts, promises)
    if said is not None and facts.salary_amount is not None and said > facts.salary_amount:
        told = _money(promises.salary_amount, _cur(promises.salary_currency or facts.salary_currency or ""))
        out.append(f"The worker was told {told} a month; the contract says {_money(facts.salary_amount, facts.salary_currency or '')}.")
    monthly = round(sum(d.amount for d in facts.deductions if d.per == "month"), 2)
    if promises.no_deductions and monthly > 0:
        out.append(f"The worker was told there would be no deductions; the contract deducts {_money(monthly, facts.salary_currency or '')} a month.")
    if promises.ticket_paid_by in ("employer", "agency") and facts.ticket_paid_by == "worker":
        out.append(f"The worker was told the {promises.ticket_paid_by} pays the air ticket; the contract makes the worker pay it.")
    return out


# ------------------------------------------------------------------ cells


def _clause_for(term: str, facts: DocFacts, clauses: list[Clause]) -> str | None:
    if term in facts.fact_clauses:  # the clause the regex fact was read from
        return facts.fact_clauses[term]
    pat = re.compile(TERM_HINTS[term], re.I)
    for c in clauses:
        if pat.search(c.text) and not (term == "salary" and re.search(r"deduct", c.text, re.I)):
            return c.id
    return None


def _deductions_text(facts: DocFacts, wage: WageCalc | None, monthly: float, cur: str) -> L10n:
    en, bn = f"{_money(monthly, cur)} a month", f"মাসে {_money(monthly, cur)}"
    if wage:
        en, bn = f"{en} ({wage.pct_deducted}% of the salary)", f"{bn} (বেতনের {_bn(wage.pct_deducted)}%)"
    for end in sorted({d.months for d in facts.deductions if d.per == "month" and d.months}):  # a deduction that stops
        after = _money(round(sum(d.amount for d in facts.deductions if d.per == "month" and (d.months is None or d.months > end)), 2), cur)
        en, bn = f"{en}; {after} a month after month {end}", f"{bn}; {_bn(end)} মাস পর মাসে {after}"
    return L10n(en=en, bn=bn)


def _paper(term: str, facts: DocFacts, wage: WageCalc | None, clause_id: str | None) -> LedgerCell | None:
    cur = facts.salary_currency
    cell = dict(clause_id=clause_id, source="contract")
    if term == "salary" and facts.salary_amount is not None:
        return LedgerCell(value=_per_month(facts.salary_amount, cur or ""), amount=facts.salary_amount, currency=cur, **cell)
    if term == "deductions" and facts.deductions:
        monthly = round(sum(d.amount for d in facts.deductions if d.per == "month"), 2)
        return LedgerCell(value=_deductions_text(facts, wage, monthly, cur or ""), amount=monthly, currency=cur, **cell)
    if term == "recruitment_cost" and (total := _recruit_from_wages(facts, None)):
        m = _money(total, cur or "")
        return LedgerCell(value=L10n(en=f"{m} taken from wages", bn=f"বেতন থেকে {m} কাটা হবে"), amount=total, currency=cur, **cell)
    if term == "hours_per_day" and facts.hours_per_day:
        h = facts.hours_per_day
        return LedgerCell(value=L10n(en=f"{h} hours a day", bn=f"দিনে {_bn(h)} ঘণ্টা"), amount=h, **cell)
    if term == "ticket" and facts.ticket_paid_by:
        return LedgerCell(value=PAID_BY[facts.ticket_paid_by], party=facts.ticket_paid_by, **cell)
    if term == "passport" and facts.passport_held_by:
        return LedgerCell(value=KEPT_BY[facts.passport_held_by], party=facts.passport_held_by, **cell)
    if term == "contract_months" and facts.contract_months:
        n = facts.contract_months
        return LedgerCell(value=L10n(en=f"{n} months", bn=f"{_bn(n)} মাস"), amount=n, confirmed_by_user=facts.contract_months_confirmed, **cell)
    return None


def _said(term: str, promises: Promises | None, facts: DocFacts) -> LedgerCell | None:
    p = promises
    if p is None:
        return None
    if term == "salary" and p.salary_amount is not None:
        cur = _cur(p.salary_currency or facts.salary_currency or "")
        return LedgerCell(value=_per_month(p.salary_amount, cur), amount=p.salary_amount, currency=cur or None, source="worker")
    if term == "deductions" and p.no_deductions is not None:
        text = L10n(en="no deductions", bn="কোনো কর্তন নেই") if p.no_deductions else L10n(en="deductions were mentioned", bn="কর্তনের কথা বলা হয়েছিল")
        return LedgerCell(value=text, amount=0.0 if p.no_deductions else None, source="worker")
    if term == "recruitment_cost" and p.recruitment_cost_paid is not None:
        cur = _cur(p.recruitment_cost_currency or "")
        m = _money(p.recruitment_cost_paid, cur)
        return LedgerCell(value=L10n(en=f"{m} already paid", bn=f"আগেই {m} দেওয়া হয়েছে"), amount=p.recruitment_cost_paid, currency=cur or None, source="worker")
    if term == "hours_per_day" and p.hours_per_day:
        return LedgerCell(value=L10n(en=f"{p.hours_per_day} hours a day", bn=f"দিনে {_bn(p.hours_per_day)} ঘণ্টা"), amount=p.hours_per_day, source="worker")
    if term == "ticket" and p.ticket_paid_by:
        return LedgerCell(value=PAID_BY[p.ticket_paid_by], party=p.ticket_paid_by, source="worker")
    if term == "passport" and p.passport_kept_by:
        return LedgerCell(value=KEPT_BY[p.passport_kept_by], party=p.passport_kept_by, source="worker")
    if term == "contract_months" and p.contract_months:
        return LedgerCell(value=L10n(en=f"{p.contract_months} months", bn=f"{_bn(p.contract_months)} মাস"), amount=p.contract_months, source="worker")
    return None


def _passed(ledger: list[Verification], risk_id: str) -> list[Verification]:
    rows = [v for v in ledger if v.claim.risk_id == risk_id and v.verdict in ("verified", "partial")]
    return sorted(rows, key=lambda v: v.section is None or v.section.kind != "law")  # statutes before voluntary codes


def _law_from(risk: Risk | None, ledger: list[Verification]) -> LawCell:
    if risk is None:
        return LawCell(status="none")
    title = LAW_TITLE.get(risk.rule_id or "")
    rows = _passed(ledger, risk.id)
    if risk.status == "dropped" or not rows:
        return LawCell(status="not_verified", risk_id=risk.id, title=title)
    ids = list(dict.fromkeys(v.claim.citation_id for v in rows))
    best = next((v for v in rows if v.verdict == "verified"), rows[0])
    return LawCell(status="verified" if best.verdict == "verified" else "partial", citation_ids=ids, risk_id=risk.id, proposition=best.claim.proposition, title=title)


def _linked_risk(term: str, risks: list[Risk], clause_id: str | None) -> Risk | None:
    rule = RULE_FOR.get(term)
    if rule and (r := next((r for r in risks if r.rule_id == rule), None)):
        return r
    if clause_id:  # e.g. an Adversary risk on the hours clause
        return next((r for r in risks if r.status != "dropped" and r.rule_id != PROMISE_RULE and clause_id in r.clause_ids), None)
    return None


def _hours_limit(facts: DocFacts) -> dict | None:
    country = countries.by_name(facts.destination_country)
    return country.hours_limit if country else None


def _against_law(term: str, paper: LedgerCell, wage: WageCalc | None, facts: DocFacts) -> L10n:
    """The paper_vs_law sentence, written per term so the Bangla reads as a sentence, not a template."""
    if term == "salary" and wage and wage.minimum_wage is not None:
        m = _money(wage.minimum_wage, wage.currency)
        return L10n(en=f"The contract pays {paper.value.en}; the cited law sets a minimum of {m} a month.",
                    bn=f"চুক্তিতে বেতন {paper.value.bn}, অথচ উল্লেখিত আইনে ন্যূনতম মাসে {m}।")
    if term == "deductions" and wage and wage.deduction_cap_pct is not None:
        m, pct, cap = _money(wage.monthly_deductions, wage.currency), wage.pct_deducted, wage.deduction_cap_pct
        return L10n(en=f"The contract deducts {m} a month ({pct}% of the salary); the cited law caps deductions at {cap:.0f}%.",
                    bn=f"চুক্তিতে মাসে {m} কর্তন (বেতনের {_bn(pct)}%), অথচ উল্লেখিত আইনে কর্তনের সীমা {_bn(round(cap))}%।")
    if term == "recruitment_cost" and paper.amount is not None:
        m = _money(paper.amount, paper.currency or "")
        return L10n(en=f"The contract takes {m} of recruitment costs from wages, against the cited law.",
                    bn=f"চুক্তি অনুযায়ী বেতন থেকে {m} নিয়োগের খরচ কাটা হবে, যা উল্লেখিত আইনের পরিপন্থী।")
    if term == "hours_per_day" and (limit := _hours_limit(facts)):
        if paper.amount is not None and paper.amount > limit["day"]:
            return L10n(en=f"The contract sets {paper.value.en}; the cited law limits a day to {limit['day']} hours.",
                        bn=f"চুক্তিতে {paper.value.bn} কাজ, অথচ উল্লেখিত আইনে দিনে সর্বোচ্চ {_bn(limit['day'])} ঘণ্টা।")
        if facts.hours_per_week is not None and facts.hours_per_week > limit["week"]:
            w = facts.hours_per_week
            return L10n(en=f"The contract sets {w} hours a week; the cited law limits a week to {limit['week']} hours.",
                        bn=f"চুক্তিতে সপ্তাহে {_bn(w)} ঘণ্টা কাজ, অথচ উল্লেখিত আইনে সপ্তাহে সর্বোচ্চ {_bn(limit['week'])} ঘণ্টা।")
    if term == "passport":
        return L10n(en=f"Under the contract {paper.value.en}, against the cited law.",
                    bn=f"চুক্তি অনুযায়ী পাসপোর্ট {paper.value.bn}, যা উল্লেখিত আইনের পরিপন্থী।")
    return L10n(en=f"The contract says {paper.value.en}, against the cited law.", bn=f"চুক্তিতে লেখা {paper.value.bn}, যা উল্লেখিত আইনের পরিপন্থী।")


def _said_worse(term: str, said: LedgerCell, paper: LedgerCell, facts: DocFacts, promises: Promises) -> bool:
    """True when the paper is worse for the worker than what they were told."""
    if term == "salary":
        s = _said_salary(facts, promises)
        return s is not None and paper.amount is not None and s > paper.amount
    if term == "deductions":
        return bool(promises.no_deductions) and (paper.amount or 0) > 0
    if term == "hours_per_day":
        return said.amount is not None and paper.amount is not None and paper.amount > said.amount
    if term == "ticket":
        return promises.ticket_paid_by in ("employer", "agency") and facts.ticket_paid_by == "worker"
    if term == "passport":
        return promises.passport_kept_by == "worker" and facts.passport_held_by == "employer"
    if term == "contract_months":
        return said.amount is not None and paper.amount is not None and said.amount != paper.amount
    return False  # recruitment_cost: what was paid is a fact the worker reports, not a promise to compare


def _promise_citations(risk: Risk, ledger: list[Verification], pending_claims: list[Claim]) -> list[str]:
    """The sections the promise-gap risk was checked against: passed ones first; while pending, the ones it will be."""
    rows = _passed(ledger, risk.id) or [v for v in ledger if v.claim.risk_id == risk.id]
    ids = [v.claim.citation_id for v in rows] or [c.citation_id for c in pending_claims if c.risk_id == risk.id]
    return list(dict.fromkeys(ids))


def _row(term: str, facts: DocFacts, wage: WageCalc | None, clauses: list[Clause], risks: list[Risk], ledger: list[Verification],
         promises: Promises | None, promise_risk: Risk | None, pending: list[Risk], pending_claims: list[Claim]) -> LedgerRow | None:
    clause_id = _clause_for(term, facts, clauses)
    said, paper = _said(term, promises, facts), _paper(term, facts, wage, clause_id)
    if said is None and paper is None:
        return None
    risk = _linked_risk(term, risks, clause_id if paper else None)
    if term == "salary" and risk is None and wage and wage.minimum_wage_citation:
        # the calculator's own citation, shown only if the verifier passed a claim on it
        rows = [v for v in ledger if v.claim.citation_id == wage.minimum_wage_citation and v.verdict in ("verified", "partial")]
        title = LAW_TITLE["PB-MIN-WAGE"]
        law = (LawCell(status="verified" if any(v.verdict == "verified" for v in rows) else "partial", citation_ids=[wage.minimum_wage_citation],
                       proposition=rows[0].claim.proposition, title=title) if rows else LawCell(status="not_verified", title=title))
    else:
        law = _law_from(risk, ledger)
    mismatches: list[Mismatch] = []
    sevs: list[str] = []
    if said and paper and promises and _said_worse(term, said, paper, facts, promises):
        rid, status, title, cites = None, None, None, []
        if promise_risk is not None and term in PAY_BENEFIT_TERMS:
            rid, status = promise_risk.id, _risk_status(promise_risk, ledger, pending)
            title, cites = PROMISE_TITLE, _promise_citations(promise_risk, ledger, pending_claims)
        mismatches.append(Mismatch(type="said_vs_paper", risk_id=rid, risk_status=status, title=title, citation_ids=cites, detail=L10n(
            en=f"Told {said.value.en}; the contract says {paper.value.en}.", bn=f"বলা হয়েছিল {said.value.bn}, কিন্তু চুক্তিতে লেখা {paper.value.bn}।")))
        # the risk's severity counts only once the gates have passed it; with no verified law the row has none
        if promise_risk and status in ("verified", "partial"):
            sevs.append(promise_risk.severity)
    if paper and risk is not None and risk.rule_id == RULE_FOR.get(term) and risk.status != "dropped" and law.status in ("verified", "partial"):
        mismatches.append(Mismatch(type="paper_vs_law", risk_id=risk.id, risk_status=law.status, title=law.title,
                                   citation_ids=law.citation_ids, detail=_against_law(term, paper, wage, facts)))
        sevs.append(risk.severity)
    return LedgerRow(
        term=term, said=said, paper=paper, law=law, mismatches=mismatches,
        severity=min(sevs, key=lambda s: SEVERITY_ORDER[s]) if sevs else None,  # type: ignore[arg-type]
        risk_id=law.risk_id or next((m.risk_id for m in mismatches if m.risk_id), None),
    )


# ------------------------------------------------------------------ projection, promise gap, break-even


def _recruit_from_wages(facts: DocFacts, months: int | None) -> float:
    total = 0.0
    for d in facts.deductions:
        if not RECRUIT_RE.search(d.label):
            continue
        if d.per == "once":
            total += d.amount
        elif n := d.months or months:
            total += d.amount * n
    return round(total, 2)


def _verified_claim(ledger: list[Verification], risk: Risk | None, citation_id: str | None = None) -> Verification | None:
    if risk is None or risk.status == "dropped":
        return None
    rows = [v for v in ledger if v.claim.risk_id == risk.id and v.verdict == "verified" and (citation_id is None or v.claim.citation_id == citation_id)]
    if citation_id is None:  # recruitment: law before voluntary codes, the destination's or Bangladesh's law before the ILO's
        rows = [v for v in rows if v.section is not None and v.section.kind == "law"]
        rows.sort(key=lambda v: v.section.jurisdiction == "INTL")
    return rows[0] if rows else None


def claim_projection(facts: DocFacts, wage: WageCalc | None, risks: list[Risk], ledger: list[Verification], promises: Promises | None) -> ClaimProjection:
    """Every line is `projected`: over the contract term at the rate on paper. `accrued` (months actually worked)
    needs payslips, so `accrued_total` stays None. `term` says where the months came from."""
    term = contract_term(facts, promises)
    months, source = (term.months, term.label.en) if term else (None, "")
    lines: list[ClaimLine] = []
    if wage and wage.below_minimum and wage.minimum_wage_citation and months:
        risk = next((r for r in risks if r.rule_id == "PB-MIN-WAGE"), None)
        if v := _verified_claim(ledger, risk, wage.minimum_wage_citation):
            short = _money(wage.shortfall, wage.currency)
            lines.append(ClaimLine(
                label=L10n(en=f"Minimum-wage shortfall: {short} a month × {months} months", bn=f"ন্যূনতম মজুরির ঘাটতি: মাসে {short} × {_bn(months)} মাস"),
                amount=round(wage.shortfall * months, 2), currency=wage.currency, citation_id=v.claim.citation_id, risk_id=risk.id,
                basis="projected", months=months, source=source))
    if wage and (taken := _recruit_from_wages(facts, months)):
        risk = next((r for r in risks if r.rule_id == "PB-RECRUIT-FEE"), None)
        if v := _verified_claim(ledger, risk):
            ded_months = max((d.months or months or 0 for d in facts.deductions if RECRUIT_RE.search(d.label)), default=0) or None
            lines.append(ClaimLine(
                label=L10n(en="Recruitment costs to be taken from wages", bn="বেতন থেকে কেটে নেওয়া হবে এমন নিয়োগ খরচ"),
                amount=taken, currency=wage.currency, citation_id=v.claim.citation_id, risk_id=risk.id,
                basis="projected", months=ded_months, source="deductions on paper"))
    return ClaimProjection(lines=lines, term=term, projected_total=round(sum(x.amount for x in lines), 2), currency=wage.currency if wage else None, label=CLAIM_LABEL)


def promise_gap(facts: DocFacts, promises: Promises | None) -> PromiseGap | None:
    if promises is None:
        return None
    said = _said_salary(facts, promises)
    months, _ = _months(facts, promises)
    if said is None or facts.salary_amount is None or not months or said <= facts.salary_amount:
        return None
    monthly = round(said - facts.salary_amount, 2)
    return PromiseGap(monthly=monthly, months=months, total=round(monthly * months, 2), currency=facts.salary_currency or "", label=GAP_LABEL)


def net_steps(salary: float, deductions: list[Deduction]) -> list[NetStep]:
    """Take-home pay on paper, month by month: a deduction with `months` stops after that many months."""
    monthly = [d for d in deductions if d.per == "month"]
    ends = sorted({d.months for d in monthly if d.months})
    steps: list[NetStep] = []
    start = 1
    for end in [*ends, None]:
        if end is not None and end < start:
            continue
        # deductions still running in this stretch: open-ended ones, and those that end at or after its last month
        net = round(salary - sum(d.amount for d in monthly if d.months is None or (end is not None and d.months >= end)), 2)
        if steps and steps[-1].net == net:
            steps[-1].to_month = end
        else:
            steps.append(NetStep(from_month=start, to_month=end, net=net))
        if end is None:
            break
        start = end + 1
    return steps


def break_even(wage: WageCalc | None, promises: Promises | None, contract_months: int | None = None) -> BreakEven | None:
    """Months of take-home pay on paper to earn back what was paid to get the job, counted month by month."""
    if promises is None or promises.recruitment_cost_paid is None:
        return None
    if wage is None:
        return BreakEven(note=L10n(en="The contract gives no take-home pay to compare the cost with.",
                                   bn="খরচের সঙ্গে তুলনা করার মতো হাতে-পাওয়া বেতন চুক্তিতে নেই।"))
    frm = promises.recruitment_cost_currency or wage.currency
    cost = convert(promises.recruitment_cost_paid, frm, wage.currency, promises.exchange_rate)
    steps = net_steps(wage.promised, wage.deductions)
    base = dict(monthly_net=wage.net, currency=wage.currency, steps=steps, horizon_months=contract_months, assumption=BREAK_EVEN_ASSUMPTION)
    if cost is None:
        return BreakEven(**base, note=L10n(
            en=f"The cost is in {_cur(frm)} and the pay in {wage.currency}: enter an exchange rate to compute this. Jukti uses no rate of its own.",
            bn=f"খরচ {_cur(frm)}-এ, বেতন {wage.currency}-এ: হিসাব করতে একটি বিনিময় হার লিখুন। যুক্তি নিজে কোনো হার ব্যবহার করে না।"))
    used = promises.exchange_rate if _cur(frm) != _cur(wage.currency) else None
    base.update(cost=round(cost, 2), rate=used)
    # "once" deductions are taken from the first month's pay
    earned = -sum(d.amount for d in wage.deductions if d.per == "once")
    for s in steps:
        last = s.to_month if s.to_month is not None else contract_months
        if contract_months is not None:
            if s.from_month > contract_months:
                break
            last = min(last, contract_months) if last is not None else contract_months
        keep = max(0.0, s.net)  # a month whose deductions exceed the pay earns nothing back
        if keep > 0 and (last is None or (cost - earned) / keep <= last - s.from_month + 1):
            months = s.from_month - 1 + (cost - earned) / keep
            return BreakEven(**base, months=round(max(months, 0.0), 1), note=L10n(
                en="At least this many months of take-home pay on paper to earn back what was paid to get the job.",
                bn="চাকরি পেতে যা খরচ হয়েছে তা তুলতে কাগজে লেখা হাতে-পাওয়া বেতনের অন্তত এত মাস লাগবে।"))
        if last is None:  # open-ended and nothing kept: never earned back
            break
        earned += keep * (last - s.from_month + 1)
    if contract_months is not None:
        got, total = _money(max(earned, 0.0), wage.currency), _money(cost, wage.currency)
        return BreakEven(**base, earned_back=round(max(earned, 0.0), 2), note=L10n(
            en=f"Not earned back within the {contract_months}-month contract: {got} of {total}, even if all of it is sent home.",
            bn=f"{_bn(contract_months)} মাসের চুক্তিতে খরচ ওঠে না: পুরো বেতন দেশে পাঠালেও {total}-এর মধ্যে ওঠে {got}।"))
    return BreakEven(**base, note=L10n(en="The contract leaves no take-home pay to earn the cost back.",
                                       bn="খরচ তোলার মতো হাতে-পাওয়া বেতন চুক্তিতে থাকে না।"))


def _risk_status(risk: Risk, ledger: list[Verification], pending: list[Risk]) -> str:
    if any(p.id == risk.id for p in pending):
        return "not_verified_yet"
    rows = _passed(ledger, risk.id)
    if risk.status == "dropped" or not rows:
        return "not_verified"
    return "verified" if any(v.verdict == "verified" for v in rows) else "partial"


# ------------------------------------------------------------------ public


def build(facts: DocFacts, wage: WageCalc | None, clauses: list[Clause], risks: list[Risk], ledger: list[Verification],
          promises: Promises | None, memo_includes_promises: bool,
          pending_risks: list[Risk] | None = None, pending_claims: list[Claim] | None = None) -> FourLedgers:
    """`pending_risks`: a promise-gap risk raised with no model call. It shows as `not_verified_yet` and adds nothing
    to severity, law cells or the projection until its claims have been through the 4 gates."""
    pending, pclaims = pending_risks or [], pending_claims or []
    promise_risk = next((r for r in [*risks, *pending] if r.rule_id == PROMISE_RULE), None)
    rows = [row for t in TERMS if (row := _row(t, facts, wage, clauses, risks, ledger, promises, promise_risk, pending, pclaims))]
    months, _ = _months(facts, promises)
    return FourLedgers(
        promises=promises,
        rows=rows,
        claim_projection=claim_projection(facts, wage, risks, ledger, promises),
        pending_risks=pending,
        pending_claims=pclaims,
        promise_gap=promise_gap(facts, promises),
        break_even=break_even(wage, promises, months),
        memo_includes_promises=memo_includes_promises and promises is not None,
    )
