"""Typed state shared by all agents. The API serialises AnalysisResult as-is to the UI."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator

Severity = Literal["critical", "high", "medium", "low"]
SEVERITY_ORDER: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class L10n(BaseModel):
    bn: str
    en: str


def _legacy_l10n(v: object) -> object:
    """A plain string saved by an older result: the English text, also shown for Bangla until the result is rebuilt."""
    return {"en": v, "bn": v} if isinstance(v, str) else v


class Section(BaseModel):
    """One citable unit of law (a section, article or paragraph) from the corpus."""

    citation_id: str
    jurisdiction: str
    act_key: str
    act: str
    act_en: str
    year: int
    section: str
    heading: str
    text: str
    lang: str
    url: str
    act_url: str
    source: str
    retrieved_at: str
    status: Literal["in_force", "amended", "repealed"] = "in_force"
    superseded_by: str | None = None
    amendment_notes: list[str] = Field(default_factory=list)
    packs: list[str] = Field(default_factory=list)
    # law: a statute or regulation; standard: a voluntary code (ILO principles, Employer Pays, RBA);
    # company_policy: an employer's own published or uploaded policy;
    # supervisory: an ILO supervisory body's observation (CEACR) - how a convention is read and applied, not binding law
    kind: Literal["law", "standard", "company_policy", "supervisory"] = "law"


# ---------------------------------------------------------------- ingestion


class Clause(BaseModel):
    id: str
    index: int
    text: str
    start: int
    end: int


class Deduction(BaseModel):
    label: str
    amount: float
    per: Literal["month", "once"] = "month"
    months: int | None = None


class DocFacts(BaseModel):
    doc_type: str = "unknown"
    languages: list[str] = Field(default_factory=list)
    destination_country: str | None = None
    workplace: str | None = None
    is_epz: bool = False
    epz_name: str | None = None
    is_export_contract: bool = False
    mentions_eu_buyer: bool = False
    mentions_personal_data: bool = False
    governing_law: str | None = None
    salary_amount: float | None = None
    salary_currency: str | None = None
    salary_text: str | None = None
    salary_confidence: float = 1.0
    deductions: list[Deduction] = Field(default_factory=list)
    payment_terms_days: int | None = None
    notice_days: int | None = None
    maternity_days: int | None = None
    # paper terms the Four Ledgers compare with what the worker was told (regex only, see ingestion.extract_facts)
    contract_months: int | None = None
    hours_per_day: int | None = None
    ticket_paid_by: Literal["worker", "employer"] | None = None
    passport_held_by: Literal["worker", "employer"] | None = None
    # fact name (contract_months | hours_per_day | ticket | passport) -> the clause it was read from
    fact_clauses: dict[str, str] = Field(default_factory=dict)
    contract_months_confirmed: bool = False  # the user confirmed or corrected the term (POST /term), like the OCR salary


class OcrCheck(BaseModel):
    field: Literal["salary"] = "salary"
    currency: str
    value: str
    confidence: float


class Document(BaseModel):
    name: str
    source_kind: Literal["text", "pdf", "docx", "image", "sample"]
    text: str
    clauses: list[Clause]
    ocr_used: bool = False
    ocr_confidence: float | None = None
    pages: int = 1


# ---------------------------------------------------------------- privacy


class Redaction(BaseModel):
    placeholder: str
    kind: str


class OutboundCall(BaseModel):
    agent: str
    role: str
    provider: str
    model: str
    chars: int
    cached: bool = False
    fallback: bool = False  # answered by a backup provider or a fallback model, not the configured primary


class PrivacyReceipt(BaseModel):
    redactions: list[Redaction] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    redacted_text: str = ""
    image_left_device: bool = False
    outbound_calls: list[OutboundCall] = Field(default_factory=list)
    pii_leaks_blocked: int = 0


# ---------------------------------------------------------------- routing


class PackDecision(BaseModel):
    pack: str
    label: str
    reason: str


class RouteDecision(BaseModel):
    packs: list[PackDecision]
    excluded: list[PackDecision] = Field(default_factory=list)
    # set when the document is outside Jukti's niche (no employment or migration terms): only general checks ran
    scope_note: L10n | None = None

    @property
    def pack_ids(self) -> set[str]:
        return {p.pack for p in self.packs}


# ---------------------------------------------------------------- risks and claims


class Claim(BaseModel):
    id: str
    risk_id: str
    proposition: str
    citation_id: str
    quote: str | None = None
    origin: Literal["playbook", "adversary", "critic", "drafter", "ablation", "policy"] = "playbook"


GateName = Literal["existence", "fidelity", "entailment", "currency"]
GateStatus = Literal["pass", "warn", "fail", "skip"]


class GateResult(BaseModel):
    gate: GateName
    status: GateStatus
    detail: str


class BenchOpinion(BaseModel):
    seat: str  # "Justice A" - anonymised label shown during peer review
    model: str
    persona: str = ""  # council personality id: happy | proud | gloomy
    name: str = ""  # the persona's display name, e.g. "Sunny"
    lens: str = ""  # the judge's reasoning lens, shown first: Remedies | Text | Enforcement
    verdict: Literal["supports", "neutral", "contradicts"]
    severity: Severity
    reasoning: str
    revised: bool = False
    fallback: bool = False  # answered by a fallback or backup model, not the seat's configured one


class BenchResult(BaseModel):
    question: str
    opinions: list[BenchOpinion]
    majority_verdict: Literal["supports", "neutral", "contradicts"]
    majority_severity: Severity
    vote: str  # e.g. "2–1"
    agreement: Literal["unanimous", "majority", "split", "no_quorum"] = "unanimous"  # on the verdict; a 1-1-1 split has no majority
    severity_range: str | None = None  # "medium–high" when the judges are one notch apart
    majority_opinion: str
    dissent: str | None = None
    human_review: bool = False
    review_reason: str | None = None  # why human review was flagged
    chairman_model: str
    peer_review: bool = True  # False when the first opinions were unanimous and the review round was skipped
    same_family: list[str] = Field(default_factory=list)  # judges whose answering models share a family (after a fallback)
    no_opinion: list[str] = Field(default_factory=list)  # judges whose call failed on every route; they do not vote
    quorum: bool = True  # False when fewer than two judges answered: the single-judge check (Gate 3) decides instead


class Verification(BaseModel):
    claim: Claim
    gates: list[GateResult]
    verdict: Literal["verified", "partial", "dropped"]
    section: Section | None = None
    bench: BenchResult | None = None
    note: str | None = None


class Risk(BaseModel):
    id: str
    rule_id: str | None = None
    origin: Literal["playbook", "adversary", "calculator", "policy"]  # policy: the contract breaks the employer's own policy
    category: str
    title: L10n
    severity: Severity
    clause_ids: list[str] = Field(default_factory=list)
    finding: str  # what the document says / omits
    why_non_obvious: str = ""
    citizen_line: L10n
    action: L10n
    mitigation_clause: str = ""
    clash: str | None = None  # "valid abroad, void in BD" explanation
    claim_ids: list[str] = Field(default_factory=list)
    status: Literal["confirmed", "partial", "dropped"] = "confirmed"
    confidence: float = 0.8
    bench: BenchResult | None = None


# ---------------------------------------------------------------- calculator


class WageCalc(BaseModel):
    currency: str
    promised: float
    confirmed_by_user: bool
    deductions: list[Deduction]
    monthly_deductions: float
    net: float
    pct_deducted: float
    minimum_wage: float | None = None
    minimum_wage_citation: str | None = None
    below_minimum: bool = False
    shortfall: float = 0.0
    deduction_cap_pct: float | None = None
    over_cap: bool = False
    cap_citation: str | None = None


# ---------------------------------------------------------------- four ledgers (told · paper · paid · law)

Party = Literal["worker", "employer", "agency"]


class ExchangeRate(BaseModel):
    """1 `per` = `value` `currency`, e.g. 1 RM = 27.5 BDT. Only ever typed by the user: Jukti has no rate of its own."""

    currency: str = Field(min_length=1, max_length=8)
    per: str = Field(min_length=1, max_length=8)
    value: float = Field(gt=0)
    source: Literal["user-entered"] = "user-entered"


class Promises(BaseModel):
    """What the worker was told (কথা), as structured fields typed by the user. No LLM reads them in v1."""

    salary_amount: float | None = Field(None, gt=0)
    salary_currency: str | None = Field(None, max_length=8)
    no_deductions: bool | None = None
    recruitment_cost_paid: float | None = Field(None, ge=0)
    recruitment_cost_currency: str | None = Field(None, max_length=8)
    hours_per_day: int | None = Field(None, gt=0, le=24)
    ticket_paid_by: Party | None = None
    passport_kept_by: Party | None = None
    contract_months: int | None = Field(None, gt=0, le=240)
    said_on: date | None = None
    note: str = Field("", max_length=1000)  # stored only after the PII Shield has redacted it
    exchange_rate: ExchangeRate | None = None


class LedgerCell(BaseModel):
    value: L10n  # what the cell says, in both languages
    amount: float | None = None
    currency: str | None = None
    party: Party | None = None  # ticket and passport: who pays or who keeps it
    clause_id: str | None = None
    source: Literal["worker", "contract", "payslip", "law"]
    confirmed_by_user: bool = False  # contract term: confirmed or corrected by the user (POST /term)

    @field_validator("value", mode="before")
    @classmethod
    def _legacy_value(cls, v: object) -> object:
        return _legacy_l10n(v)


class LawCell(BaseModel):
    """Filled only from claims that passed the 4 gates; a risk whose claims did not pass leaves it `not_verified`."""

    status: Literal["verified", "partial", "not_verified", "none"] = "none"
    citation_ids: list[str] = Field(default_factory=list)
    risk_id: str | None = None
    proposition: str = ""
    title: L10n | None = None  # a short name for the rule, e.g. "Minimum wage"; None for a risk outside the playbook


MismatchType = Literal["said_vs_paper", "paper_vs_law", "paid_vs_paper"]  # paid_vs_paper: reserved for the payslip spec


class Mismatch(BaseModel):
    type: MismatchType
    detail: L10n
    risk_id: str | None = None
    # the linked risk's standing with the 4 gates; not_verified_yet: raised with no model call (POST /promises), and
    # held back until POST /promises/verify runs the gates on it
    risk_status: Literal["verified", "partial", "not_verified", "not_verified_yet"] | None = None
    # the law the linked risk rests on: a short title and the citations its claims make (passed or, while pending, not)
    title: L10n | None = None
    citation_ids: list[str] = Field(default_factory=list)


class LedgerRow(BaseModel):
    term: str  # salary | deductions | recruitment_cost | hours_per_day | ticket | passport | contract_months
    said: LedgerCell | None = None
    paper: LedgerCell | None = None
    paid: LedgerCell | None = None  # always None in v1 (no payslip yet)
    law: LawCell = Field(default_factory=LawCell)
    mismatches: list[Mismatch] = Field(default_factory=list)
    severity: Severity | None = None
    risk_id: str | None = None


class ClaimLine(BaseModel):
    label: L10n
    amount: float
    currency: str
    citation_id: str
    risk_id: str
    # projected: over the contract term at the rate on paper; accrued: months actually worked (reserved for payslips)
    basis: Literal["projected", "accrued"] = "projected"
    months: int | None = None
    source: str = ""  # where the months or amounts come from, e.g. "contract term on paper"


class ContractTerm(BaseModel):
    """The months a projection runs over, and where that number came from."""

    months: int
    source: Literal["user", "contract", "worker"]  # confirmed by the user | read from the contract | told (none on paper)
    clause_id: str | None = None
    label: L10n


class ClaimProjection(BaseModel):
    """Arithmetic under verified law only. A projection over the contract term, not money owed."""

    lines: list[ClaimLine] = Field(default_factory=list)
    term: ContractTerm | None = None
    projected_total: float = 0.0
    accrued_total: float | None = None  # reserved: needs payslips (months actually worked)
    currency: str | None = None
    label: L10n


class PromiseGap(BaseModel):
    """What was said minus what the paper says. The worker's account: never part of the claim total."""

    monthly: float
    months: int
    total: float
    currency: str
    label: L10n


