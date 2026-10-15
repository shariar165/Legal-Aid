"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { api, type AnalysisResult, type Severity } from "@/lib/api";
import { useAnalysis } from "@/lib/useAnalysis";
import { money, SEVERITY_RANK } from "./format";
import { AblationPanel, BenchPanel, LedgerPanel, PrivacyPanel, TracePanel } from "./Panels";
import { RiskCard } from "./RiskCard";
import styles from "./counsel.module.css";

type Tab = "ledger" | "bench" | "trace" | "ablation" | "privacy";
const TABS: { id: Tab; label: string }[] = [
  { id: "ledger", label: "Verification Ledger" },
  { id: "bench", label: "Virtual Bench" },
  { id: "trace", label: "Agent Trace" },
  { id: "ablation", label: "vs Plain LLM" },
  { id: "privacy", label: "Privacy" },
];

export function CounselApp({ jobId }: { jobId: string }) {
  const analysis = useAnalysis(jobId);
  const { result, status, events, error } = analysis;

  return (
    <div className={styles.page}>
      <header className={styles.topbar}>
        <Link href="/counsel" className={styles.brand}>
          <span className={styles.brandMark}>আ</span>
          <span>
            Ain Copilot <span className={styles.brandSub}>Counsel mode</span>
          </span>
        </Link>
        {result && <Toolbar result={result} />}
      </header>
      {status === "error" && (
        <main className={styles.startMain}>
          <p className={styles.errorBox}>{error === "offline" ? "The analysis server is not reachable." : error}</p>
          <Link href="/counsel">← Start a new analysis</Link>
        </main>
      )}
      {status !== "error" && !result && (
        <main className={styles.running}>
          <h1 className={styles.heroTitle}>Agents at work…</h1>
          <p className={styles.heroLead}>
            {status === "waiting"
              ? "Waiting for the salary to be confirmed on the citizen screen; the rest of the analysis continues in parallel."
              : "Each step below is a real event streamed from the backend."}
          </p>
          <TracePanel events={events} />
        </main>
      )}
      {result && <Workspace result={result} events={result.trace.length ? result.trace : events} />}
    </div>
  );
}

function Toolbar({ result }: { result: AnalysisResult }) {
  const s = result.stats;
  return (
    <div className={styles.toolbar}>
      <span className={styles.docName} title={result.document.name}>
        {result.document.name}
      </span>
      <span className={styles.chip} data-tone={result.llm_mode === "live" ? "ok" : "warn"}>
        {result.llm_mode === "fake" ? "offline demo" : result.llm_mode}
      </span>
      <span className={styles.chip}>{s.risks_confirmed} risks</span>
      <span className={styles.chip} data-tone="ok">
        ✓ {s.verified}
      </span>
      <span className={styles.chip} data-tone="warn">
        ⚠ {s.partial}
      </span>
      <span className={styles.chip} data-tone="bad">
        ✕ {s.dropped}
      </span>
      <span className={styles.chip}>
        {s.llm_calls} model calls · {s.seconds}s
      </span>
      <a className={styles.primaryBtn} href={api.memoUrl(result.job_id)}>
        Download memo (.docx)
      </a>
      <button type="button" className={styles.ghostBtn} onClick={() => window.print()}>
        Print
      </button>
    </div>
  );
}

