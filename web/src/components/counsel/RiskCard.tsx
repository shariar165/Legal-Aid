"use client";

import { useState } from "react";
import type { Clause, MemoIssue, Risk, Verification } from "@/lib/api";
import { CouncilFaces, MemberVotes } from "./Council";
import { citeLabel, SEVERITY_LABEL } from "./format";
import { Icon } from "./Icons";
import styles from "./counsel.module.css";

interface Props {
  risk: Risk;
  index: number;
  issue: MemoIssue | undefined;
  rows: Verification[];
  clauses: Clause[];
  active: boolean;
  onAskCouncil: () => void;
  onClause: (clauseId: string) => void;
}

/* One risk: what is wrong, what to do, and the law behind it. Everything else sits behind "Details". */
export function RiskCard({ risk, index, issue, rows, clauses, active, onAskCouncil, onClause }: Props) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const laws = rows.filter((v) => v.section && v.verdict !== "dropped");
  const detailsId = `risk-details-${risk.id}`;

  return (
    <article id={`risk-${risk.id}`} className={styles.risk} data-sev={risk.severity} data-active={active} aria-labelledby={`risk-title-${risk.id}`}>
      <header className={styles.riskHead}>
        <span className={styles.riskNum}>Risk {index}</span>
        <span className={styles.sev} data-sev={risk.severity}>
          <span className={styles.sevDot} data-sev={risk.severity} />
          {SEVERITY_LABEL[risk.severity]}
        </span>
        {risk.bench?.human_review && (
          <span className={styles.review}>
            <Icon name="shield" size={13} />
            Lawyer review advised
          </span>
        )}
      </header>

      <h3 id={`risk-title-${risk.id}`} className={styles.riskTitle}>
        {risk.title.en}
      </h3>
      <p className={styles.riskBn} lang="bn">
        {risk.title.bn}
      </p>
      <p className={styles.finding}>{risk.finding}</p>

      {risk.action.en && (
        <div className={styles.todo}>
          <Icon name="checkCircle" size={18} />
          <p>
            <b>Recommended action</b>
            {risk.action.en}
          </p>
        </div>
      )}

      {(laws.length > 0 || risk.bench) && (
        <dl className={styles.riskMeta}>
          {laws.length > 0 && (
            <div>
              <dt>Legal basis</dt>
              <dd className={styles.citeList}>
                {laws.map((v) => (
                  <a
                    key={v.claim.id}
                    href={v.section!.url}
                    target="_blank"
                    rel="noreferrer"
                    className={styles.citeChip}
                    data-verdict={v.verdict}
                    title={v.verdict === "verified" ? "Passed all four checks" : "Passed with a warning"}
                  >
                    <Icon name={v.verdict === "verified" ? "check" : "alert"} size={13} />
                    {citeLabel(v.section!)}
                    <Icon name="external" size={12} className={styles.extIcon} />
                  </a>
                ))}
              </dd>
            </div>
          )}
          {risk.bench && (
            <div>
              <dt>Council</dt>
              <dd className={styles.councilVote} title={risk.bench.majority_opinion}>
                <CouncilFaces size={20} />
                Voted {risk.bench.vote}
                {risk.bench.dissent && <span className={styles.splitTag}>Split view</span>}
              </dd>
            </div>
          )}
        </dl>
      )}

      <div className={styles.riskActions}>
        <button type="button" className={styles.secondaryBtn} onClick={onAskCouncil}>
          <Icon name="message" size={15} />
          Discuss with the council
        </button>
        <button type="button" className={styles.quietBtn} aria-expanded={open} aria-controls={detailsId} onClick={() => setOpen((o) => !o)}>
          {open ? "Hide details" : "Show details"}
          <Icon name="chevronDown" size={15} className={styles.chevron} />
        </button>
      </div>

      {open && (
        <div id={detailsId} className={styles.riskDetails}>
          {clauses.length > 0 && (
            <section>
              <h4>In the contract</h4>
              {clauses.map((c) => (
                <blockquote key={c.id} className={styles.quote}>
                  <span>{c.text}</span>
                  <button type="button" className={styles.linkBtn} onClick={() => onClause(c.id)}>
                    Show in the contract <Icon name="arrowRight" size={14} />
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
                  className={styles.quietBtn}
                  data-size="sm"
                  onClick={() => {
                    void navigator.clipboard?.writeText(risk.mitigation_clause).then(() => {
                      setCopied(true);
                      setTimeout(() => setCopied(false), 2000);
                    });
                  }}
                >
                  <Icon name={copied ? "check" : "copy"} size={14} />
                  {copied ? "Copied" : "Copy"}
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
              {risk.bench.dissent && (
                <p className={styles.dissent}>
                  <b>Dissent.</b> {risk.bench.dissent}
                </p>
              )}
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
