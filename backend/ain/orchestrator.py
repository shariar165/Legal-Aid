"""Orchestrator: runs the agent graph for one document and streams a trace.

    Ingestion -> PII Shield -> Jurisdiction Router
        -> [Risk Analyst (text rules) || Adversarial Counsel || Wage Calculator (waits for human salary check)]
        -> Risk Analyst (fact rules) -> Citation Verifier (+ Virtual Bench) -> Critic -> Memo Drafter

Every step emits TraceEvents onto the job, which the API streams to the UI over SSE.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field

from ain import companies, config, countries, vault
from ain.agents import adversary, calculator, critic, drafter, ingestion, policy_check, risk_analyst, router, verifier
from ain.agents.pii import redact
from ain.llm import LLM
from ain.models import AnalysisResult, Claim, OcrCheck, OutboundCall, PackDecision, Stats, TraceEvent, Verification
from ain.retrieval import CorpusOverlay, get_corpus

CONFIRM_TIMEOUT_S = 600.0
OCR_CONFIDENCE_FLOOR = 0.9

# Procedural facts the citizen cards rely on (deadline / what to do). They are claims like any
# other and must pass the same gates before they are shown.
PROCEDURAL = {
    "bd_migration": [
        ("BD-OEMA-2013-s20", "Under OEMA 2013 s.20, the Bureau (BMET) issues emigration clearance to each registered worker, after migration formalities are completed, on an electronic card carrying biometric and migration data.", "বহির্গমন ছাড়পত্র প্রদান করিবে"),
        ("BD-OEMA-2013-s22", "Under OEMA 2013 s.22(3), the recruiting agent must send a copy of the employment contract to the Bureau and to the Bangladesh Mission abroad.", "চুক্তির অনুলিপি ব্যুরো এবং বিদেশে অবস্থিত বাংলাদেশ মিশন বা দূতাবাসে প্রেরণ করিবেন"),
    ]
}


@dataclass
class Job:
    id: str
    name: str
    t0: float = field(default_factory=time.time)
    status: str = "running"  # running | waiting | done | error
    events: list[TraceEvent] = field(default_factory=list)
    result: AnalysisResult | None = None
    error: str | None = None
    confirmed_salary: float | None = None
    _confirm: asyncio.Event = field(default_factory=asyncio.Event)
    _changed: asyncio.Condition = field(default_factory=asyncio.Condition)

    def emit(self, ev: TraceEvent) -> None:
        ev.t = round(time.time() - self.t0, 2)
        self.events.append(ev)
        asyncio.get_event_loop().create_task(self._notify())

    async def _notify(self) -> None:
        async with self._changed:
            self._changed.notify_all()

    def say(self, type_: str, agent: str | None = None, message: str = "", **data) -> None:
        self.emit(TraceEvent(t=0, type=type_, agent=agent, message=message, data=data))

    def confirm(self, value: float) -> None:
        self.confirmed_salary = value
        self._confirm.set()

    async def wait_confirm(self, timeout: float) -> bool:
        try:
            await asyncio.wait_for(self._confirm.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def stream(self, start: int = 0):
        i = start
        while True:
            while i < len(self.events):
                yield i, self.events[i]
                i += 1
            if self.status in ("done", "error"):
                return
            async with self._changed:
                try:
                    await asyncio.wait_for(self._changed.wait(), 15)
                except asyncio.TimeoutError:
                    yield i, None  # keep-alive


JOBS: dict[str, Job] = {}


def new_job(name: str) -> Job:
    job = Job(id=uuid.uuid4().hex[:12], name=name)
    JOBS[job.id] = job
    return job


async def run_pipeline(
    job: Job, data: bytes, filename: str, source_kind: str | None = None, llm_mode: str | None = None,
    confirm_timeout: float = CONFIRM_TIMEOUT_S, llm: LLM | None = None, destination: str | None = None,
    policy: tuple[bytes, str] | None = None,
) -> AnalysisResult:
    """`destination` is the country the user picked when the document does not name one clearly;
    `policy` is the employer's own policy or handbook as (file bytes, file name), checked against the contract."""
    try:
        return await _run(job, data, filename, source_kind, llm_mode, confirm_timeout, llm, destination, policy)
    except Exception as e:  # surfaced to the UI; the trace keeps what happened before
        job.status = "error"
        job.error = f"{type(e).__name__}: {e}"
        job.say("error", None, job.error)
        raise


