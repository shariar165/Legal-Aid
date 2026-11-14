"""Four Ledgers (চার খাতা): for each contract term, what the worker was TOLD (কথা), what the PAPER says (কাগজ),
what was PAID (টাকা) and what the LAW says (আইন). Plain comparisons and arithmetic, no LLM.

* The law cell is read only from claims the 4-gate verifier already passed for a risk on that term (or for the
  calculator's own citation). This module never looks up a section itself: an unverified risk leaves the cell
  `not_verified` and empty.
* The টাকা cell waits for the payslip spec and is always empty.
* Money is never converted with a rate of our own: only with one the user typed, returned marked "user-entered".
"""

from __future__ import annotations

import re

from ain.agents.ingestion import _cur
from ain.models import (
    SEVERITY_ORDER,
    BreakEven,
    Claim,
    ClaimLine,
    ClaimProjection,
    Clause,
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
RULE_FOR = {"salary": "PB-MIN-WAGE", "deductions": "PB-DEDUCTION-CAP", "recruitment_cost": "PB-RECRUIT-FEE", "passport": "PB-PASSPORT"}
PAY_BENEFIT_TERMS = ("salary", "deductions", "ticket")  # a said_vs_paper gap on these is the PB-PROMISE-GAP risk
TERMS = ("salary", "deductions", "recruitment_cost", "hours_per_day", "ticket", "passport", "contract_months")
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
PARTY_BN = {"worker": "কর্মী", "employer": "মালিক", "agency": "এজেন্সি"}

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


# ------------------------------------------------------------------ money


def _money(amount: float, currency: str) -> str:
    return f"{currency} {amount:,.0f}"


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


def _months(facts: DocFacts, promises: Promises | None) -> tuple[int | None, str]:
    if facts.contract_months:
        return facts.contract_months, "contract term on paper"
    if promises and promises.contract_months:
        return promises.contract_months, "contract term the worker was told (none on paper)"
    return None, ""


# ------------------------------------------------------------------ told vs paper


def pay_benefit_gaps(facts: DocFacts, wage: WageCalc | None, promises: Promises | None) -> list[str]:
    """Where the paper gives less pay or fewer benefits than the worker was told. Shared with the PB-PROMISE-GAP rule."""
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


def _clause_for(term: str, clauses: list[Clause]) -> str | None:
    pat = re.compile(TERM_HINTS[term], re.I)
    for c in clauses:
        if pat.search(c.text) and not (term == "salary" and re.search(r"deduct", c.text, re.I)):
            return c.id
    return None


def _paper(term: str, facts: DocFacts, wage: WageCalc | None, clause_id: str | None) -> LedgerCell | None:
    cur = facts.salary_currency
    if term == "salary" and facts.salary_amount is not None:
        return LedgerCell(value=f"{_money(facts.salary_amount, cur or '')} a month", amount=facts.salary_amount, currency=cur, clause_id=clause_id, source="contract")
    if term == "deductions" and facts.deductions:
        monthly = round(sum(d.amount for d in facts.deductions if d.per == "month"), 2)
        pct = f" ({wage.pct_deducted}% of the salary)" if wage else ""
        for end in sorted({d.months for d in facts.deductions if d.per == "month" and d.months}):  # a deduction that stops
            after = round(sum(d.amount for d in facts.deductions if d.per == "month" and (d.months is None or d.months > end)), 2)
            pct += f"; {_money(after, cur or '')} a month after month {end}"
        return LedgerCell(value=f"{_money(monthly, cur or '')} a month{pct}", amount=monthly, currency=cur, clause_id=clause_id, source="contract")
    if term == "recruitment_cost":
        total = _recruit_from_wages(facts, None)
        if total:
            return LedgerCell(value=f"{_money(total, cur or '')} taken from wages", amount=total, currency=cur, clause_id=clause_id, source="contract")
    if term == "hours_per_day" and facts.hours_per_day:
        return LedgerCell(value=f"{facts.hours_per_day} hours a day", amount=facts.hours_per_day, clause_id=clause_id, source="contract")
    if term == "ticket" and facts.ticket_paid_by:
        return LedgerCell(value=f"{facts.ticket_paid_by} pays", clause_id=clause_id, source="contract")
    if term == "passport" and facts.passport_held_by:
        return LedgerCell(value=f"{facts.passport_held_by} keeps it", clause_id=clause_id, source="contract")
    if term == "contract_months" and facts.contract_months:
        return LedgerCell(value=f"{facts.contract_months} months", amount=facts.contract_months, clause_id=clause_id, source="contract")
    return None


def _said(term: str, promises: Promises | None, facts: DocFacts) -> LedgerCell | None:
    p = promises
    if p is None:
        return None
    if term == "salary" and p.salary_amount is not None:
        cur = _cur(p.salary_currency or facts.salary_currency or "")
        return LedgerCell(value=f"{_money(p.salary_amount, cur)} a month", amount=p.salary_amount, currency=cur or None, source="worker")
    if term == "deductions" and p.no_deductions is not None:
        return LedgerCell(value="no deductions" if p.no_deductions else "deductions were mentioned", amount=0.0 if p.no_deductions else None, source="worker")
    if term == "recruitment_cost" and p.recruitment_cost_paid is not None:
        cur = _cur(p.recruitment_cost_currency or "")
        return LedgerCell(value=f"{_money(p.recruitment_cost_paid, cur)} already paid", amount=p.recruitment_cost_paid, currency=cur or None, source="worker")
    if term == "hours_per_day" and p.hours_per_day:
        return LedgerCell(value=f"{p.hours_per_day} hours a day", amount=p.hours_per_day, source="worker")
    if term == "ticket" and p.ticket_paid_by:
        return LedgerCell(value=f"{p.ticket_paid_by} pays", source="worker")
    if term == "passport" and p.passport_kept_by:
        return LedgerCell(value=f"{p.passport_kept_by} keeps it", source="worker")
    if term == "contract_months" and p.contract_months:
        return LedgerCell(value=f"{p.contract_months} months", amount=p.contract_months, source="worker")
    return None


def _passed(ledger: list[Verification], risk_id: str) -> list[Verification]:
    rows = [v for v in ledger if v.claim.risk_id == risk_id and v.verdict in ("verified", "partial")]
    return sorted(rows, key=lambda v: v.section is None or v.section.kind != "law")  # statutes before voluntary codes


def _law_from(risk: Risk | None, ledger: list[Verification]) -> LawCell:
    if risk is None:
        return LawCell(status="none")
    rows = _passed(ledger, risk.id)
    if risk.status == "dropped" or not rows:
        return LawCell(status="not_verified", risk_id=risk.id)
    ids = list(dict.fromkeys(v.claim.citation_id for v in rows))
    best = next((v for v in rows if v.verdict == "verified"), rows[0])
    return LawCell(status="verified" if best.verdict == "verified" else "partial", citation_ids=ids, risk_id=risk.id, proposition=best.claim.proposition)


def _linked_risk(term: str, risks: list[Risk], clause_id: str | None) -> Risk | None:
    rule = RULE_FOR.get(term)
    if rule and (r := next((r for r in risks if r.rule_id == rule), None)):
        return r
    if clause_id:  # e.g. an Adversary risk on the hours clause
        return next((r for r in risks if r.status != "dropped" and r.rule_id != PROMISE_RULE and clause_id in r.clause_ids), None)
    return None


def _law_extra(term: str, wage: WageCalc | None) -> tuple[str, str]:
    if term == "salary" and wage and wage.minimum_wage is not None:
        m = _money(wage.minimum_wage, wage.currency)
        return f" (minimum {m} a month)", f" (ন্যূনতম মাসে {m})"
    if term == "deductions" and wage and wage.deduction_cap_pct is not None:
        return f" (deductions capped at {wage.deduction_cap_pct:.0f}%)", f" (কর্তনের সীমা {wage.deduction_cap_pct:.0f}%)"
    return "", ""


def _bn(cell: LedgerCell) -> str:
    v = cell.value
    for en, bn in PARTY_BN.items():
        v = re.sub(rf"^{en}\b", bn, v)
    return v


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


def _row(term: str, facts: DocFacts, wage: WageCalc | None, clauses: list[Clause], risks: list[Risk], ledger: list[Verification],
         promises: Promises | None, promise_risk: Risk | None, pending: list[Risk]) -> LedgerRow | None:
    clause_id = _clause_for(term, clauses)
    said, paper = _said(term, promises, facts), _paper(term, facts, wage, clause_id)
    if said is None and paper is None:
        return None
    risk = _linked_risk(term, risks, clause_id if paper else None)
    if term == "salary" and risk is None and wage and wage.minimum_wage_citation:
        # the calculator's own citation, shown only if the verifier passed a claim on it
        rows = [v for v in ledger if v.claim.citation_id == wage.minimum_wage_citation and v.verdict in ("verified", "partial")]
        law = LawCell(status="verified" if any(v.verdict == "verified" for v in rows) else "partial", citation_ids=[wage.minimum_wage_citation], proposition=rows[0].claim.proposition) if rows else LawCell(status="not_verified")
    else:
        law = _law_from(risk, ledger)
    mismatches: list[Mismatch] = []
    sevs: list[str] = []
    if said and paper and promises and _said_worse(term, said, paper, facts, promises):
        rid, status = None, None
        if promise_risk is not None and term in PAY_BENEFIT_TERMS:
            rid, status = promise_risk.id, _risk_status(promise_risk, ledger, pending)
        mismatches.append(Mismatch(type="said_vs_paper", risk_id=rid, risk_status=status, detail=L10n(
            en=f"Told {said.value}; the contract says {paper.value}.", bn=f"বলা হয়েছিল {_bn(said)}; চুক্তিতে লেখা {_bn(paper)}।")))
        # the risk's severity counts only once the gates have passed it
        sevs.append(promise_risk.severity if promise_risk and status in ("verified", "partial") else "low")
    if paper and risk is not None and risk.rule_id == RULE_FOR.get(term) and risk.status != "dropped" and law.status in ("verified", "partial"):
        en_x, bn_x = _law_extra(term, wage)
        mismatches.append(Mismatch(type="paper_vs_law", risk_id=risk.id, detail=L10n(
            en=f"The contract says {paper.value}, against the cited law{en_x}.", bn=f"চুক্তিতে লেখা {_bn(paper)}, যা উল্লেখিত আইনের বিরুদ্ধে{bn_x}।")))
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
    needs payslips, so `accrued_total` stays None."""
    months, source = _months(facts, promises)
    lines: list[ClaimLine] = []
    if wage and wage.below_minimum and wage.minimum_wage_citation and months:
        risk = next((r for r in risks if r.rule_id == "PB-MIN-WAGE"), None)
        if v := _verified_claim(ledger, risk, wage.minimum_wage_citation):
            lines.append(ClaimLine(
                label=L10n(en=f"Minimum-wage shortfall: {_money(wage.shortfall, wage.currency)} a month × {months} months",
                           bn=f"ন্যূনতম মজুরির ঘাটতি: মাসে {_money(wage.shortfall, wage.currency)} × {months} মাস"),
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
    return ClaimProjection(lines=lines, projected_total=round(sum(x.amount for x in lines), 2), currency=wage.currency if wage else None, label=CLAIM_LABEL)


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
        return BreakEven(note="The contract gives no take-home pay to compare the cost with.")
    frm = promises.recruitment_cost_currency or wage.currency
    cost = convert(promises.recruitment_cost_paid, frm, wage.currency, promises.exchange_rate)
    steps = net_steps(wage.promised, wage.deductions)
    base = dict(monthly_net=wage.net, currency=wage.currency, steps=steps, horizon_months=contract_months, assumption=BREAK_EVEN_ASSUMPTION)
    if cost is None:
        return BreakEven(**base, note=f"The cost is in {_cur(frm)} and the pay in {wage.currency}: enter an exchange rate to compute this. Ain uses no rate of its own.")
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
            return BreakEven(**base, months=round(max(months, 0.0), 1),
                             note="At least this many months of take-home pay on paper to earn back what was paid to get the job.")
        if last is None:  # open-ended and nothing kept: never earned back
            break
        earned += keep * (last - s.from_month + 1)
    if contract_months is not None:
        return BreakEven(**base, earned_back=round(max(earned, 0.0), 2),
                         note=f"Not earned back within the {contract_months}-month contract: {_money(max(earned, 0.0), wage.currency)} of {_money(cost, wage.currency)}, even if all of it is sent home.")
    return BreakEven(**base, note="The contract leaves no take-home pay to earn the cost back.")


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
    pending = pending_risks or []
    promise_risk = next((r for r in [*risks, *pending] if r.rule_id == PROMISE_RULE), None)
    rows = [row for t in TERMS if (row := _row(t, facts, wage, clauses, risks, ledger, promises, promise_risk, pending))]
    months, _ = _months(facts, promises)
    return FourLedgers(
        promises=promises,
        rows=rows,
        claim_projection=claim_projection(facts, wage, risks, ledger, promises),
        pending_risks=pending,
        pending_claims=pending_claims or [],
        promise_gap=promise_gap(facts, promises),
        break_even=break_even(wage, promises, months),
        memo_includes_promises=memo_includes_promises and promises is not None,
    )
