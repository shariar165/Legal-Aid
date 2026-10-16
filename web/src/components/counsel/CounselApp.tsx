"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { api, type AnalysisResult, type Severity } from "@/lib/api";
import { STEP_ORDER, useAnalysis, type StepId } from "@/lib/useAnalysis";
import { CouncilFaces, CouncilPanel, type CouncilNav, type CouncilTarget } from "./Council";
import { money, SEVERITY_LABEL, SEVERITY_RANK } from "./format";
import { AblationPanel, LedgerPanel, PrivacyPanel, TracePanel } from "./Panels";
import { RiskCard } from "./RiskCard";
import styles from "./counsel.module.css";

type View = "report" | "contract" | "council" | "checks";

const STEP_LABEL: Record<StepId, string> = {
  read: "Reading the document",
  redact: "Hiding personal details",
  match: "Finding the law that applies and the risks",
  verify: "Checking every legal claim against the statute",
};

export function CounselApp({ jobId }: { jobId: string }) {
  const analysis = useAnalysis(jobId);
  const { result, status, events, error, stepsDone } = analysis;
  const [view, setView] = useState<View>("report");
  const [target, setTarget] = useState<CouncilTarget>("all");
  const [riskId, setRiskId] = useState<string | null>(null);
  const [focusRisk, setFocusRisk] = useState<string | null>(null);

  const go = useCallback((v: View, anchor?: string) => {
    setView(v);
    requestAnimationFrame(() => {
      const el = anchor ? document.getElementById(anchor) : null;
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
      else window.scrollTo({ top: 0 });
    });
  }, []);

  const open = useCallback(
    (t: CouncilTarget, risk?: string | null) => {
      setTarget(t);
      if (risk !== undefined) setRiskId(risk);
      go("council");
    },
    [go],
  );
  const nav: CouncilNav = { target, riskId, setTarget, setRiskId, open };

  const showRisk = (id: string) => {
    setFocusRisk(id);
    go("report", `risk-${id}`);
  };

  return (
    <div className={styles.page}>
      <header className={styles.topbar}>
        <div className={styles.topRow}>
          <Link href="/counsel" className={styles.brand}>
            <span className={styles.brandMark}>আ</span>
            <span>Ain Copilot</span>
          </Link>
          {result && (
            <>
              <span className={styles.docName} title={result.document.name}>
                {result.document.name}
              </span>
              {result.llm_mode !== "live" && (
                <span className={styles.chip} data-tone="warn" title="Answers come from saved or offline model responses">
                  {result.llm_mode === "fake" ? "Offline demo" : "Replay"}
                </span>
              )}
              <div className={styles.actions}>
                <a className={styles.primaryBtn} href={api.memoUrl(result.job_id)}>
                  Download memo
                </a>
                <button type="button" className={styles.ghostBtn} onClick={() => window.print()}>
                  Print
                </button>
              </div>
            </>
          )}
        </div>
        {result && (
          <nav className={styles.views} aria-label="Sections">
            <ViewTab id="report" view={view} onClick={() => go("report")}>
              Report
            </ViewTab>
            <ViewTab id="contract" view={view} onClick={() => go("contract")}>
              Contract
            </ViewTab>
            <ViewTab id="council" view={view} onClick={() => go("council")}>
              <CouncilFaces size={20} /> Ask the council
            </ViewTab>
            <ViewTab id="checks" view={view} onClick={() => go("checks")}>
              How we checked
            </ViewTab>
          </nav>
        )}
      </header>

      {status === "error" && (
        <main className={styles.narrow}>
          <p className={styles.errorBox}>{error === "offline" ? "The analysis server is not reachable." : error}</p>
          <Link href="/counsel">← Start a new analysis</Link>
        </main>
      )}

      {status !== "error" && !result && (
        <main className={styles.narrow}>
          <h1 className={styles.heroTitle}>Reviewing your contract…</h1>
          <p className={styles.heroLead}>
            {status === "waiting"
              ? "Waiting for the salary to be confirmed on the citizen screen. The rest of the review carries on."
              : "This usually takes under a minute."}
          </p>
          <ol className={styles.progress}>
            {STEP_ORDER.map((s) => {
              const done = stepsDone.includes(s);
              const current = !done && STEP_ORDER.find((x) => !stepsDone.includes(x)) === s;
              return (
                <li key={s} data-state={done ? "done" : current ? "current" : "todo"}>
                  <span className={styles.progressDot} aria-hidden="true">
                    {done ? "✓" : ""}
                  </span>
                  {STEP_LABEL[s]}
                </li>
              );
            })}
          </ol>
          <details className={styles.more}>
            <summary>Show the live agent log</summary>
            <TracePanel events={events} />
          </details>
        </main>
      )}

      {result && view === "report" && (
        <Report result={result} focusRisk={focusRisk} onAsk={(id) => open("all", id)} onChecks={() => go("checks")} onClause={(id) => go("contract", `clause-${id}`)} />
      )}
      {result && view === "contract" && <Contract result={result} onRisk={showRisk} />}
      {result && (
        <main className={styles.wide} hidden={view !== "council"}>
          <CouncilPanel result={result} nav={nav} />
        </main>
      )}
      {result && view === "checks" && <Checks result={result} events={result.trace.length ? result.trace : events} />}
    </div>
  );
}

