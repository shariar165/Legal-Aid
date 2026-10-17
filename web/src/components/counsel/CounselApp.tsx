"use client";

import Link from "next/link";
import { useCallback, useMemo, useState, type FormEvent } from "react";
import { api, type AnalysisResult, type Risk, type Severity } from "@/lib/api";
import { STEP_ORDER, useAnalysis, type OcrCheck, type StepId } from "@/lib/useAnalysis";
import { CouncilFaces, CouncilPanel, type CouncilNav, type CouncilTarget } from "./Council";
import { money, SEVERITY_LABEL, SEVERITY_RANK } from "./format";
import { Icon, type IconName } from "./Icons";
import { AblationPanel, LedgerPanel, PrivacyPanel, TracePanel } from "./Panels";
import { RiskCard } from "./RiskCard";
import styles from "./counsel.module.css";

type View = "report" | "contract" | "council" | "checks";

const STEP_LABEL: Record<StepId, { title: string; detail: string }> = {
  read: { title: "Reading the document", detail: "Text extraction and clause splitting" },
  redact: { title: "Hiding personal details", detail: "Names, phone and ID numbers are masked before any AI call" },
  match: { title: "Finding the applicable law and risks", detail: "Jurisdiction routing, risk analysis and adversarial review" },
  verify: { title: "Verifying every legal claim", detail: "Four checks against the statute book, then the council vote" },
};

const SEVERITIES: Severity[] = ["critical", "high", "medium", "low"];

/* live risks, most serious first */
function liveRisks(result: AnalysisResult) {
  return result.risks.filter((r) => r.status !== "dropped").sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]);
}

/* clause id -> the most serious live risk that touches it */
function clauseHeat(risks: Risk[]) {
  const m = new Map<string, { sev: Severity; risk: string; title: string }>();
  for (const r of risks) {
    if (r.status === "dropped") continue;
    for (const c of r.clause_ids) {
      const cur = m.get(c);
      if (!cur || SEVERITY_RANK[r.severity] < SEVERITY_RANK[cur.sev]) m.set(c, { sev: r.severity, risk: r.id, title: r.title.en });
    }
  }
  return m;
}

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
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
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

  const live = useMemo(() => (result ? liveRisks(result) : []), [result]);
  const heat = useMemo(() => clauseHeat(result?.risks ?? []), [result]);

  return (
    <div className={styles.page}>
      <header className={styles.topbar}>
        <div className={styles.topRow}>
          <Link href="/counsel" className={styles.brand} aria-label="Ain Copilot, start a new analysis">
            <span className={styles.brandMark}>আ</span>
            <span className={styles.brandText}>
              Ain Copilot <span>Counsel</span>
            </span>
          </Link>
          {result && (
            <>
              <span className={styles.docPill} title={result.document.name}>
                <Icon name="file" size={15} />
                <span className={styles.docName}>{result.document.name}</span>
                {result.llm_mode !== "live" && (
                  <span className={styles.chip} data-tone="warn" title="Answers come from saved or offline model responses">
                    {result.llm_mode === "fake" ? "Offline demo" : "Replay"}
                  </span>
                )}
              </span>
              <div className={styles.actions}>
                <Link href="/counsel" className={styles.quietBtn} title="Analyse another contract">
                  <Icon name="plus" size={16} />
                  <span className={styles.hideSm}>New analysis</span>
                </Link>
                <button type="button" className={styles.iconBtn} onClick={() => window.print()} aria-label="Print memo" title="Print memo">
                  <Icon name="printer" size={18} />
                </button>
                <a className={styles.primaryBtn} href={api.memoUrl(result.job_id)}>
                  <Icon name="download" size={16} />
                  <span>Download memo</span>
                </a>
              </div>
            </>
          )}
        </div>
        {result && (
          <nav className={styles.views} aria-label="Sections">
            <ViewTab id="report" view={view} icon="book" count={live.length} onClick={() => go("report")}>
              Report
            </ViewTab>
            <ViewTab id="contract" view={view} icon="file" count={heat.size} onClick={() => go("contract")}>
              Contract
            </ViewTab>
            <ViewTab id="council" view={view} onClick={() => go("council")}>
              <CouncilFaces size={18} /> Council
            </ViewTab>
            <ViewTab id="checks" view={view} icon="shieldCheck" count={`${result.stats.verified}/${result.stats.claims}`} onClick={() => go("checks")}>
              Verification
            </ViewTab>
          </nav>
        )}
      </header>

      {status === "error" && (
        <main className={styles.narrow}>
          <div className={styles.stateCard} role="alert">
            <span className={styles.stateIcon} data-tone="bad">
              <Icon name="alert" size={22} />
            </span>
            <h1 className={styles.stateTitle}>The analysis could not be completed</h1>
            <p className={styles.stateText}>{error === "offline" ? "The analysis server is not reachable. Check that the backend is running, then try again." : error}</p>
            <Link href="/counsel" className={styles.primaryBtn}>
              <Icon name="arrowLeft" size={16} />
              Start a new analysis
            </Link>
          </div>
        </main>
      )}

      {status !== "error" && !result && (
        <Progress
          status={status}
          stepsDone={stepsDone}
          events={events}
          ocrCheck={analysis.ocrCheck}
          confirmed={analysis.confirmed}
          onConfirm={analysis.confirm}
        />
      )}

      {result && view === "report" && (
        <Report
          result={result}
          live={live}
          focusRisk={focusRisk}
          onAsk={(id) => open("all", id)}
          onCouncil={() => open("all", null)}
          onChecks={() => go("checks")}
          onJump={showRisk}
          onClause={(id) => go("contract", `clause-${id}`)}
        />
      )}
      {result && view === "contract" && <Contract result={result} heat={heat} onRisk={showRisk} />}
      {result && (
        <main className={styles.wide} hidden={view !== "council"}>
          <CouncilPanel result={result} nav={nav} />
        </main>
      )}
      {result && view === "checks" && <Checks result={result} events={result.trace.length ? result.trace : events} />}
    </div>
  );
}