class NetStep(BaseModel):
    """Take-home pay on paper for a run of months (deductions can stop, e.g. a recruitment recovery for 12 months)."""

    from_month: int
    to_month: int | None = None  # None: to the end of the contract
    net: float


class BreakEven(BaseModel):
    months: float | None = None  # a minimum: see `assumption`
    cost: float | None = None  # in `currency`, after the user's rate if one was needed
    monthly_net: float | None = None  # in month 1
    currency: str | None = None
    rate: ExchangeRate | None = None
    steps: list[NetStep] = Field(default_factory=list)
    horizon_months: int | None = None  # the contract term it was counted over, when known
    earned_back: float | None = None  # set when the cost is not earned back within the contract
    is_minimum: bool = True
    assumption: L10n | None = None
    note: L10n | None = None

    @field_validator("note", mode="before")
    @classmethod
    def _legacy_note(cls, v: object) -> object:
        return None if v == "" else _legacy_l10n(v)


class FourLedgers(BaseModel):
    promises: Promises | None = None
    rows: list[LedgerRow] = Field(default_factory=list)
    claim_projection: ClaimProjection
    # a promise-gap risk raised with no model call (POST /promises): kept out of `risks` and the citation ledger until
    # POST /promises/verify puts its claims through the 4 gates
    pending_risks: list[Risk] = Field(default_factory=list)
    pending_claims: list[Claim] = Field(default_factory=list)
    promise_gap: PromiseGap | None = None
    break_even: BreakEven | None = None
    memo_includes_promises: bool = False