function ViewTab({ id, view, onClick, children }: { id: View; view: View; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" className={styles.viewTab} aria-current={view === id ? "page" : undefined} onClick={onClick}>
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------ Report */

interface ReportProps {
  result: AnalysisResult;
  focusRisk: string | null;
  onAsk: (riskId: string) => void;
  onChecks: () => void;
  onClause: (clauseId: string) => void;
}

function Report({ result, focusRisk, onAsk, onChecks, onClause }: ReportProps) {
  const live = useMemo(
    () => result.risks.filter((r) => r.status !== "dropped").sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]),
    [result.risks],
  );
  const withdrawn = result.risks.length - live.length;
  const counts = (["critical", "high", "medium", "low"] as Severity[])
    .map((s) => [s, live.filter((r) => r.severity === s).length] as const)
    .filter(([, n]) => n);
  const w = result.wage;

  return (
    <main className={styles.narrow}>
      <section className={styles.overview}>
        <p className={styles.kicker}>Legal risk memo · for {result.memo.prepared_for.toLowerCase()}</p>
        <h1 className={styles.memoTitle}>
          {live.length === 0 ? "No risks found" : `${live.length} ${live.length === 1 ? "risk needs" : "risks need"} your attention`}
        </h1>
        {counts.length > 0 && (
          <div className={styles.sevCounts}>
            {counts.map(([s, n]) => (
              <span key={s} className={styles.sev} data-sev={s}>
                {n} {SEVERITY_LABEL[s]}
              </span>
            ))}
          </div>
        )}
        <p className={styles.summary}>{result.memo.executive_summary}</p>
        <p className={styles.summaryBn} lang="bn">
          {result.memo.summary_bn}
        </p>
        <details className={styles.laws}>
          <summary>
            <b>Laws applied:</b> {result.route.packs.map((p) => p.label).join(" · ")}
          </summary>
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
                <span>Not applied: {p.reason}</span>
              </li>
            ))}
          </ul>
        </details>
      </section>

      {w && (
        <section className={styles.wage} aria-label="Wage check">
          <h2 className={styles.sectionTitle}>What the worker actually takes home</h2>
          <div className={styles.wageRow}>
            <div>
              <span className={styles.wageLabel}>Promised</span>
              <span className={styles.wageNum}>{money(w.currency, w.promised)}</span>
            </div>
            <div>
              <span className={styles.wageLabel}>Deducted each month</span>
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
            {w.confirmed_by_user ? "Salary confirmed by the user after reading the photo." : "Salary as written in the document."} Plain arithmetic, no AI
            involved.
          </p>
        </section>
      )}

      {live.length > 0 && <h2 className={styles.sectionTitle}>Risks, most serious first</h2>}
      {live.map((r) => (
        <RiskCard
          key={r.id}
          risk={r}
          issue={result.memo.issues.find((i) => i.risk_id === r.id)}
          rows={result.ledger.filter((v) => v.claim.risk_id === r.id)}
          clauses={result.document.clauses.filter((c) => r.clause_ids.includes(c.id))}
          active={focusRisk === r.id}
          onAskCouncil={() => onAsk(r.id)}
          onClause={onClause}
        />
      ))}

      {withdrawn > 0 && (
        <p className={styles.paneNote}>
          {withdrawn} more possible {withdrawn === 1 ? "risk was" : "risks were"} left out because the law behind {withdrawn === 1 ? "it" : "them"} could not be
          verified.{" "}
          <button type="button" className={styles.askLink} onClick={onChecks}>
            See how we checked →
          </button>
        </p>
      )}

      <details className={styles.more}>
        <summary>Limits of this memo</summary>
        <ul className={styles.caveatList}>
          {result.memo.caveats.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </details>
    </main>
  );
}