function ViewTab({
  id,
  view,
  icon,
  count,
  onClick,
  children,
}: {
  id: View;
  view: View;
  icon?: IconName;
  count?: number | string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button type="button" className={styles.viewTab} aria-current={view === id ? "page" : undefined} onClick={onClick}>
      {icon && <Icon name={icon} size={16} />}
      {children}
      {count !== undefined && <span className={styles.count}>{count}</span>}
    </button>
  );
}

/* ------------------------------------------------------------------ Running */

function Progress({
  status,
  stepsDone,
  events,
  ocrCheck,
  confirmed,
  onConfirm,
}: {
  status: string;
  stepsDone: StepId[];
  events: AnalysisResult["trace"];
  ocrCheck: OcrCheck | null;
  confirmed: boolean;
  onConfirm: (value: string) => Promise<void>;
}) {
  const current = STEP_ORDER.find((x) => !stepsDone.includes(x));
  const needsCheck = !!ocrCheck && !confirmed;
  return (
    <main className={styles.narrow}>
      <div className={styles.stateCard}>
        <p className={styles.kicker}>Analysis in progress</p>
        <h1 className={styles.stateTitle}>Reviewing your contract</h1>
        <p className={styles.stateText}>
          {needsCheck
            ? "One figure in the photo is hard to read. Please confirm it below; the rest of the review carries on meanwhile."
            : "This usually takes under a minute. You can keep this tab open."}
        </p>
        {needsCheck && <SalaryCheck check={ocrCheck} onConfirm={onConfirm} />}
        <div className={styles.progressBar} role="progressbar" aria-valuemin={0} aria-valuemax={STEP_ORDER.length} aria-valuenow={stepsDone.length}>
          <span style={{ width: `${(100 * stepsDone.length) / STEP_ORDER.length}%` }} />
        </div>
        <ol className={styles.stepper}>
          {STEP_ORDER.map((s, i) => {
            const state = stepsDone.includes(s) ? "done" : current === s ? "current" : "todo";
            return (
              <li key={s} data-state={state} aria-current={state === "current" ? "step" : undefined}>
                <span className={styles.stepDot} aria-hidden="true">
                  {state === "done" ? <Icon name="check" size={14} /> : i + 1}
                </span>
                <span>
                  <b>{STEP_LABEL[s].title}</b>
                  <span>{s === "match" && status === "waiting" && needsCheck ? "Waiting for the salary figure to be confirmed" : STEP_LABEL[s].detail}</span>
                </span>
              </li>
            );
          })}
        </ol>
        <details className={styles.more}>
          <summary>
            <Icon name="chevronRight" size={16} className={styles.summaryChevron} />
            Live agent log
          </summary>
          <TracePanel events={events} />
        </details>
      </div>
    </main>
  );
}

