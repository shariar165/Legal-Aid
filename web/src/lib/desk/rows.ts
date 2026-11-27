/* The Case Desk's rows, built from the Four Ledgers payload, or from the risks alone (flag off, older results).
   Pure and display-only: every amount, mismatch and status comes from the backend. The only decisions here are how
   to draw them (spec 20, Phase 1 corrections). */

import type { AnalysisResult, Claim, LawStatus, LedgerCell, LedgerRow, Mismatch, Risk, RiskStatus, Severity, Verification } from "../api";
import type { L10n } from "../citizen/i18n";
import { TERM_NAME } from "./i18n";

/** between two cells: ≠ only where the backend found a mismatch, = only for comparable cells with none, else a dash */
export type Node = "ne" | "eq" | "dash";
export type LawBadge = "violation" | "below_ilo" | "verified" | "partial" | "not_verified" | "pending";

/** A violation of an instrument neither party ratified is a breach of an international standard, not of binding law
 *  here: it reads "Below ILO standard" in amber, not a red "Violation" (step 2.1's ratification table). */
export function persuasiveBadge(badge: LawBadge, result: AnalysisResult, citationId: string | undefined): LawBadge {
  return badge === "violation" && citationId && result.ratification?.[citationId]?.persuasive ? "below_ilo" : badge;
}

/** One law a row rests on, for the evidence file. */
export interface LawRef {
  riskId: string | null;
  title: L10n | null;
  citationIds: string[];
  status: RiskStatus | LawStatus;
  /** the promise gap: what the worker reports may fall under the section, never a proven offence */
  promise: boolean;
}

export interface DeskRow {
  key: string;
  kind: "term" | "risk";
  term: string | null;
  title: L10n;
  severity: Severity | null;
  /** a promise-gap risk raised with no model call, waiting for POST /promises/verify */
  pending: boolean;
  said: LedgerCell | null;
  paper: LedgerCell | null;
  /** what the payslip shows (null until payslips exist) */
  paid: LedgerCell | null;
  saidPaper: Node;
  law: { title: L10n | null; citationIds: string[]; badge: LawBadge | null };
  mismatches: Mismatch[];
  /** the risk the council and the bench votes are about (never a pending one: it is not in the risk list yet) */
  riskId: string | null;
  lawRefs: LawRef[];
  clauseIds: string[];
}

const RANK: Record<Severity, number> = { critical: 0, high: 1, medium: 2, low: 3 };

const STATUS_BADGE: Record<RiskStatus | LawStatus, LawBadge | null> = {
  verified: "verified",
  partial: "partial",
  not_verified: "not_verified",
  not_verified_yet: "pending",
  none: null,
};

/** Can the told and paper cells be set side by side at all? Recruitment cost "already paid" is a fact, not a promise. */
function comparable(row: LedgerRow, rate: { currency: string; per: string } | null | undefined): boolean {
  const { said, paper } = row;
  if (!said || !paper) return false;
  switch (row.term) {
    case "recruitment_cost":
      return false;
    case "salary":
      if (!said.currency || !paper.currency) return false;
      return said.currency === paper.currency || (!!rate && [rate.currency, rate.per].includes(said.currency) && [rate.currency, rate.per].includes(paper.currency));
    case "deductions":
      return said.amount === 0; // "no deductions"; "deductions were mentioned" names no amount to compare
    default:
      return true;
  }
}

