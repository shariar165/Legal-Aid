/** Rehearsal Council client (backend/ain/api.py, /api/rehearsals). Types mirror ain/models.py. */

import { API_URL, type Gate, type PersonaId, type Section, type TraceEvent, type Verification } from "../api";
import type { L10n } from "../citizen/i18n";

export type PassportKeeper = "me" | "agent" | "employer" | "unsure";
export type WorkerAction = "none" | "paid" | "gave_passport";

export interface PromisedTerms {
  salary: string;
  total_cost: string;
  job: string;
  duration: string;
  passport_keeper: PassportKeeper;
  paid_so_far: string;
  extra: string[];
}

export interface RehearsalSetup {
  country: string | null;
  job: string;
  promises: PromisedTerms;
  has_contract: boolean;
  through_dalal: boolean;
  job_id: string | null;
  language: "bn" | "en";
}

export interface CoachHint {
  member: PersonaId;
  name: string;
  lens: string;
  text: string;
  /** Sunny only: a polite reply the worker can tap */
  say: string;
  citations: string[];
  /** Regal only: the evidence gate on his one citation */
  gates: Gate[];
  /** why a citation or the model's hint was not shown ("" if nothing was dropped) */
  dropped: string;
}

export interface RehearsalTurn {
  n: number;
  tactic_id: string;
  /** the tactic's name, shown once the worker has answered */
  label: L10n | null;
  dalal_line: string;
  /** why the model's own line was replaced by the tactic's curated line */
  guardrail: string;
  worker_reply: string;
  action: WorkerAction;
  hints: CoachHint[];
  hits: string[];
}

export interface RubricItem {
  id: string;
  label: L10n;
  status: "met" | "missed" | "not_tested";
  turn: number | null;
  weight: number;
}

export interface RehearsalDebrief {
  score: number;
  items: RubricItem[];
  checklist: L10n[];
  note: string;
  citations: string[];
  model: string;
}

export interface PromiseRow {
  field: string;
  label: L10n;
  promised: string;
  checks: Verification[];
  unverified: string[];
  note: L10n | null;
}

export interface ComplaintPath {
  id: string;
  label: L10n;
  check: Verification;
}

export interface PromiseContacts {
  agent_name: string;
  agent_phone: string;
  agency_name: string;
  place: string;
  notes: string;
}

export interface PromiseRecord {
  created_at: string;
  contacts: PromiseContacts;
  rows: PromiseRow[];
  paths: ComplaintPath[];
  unverified: string[];
}

export interface RehearsalSession {
  id: string;
  created_at: number;
  setup: RehearsalSetup;
  turns: RehearsalTurn[];
  status: "running" | "done";
  debrief: RehearsalDebrief | null;
  record: PromiseRecord | null;
  mode: string;
}

/** The worker's own values, put back on this machine for the print view. */
export interface RecordPrint {
  contacts: PromiseContacts;
  rows: { field: string; promised: string }[];
  job: string;
}

export type { TraceEvent };

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

const call = (path: string, init?: RequestInit) => fetch(`${API_URL}${path}`, { credentials: "include", ...init });
const post = (path: string, body?: unknown) =>
  call(path, body === undefined ? { method: "POST" } : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

const sections = new Map<string, Promise<Section | null>>();

export const rehearsalApi = {
  create: (setup: RehearsalSetup) => post("/api/rehearsals", setup).then((r) => json<{ id: string }>(r)),
  get: (id: string) => call(`/api/rehearsals/${id}`).then((r) => json<RehearsalSession>(r)),
  turn: (id: string, reply: string, action: WorkerAction) => post(`/api/rehearsals/${id}/turns`, { reply, action }).then((r) => json<{ ok: boolean }>(r)),
  finish: (id: string) => post(`/api/rehearsals/${id}/finish`).then((r) => json<{ ok: boolean }>(r)),
  saveContacts: (id: string, contacts: PromiseContacts) => post(`/api/rehearsals/${id}/record`, contacts).then((r) => json<RehearsalSession>(r)),
  print: (id: string) => call(`/api/rehearsals/${id}/record/print`).then((r) => json<RecordPrint>(r)),
  remove: (id: string) => call(`/api/rehearsals/${id}`, { method: "DELETE" }).then((r) => json<{ ok: boolean }>(r)),
  eventsUrl: (id: string) => `${API_URL}/api/rehearsals/${id}/events`,
  docxUrl: (id: string) => `${API_URL}/api/rehearsals/${id}/record.docx`,
  /** A corpus section for a citation chip, fetched once per page. */
  section(citationId: string): Promise<Section | null> {
    let p = sections.get(citationId);
    if (!p) {
      p = call(`/api/corpus/${encodeURIComponent(citationId)}`)
        .then((r) => (r.ok ? (r.json() as Promise<Section>) : null))
        .catch(() => null);
      sections.set(citationId, p);
    }
    return p;
  },
};