/* ------------------------------------------------------------------ Contract */

function Contract({ result, onRisk }: { result: AnalysisResult; onRisk: (riskId: string) => void }) {
  const [onlyFlagged, setOnlyFlagged] = useState(false);
  const heat = useMemo(() => {
    const m = new Map<string, { sev: Severity; risk: string; title: string }>();
    for (const r of result.risks) {
      if (r.status === "dropped") continue;
      for (const c of r.clause_ids) {
        const cur = m.get(c);
        if (!cur || SEVERITY_RANK[r.severity] < SEVERITY_RANK[cur.sev]) m.set(c, { sev: r.severity, risk: r.id, title: r.title.en });
      }
    }
    return m;
  }, [result.risks]);
  const clauses = result.document.clauses.filter((c) => !onlyFlagged || heat.has(c.id));

  return (
    <main className={styles.narrow}>
      <h1 className={styles.viewTitle}>The contract</h1>
      <p className={styles.viewLead}>
        This is the copy the AI saw: names, phone numbers and ID numbers are hidden. Coloured clauses have a risk. Click one to read about it.
      </p>
      <div className={styles.contractBar}>
        <span className={styles.legend}>
          {(["critical", "high", "medium"] as Severity[]).map((s) => (
            <span key={s} className={styles.legendItem} data-sev={s}>
              {SEVERITY_LABEL[s]}
            </span>
          ))}
        </span>
        <label className={styles.toggle}>
          <input type="checkbox" checked={onlyFlagged} onChange={(e) => setOnlyFlagged(e.target.checked)} /> Only show risky clauses
        </label>
      </div>
      <ol className={styles.clauses}>
        {clauses.map((c) => {
          const h = heat.get(c.id);
          return (
            <li key={c.id} id={`clause-${c.id}`}>
              {h ? (
                <button type="button" className={styles.clause} data-sev={h.sev} onClick={() => onRisk(h.risk)}>
                  <span className={styles.clauseText}>{c.text}</span>
                  <span className={styles.clauseRisk}>
                    {SEVERITY_LABEL[h.sev]} risk: {h.title} →
                  </span>
                </button>
              ) : (
                <div className={styles.clause} data-sev="none">
                  <span className={styles.clauseText}>{c.text}</span>
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </main>
  );
}

/* ------------------------------------------------------------------ How we checked */

type CheckTab = "ledger" | "trace" | "ablation" | "privacy";
const CHECK_TABS: { id: CheckTab; label: string }[] = [
  { id: "ledger", label: "Every legal claim" },
  { id: "trace", label: "Agent activity" },
  { id: "ablation", label: "Compare with a plain chatbot" },
  { id: "privacy", label: "Privacy" },
];

function Checks({ result, events }: { result: AnalysisResult; events: AnalysisResult["trace"] }) {
  const [tab, setTab] = useState<CheckTab>("ledger");
  const s = result.stats;
  return (
    <main className={styles.wide}>
      <h1 className={styles.viewTitle}>How we checked this memo</h1>
      <p className={styles.viewLead}>
        AI agents suggested legal points, and each one had to pass four checks before it could go in the memo. The section must exist and apply to this
        contract. The quote must match the statute. Independent AI judges must agree the law says what we claim. The law must still be in force.
      </p>
      <div className={styles.statRow}>
        <div>
          <span className={styles.statNum}>{s.claims}</span>
          <span className={styles.statLabel}>legal claims checked</span>
        </div>
        <div data-tone="ok">
          <span className={styles.statNum}>{s.verified}</span>
          <span className={styles.statLabel}>passed every check</span>
        </div>
        <div data-tone="warn">
          <span className={styles.statNum}>{s.partial}</span>
          <span className={styles.statLabel}>passed with a warning</span>
        </div>
        <div data-tone="bad">
          <span className={styles.statNum}>{s.dropped}</span>
          <span className={styles.statLabel}>rejected and left out</span>
        </div>
        <div>
          <span className={styles.statNum}>{s.seconds}s</span>
          <span className={styles.statLabel}>{s.llm_calls} AI model calls</span>
        </div>
      </div>
      <div className={styles.subTabs} role="tablist">
        {CHECK_TABS.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} className={styles.subTab} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        {tab === "ledger" && <LedgerPanel result={result} />}
        {tab === "trace" && <TracePanel events={events} />}
        {tab === "ablation" && <AblationPanel result={result} />}
        {tab === "privacy" && <PrivacyPanel result={result} />}
      </div>
    </main>
  );
}
