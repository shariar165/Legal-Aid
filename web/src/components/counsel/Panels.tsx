"use client";

import { useMemo, useState } from "react";
import { api, type Ablation, type AnalysisResult, type TraceEvent, type Verdict } from "@/lib/api";
import { citeLabel, GATE_SYMBOL, GATES, OUTCOME, VERDICT_LABEL } from "./format";
import styles from "./counsel.module.css";

/* ------------------------------------------------------------------ Ledger */

export function LedgerPanel({ result }: { result: AnalysisResult }) {
  const [filter, setFilter] = useState<Verdict | "all">("all");
  const rows = result.ledger.filter((v) => filter === "all" || v.verdict === filter);
  const count = (v: Verdict) => result.ledger.filter((x) => x.verdict === v).length;

  return (
    <div className={styles.panel}>
      <p className={styles.panelLead}>
        Every legal proposition the agents produced, and what the four gates decided. Dropped claims stay here and never reach
        the memo.
      </p>
      <div className={styles.filters} role="group" aria-label="Filter ledger">
        {(["all", "verified", "partial", "dropped"] as const).map((f) => (
          <button key={f} type="button" aria-pressed={filter === f} className={styles.filterBtn} data-f={f} onClick={() => setFilter(f)}>
            {f === "all" ? `All ${result.ledger.length}` : `${VERDICT_LABEL[f]} ${count(f)}`}
          </button>
        ))}
      </div>
      <div className={styles.gateLegend}>
        {GATES.map((g) => (
          <span key={g.id}>
            <b>{g.short}</b> {g.name}
          </span>
        ))}
      </div>
      <ol className={styles.ledger}>
        {rows.map((v) => (
          <li key={v.claim.id} className={styles.ledgerRow} data-verdict={v.verdict}>
            <div className={styles.ledgerTop}>
              <span className={styles.claimId}>{v.claim.id}</span>
              {v.section ? (
                <a href={v.section.url} target="_blank" rel="noreferrer" className={styles.citeLink}>
                  {citeLabel(v.section)}
                </a>
              ) : (
                <code>{v.claim.citation_id}</code>
              )}
              <span className={styles.verdictPill} data-verdict={v.verdict}>
                {VERDICT_LABEL[v.verdict]}
              </span>
            </div>
            <p className={styles.prop}>{v.claim.proposition}</p>
            <div className={styles.gates}>
              {GATES.map((g) => {
                const gate = v.gates.find((x) => x.gate === g.id);
                const st = gate?.status ?? "skip";
                return (
                  <span key={g.id} className={styles.gate} data-status={st} title={`${g.name}: ${gate?.detail ?? ""}`}>
                    {g.short} {GATE_SYMBOL[st]}
                  </span>
                );
              })}
              <span className={styles.originTag}>{v.claim.origin}</span>
            </div>
            {v.gates
              .filter((g) => g.status === "fail" || g.status === "warn")
              .map((g) => (
                <p key={g.gate} className={styles.gateDetail} data-status={g.status}>
                  {g.detail}
                </p>
              ))}
            {v.note && <p className={styles.gateDetail}>{v.note}</p>}
            {v.claim.quote && v.section && (
              <blockquote className={styles.quote} lang={v.section.lang}>
                “{v.claim.quote}”
              </blockquote>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}

/* ------------------------------------------------------------------ Trace */

const AGENT_ORDER = ["Ingestion", "PII Shield", "Jurisdiction Router", "Risk Analyst", "Adversarial Counsel", "Wage Calculator", "Citation Verifier", "Virtual Bench", "Critic", "Memo Drafter"];

export function TracePanel({ events }: { events: TraceEvent[] }) {
  const [showCalls, setShowCalls] = useState(false);
  const calls = events.filter((e) => e.type === "llm_call");
  const shown = events.filter((e) => e.type !== "ping" && (showCalls || e.type !== "llm_call"));
  const agents = useMemo(() => {
    const seen = new Map<string, { start?: number; end?: number; msg?: string }>();
    for (const e of events) {
      if (!e.agent) continue;
      const base = AGENT_ORDER.find((a) => e.agent!.startsWith(a)) ?? e.agent;
      const cur = seen.get(base) ?? {};
      if (e.type === "agent_start" && cur.start === undefined) cur.start = e.t;
      if (e.type === "agent_done") {
        cur.end = e.t;
        cur.msg = e.message;
      }
      seen.set(base, cur);
    }
    return AGENT_ORDER.filter((a) => seen.has(a)).map((a) => ({ name: a, ...seen.get(a)! }));
  }, [events]);

  return (
    <div className={styles.panel}>
      <div className={styles.agentGrid}>
        {agents.map((a) => (
          <div key={a.name} className={styles.agentCell} data-state={a.end !== undefined ? "done" : "run"}>
            <b>{a.name}</b>
            <span>{a.end !== undefined ? a.msg : "working…"}</span>
          </div>
        ))}
      </div>
      <label className={styles.toggle}>
        <input type="checkbox" checked={showCalls} onChange={(e) => setShowCalls(e.target.checked)} /> Show {calls.length} model calls
      </label>
      <ol className={styles.trace}>
        {shown.map((e, i) => (
          <li key={i} className={styles.traceRow} data-type={e.type}>
            <span className={styles.traceT}>{e.t.toFixed(2)}s</span>
            <span className={styles.traceAgent}>{e.agent ?? "system"}</span>
            <span className={styles.traceMsg}>{e.type === "step" ? `step complete: ${e.message}` : e.message}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

/* ------------------------------------------------------------------ Ablation */

export function AblationPanel({ result }: { result: AnalysisResult }) {
  const [data, setData] = useState<Ablation | null>(result.ablation);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setData(await api.ablation(result.job_id));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!data) {
    return (
      <div className={styles.panel}>
        <p className={styles.panelLead}>
          Ask a single language model, with one plain prompt, to find the risks and cite the law. Then run its citations through the
          same gates and compare.
        </p>
        <button type="button" className={styles.primaryBtn} onClick={run} disabled={busy}>
          {busy ? "Running the baseline…" : "Run plain-LLM baseline"}
        </button>
        {error && <p className={styles.errorBox}>{error}</p>}
      </div>
    );
  }
  const ainPct = data.ain_citations ? Math.round((100 * data.ain_verified) / data.ain_citations) : 0;
  const plainPct = data.citations_found ? Math.round((100 * data.supported) / data.citations_found) : 0;
  return (
    <div className={styles.panel}>
      <div className={styles.versus}>
        <div className={styles.vsCol} data-side="plain">
          <span className={styles.vsLabel}>Plain LLM · one prompt</span>
          <span className={styles.vsBig}>{plainPct}%</span>
          <span className={styles.vsSub}>
            {data.supported} of {data.citations_found} citations survive the gates
          </span>
          <span className={styles.judgeModel}>{data.plain_model}</span>
        </div>
        <div className={styles.vsCol} data-side="ain">
          <span className={styles.vsLabel}>Ain Copilot · memo</span>
          <span className={styles.vsBig}>100%</span>
          <span className={styles.vsSub}>
            of memo citations passed all gates ({data.ain_verified} of {data.ain_citations} proposed claims kept, {ainPct}%)
          </span>
        </div>
      </div>
      <ol className={styles.ledger}>
        {data.rows.map((r, i) => (
          <li key={i} className={styles.ledgerRow} data-verdict={OUTCOME[r.outcome].ok ? "verified" : "dropped"}>
            <div className={styles.ledgerTop}>
              <span className={styles.claimId}>{r.risk}</span>
              <span className={styles.citeLink}>{r.cited}</span>
              <span className={styles.verdictPill} data-verdict={OUTCOME[r.outcome].ok ? "verified" : "dropped"}>
                {OUTCOME[r.outcome].ok ? "✓" : "✕"} {OUTCOME[r.outcome].label}
              </span>
            </div>
            <p className={styles.prop}>{r.claim}</p>
            <p className={styles.gateDetail}>{r.detail}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

/* ------------------------------------------------------------------ Privacy */

export function PrivacyPanel({ result }: { result: AnalysisResult }) {
  const p = result.privacy;
  const byModel = useMemo(() => {
    const m = new Map<string, { calls: number; chars: number; cached: number }>();
    for (const c of p.outbound_calls) {
      const key = `${c.provider} · ${c.model}`;
      const cur = m.get(key) ?? { calls: 0, chars: 0, cached: 0 };
      cur.calls++;
      cur.chars += c.chars;
      cur.cached += c.cached ? 1 : 0;
      m.set(key, cur);
    }
    return [...m.entries()];
  }, [p.outbound_calls]);

  return (
    <div className={styles.panel}>
      <div className={styles.privacyStats}>
        <div>
          <span className={styles.vsBig}>{p.redactions.length}</span>
          <span className={styles.vsSub}>identifiers redacted</span>
        </div>
        <div>
          <span className={styles.vsBig}>{p.image_left_device ? "Yes" : "No"}</span>
          <span className={styles.vsSub}>photo sent to any server</span>
        </div>
        <div>
          <span className={styles.vsBig}>{p.pii_leaks_blocked}</span>
          <span className={styles.vsSub}>outbound calls blocked by the PII guard</span>
        </div>
      </div>
      <div className={styles.kinds}>
        {Object.entries(p.counts).map(([k, n]) => (
          <span key={k} className={styles.chip}>
            {k} × {n}
          </span>
        ))}
      </div>
      <h4 className={styles.subhead}>Model calls (only redacted text is sent)</h4>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Provider · model</th>
            <th>Calls</th>
            <th>Chars sent</th>
            <th>From cache</th>
          </tr>
        </thead>
        <tbody>
          {byModel.map(([k, v]) => (
            <tr key={k}>
              <td>{k}</td>
              <td>{v.calls}</td>
              <td>{v.chars.toLocaleString()}</td>
              <td>{v.cached}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h4 className={styles.subhead}>Exactly what the models saw</h4>
      <pre className={styles.redacted}>{p.redacted_text}</pre>
    </div>
  );
}