function Workspace({ result, events }: { result: AnalysisResult; events: AnalysisResult["trace"] }) {
  const [tab, setTab] = useState<Tab>("ledger");
  const [activeRisk, setActiveRisk] = useState<string | null>(null);
  const [activeClause, setActiveClause] = useState<string | null>(null);

  const live = useMemo(
    () => result.risks.filter((r) => r.status !== "dropped").sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]),
    [result.risks],
  );
  const withdrawn = result.risks.filter((r) => r.status === "dropped");
  const heat = useMemo(() => {
    const m = new Map<string, Severity>();
    for (const r of live)
      for (const c of r.clause_ids) {
        const cur = m.get(c);
        if (!cur || SEVERITY_RANK[r.severity] < SEVERITY_RANK[cur]) m.set(c, r.severity);
      }
    return m;
  }, [live]);

  const focusRisk = (id: string) => {
    setActiveRisk(id);
    const r = result.risks.find((x) => x.id === id);
    const first = r?.clause_ids[0];
    if (first) {
      setActiveClause(first);
      document.getElementById(`clause-${first}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  const focusClause = (id: string) => {
    setActiveClause(id);
    const r = live.find((x) => x.clause_ids.includes(id));
    if (r) {
      setActiveRisk(r.id);
      document.getElementById(`risk-${r.id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const w = result.wage;
  return (
    <div className={styles.workspace}>
      {/* ---------------- document with risk heatmap */}
      <aside className={styles.docPane} aria-label="Document">
        <h2 className={styles.paneTitle}>Document · risk heatmap</h2>
        <p className={styles.paneNote}>Redacted copy. Click a highlighted clause to jump to its risk.</p>
        <ol className={styles.clauses}>
          {result.document.clauses.map((c) => {
            const sev = heat.get(c.id);
            return (
              <li key={c.id} id={`clause-${c.id}`}>
                <button
                  type="button"
                  className={styles.clause}
                  data-sev={sev ?? "none"}
                  data-active={activeClause === c.id}
                  onClick={() => sev && focusClause(c.id)}
                  disabled={!sev}
                >
                  <span className={styles.clauseId}>{c.id}</span>
                  <span className={styles.clauseText}>{c.text}</span>
                </button>
              </li>
            );
          })}
        </ol>
      </aside>

      {/* ---------------- memorandum */}
      <main className={styles.memoPane}>
        <p className={styles.kicker}>Legal risk memorandum · prepared for {result.memo.prepared_for.toLowerCase()}</p>
        <h1 className={styles.memoTitle}>{result.document.name}</h1>
        <p className={styles.summary}>{result.memo.executive_summary}</p>
        <p className={styles.summaryBn} lang="bn">
          {result.memo.summary_bn}
        </p>

        <section className={styles.routing} aria-label="Applicable law">
          <h2 className={styles.sectionTitle}>Jurisdiction Router</h2>
          <ul className={styles.packs}>
            {result.route.packs.map((p) => (
              <li key={p.pack} className={styles.pack}>
                <b>{p.label}</b>
                <span>{p.reason}</span>
              </li>
            ))}
            {result.route.excluded.map((p) => (
              <li key={p.pack} className={styles.pack} data-off>
                <b>{p.label}</b>
                <span>{p.reason}</span>
              </li>
            ))}
          </ul>
        </section>

        {w && (
          <section className={styles.wage} aria-label="Wage calculation">
            <h2 className={styles.sectionTitle}>Wage Truth Calculator</h2>
            <div className={styles.wageRow}>
              <div>
                <span className={styles.wageLabel}>Promised</span>
                <span className={styles.wageNum}>{money(w.currency, w.promised)}</span>
              </div>
              <div>
                <span className={styles.wageLabel}>Deducted / month</span>
                <span className={styles.wageNum} data-bad={w.over_cap}>
                  − {money(w.currency, w.monthly_deductions)} ({w.pct_deducted}%)
                </span>
              </div>
              <div>
                <span className={styles.wageLabel}>Take-home</span>
                <span className={styles.wageNum} data-bad={w.below_minimum || w.over_cap}>
                  {money(w.currency, w.net)}
                </span>
              </div>
              {w.minimum_wage && (
                <div>
                  <span className={styles.wageLabel}>Legal minimum</span>
                  <span className={styles.wageNum}>{money(w.currency, w.minimum_wage)}</span>
                </div>
              )}
            </div>
            <div className={styles.wageBar} aria-hidden="true">
              <span style={{ width: `${Math.max(0, Math.min(100, (100 * w.net) / Math.max(w.promised, w.minimum_wage ?? 0)))}%` }} />
            </div>
            <p className={styles.paneNote}>
              {w.confirmed_by_user ? "Salary confirmed by the user after OCR." : "Salary as written in the document."} Arithmetic only, no model involved.
            </p>
          </section>
        )}

        <h2 className={styles.sectionTitle}>
          Risks <span className={styles.count}>{live.length}</span>
        </h2>
        {live.length === 0 && <p className={styles.paneNote}>No verified risk was found in this document.</p>}
        {live.map((r) => (
          <RiskCard
            key={r.id}
            risk={r}
            issue={result.memo.issues.find((i) => i.risk_id === r.id)}
            rows={result.ledger.filter((v) => v.claim.risk_id === r.id)}
            active={activeRisk === r.id}
            onFocus={() => focusRisk(r.id)}
          />
        ))}

        {withdrawn.length > 0 && (
          <details className={styles.withdrawn}>
            <summary>{withdrawn.length} risk(s) withdrawn: no claim survived verification</summary>
            {withdrawn.map((r) => (
              <RiskCard key={r.id} risk={r} issue={undefined} rows={result.ledger.filter((v) => v.claim.risk_id === r.id)} active={false} onFocus={() => focusRisk(r.id)} />
            ))}
          </details>
        )}

        <section className={styles.caveats}>
          <h2 className={styles.sectionTitle}>Caveats</h2>
          <ul>
            {result.memo.caveats.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </section>
      </main>

      {/* ---------------- evidence tabs */}
      <aside className={styles.sidePane} aria-label="Evidence">
        <div className={styles.tabs} role="tablist">
          {TABS.map((t) => (
            <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} className={styles.tab} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>
        <div className={styles.tabBody} role="tabpanel">
          {tab === "ledger" && <LedgerPanel result={result} />}
          {tab === "bench" && <BenchPanel result={result} />}
          {tab === "trace" && <TracePanel events={events} />}
          {tab === "ablation" && <AblationPanel result={result} />}
          {tab === "privacy" && <PrivacyPanel result={result} />}
        </div>
      </aside>
    </div>
  );
}
