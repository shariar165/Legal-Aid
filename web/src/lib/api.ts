/** Typed client for the Ain Copilot backend (FastAPI, see backend/ain/api.py). */

import type { L10n } from "./citizen/i18n";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Severity = "critical" | "high" | "medium" | "low";
export type Verdict = "verified" | "partial" | "dropped";
export type GateStatus = "pass" | "warn" | "fail" | "skip";

export interface Sample {
  id: string;
  kind: "text" | "image";
  title: L10n;
  subtitle: L10n;
}

export interface Health {
  ok: boolean;
  llm_mode: "live" | "replay" | "fake";
  providers: Record<string, boolean>;
  corpus_sections: number;
  acts: number;
  dense_retrieval: boolean;
}

export interface Section {
  citation_id: string;
  act: string;
  act_en: string;
  act_key: string;
  section: string;
  heading: string;
  text: string;
  lang: string;
  url: string;
  source: string;
  retrieved_at: string;
  status: "in_force" | "amended" | "repealed";
  superseded_by: string | null;
  amendment_notes: string[];
}

export interface Claim {
  id: string;
  risk_id: string;
  proposition: string;
  citation_id: string;
  quote: string | null;
  origin: "playbook" | "adversary" | "critic" | "drafter" | "ablation";
}

export interface Gate {
  gate: "existence" | "fidelity" | "entailment" | "currency";
  status: GateStatus;
  detail: string;
}

export type PersonaId = "happy" | "proud" | "gloomy";

export interface BenchOpinion {
  seat: string;
  model: string;
  persona: PersonaId | "";
  name: string;
  verdict: "supports" | "neutral" | "contradicts";
  severity: Severity;
  reasoning: string;
  revised: boolean;
}

export interface BenchResult {
  question: string;
  opinions: BenchOpinion[];
  majority_verdict: string;
  majority_severity: Severity;
  vote: string;
  majority_opinion: string;
  dissent: string | null;
  human_review: boolean;
  chairman_model: string;
}

export interface Verification {
  claim: Claim;
  gates: Gate[];
  verdict: Verdict;
  section: Section | null;
  bench: BenchResult | null;
  note: string | null;
}

export interface Risk {
  id: string;
  rule_id: string | null;
  origin: "playbook" | "adversary" | "calculator";
  category: string;
  title: L10n;
  severity: Severity;
  clause_ids: string[];
  finding: string;
  why_non_obvious: string;
  citizen_line: L10n;
  action: L10n;
  mitigation_clause: string;
  clash: string | null;
  claim_ids: string[];
  status: "confirmed" | "partial" | "dropped";
  confidence: number;
  bench: BenchResult | null;
}

export interface Clause {
  id: string;
  index: number;
  text: string;
}

export interface WageCalc {
  currency: string;
  promised: number;
  confirmed_by_user: boolean;
  deductions: { label: string; amount: number; per: string; months: number | null }[];
  monthly_deductions: number;
  net: number;
  pct_deducted: number;
  minimum_wage: number | null;
  minimum_wage_citation: string | null;
  below_minimum: boolean;
  shortfall: number;
  deduction_cap_pct: number | null;
  over_cap: boolean;
  cap_citation: string | null;
}

export interface CitizenCitation {
  name: L10n;
  status: "verified" | "partial";
  citation_id: string;
  url: string;
}

export type CardKind = "danger" | "todo" | "deadline" | "pay";

export interface CitizenCard {
  kind: CardKind;
  title: L10n;
  big?: L10n | null;
  lines: L10n[];
  citations: CitizenCitation[];
}

export interface CitizenView {
  dangerCount: number;
  cards: CitizenCard[];
  letter: L10n;
}

export interface MemoIssue {
  risk_id: string;
  heading: string;
  issue: string;
  rule: string;
  application: string;
  conclusion: string;
  citation_ids: string[];
  mitigation_clause: string;
}

export interface Memo {
  title: string;
  prepared_for: string;
  executive_summary: string;
  summary_bn: string;
  jurisdiction_note: string;
  issues: MemoIssue[];
  caveats: string[];
}

export interface TraceEvent {
  t: number;
  type: string;
  agent: string | null;
  message: string;
  data: Record<string, unknown>;
}

export interface PackDecision {
  pack: string;
  label: string;
  reason: string;
}

export interface OutboundCall {
  agent: string;
  role: string;
  provider: string;
  model: string;
  chars: number;
  cached: boolean;
}

export interface PrivacyReceipt {
  redactions: { placeholder: string; kind: string }[];
  counts: Record<string, number>;
  redacted_text: string;
  image_left_device: boolean;
  outbound_calls: OutboundCall[];
  pii_leaks_blocked: number;
}