# ---------------------------------------------------------------- outputs


class CitizenCitation(BaseModel):
    name: L10n
    status: Literal["verified", "partial"]
    citation_id: str
    url: str


class CitizenCard(BaseModel):
    kind: Literal["danger", "todo", "deadline", "pay", "policy"]
    title: L10n
    big: L10n | None = None
    lines: list[L10n]
    citations: list[CitizenCitation]


class CitizenView(BaseModel):
    dangerCount: int
    cards: list[CitizenCard]
    letter: L10n


class MemoIssue(BaseModel):
    risk_id: str
    heading: str
    issue: str
    rule: str
    application: str
    conclusion: str
    citation_ids: list[str]
    mitigation_clause: str = ""


class Memo(BaseModel):
    title: str
    prepared_for: str
    executive_summary: str
    summary_bn: str
    jurisdiction_note: str
    issues: list[MemoIssue]
    caveats: list[str]


class TraceEvent(BaseModel):
    t: float
    type: str
    agent: str | None = None
    message: str = ""
    data: dict = Field(default_factory=dict)


class AblationResult(BaseModel):
    plain_model: str
    plain_answer: str
    citations_found: int
    resolvable: int
    supported: int
    rows: list[dict]
    ain_citations: int
    ain_verified: int


class Stats(BaseModel):
    clauses: int = 0
    risks_found: int = 0
    risks_confirmed: int = 0
    claims: int = 0
    verified: int = 0
    partial: int = 0
    dropped: int = 0
    llm_calls: int = 0
    seconds: float = 0.0


