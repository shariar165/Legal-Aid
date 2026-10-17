"""Typed state shared by all agents. The API serialises AnalysisResult as-is to the UI."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "high", "medium", "low"]
SEVERITY_ORDER: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class L10n(BaseModel):
    bn: str
    en: str


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
    origin: Literal["playbook", "adversary", "critic", "drafter", "ablation"] = "playbook"


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
    verdict: Literal["supports", "neutral", "contradicts"]
    severity: Severity
    reasoning: str
    revised: bool = False


class BenchResult(BaseModel):
    question: str
    opinions: list[BenchOpinion]
    majority_verdict: Literal["supports", "neutral", "contradicts"]
    majority_severity: Severity
    vote: str  # e.g. "2–1"
    majority_opinion: str
    dissent: str | None = None
    human_review: bool = False
    chairman_model: str


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
    origin: Literal["playbook", "adversary", "calculator"]
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


# ---------------------------------------------------------------- outputs


class CitizenCitation(BaseModel):
    name: L10n
    status: Literal["verified", "partial"]
    citation_id: str
    url: str


class CitizenCard(BaseModel):
    kind: Literal["danger", "todo", "deadline", "pay"]
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


class AnalysisResult(BaseModel):
    job_id: str
    llm_mode: str
    document: Document
    facts: DocFacts
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


# ---------------------------------------------------------------- council chat


class CouncilMember(BaseModel):
    id: str  # happy | proud | gloomy
    name: str
    title: str  # e.g. "the Happy AI"
    tagline: str
    seat: str
    model: str


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


class CouncilReply(BaseModel):
    member: str
    name: str
    model: str
    text: str
    citations: list[str] = Field(default_factory=list)
    position: str = ""  # one-line stance shown as the reply's headline
    confidence: Confidence = "medium"
    round: int = 1  # 1 = first answer, 2 = response to colleagues during deliberation
    revised: bool = False  # round 2 only: the member changed their position
    responds_to: str | None = None  # round 2 only: the colleague (member id) mainly addressed


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


class CouncilRuling(BaseModel):
    agreement: Literal["unanimous", "majority", "split"]
    consensus: str
    disagreements: list[CouncilDisagreement] = Field(default_factory=list)
    next_step: str
    citations: list[str] = Field(default_factory=list)
    model: str = ""


class CouncilDeliberateResponse(BaseModel):
    rebuttals: list[CouncilReply]
    ruling: CouncilRuling
