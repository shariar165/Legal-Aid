"use client";

import { useState } from "react";
import type { Clause, MemoIssue, Risk, Verification } from "@/lib/api";
import { CouncilFaces, MemberVotes } from "./Council";
import { citeLabel, SEVERITY_LABEL } from "./format";
import styles from "./counsel.module.css";

interface Props {
  risk: Risk;
  issue: MemoIssue | undefined;
  rows: Verification[];
  clauses: Clause[];
  active: boolean;
  onAskCouncil: () => void;
  onClause: (clauseId: string) => void;
}

/* One risk: what is wrong, what to do, and the law behind it. Everything else sits behind "More details". */
export function RiskCard({ risk, issue, rows, clauses, active, onAskCouncil, onClause }: Props) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const laws = rows.filter((v) => v.section && v.verdict !== "dropped");

  return (
    <article id={`risk-${risk.id}`} className={styles.risk} data-sev={risk.severity} data-active={active} aria-labelledby={`risk-title-${risk.id}`}>
      <header className={styles.riskHead}>
        <span className={styles.sev} data-sev={risk.severity}>
          {SEVERITY_LABEL[risk.severity]}
        </span>
        {risk.bench?.human_review && <span className={styles.review}>A lawyer should double-check this</span>}
      </header>

      <h3 id={`risk-title-${risk.id}`} className={styles.riskTitle}>
        {risk.title.en}
      </h3>
      <p className={styles.riskBn} lang="bn">
        {risk.title.bn}
      </p>
      <p className={styles.finding}>{risk.finding}</p>

      {risk.action.en && (
        <p className={styles.todo}>
          <b>What to do:</b> {risk.action.en}
        </p>
      )}

      <div className={styles.riskFoot}>
        {laws.map((v) => (
          <a key={v.claim.id} href={v.section!.url} target="_blank" rel="noreferrer" className={styles.lawLink} data-verdict={v.verdict}>
            {v.verdict === "verified" ? "✓" : "⚠"} {citeLabel(v.section!)}
          </a>
        ))}
        {risk.bench && (
          <span className={styles.councilVote} title={risk.bench.majority_opinion}>
            <CouncilFaces size={18} /> Council voted {risk.bench.vote}
          </span>
        )}
      </div>

      <div className={styles.riskActions}>
        <button type="button" className={styles.smallBtn} onClick={onAskCouncil}>
          Ask the council
        </button>
        <button type="button" className={styles.smallBtn} data-quiet aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {open ? "Hide details" : "More details"}
        </button>
      </div>

      {open && (
        <div className={styles.riskDetails}>
          {clauses.length > 0 && (
            <section>
              <h4>In the contract</h4>
              {clauses.map((c) => (
                <blockquote key={c.id} className={styles.quote}>
                  {c.text}
                  <button type="button" className={styles.askLink} onClick={() => onClause(c.id)}>
                    Show in the contract →
                  </button>
                </blockquote>
              ))}
            </section>
          )}

          {risk.why_non_obvious && (
            <section>
              <h4>Why it is easy to miss</h4>
              <p>{risk.why_non_obvious}</p>
            </section>
          )}
          {risk.clash && (
            <section>
              <h4>Valid abroad, void in Bangladesh</h4>
              <p>{risk.clash}</p>
            </section>
          )}

          {risk.mitigation_clause && (
            <section className={styles.mitigation}>
              <div className={styles.mitHead}>
                <h4>Suggested replacement clause</h4>
                <button
                  type="button"
                  className={styles.smallBtn}
                  onClick={() => {
                    void navigator.clipboard?.writeText(risk.mitigation_clause).then(() => {
                      setCopied(true);
                      setTimeout(() => setCopied(false), 2000);
                    });
                  }}
                >
                  {copied ? "✓ Copied" : "Copy"}
                </button>
              </div>
              <p>{risk.mitigation_clause}</p>
            </section>
          )}

          {risk.bench && (
            <section>
              <h4>How the council voted</h4>
              <MemberVotes bench={risk.bench} />
              <p>{risk.bench.majority_opinion}</p>
              {risk.bench.dissent && <p className={styles.dissent}>Disagreement: {risk.bench.dissent}</p>}
            </section>
          )}

          {issue && (
            <section>
              <h4>Legal analysis</h4>
              <dl className={styles.irac}>
                <dt>Issue</dt>
                <dd>{issue.issue}</dd>
                <dt>Rule</dt>
                <dd>{issue.rule}</dd>
                <dt>Application</dt>
                <dd>{issue.application}</dd>
                <dt>Conclusion</dt>
                <dd>{issue.conclusion}</dd>
              </dl>
            </section>
          )}
        </div>
      )}
    </article>
  );
}