function termRow(row: LedgerRow, result: AnalysisResult): DeskRow {
  const four = result.four_ledgers!;
  const svp = row.mismatches.find((m) => m.type === "said_vs_paper");
  const pvl = row.mismatches.find((m) => m.type === "paper_vs_law");
  const promise = svp && svp.title ? svp : undefined;

  let law: DeskRow["law"];
  if (pvl) {
    law = {
      title: pvl.title ?? row.law.title ?? null,
      citationIds: pvl.citation_ids?.length ? pvl.citation_ids : row.law.citation_ids,
      badge: pvl.risk_status === "verified" ? "violation" : STATUS_BADGE[pvl.risk_status ?? row.law.status],
    };
  } else if (promise) {
    law = { title: promise.title ?? null, citationIds: promise.citation_ids ?? [], badge: STATUS_BADGE[promise.risk_status ?? "none"] };
  } else {
    law = { title: row.law.title ?? null, citationIds: row.law.citation_ids, badge: STATUS_BADGE[row.law.status] };
  }

  const lawRefs: LawRef[] = [];
  if (row.law.status !== "none") {
    lawRefs.push({ riskId: row.law.risk_id, title: row.law.title ?? null, citationIds: row.law.citation_ids, status: row.law.status, promise: false });
  }
  if (promise && promise.risk_id !== row.law.risk_id) {
    lawRefs.push({ riskId: promise.risk_id, title: promise.title ?? null, citationIds: promise.citation_ids ?? [], status: promise.risk_status ?? "none", promise: true });
  }

  const pending = row.mismatches.some((m) => m.risk_status === "not_verified_yet");
  const live = (id: string | null | undefined) => (id && result.risks.some((r) => r.id === id && r.status !== "dropped") ? id : null);
  return {
    key: row.term,
    kind: "term",
    term: row.term,
    title: TERM_NAME[row.term] ?? { bn: row.term, en: row.term },
    // a row whose mismatches rest on no verified law has no severity (older results saved "low" for it)
    severity: row.mismatches.some((m) => m.risk_status === "verified" || m.risk_status === "partial") ? row.severity : null,
    pending,
    said: row.said,
    paper: row.paper,
    paid: row.paid,
    saidPaper: svp ? "ne" : comparable(row, four.promises?.exchange_rate) ? "eq" : "dash",
    law,
    mismatches: row.mismatches,
    riskId: live(pvl?.risk_id) ?? live(row.law.risk_id) ?? live(promise?.risk_id),
    lawRefs,
    clauseIds: row.paper?.clause_id ? [row.paper.clause_id] : [],
  };
}

/** The verified or partial claims behind a risk, statutes before voluntary codes. */
export function passedRows(ledger: Verification[], riskId: string): Verification[] {
  return ledger
    .filter((v) => v.claim.risk_id === riskId && (v.verdict === "verified" || v.verdict === "partial"))
    .sort((a, b) => Number(a.section?.kind !== "law") - Number(b.section?.kind !== "law"));
}

function riskRow(risk: Risk, result: AnalysisResult): DeskRow {
  const rows = passedRows(result.ledger, risk.id);
  const ids = Array.from(new Set(rows.map((v) => v.claim.citation_id)));
  const status: LawStatus = rows.some((v) => v.verdict === "verified") ? "verified" : rows.length ? "partial" : "not_verified";
  return {
    key: risk.id,
    kind: "risk",
    term: null,
    title: risk.title,
    severity: risk.severity,
    pending: false,
    said: null,
    paper: null,
    paid: null,
    saidPaper: "dash",
    law: { title: null, citationIds: ids, badge: STATUS_BADGE[status] },
    mismatches: [],
    riskId: risk.id,
    lawRefs: [{ riskId: risk.id, title: null, citationIds: ids, status, promise: false }],
    clauseIds: risk.clause_ids,
  };
}

/** Ledger rows first (the backend's term order), then one row per live risk no ledger row links to, most serious first. */
export function deskRows(result: AnalysisResult): DeskRow[] {
  const four = result.four_ledgers;
  const terms = four ? four.rows.map((r) => termRow(r, result)) : [];
  const covered = new Set<string>();
  for (const r of four?.rows ?? []) {
    for (const id of [r.risk_id, r.law.risk_id, ...r.mismatches.map((m) => m.risk_id)]) if (id) covered.add(id);
  }
  const risks = result.risks
    .filter((r) => r.status !== "dropped" && !covered.has(r.id))
    .sort((a, b) => RANK[a.severity] - RANK[b.severity])
    .map((r) => riskRow(r, result));
  return [...terms, ...risks];
}

/** The row the desk opens on: the first with a mismatch (the money terms come first), else the first. */
export function firstRow(rows: DeskRow[]): string | null {
  return (rows.find((r) => r.mismatches.length) ?? rows[0])?.key ?? null;
}

/** The claim behind a citation on a row: from the citation ledger, or (pending) from the claims waiting for the gates. */
export function claimFor(result: AnalysisResult, citationId: string, riskId: string | null): { verification: Verification | null; claim: Claim | null } {
  const v =
    result.ledger.find((x) => x.claim.citation_id === citationId && (!riskId || x.claim.risk_id === riskId)) ??
    result.ledger.find((x) => x.claim.citation_id === citationId && x.verdict !== "dropped") ??
    null;
  if (v) return { verification: v, claim: v.claim };
  const c = result.four_ledgers?.pending_claims.find((x) => x.citation_id === citationId && (!riskId || x.risk_id === riskId)) ?? null;
  return { verification: null, claim: c };
}