async def _run(
    job: Job, data: bytes, filename: str, source_kind: str | None, llm_mode: str | None, confirm_timeout: float, llm: LLM | None,
    destination: str | None, policy: tuple[bytes, str] | None,
) -> AnalysisResult:
    t_start = time.time()

    def on_call(call: OutboundCall) -> None:
        job.say("llm_call", call.agent, f"{call.provider}/{call.model}" + (" (cached)" if call.cached else ""), role=call.role, chars=call.chars, cached=call.cached)

    if llm is None:
        llm = LLM(mode=llm_mode, on_call=on_call)
    else:
        llm._on_call = on_call
    corpus = get_corpus()
    job.say("start", None, f"Analysing {filename}", llm_mode=llm.mode)

    # 1. ingestion -----------------------------------------------------------------
    job.say("agent_start", "Ingestion", "Reading the document")
    doc, facts, ex = await asyncio.to_thread(ingestion.build_document, data, filename, source_kind)
    job.say("agent_done", "Ingestion", f"{len(doc.clauses)} clauses" + (f", OCR confidence {doc.ocr_confidence:.0%}" if doc.ocr_confidence is not None else ""), clauses=len(doc.clauses), ocr=doc.ocr_used)
    job.say("step", None, "read", step="read")

    # 2. PII shield ----------------------------------------------------------------
    job.say("agent_start", "PII Shield", "Hiding personal identifiers")
    red = redact(doc.text)
    mapping = red.mapping
    privacy = red.receipt()
    privacy.image_left_device = False

    def red_text(t: str) -> str:
        return redact(t, mapping).text

    job.say("agent_done", "PII Shield", f"{len(red.redactions)} identifiers redacted", counts=privacy.counts)

    # 2b. the employer's own policy: read and redacted exactly like the contract (same placeholders)
    policy_doc, policy_secs = None, []
    if policy:
        pdoc, _, _ = await asyncio.to_thread(ingestion.build_document, policy[0], policy[1], None)
        pred = redact(pdoc.text, mapping)
        mapping = pred.mapping  # red_text() reads this, so placeholders stay the same across both documents
        privacy.redactions += pred.redactions
        for r in pred.redactions:
            privacy.counts[r.kind] = privacy.counts.get(r.kind, 0) + 1
        policy_doc = pdoc.model_copy(update={"text": pred.text, "clauses": [c.model_copy(update={"text": red_text(c.text)}) for c in pdoc.clauses]})
        policy_secs = policy_check.sections_from_clauses(policy_doc.clauses, policy[1], "uploaded by the user")
        job.say("agent_done", "PII Shield", f"Employer policy: {len(policy_doc.clauses)} clauses, {len(pred.redactions)} identifiers redacted")
    job.say("step", None, "redact", step="redact")

    # 3. routing -------------------------------------------------------------------
    job.say("agent_start", "Jurisdiction Router", "Choosing the applicable law")
    facts = await router.refine_facts(llm, facts, red.text)
    if picked := countries.by_name(destination):  # the user's choice beats detection
        facts.destination_country = picked.name["en"]
    route = router.decide(facts, doc.text.lower())
    if policy_secs:
        route.packs.append(PackDecision(pack=policy_check.POLICY_PACK, label=policy_check.POLICY_LABEL, reason="The user added the employer's own policy; the contract is checked against what it promises."))
        corpus = CorpusOverlay(corpus, policy_secs)  # the policy's clauses become citable for this job only
    # a named employer whose own published policy is in the corpus (corpus/companies.yaml)
    company = companies.detect(doc.text)
    company_secs = [s for s in corpus.sections if company and company.pack in s.packs]
    if company_secs:
        route.packs.append(PackDecision(pack=company.pack, label=company.label, reason=f"The contract names {company.name}; the company's own published policy is checked against the contract."))
    job.say("agent_done", "Jurisdiction Router", ", ".join(p.label for p in route.packs), packs=[p.pack for p in route.packs], excluded=[p.model_dump() for p in route.excluded])

    # human-in-the-loop: a blurry salary must be confirmed before the wage maths runs
    need_confirm = doc.ocr_used and facts.salary_amount is not None and facts.salary_confidence < OCR_CONFIDENCE_FLOOR

    async def wage_task():
        salary, confirmed = facts.salary_amount, False
        if need_confirm:
            check = OcrCheck(currency=facts.salary_currency or "", value=f"{facts.salary_amount:,.0f}", confidence=facts.salary_confidence)
            job.status = "waiting"
            job.say("ocr_check", "Wage Calculator", "Please confirm the salary read from the photo", **check.model_dump())
            if await job.wait_confirm(confirm_timeout):
                salary, confirmed = job.confirmed_salary, True
            job.status = "running"
        job.say("agent_start", "Wage Calculator", "Computing take-home pay")
        w = calculator.compute(facts, route, salary, confirmed)
        if w:
            job.say("agent_done", "Wage Calculator", f"In hand {w.currency} {w.net:,.0f} of {w.promised:,.0f} ({w.pct_deducted}% deducted)", **w.model_dump(include={"net", "pct_deducted", "below_minimum", "over_cap"}))
        else:
            job.say("agent_done", "Wage Calculator", "No salary terms to compute")
        return w

    # 4. parallel analysis ------------------------------------------------------------
    job.say("agent_start", "Risk Analyst", "Running the playbook")
    job.say("agent_start", "Adversarial Counsel", "Looking for what the playbook missed")
    text_task = asyncio.create_task(risk_analyst.run_text_rules(llm, doc.clauses, route, red_text, start=1))
    wage_t = asyncio.create_task(wage_task())
    text_risks, text_claims = await text_task
    for r in text_risks:
        job.say("risk_found", "Risk Analyst", r.title.en, risk_id=r.id, severity=r.severity, origin=r.origin)
    adv_t = asyncio.create_task(
        adversary.run(llm, corpus, doc.clauses, facts, route, text_risks, red_text, doc.text, start=100, emit=job.emit)
    )
    wage = await wage_t
    fact_risks, fact_claims = risk_analyst.run_fact_rules(facts, wage, doc.clauses, route, start=len(text_risks) + 1)
    for r in fact_risks:
        job.say("risk_found", "Risk Analyst", r.title.en, risk_id=r.id, severity=r.severity, origin=r.origin)
    job.say("agent_done", "Risk Analyst", f"{len(text_risks) + len(fact_risks)} playbook risks")
    adv_risks, adv_claims, rejected = await adv_t
    # renumber adversary risks to follow the playbook ones
    n = len(text_risks) + len(fact_risks)
    for r in adv_risks:
        n += 1
        old = r.id
        r.id = f"R{n}"
        r.claim_ids = [cid.replace(f"{old}.", f"{r.id}.", 1) for cid in r.claim_ids]
        for c in adv_claims:
            if c.risk_id == old:
                c.risk_id = r.id
                c.id = c.id.replace(f"{old}.", f"{r.id}.", 1)
        job.say("risk_found", "Adversarial Counsel", r.title.en, risk_id=r.id, severity=r.severity, origin="adversary")
    for rj in rejected:
        job.say("citation_rejected", "Adversarial Counsel", f"{rj['citation_id']}: {rj['reason']}", **rj)
    job.say("agent_done", "Adversarial Counsel", f"{len(adv_risks)} additional risks")

    pol_risks, pol_claims = [], []
    if policy_secs:
        job.say("agent_start", "Policy Check", "Comparing the contract with the employer's own policy")
        pol_risks, pol_claims = await policy_check.run(llm, doc.clauses, policy_secs, red_text, start=n + 1, source_label="own policy (uploaded)")
        for r in pol_risks:
            job.say("risk_found", "Policy Check", r.title.en, risk_id=r.id, severity=r.severity, origin="policy")
        job.say("agent_done", "Policy Check", f"{len(pol_risks)} contradiction(s) with the employer's policy")
    if company_secs:
        job.say("agent_start", "Policy Check", f"Comparing the contract with {company.name}'s published policy")
        co_risks, co_claims = await policy_check.run(llm, doc.clauses, company_secs, red_text, start=n + 1 + len(pol_risks), source_label=company.source_label)
        for r in co_risks:
            job.say("risk_found", "Policy Check", r.title.en, risk_id=r.id, severity=r.severity, origin="policy")
        job.say("agent_done", "Policy Check", f"{len(co_risks)} contradiction(s) with {company.name}'s published policy")
        pol_risks, pol_claims = pol_risks + co_risks, pol_claims + co_claims
    job.say("step", None, "match", step="match")

    risks = text_risks + fact_risks + adv_risks + pol_risks
    claims: list[Claim] = text_claims + fact_claims + adv_claims + pol_claims
    proc_claims = [
        Claim(id=f"P{i + 1}", risk_id="P", proposition=prop, citation_id=cid, quote=q, origin="drafter")
        for pack, items in PROCEDURAL.items() if pack in route.pack_ids for i, (cid, prop, q) in enumerate(items)
    ]

    # 5. verification ----------------------------------------------------------------
    job.say("agent_start", "Citation Verifier", f"Checking {len(claims) + len(proc_claims)} legal claims through 4 gates")

    def on_verified(v: Verification) -> None:
        kind = {"verified": "claim_verified", "partial": "claim_partial", "dropped": "claim_dropped"}[v.verdict]
        job.say(kind, "Citation Verifier", f"{v.claim.citation_id}: {v.verdict}", claim_id=v.claim.id, citation_id=v.claim.citation_id, gates={g.gate: g.status for g in v.gates})
        if v.bench:
            job.say("bench_ruling", "Virtual Bench", f"{v.bench.vote} {v.bench.majority_verdict}, severity {v.bench.majority_severity}" + (" · dissent" if v.bench.human_review else ""), claim_id=v.claim.id, human_review=v.bench.human_review)

    ledger = await verifier.verify_all(llm, corpus, route, risks, claims, on_result=on_verified)
    proc_ledger = await verifier.verify_all(llm, corpus, route, [], proc_claims)
    job.say("agent_done", "Citation Verifier", f"{sum(v.verdict == 'verified' for v in ledger)} verified · {sum(v.verdict == 'partial' for v in ledger)} partial · {sum(v.verdict == 'dropped' for v in ledger)} dropped")

    job.say("agent_start", "Critic", "Re-checking dropped claims and enforcing citation rules")
    healed = await critic.heal(llm, corpus, route, risks, ledger, on_result=on_verified)
    job.say("agent_done", "Critic", f"{len(healed)} claim(s) re-anchored; {sum(r.status == 'dropped' for r in risks)} risk(s) withdrawn")

    # 6. drafting ----------------------------------------------------------------------
    job.say("agent_start", "Memo Drafter", "Writing the memorandum")
    memo, letter = await drafter.draft(llm, doc.name, facts, route, risks, ledger, wage, job.emit)
    citizen = drafter.citizen_view(route, risks, ledger, wage, letter, [v for v in proc_ledger if v.verdict != "dropped"])
    job.say("agent_done", "Memo Drafter", f"{len(memo.issues)} issues in the memo")
    job.say("step", None, "verify", step="verify")

    privacy.outbound_calls = llm.calls
    privacy.pii_leaks_blocked = llm.blocked
    full_ledger = ledger + proc_ledger
    stats = Stats(
        clauses=len(doc.clauses),
        risks_found=len(risks),
        risks_confirmed=sum(r.status != "dropped" for r in risks),
        claims=len(full_ledger),
        verified=sum(v.verdict == "verified" for v in full_ledger),
        partial=sum(v.verdict == "partial" for v in full_ledger),
        dropped=sum(v.verdict == "dropped" for v in full_ledger),
        llm_calls=len(llm.calls),
        seconds=round(time.time() - t_start, 2),
    )
    result = AnalysisResult(
        job_id=job.id,
        llm_mode=llm.mode,
        # only redacted text is ever stored or served
        document=doc.model_copy(update={"text": red.text, "clauses": [c.model_copy(update={"text": red_text(c.text)}) for c in doc.clauses]}),
        policy=policy_doc,
        facts=facts,
        destination=countries.destination(facts.destination_country),
        route=route,
        risks=risks,
        ledger=full_ledger,
        wage=wage,
        memo=memo,
        citizen=citizen,
        privacy=privacy,
        trace=[],
        stats=stats,
    )
    job.result = result
    job.status = "done"
    job.say("done", None, f"{stats.risks_confirmed} risks · {stats.verified} verified claims · {stats.dropped} dropped", stats=stats.model_dump())
    result.trace = list(job.events)
    save_result(result)
    return result


def _run_path(job_id: str):
    return config.RUNS_DIR / f"{job_id}.json.enc"


def save_result(result: AnalysisResult) -> None:
    """The only way results reach disk: encrypted (see ain/vault.py)."""
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    _run_path(result.job_id).write_bytes(vault.encrypt(result.model_dump_json().encode("utf-8")))


def load_result(job_id: str) -> AnalysisResult | None:
    job = JOBS.get(job_id)
    if job and job.result:
        return job.result
    path = _run_path(job_id)
    if path.exists():
        return AnalysisResult.model_validate_json(vault.decrypt(path.read_bytes()))
    return None


def delete_result(job_id: str) -> None:
    JOBS.pop(job_id, None)
    _run_path(job_id).unlink(missing_ok=True)
