"use client";

import type { AnalysisResult, LedgerCell } from "@/lib/api";
import { DESK, SEVERITY_NAME, type Lang } from "@/lib/desk/i18n";
import type { DeskRow, LawBadge, Node } from "@/lib/desk/rows";
import { Icon } from "@/components/shared/Icons";
import { RatifyBadge } from "@/components/shared/RatifyBadge";
import { citeName, citeShort, clauseNo, isBangla } from "./util";
import s from "./desk.module.css";

/* The chain rows: told · paper · paid · law for each term, one button per row. Nodes and badges follow the
   backend's mismatches only (rows.ts); nothing here compares amounts. */

const BADGE: Record<LawBadge, keyof typeof DESK.rows> = {
  violation: "violation",
  verified: "verified",
  partial: "partial",
  not_verified: "notVerified",
  pending: "pending",
};

export function NodeMark({ n, lang, size = 28 }: { n: Node; lang: Lang; size?: number }) {
  if (n === "dash") {
    return (
      <span className={s.nodeDash} aria-hidden="true">
        <span />
      </span>
    );
  }
  return (
    <span className={s.node} data-n={n} style={{ width: size, height: size }}>
      <Icon name={n === "ne" ? "notEqual" : "equal"} size={Math.round(size * 0.6)} strokeWidth={2.5} />
      <span className={s.srOnly}>{n === "ne" ? DESK.rows.ne[lang] : DESK.rows.eq[lang]}</span>
    </span>
  );
}

export function LawBadgePill({ badge, lang }: { badge: LawBadge; lang: Lang }) {
  const label = DESK.rows[BADGE[badge]] as { bn: string; en: string };
  return (
    <span className={s.badge} data-b={badge}>
      {label[lang]}
    </span>
  );
}

function Cell({ k, label, cell, empty, lang }: { k: "said" | "paper" | "paid"; label: string; cell: LedgerCell | null; empty: string; lang: Lang }) {
  return (
    <span className={s.cell} data-k={k} data-empty={!cell}>
      <span className={s.cellLabel}>{label}</span>
      <span className={s.cellValue}>
        {cell ? cell.value[lang] : empty}
        {cell?.confirmed_by_user && <Icon name="check" size={14} strokeWidth={2.5} label={lang === "bn" ? "ব্যবহারকারী নিশ্চিত করেছেন" : "confirmed by user"} />}
      </span>
    </span>
  );
}

interface Props {
  result: AnalysisResult;
  rows: DeskRow[];
  selectedKey: string | null;
  onSelect: (key: string) => void;
  lang: Lang;
  /** what the worker was told is on file: an empty told cell then means "not said" */
  hasPromises: boolean;
  ledgerOn: boolean;
  /** some row has a told value / a paid value; else that column is left out (spec 29 step 3.2) */
  showTold: boolean;
  showPaid: boolean;
}

export function ChainRows({ result, rows, selectedKey, onSelect, lang, hasPromises, ledgerOn, showTold, showPaid }: Props) {
  const T = DESK.rows;
  const told = ledgerOn && showTold;
  const paid = ledgerOn && showPaid;
  const cols = 2 + Number(told) + Number(paid); // paper and law always
  const clauseIndex = new Map(result.document.clauses.map((c) => [c.id, c]));
  return (
    <section className={s.chain} aria-labelledby="chain-title">
      <div className={s.chainHead}>
        <h2 id="chain-title" className={s.paneTitle}>
          {ledgerOn ? T.title[lang] : T.riskTitle[lang]}
        </h2>
        {/* the ≠ / = marks sit between told and paper, so the legend goes with them */}
        {told && (
          <>
            <span className={s.legend} aria-hidden="true">
              <NodeMark n="ne" lang={lang} size={22} /> {T.ne[lang]}
            </span>
            <span className={s.legend} aria-hidden="true">
              <NodeMark n="eq" lang={lang} size={22} /> {T.eq[lang]}
            </span>
          </>
        )}
        {ledgerOn && !paid && <span className={s.legend}>{T.noPayslips[lang]}</span>}
      </div>

      {rows.length === 0 ? (
        <p className={s.muted}>{T.empty[lang]}</p>
      ) : (
        <div className={s.chainScroll}>
          <ul className={s.chainList} data-cols={cols}>
            {rows.map((r) => {
              const clause = r.kind === "risk" && r.clauseIds[0] ? clauseIndex.get(r.clauseIds[0]) : undefined;
              const cite = r.law.citationIds[0];
              const lawShort = cite ? citeShort(result, cite, lang) : null;
              // the cell shows the short citation; the hover names the act in full, after what the law says here
              const lawTip = [r.law.title?.[lang], cite && citeName(result, cite, lang)].filter(Boolean).join(" · ") || undefined;
              const ratify = cite ? result.ratification?.[cite] : undefined;
              return (
                <li key={r.key}>
                  <button type="button" className={s.row} aria-pressed={r.key === selectedKey} onClick={() => onSelect(r.key)}>
                    <span className={s.rowHead}>
                      <span className={s.rowTitle} lang={lang}>
                        {r.title[lang]}
                      </span>
                      {r.severity && (
                        <span className={s.sev} data-sev={r.severity}>
                          {SEVERITY_NAME[r.severity][lang]}
                        </span>
                      )}
                      {r.pending && <span className={s.pendingPill}>{T.pending[lang]}</span>}
                      {r.mismatches.length > 0 && <span className={s.count}>{T.count(r.mismatches.length, lang)}</span>}
                    </span>
                    {/* flag off, an older result or nothing told / paid yet: those cells are left out and the rest get the width */}
                    <span className={s.cells} data-cols={cols}>
                      {told && (
                        <>
                          <Cell k="said" label={T.said[lang]} cell={r.kind === "term" ? r.said : null} empty={hasPromises ? T.notSaid[lang] : "–"} lang={lang} />
                          <NodeMark n={r.saidPaper} lang={lang} />
                        </>
                      )}
                      {r.kind === "term" ? (
                        <Cell k="paper" label={T.paper[lang]} cell={r.paper} empty={T.notOnPaper[lang]} lang={lang} />
                      ) : (
                        <span className={s.cell} data-k="paper">
                          <span className={s.cellLabel}>
                            {T.paper[lang]}
                            {clause && ` · ${T.clause(clauseNo(clause), lang)}`}
                          </span>
                          {clause && (
                            <span className={s.cellClamp} lang={isBangla(clause.text) ? "bn" : "en"}>
                              {clause.text}
                            </span>
                          )}
                        </span>
                      )}
                      {paid && (
                        <>
                          <NodeMark n="dash" lang={lang} />
                          <Cell k="paid" label={T.paid[lang]} cell={r.paid} empty={T.noPayslip[lang]} lang={lang} />
                        </>
                      )}
                      <span className={s.divider} aria-hidden="true" />
                      {/* spec 29 step 3.1: the short citation, then the status on a line of its own (never beside it) */}
                      <span className={s.lawCell} data-empty={!r.law.badge && !lawShort && !r.law.title} title={lawTip}>
                        <span className={s.cellLabel} data-k="law">
                          {T.law[lang]}
                        </span>
                        <span className={s.lawValue}>{lawShort ?? r.law.title?.[lang] ?? (r.law.badge ? "" : T.noLaw[lang])}</span>
                        {(r.law.badge || ratify) && (
                          <span className={s.lawStatus}>
                            {r.law.badge && <LawBadgePill badge={r.law.badge} lang={lang} />}
                            <RatifyBadge r={ratify} lang={lang} />
                          </span>
                        )}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
