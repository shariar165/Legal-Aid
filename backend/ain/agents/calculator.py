"""Wage Truth Calculator: plain arithmetic, no LLM.

promised salary - monthly deductions = what the worker actually receives, compared with the
legal floor and the legal cap on deductions. Legal numbers come from the country registry
(ain/countries.yaml), each tied to a corpus section (e.g. MY-MWO-2024-p3, SA-LABOR-2005-a93), and
those citations go through the verifier like any other claim.
"""

from __future__ import annotations

from ain import countries
from ain.models import DocFacts, RouteDecision, WageCalc

# (currency, pack) -> (figure, citation) ; values are read from the cited statute text
MINIMUM_WAGES = {
    (c.currency, c.pack): (float(c.min_wage["amount"]), c.min_wage["citation_id"]) for c in countries.load_countries() if c.min_wage
}
DEDUCTION_CAPS = {
    (c.currency, c.pack): (float(c.deduction_cap["pct"]), c.deduction_cap["citation_id"]) for c in countries.load_countries() if c.deduction_cap
}


def compute(facts: DocFacts, route: RouteDecision, salary: float | None = None, confirmed: bool = False) -> WageCalc | None:
    promised = salary if salary is not None else facts.salary_amount
    if promised is None or not facts.salary_currency:
        return None
    cur = facts.salary_currency
    monthly = round(sum(d.amount for d in facts.deductions if d.per == "month"), 2)
    net = round(promised - monthly, 2)
    calc = WageCalc(
        currency=cur,
        promised=promised,
        confirmed_by_user=confirmed,
        deductions=facts.deductions,
        monthly_deductions=monthly,
        net=net,
        pct_deducted=round(100 * monthly / promised, 1) if promised else 0.0,
    )
    for (c, pack), (floor, cid) in MINIMUM_WAGES.items():
        if c == cur and pack in route.pack_ids:
            calc.minimum_wage, calc.minimum_wage_citation = floor, cid
            calc.below_minimum = promised < floor
            calc.shortfall = round(max(0.0, floor - promised), 2)
    for (c, pack), (cap, cid) in DEDUCTION_CAPS.items():
        if c == cur and pack in route.pack_ids:
            calc.deduction_cap_pct, calc.cap_citation = cap, cid
            calc.over_cap = calc.pct_deducted > cap
    if not calc.deductions and calc.minimum_wage is None:
        return None  # nothing to compare against: a bare salary figure adds no insight
    return calc