class Destination(BaseModel):
    """The country where the job is, as the UI shows it (from ain/countries.yaml)."""

    code: str | None = None  # None: a country we have no labour law for yet
    name: L10n
    of: L10n | None = None  # possessive: "Saudi Arabia's" / "সৌদি আরবের"
    supported: bool = False
    law: str | None = None  # label of the country's law pack
    help: L10n | None = None  # where the worker can get help there


class AnalysisResult(BaseModel):
    job_id: str
    llm_mode: str
    document: Document
    policy: Document | None = None  # the employer's own policy, if one was uploaded (redacted like the contract)
    facts: DocFacts
    destination: Destination | None = None
    route: RouteDecision
    risks: list[Risk]
    ledger: list[Verification]
    wage: WageCalc | None = None
    memo: Memo
    citizen: CitizenView
    privacy: PrivacyReceipt
    trace: list[TraceEvent]
    stats: Stats
    ablation: AblationResult | None = None
    four_ledgers: FourLedgers | None = None  # behind `ledger.enabled`; `ledger` above is the citation ledger

    @computed_field  # type: ignore[prop-decorator]
    @property
    def citation_names(self) -> dict[str, L10n]:
        """Every cited section's name in Bangla and English, built from its corpus record (computed, so older results
        have it too)."""
        from ain.naming import label  # naming imports this module

        return {v.claim.citation_id: label(v.section) for v in self.ledger if v.section is not None}


# ---------------------------------------------------------------- council chat