/* The photo's salary was read with low confidence: a human confirms or corrects it before the wage maths runs. */
function SalaryCheck({ check, onConfirm }: { check: OcrCheck; onConfirm: (value: string) => Promise<void> }) {
  const [value, setValue] = useState(check.value);
  const [editing, setEditing] = useState(false);
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const submit = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!value.trim()) return;
    setSending(true);
    setErr(null);
    try {
      await onConfirm(value.trim());
    } catch (x) {
      setErr((x as Error).message.replace(/^\d+: /, ""));
      setSending(false);
    }
  };
  return (
    <form className={styles.salaryCheck} onSubmit={submit} aria-labelledby="salary-check-title">
      <span className={styles.salaryIcon} aria-hidden="true">
        <Icon name="camera" size={18} />
      </span>
      <div className={styles.salaryBody}>
        <p id="salary-check-title" className={styles.salaryTitle}>
          Check the monthly salary
          <span className={styles.chip} data-tone="warn">
            Read with {Math.round(check.confidence * 100)}% confidence
          </span>
        </p>
        <p className={styles.salaryText}>The wage calculation uses this number, so it must match the contract.</p>
        {editing ? (
          <div className={styles.salaryRow}>
            <label className={styles.salaryInput}>
              <span>{check.currency}</span>
              <input value={value} inputMode="numeric" autoFocus onChange={(e) => setValue(e.target.value)} aria-label="Monthly salary" />
            </label>
            <button type="submit" className={styles.primaryBtn} disabled={sending}>
              {sending ? "Saving…" : "Save"}
            </button>
          </div>
        ) : (
          <div className={styles.salaryRow}>
            <span className={styles.salaryValue}>
              {check.currency} {value}
            </span>
            <button type="submit" className={styles.primaryBtn} disabled={sending}>
              <Icon name="check" size={16} />
              {sending ? "Confirming…" : "Yes, this is correct"}
            </button>
            <button type="button" className={styles.secondaryBtn} disabled={sending} onClick={() => setEditing(true)}>
              Correct it
            </button>
          </div>
        )}
        {err && (
          <p className={styles.errorBox} role="alert">
            <Icon name="alert" size={16} />
            {err}
          </p>
        )}
      </div>
    </form>
  );
}

/* ------------------------------------------------------------------ Report */

interface ReportProps {
  result: AnalysisResult;
  live: Risk[];
  focusRisk: string | null;
  onAsk: (riskId: string) => void;
  onCouncil: () => void;
  onChecks: () => void;
  onJump: (riskId: string) => void;
  onClause: (clauseId: string) => void;
}