export interface AblationRow {
  risk: string;
  cited: string;
  claim: string;
  citation_id: string | null;
  outcome: "supported" | "unsupported" | "unresolvable" | "repealed" | "inapplicable";
  detail: string;
}

export interface Ablation {
  plain_model: string;
  plain_answer: string;
  citations_found: number;
  resolvable: number;
  supported: number;
  rows: AblationRow[];
  ain_citations: number;
  ain_verified: number;
}

export interface Stats {
  clauses: number;
  risks_found: number;
  risks_confirmed: number;
  claims: number;
  verified: number;
  partial: number;
  dropped: number;
  llm_calls: number;
  seconds: number;
}

export interface AnalysisResult {
  job_id: string;
  llm_mode: string;
  document: { name: string; source_kind: string; text: string; clauses: Clause[]; ocr_used: boolean; ocr_confidence: number | null; pages: number };
  facts: Record<string, unknown>;
  route: { packs: PackDecision[]; excluded: PackDecision[] };
  risks: Risk[];
  ledger: Verification[];
  wage: WageCalc | null;
  memo: Memo;
  citizen: CitizenView;
  privacy: PrivacyReceipt;
  trace: TraceEvent[];
  stats: Stats;
  ablation: Ablation | null;
}

export interface CouncilMember {
  id: PersonaId;
  name: string;
  title: string;
  tagline: string;
  seat: string;
  model: string;
}

export interface ChatTurn {
  speaker: "user" | PersonaId;
  text: string;
}

export type CouncilLanguage = "en" | "bn";

export interface CouncilReply {
  member: PersonaId;
  name: string;
  model: string;
  text: string;
  citations: string[];
  /** one-line stance shown as the reply's headline */
  position: string;
  confidence: "high" | "medium" | "low";
  /** 1 = first answer, 2 = response to colleagues during deliberation */
  round: number;
  revised: boolean;
  responds_to: PersonaId | null;
}

export interface CouncilChatBody {
  message: string;
  members: PersonaId[];
  risk_id?: string | null;
  history?: ChatTurn[];
  language?: CouncilLanguage;
}

export interface CouncilDeliberateBody {
  message: string;
  replies: CouncilReply[];
  risk_id?: string | null;
  history?: ChatTurn[];
  language?: CouncilLanguage;
}

export interface CouncilRuling {
  agreement: "unanimous" | "majority" | "split";
  consensus: string;
  disagreements: { point: string; members: PersonaId[] }[];
  next_step: string;
  citations: string[];
  model: string;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : (body.detail?.[0]?.msg ?? detail);
    } catch {
      /* not JSON */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => fetch(`${API_URL}/api/health`).then((r) => json<Health>(r)),
  samples: () => fetch(`${API_URL}/api/samples`).then((r) => json<Sample[]>(r)),
  analyzeSample(sampleId: string) {
    const form = new FormData();
    form.append("sample_id", sampleId);
    return fetch(`${API_URL}/api/analyze`, { method: "POST", body: form }).then((r) => json<{ job_id: string; name: string }>(r));
  },
  analyzeFile(file: File) {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${API_URL}/api/analyze`, { method: "POST", body: form }).then((r) => json<{ job_id: string; name: string }>(r));
  },
  confirm: (jobId: string, value: string) =>
    fetch(`${API_URL}/api/jobs/${jobId}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ field: "salary", value }),
    }).then((r) => json<{ ok: boolean; value: number }>(r)),
  status: (jobId: string) => fetch(`${API_URL}/api/jobs/${jobId}`).then((r) => json<{ status: string; error: string | null }>(r)),
  result: (jobId: string) => fetch(`${API_URL}/api/jobs/${jobId}/result`).then((r) => json<AnalysisResult>(r)),
  ablation: (jobId: string) => fetch(`${API_URL}/api/jobs/${jobId}/ablation`, { method: "POST" }).then((r) => json<Ablation>(r)),
  council: () => fetch(`${API_URL}/api/council`).then((r) => json<CouncilMember[]>(r)),
  councilChat: (jobId: string, body: CouncilChatBody) =>
    fetch(`${API_URL}/api/jobs/${jobId}/council/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => json<{ replies: CouncilReply[] }>(r)),
  councilDeliberate: (jobId: string, body: CouncilDeliberateBody) =>
    fetch(`${API_URL}/api/jobs/${jobId}/council/deliberate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => json<{ rebuttals: CouncilReply[]; ruling: CouncilRuling }>(r)),
  memoUrl: (jobId: string) => `${API_URL}/api/jobs/${jobId}/memo.docx`,
  eventsUrl: (jobId: string) => `${API_URL}/api/jobs/${jobId}/events`,
};