class CouncilMember(BaseModel):
    id: str  # happy | proud | gloomy
    name: str
    title: str  # e.g. "the Constructive AI"
    tagline: str
    seat: str
    model: str
    lens: str = ""  # Remedies | Text | Enforcement - shown before the name


class ChatTurn(BaseModel):
    speaker: str  # "user" or a council member id
    text: str = Field(max_length=2000)


CouncilLanguage = Literal["en", "bn"]
Confidence = Literal["high", "medium", "low"]


class CouncilChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    members: list[str] = Field(min_length=1, max_length=3)
    risk_id: str | None = None
    history: list[ChatTurn] = Field(default_factory=list)
    language: CouncilLanguage = "en"


class ChangedBecause(BaseModel):
    """What moved a member in round 2: a section or a contract clause new to that member, and a phrase checked against
    its text. Exactly one of citation_id and clause_id is set."""

    citation_id: str | None = None
    clause_id: str | None = None
    quote: str
    label: str = ""  # how the UI names the source, e.g. "Contract Act 1872, s.27"
    url: str = ""
    verified: bool = True  # False: a section retrieved for round 2, which has not been through the 4 gates for this risk


class CouncilReply(BaseModel):
    member: str
    name: str
    model: str
    text: str
    citations: list[str] = Field(default_factory=list)
    position: str = ""  # one-line stance shown as the reply's headline
    confidence: Confidence = "medium"
    round: int = 1  # 1 = first answer, 2 = response to colleagues during deliberation
    revised: bool = False  # round 2 only: the member SAID it changed its position; flip_basis and restated say what happened
    responds_to: str | None = None  # round 2 only: the colleague (member id) mainly addressed
    severity: Severity | None = None  # set when a risk is in focus; None if the model gave no valid rating
    verdict: Literal["supports", "rejects"] | None = None  # risk in focus: does this member uphold the risk's finding?
    stance: Literal["sign", "renegotiate", "do_not_sign"] | None = None  # whole contract: this member's overall advice
    clause_ids: list[str] = Field(default_factory=list)  # contract clauses the answer relies on
    flip_basis: Literal["evidence", "pressure"] | None = None  # round 2 only, decided in code: None = no change of view
    changed_because: ChangedBecause | None = None  # kept only when flip_basis is "evidence": never an unchecked citation
    restated: bool = False  # round 2 only, decided in code: declared a revision, but every rating equals round 1 (not a flip)
    flip_note: str = ""  # why a "pressure" revision does not count (fixed strings, never model text)


class CouncilChatResponse(BaseModel):
    replies: list[CouncilReply]


class CouncilDeliberateRequest(BaseModel):
    """Round 2: every member reads the others' first answers, then the Chief Justice rules."""

    message: str = Field(min_length=1, max_length=1000)
    replies: list[CouncilReply] = Field(min_length=2, max_length=3)
    risk_id: str | None = None
    history: list[ChatTurn] = Field(default_factory=list)
    language: CouncilLanguage = "en"


class CouncilDisagreement(BaseModel):
    point: str
    members: list[str] = Field(default_factory=list)  # member ids on the minority / differing side


class CouncilVote(BaseModel):
    """What a member's vote counts as: a revision that failed the evidence gate leaves round 1 standing."""

    member: str
    severity: Severity | None = None
    verdict: Literal["supports", "rejects"] | None = None
    stance: Literal["sign", "renegotiate", "do_not_sign"] | None = None
    position: str = ""
    flip_basis: Literal["evidence", "pressure"] | None = None


class CouncilRuling(BaseModel):
    agreement: Literal["unanimous", "majority", "split"]
    consensus: str
    disagreements: list[CouncilDisagreement] = Field(default_factory=list)
    next_step: str
    citations: list[str] = Field(default_factory=list)
    model: str = ""
    votes: list[CouncilVote] = Field(default_factory=list)  # computed in code from the counted positions, not by the model


class CouncilDeliberateResponse(BaseModel):
    rebuttals: list[CouncilReply]
    ruling: CouncilRuling


# ---------------------------------------------------------------- accounts


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)  # length policy is enforced (with a clear message) in ain/auth.py


class Me(BaseModel):
    kind: Literal["guest", "account"] | None
    email: str | None = None


class JobSummary(BaseModel):
    job_id: str
    name: str
    created_at: float