function Report({ result, live, focusRisk, onAsk, onCouncil, onChecks, onJump, onClause }: ReportProps) {
  const [sevFilter, setSevFilter] = useState<Severity | "all">("all");
  const withdrawn = result.risks.length - live.length;
  const counts = SEVERITIES.map((s) => [s, live.filter((r) => r.severity === s).length] as const).filter(([, n]) => n);
  const shown = sevFilter === "all" ? live : live.filter((r) => r.severity === sevFilter);
  const w = result.wage;
  const s = result.stats;
  const scale = w ? Math.max(w.promised, w.minimum_wage ?? 0) : 1;
  const pct = (n: number) => `${Math.max(0, Math.min(100, (100 * n) / scale))}%`;

  return (
    <main className={styles.reportGrid}>
      <div className={styles.reportMain}>
        <section className={styles.card} aria-labelledby="memo-title">
          <p className={styles.kicker}>Legal risk memo · Prepared for {result.memo.prepared_for}</p>
          <h1 id="memo-title" className={styles.memoTitle}>
            {live.length === 0 ? "No risks found" : `${live.length} ${live.length === 1 ? "risk needs" : "risks need"} your attention`}
          </h1>
          {counts.length > 0 && (
            <div className={styles.sevCounts}>
              {counts.map(([sv, n]) => (
                <span key={sv} className={styles.sev} data-sev={sv}>
                  <span className={styles.sevDot} data-sev={sv} />
                  {n} {SEVERITY_LABEL[sv]}
                </span>
              ))}
            </div>
          )}
          <p className={styles.summary}>{result.memo.executive_summary}</p>
          <div className={styles.summaryBn}>
            <span className={styles.insetLabel}>বাংলা সারাংশ · Summary in Bangla</span>
            <p lang="bn">{result.memo.summary_bn}</p>
          </div>
          <details className={styles.laws}>
            <summary>
              <Icon name="chevronRight" size={16} className={styles.summaryChevron} />
              <span>
                <b>Laws applied:</b> {result.route.packs.map((p) => p.label).join(" · ")}
              </span>
            </summary>
            <ul className={styles.packs}>
              {result.route.packs.map((p) => (
                <li key={p.pack} title={p.reason}>
                  <Icon name="check" size={14} />
                  <span>
                    <b>{p.label}</b>
                    <span>{p.reason}</span>
                  </span>
                </li>
              ))}
              {result.route.excluded.map((p) => (
                <li key={p.pack} data-off title={p.reason}>
                  <Icon name="minus" size={14} />
                  <span>
                    <b>{p.label}</b>
                    <span>Not applied: {p.reason}</span>
                  </span>
                </li>
              ))}
            </ul>
          </details>
        </section>

        {w && (
          <section className={styles.card} aria-labelledby="wage-title">
            <div className={styles.sectionHead}>
              <h2 id="wage-title" className={styles.cardTitle}>
                What the worker actually takes home
              </h2>
              <span className={styles.sectionMeta}>Plain arithmetic, no AI</span>
            </div>
            <div className={styles.kpis}>
              <div>
                <span className={styles.kpiLabel}>Promised</span>
                <span className={styles.kpiNum}>{money(w.currency, w.promised)}</span>
              </div>
              <div data-tone={w.over_cap ? "bad" : undefined}>
                <span className={styles.kpiLabel}>Deducted monthly</span>
                <span className={styles.kpiNum}>
                  − {money(w.currency, w.monthly_deductions)} <small>{w.pct_deducted}%</small>
                </span>
              </div>
              <div data-tone={w.below_minimum || w.over_cap ? "bad" : "ok"}>
                <span className={styles.kpiLabel}>Take-home</span>
                <span className={styles.kpiNum}>{money(w.currency, w.net)}</span>
              </div>
              {w.minimum_wage && (
                <div>
                  <span className={styles.kpiLabel}>Legal minimum</span>
                  <span className={styles.kpiNum}>{money(w.currency, w.minimum_wage)}</span>
                </div>
              )}
            </div>
            <div className={styles.wageBar} aria-hidden="true">
              <span className={styles.wageFill} data-bad={w.below_minimum || w.over_cap} style={{ width: pct(w.net) }} />
              {w.minimum_wage && <span className={styles.wageMin} style={{ left: pct(w.minimum_wage) }} />}
            </div>
            <div className={styles.wageLegend} aria-hidden="true">
              <span>
                <i data-k="net" data-bad={w.below_minimum || w.over_cap} /> Take-home
              </span>
              {w.minimum_wage && (
                <span>
                  <i data-k="min" /> Legal minimum
                </span>
              )}
            </div>
            <p className={styles.note}>{w.confirmed_by_user ? "Salary confirmed by the user after reading the photo." : "Salary as written in the document."}</p>
          </section>
        )}

        {live.length > 0 && (
          <div className={styles.sectionHead}>
            <h2 className={styles.sectionTitle}>Risks, most serious first</h2>
            {counts.length > 1 ? (
              <div className={styles.filterChips} role="group" aria-label="Filter risks by severity">
                <button type="button" aria-pressed={sevFilter === "all"} onClick={() => setSevFilter("all")}>
                  All <span className={styles.count}>{live.length}</span>
                </button>
                {counts.map(([sv, n]) => (
                  <button key={sv} type="button" data-sev={sv} aria-pressed={sevFilter === sv} onClick={() => setSevFilter(sv)}>
                    <span className={styles.sevDot} data-sev={sv} />
                    {SEVERITY_LABEL[sv]} <span className={styles.count}>{n}</span>
                  </button>
                ))}
              </div>
            ) : (
              <span className={styles.sectionMeta}>Each one is backed by verified law</span>
            )}
          </div>
        )}
        {shown.map((r) => (
          <RiskCard
            key={r.id}
            index={live.indexOf(r) + 1}
            risk={r}
            issue={result.memo.issues.find((x) => x.risk_id === r.id)}
            rows={result.ledger.filter((v) => v.claim.risk_id === r.id)}
            clauses={result.document.clauses.filter((c) => r.clause_ids.includes(c.id))}
            active={focusRisk === r.id}
            onAskCouncil={() => onAsk(r.id)}
            onClause={onClause}
          />
        ))}

        {withdrawn > 0 && (
          <p className={styles.notice}>
            <Icon name="info" size={16} />
            <span>
              {withdrawn} more possible {withdrawn === 1 ? "risk was" : "risks were"} left out because the law behind {withdrawn === 1 ? "it" : "them"} could
              not be verified.{" "}
              <button type="button" className={styles.linkBtn} onClick={onChecks}>
                See how we checked <Icon name="arrowRight" size={14} />
              </button>
            </span>
          </p>
        )}

        <details className={styles.more}>
          <summary>
            <Icon name="chevronRight" size={16} className={styles.summaryChevron} />
            Limits of this memo
          </summary>
          <ul className={styles.caveatList}>
            {result.memo.caveats.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </details>
      </div>

      {/* ---------------- at a glance */}
      <aside className={styles.aside} aria-label="At a glance">
        <section className={styles.asideCard}>
          <h2 className={styles.asideTitle}>At a glance</h2>
          {live.length > 0 && (
            <>
              <div className={styles.sevBar} aria-hidden="true">
                {counts.map(([sv, n]) => (
                  <span key={sv} data-sev={sv} style={{ flexGrow: n }} />
                ))}
              </div>
              <ul className={styles.sevLegend}>
                {counts.map(([sv, n]) => (
                  <li key={sv}>
                    <span className={styles.sevDot} data-sev={sv} />
                    {SEVERITY_LABEL[sv]}
                    <b>{n}</b>
                  </li>
                ))}
              </ul>
            </>
          )}
          <button type="button" className={styles.verifiedStat} onClick={onChecks}>
            <Icon name="shieldCheck" size={20} />
            <span>
              <b>
                {s.verified} of {s.claims}
              </b>{" "}
              legal claims passed every check
            </span>
            <Icon name="chevronRight" size={16} />
          </button>
        </section>

        {live.length > 0 && (
          <nav className={styles.asideCard} aria-label="Jump to a risk">
            <h2 className={styles.asideTitle}>Risks</h2>
            <ol className={styles.jumpList}>
              {live.map((r, i) => (
                <li key={r.id}>
                  <button
                    type="button"
                    onClick={() => {
                      if (sevFilter !== "all" && sevFilter !== r.severity) setSevFilter("all");
                      onJump(r.id);
                    }}
                  >
                    <span className={styles.jumpNum} data-sev={r.severity}>
                      {i + 1}
                    </span>
                    <span>{r.title.en}</span>
                  </button>
                </li>
              ))}
            </ol>
          </nav>
        )}


        <button type="button" className={styles.councilCta} onClick={onCouncil}>
          <CouncilFaces size={28} />
          <span className={styles.ctaText}>
            <b>Ask the council</b>
            <span>Three AI reviewers, grounded in verified law</span>
          </span>
          <Icon name="arrowRight" size={16} />
        </button>
      </aside>
    </main>
  );
}

/* ------------------------------------------------------------------ Contract */

function Contract({ result, heat, onRisk }: { result: AnalysisResult; heat: ReturnType<typeof clauseHeat>; onRisk: (riskId: string) => void }) {
  const [onlyFlagged, setOnlyFlagged] = useState(false);
  const all = result.document.clauses;
  const clauses = all.filter((c) => !onlyFlagged || heat.has(c.id));

  return (
    <main className={styles.narrow}>
      <header className={styles.viewHead}>
        <h1 className={styles.viewTitle}>The contract</h1>
        <p className={styles.viewLead}>
          This is the exact copy the AI saw. Names, phone numbers and ID numbers are hidden. Highlighted clauses carry a risk; select one to read the
          analysis.
        </p>
      </header>
      <div className={styles.contractBar}>
        <div className={styles.segmented} role="group" aria-label="Which clauses to show">
          <button type="button" aria-pressed={!onlyFlagged} onClick={() => setOnlyFlagged(false)}>
            All clauses <span className={styles.count}>{all.length}</span>
          </button>
          <button type="button" aria-pressed={onlyFlagged} onClick={() => setOnlyFlagged(true)}>
            Flagged only <span className={styles.count}>{heat.size}</span>
          </button>
        </div>
        <span className={styles.legend}>
          {(["critical", "high", "medium", "low"] as Severity[]).map((s) => (
            <span key={s}>
              <span className={styles.sevDot} data-sev={s} />
              {SEVERITY_LABEL[s]}
            </span>
          ))}
        </span>
      </div>
      <ol className={styles.sheet}>
        {clauses.map((c) => {
          const h = heat.get(c.id);
          return (
            <li key={c.id} id={`clause-${c.id}`} className={styles.clauseItem}>
              <span className={styles.clauseNum} aria-hidden="true">
                {c.index + 1}
              </span>
              {h ? (
                <button type="button" className={styles.clause} data-sev={h.sev} onClick={() => onRisk(h.risk)}>
                  <span className={styles.clauseText}>{c.text}</span>
                  <span className={styles.clauseRisk}>
                    <span className={styles.sev} data-sev={h.sev}>
                      <span className={styles.sevDot} data-sev={h.sev} />
                      {SEVERITY_LABEL[h.sev]}
                    </span>
                    {h.title}
                    <Icon name="arrowRight" size={14} />
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

/* ------------------------------------------------------------------ Verification */

type CheckTab = "ledger" | "trace" | "ablation" | "privacy";
const CHECK_TABS: { id: CheckTab; label: string; icon: IconName }[] = [
  { id: "ledger", label: "Every legal claim", icon: "list" },
  { id: "trace", label: "Agent activity", icon: "activity" },
  { id: "ablation", label: "Compare with a plain chatbot", icon: "scale" },
  { id: "privacy", label: "Privacy", icon: "lock" },
];

function Checks({ result, events }: { result: AnalysisResult; events: AnalysisResult["trace"] }) {
  const [tab, setTab] = useState<CheckTab>("ledger");
  const s = result.stats;
  return (
    <main className={styles.wide}>
      <header className={styles.viewHead}>
        <h1 className={styles.viewTitle}>How we checked this memo</h1>
        <p className={styles.viewLead}>
          AI agents proposed legal points, and each one had to pass four checks before it could appear in the memo: the section must exist and apply to
          this contract, the quote must match the statute, independent AI judges must agree the law says what we claim, and the law must still be in
          force.
        </p>
      </header>
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
      <div className={styles.subTabs} role="tablist" aria-label="Verification details">
        {CHECK_TABS.map((t) => (
          <button
            key={t.id}
            id={`check-tab-${t.id}`}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            aria-controls="check-panel"
            className={styles.subTab}
            onClick={() => setTab(t.id)}
          >
            <Icon name={t.icon} size={15} />
            {t.label}
          </button>
        ))}
      </div>
      <div id="check-panel" role="tabpanel" aria-labelledby={`check-tab-${tab}`} className={styles.card}>
        {tab === "ledger" && <LedgerPanel result={result} />}
        {tab === "trace" && <TracePanel events={events} />}
        {tab === "ablation" && <AblationPanel result={result} />}
        {tab === "privacy" && <PrivacyPanel result={result} />}
      </div>
    </main>
  );
}
