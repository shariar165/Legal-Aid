"use client";

import { useState } from "react";
import type { MemoIssue, Risk, Verification } from "@/lib/api";
import { citeLabel, ORIGIN_LABEL, SEVERITY_LABEL, VERDICT_LABEL } from "./format";
import styles from "./counsel.module.css";

interface Props {
  risk: Risk;
  issue: MemoIssue | undefined;
  rows: Verification[];
  active: boolean;
  onFocus: () => void;
}

export function RiskCard({ risk, issue, rows, active, onFocus }: Props) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const dropped = risk.status === "dropped";

  return (
    <article
      id={`risk-${risk.id}`}
      className={styles.risk}
      data-sev={risk.severity}
      data-active={active}
      data-dropped={dropped}
      aria-labelledby={`risk-title-${risk.id}`}
    >
      <header className={styles.riskHead}>
        <span className={styles.sev} data-sev={risk.severity}>
          {SEVERITY_LABEL[risk.severity]}
        </span>
        <span className={styles.origin} data-origin={risk.origin}>
          {ORIGIN_LABEL[risk.origin]}
        </span>
        {risk.clash && <span className={styles.clash}>Valid abroad · void in BD</span>}
        {risk.bench?.human_review && <span className={styles.review}>⚠ Human review</span>}
        <span className={styles.riskId}>{risk.id}</span>
      </header>

      <h3 id={`risk-title-${risk.id}`} className={styles.riskTitle}>
        <button type="button" className={styles.linkish} onClick={onFocus}>
          {risk.title.en}
        </button>
      </h3>
      <p className={styles.riskBn} lang="bn">
        {risk.title.bn}
      </p>
      <p className={styles.finding}>{risk.finding}</p>
      {risk.why_non_obvious && (
        <p className={styles.why}>
          <strong>Why it is easy to miss.</strong> {risk.why_non_obvious}
        </p>
      )}
      {risk.clash && <p className={styles.clashText}>{risk.clash}</p>}

      <ul className={styles.citeList}>
        {rows.map((v) => (
          <li key={v.claim.id} className={styles.citeRow} data-verdict={v.verdict}>
            <span className={styles.verdictPill} data-verdict={v.verdict}>
              {VERDICT_LABEL[v.verdict]}
            </span>
            {v.section ? (
              <a href={v.section.url} target="_blank" rel="noreferrer" className={styles.citeLink}>
                {citeLabel(v.section)}
              </a>
            ) : (
              <span className={styles.citeLink}>{v.claim.citation_id}</span>
            )}
            {v.note && <span className={styles.citeNote}>{v.note}</span>}
          </li>
        ))}
      </ul>

      {risk.bench && (
        <div className={styles.benchMini}>
          <span className={styles.benchVote}>Virtual Bench {risk.bench.vote}</span>
          <span>{risk.bench.majority_opinion}</span>
          {risk.bench.dissent && <span className={styles.dissent}>Dissent: {risk.bench.dissent}</span>}
        </div>
      )}

      {issue && (
        <>
          <button type="button" className={styles.iracBtn} aria-expanded={open} onClick={() => setOpen((o) => !o)}>
            {open ? "Hide" : "Show"} IRAC analysis {open ? "▾" : "▸"}
          </button>
          {open && (
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
          )}
        </>
      )}

      {risk.mitigation_clause && !dropped && (
        <div className={styles.mitigation}>
          <div className={styles.mitHead}>
            <span>Suggested replacement clause</span>
            <button
              type="button"
              className={styles.ghostBtn}
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
        </div>
      )}
    </article>
  );
}
