"use client";

import type { Ref } from "react";
import type { AnalysisResult, BenchResult, PersonaId, Severity } from "@/lib/api";
import { DESK, num, SEVERITY_NAME, type Lang } from "@/lib/desk/i18n";
import { claimFor, type DeskRow, type LawRef } from "@/lib/desk/rows";
import { Icon } from "@/components/shared/Icons";
import { RatifyBadge } from "@/components/shared/RatifyBadge";
import { CouncilAvatar, memberLabel } from "../Council";
import { GATE_ICON } from "../format";
import { LawBadgePill, NodeMark } from "./ChainRows";
import { citeName, clauseNo, isBangla } from "./util";
import s from "./desk.module.css";

/* The evidence file for the selected row, in one place: what was said, the clause, the verbatim law, the 4 gates,
   the council's votes and what evidence exists. Nothing here is computed: it reads the result as saved. */

const GATE_ORDER = ["existence", "fidelity", "entailment", "currency"] as const;
const SCALE: Severity[] = ["low", "medium", "high", "critical"];
const MONEY_TERMS = new Set(["salary", "deductions", "recruitment_cost"]);

interface Props {
  ref?: Ref<HTMLElement>;
  result: AnalysisResult;
  row: DeskRow | null;
  lang: Lang;
  onAsk: (riskId: string) => void;
  onVerify: () => void;
  verifying: boolean;
}

export function EvidenceFile({ ref, result, row, lang, onAsk, onVerify, verifying }: Props) {
  const T = DESK.evidence;
  if (!row) {
    return (
      <aside ref={ref} className={s.evidence} aria-label={T.region[lang]}>
        <div className={s.evBody}>
          <p className={s.muted}>{DESK.rows.empty[lang]}</p>
        </div>
      </aside>
    );
  }

  const four = result.four_ledgers;
  const types = new Set(row.mismatches.map((m) => m.type));
  const clause = row.clauseIds[0] ? result.document.clauses.find((c) => c.id === row.clauseIds[0]) : undefined;
  const risk = row.riskId ? result.risks.find((r) => r.id === row.riskId) : undefined;
  const saidOn = four?.promises?.said_on ?? null;
  const pvl = row.mismatches.find((m) => m.type === "paper_vs_law");

  // the 4 gates of the first law that went through them
  const gated = row.lawRefs
    .filter((l) => l.status !== "not_verified_yet" && l.citationIds.length)
    .map((l) => claimFor(result, l.citationIds[0], l.riskId).verification)
    .find(Boolean);

  const items = [
    { key: "clause", label: T.item.clause[lang], have: !!clause },
    ...(row.kind === "term" ? [{ key: "account", label: (saidOn ? T.item.accountDated : T.item.account)[lang], have: !!row.said }] : []),
    { key: "law", label: T.item.law[lang], have: row.lawRefs.some((l) => l.status === "verified" || l.status === "partial") },
    ...(row.term && MONEY_TERMS.has(row.term) ? [{ key: "payslip", label: T.item.payslip[lang], have: false }] : []),
  ];
  const have = items.filter((i) => i.have).length;

  return (
    <aside ref={ref} className={s.evidence} aria-labelledby="evidence-title">
      <div className={s.evHead}>
        <span className={s.evKicker}>{T.file[lang]}</span>
        <div className={s.evTitleRow}>
          <h2 id="evidence-title" className={s.evTitle}>
            {row.title[lang]}
          </h2>
          {row.severity && (
            <span className={s.sev} data-sev={row.severity}>
              {SEVERITY_NAME[row.severity][lang]}
            </span>
          )}
          {row.pending && <span className={s.pendingPill}>{DESK.rows.pending[lang]}</span>}
        </div>
        {types.size > 0 && (
          <div className={s.evChips}>
            {types.has("said_vs_paper") && <span>{T.saidPaper[lang]}</span>}
            {types.has("paper_vs_law") && <span>{T.paperLaw[lang]}</span>}
          </div>
        )}
      </div>

      <div className={s.evBody}>
        <div className={s.evChain}>
          {row.said && (
            <>
              <div className={s.block} data-k="said">
                <span className={s.blockLabel}>
                  {T.worker[lang]}
                  {saidOn && ` · ${T.saidOn(saidOn, lang)}`}
                </span>
                <span className={s.blockValue}>{row.said.value[lang]}</span>
              </div>
              <NodeMark n={row.saidPaper} lang={lang} size={34} />
            </>
          )}
          {(clause || row.paper) && (
            <div className={s.block} data-k="paper">
              <span className={s.blockLabel}>{T.contract(clause ? DESK.rows.clause(clauseNo(clause), lang) : "", lang)}</span>
              {clause && (
                <span className={s.quoteText} lang={isBangla(clause.text) ? "bn" : "en"}>
                  {clause.text}
                </span>
              )}
              {row.paper && <span className={s.blockValue}>{row.paper.value[lang]}</span>}
            </div>
          )}
          {row.lawRefs.some((l) => l.citationIds.length) && <NodeMark n={pvl ? "ne" : "dash"} lang={lang} size={34} />}
          {row.lawRefs.map((l) => (
            <LawBlock key={`${l.riskId}-${l.citationIds[0] ?? ""}`} result={result} law={l} lang={lang} violation={!!pvl && pvl.risk_id === l.riskId && pvl.risk_status === "verified"} />
          ))}
        </div>

        {row.mismatches.length > 0 && (
          <ul className={s.details}>
            {row.mismatches.map((m, i) => (
              <li key={i}>{m.detail[lang]}</li>
            ))}
          </ul>
        )}

        {gated && (
          <section className={s.evSection} aria-labelledby="gates-title">
            <h3 id="gates-title" className={s.evSectionTitle}>
              {T.gates[lang]}
            </h3>
            <ol className={s.gates}>
              {GATE_ORDER.map((g, i) => {
                const gate = gated.gates.find((x) => x.gate === g);
                const st = gate?.status ?? "skip";
                const sub = g === "entailment" && gated.bench ? `${T.bench[lang]} ${digits(gated.bench.vote, lang)}` : T.gateStatus[st][lang];
                return (
                  <li key={g} data-status={st} title={gate?.detail}>
                    <span className={s.gateDot}>
                      <Icon name={GATE_ICON[st]} size={16} strokeWidth={3} />
                    </span>
                    <b>{T.gateName[i][lang]}</b>
                    <span>{sub}</span>
                  </li>
                );
              })}
            </ol>
          </section>
        )}

        {risk && (
          <section className={s.evSection} aria-labelledby="votes-title">
            <h3 id="votes-title" className={s.evSectionTitle}>
              {T.council[lang]}
            </h3>
            {risk.bench ? <Votes bench={risk.bench} lang={lang} /> : <p className={s.muted}>{T.noBench[lang]}</p>}
          </section>
        )}

        <section className={s.evSection} aria-labelledby="have-title">
          <div className={s.haveHead}>
            <h3 id="have-title" className={s.evSectionTitle}>
              {T.evidence[lang]}
            </h3>
            <span className={s.haveCount}>
              {num(have, lang)} / {num(items.length, lang)}
            </span>
          </div>
          <div className={s.haveBar} aria-hidden="true">
            {items.map((i) => (
              <span key={i.key} data-have={i.have} />
            ))}
          </div>
          <ul className={s.haveList}>
            {items.map((i) => (
              <li key={i.key}>
                <span>{i.label}</span>
                <span className={s.havePill} data-have={i.have}>
                  {i.have ? T.have[lang] : T.need[lang]}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <div className={s.evActions}>
          {row.riskId ? (
            <button type="button" className={s.btnSecondary} onClick={() => onAsk(row.riskId!)}>
              <Icon name="message" size={18} />
              {T.ask[lang]}
            </button>
          ) : (
            row.pending && <p className={s.muted}>{T.askPending[lang]}</p>
          )}
          {row.pending && (
            <button type="button" className={s.btnPrimary} onClick={onVerify} disabled={verifying}>
              <Icon name="shieldCheck" size={18} />
              {verifying ? DESK.rows.verifying[lang] : DESK.rows.verify[lang]}
            </button>
          )}
        </div>
        <p className={s.disclaimer}>{T.disclaimer[lang]}</p>
      </div>
    </aside>
  );
}

const digits = (text: string, lang: Lang) => (lang === "bn" ? text.replace(/[0-9]/g, (d) => "০১২৩৪৫৬৭৮৯"[Number(d)]) : text);

function LawBlock({ result, law, lang, violation }: { result: AnalysisResult; law: LawRef; lang: Lang; violation: boolean }) {
  const T = DESK.evidence;
  const id = law.citationIds[0];
  if (!id) return null;
  const { verification, claim } = claimFor(result, id, law.riskId);
  const section = verification?.section ?? null;
  const pending = law.status === "not_verified_yet";
  const badge = violation ? "violation" : pending ? "pending" : law.status === "verified" ? "verified" : law.status === "partial" ? "partial" : "not_verified";
  return (
    <div className={s.block} data-k="law">
      <span className={s.blockLabel}>
        {pending ? T.lawPending[lang] : T.law[lang]}
        <LawBadgePill badge={badge} lang={lang} />
      </span>
      {law.title && <span className={s.blockValue}>{law.title[lang]}</span>}
      {claim?.quote ? (
        <blockquote className={s.lawQuote} lang={section?.lang ?? (isBangla(claim.quote) ? "bn" : "en")}>
          {claim.quote}
        </blockquote>
      ) : (
        <span className={s.muted}>{T.noQuote[lang]}</span>
      )}
      <span className={s.lawSource}>
        {!pending && law.status === "verified" && <Icon name="check" size={14} strokeWidth={2.75} />}
        {section?.url ? (
          <a href={section.url} target="_blank" rel="noreferrer">
            {citeName(result, id, lang)}
            <Icon name="external" size={12} />
          </a>
        ) : (
          citeName(result, id, lang)
        )}
      </span>
      <RatifyBadge r={result.ratification?.[id]} lang={lang} full />
    </div>
  );
}

/* Each member's severity vote, placed over the severity scale with their sticker. */
function Votes({ bench, lang }: { bench: BenchResult; lang: Lang }) {
  const T = DESK.evidence;
  const voters = bench.opinions.filter((o) => o.persona);
  return (
    <>
      <div className={s.scale}>
        {SCALE.map((sev) => (
          <div key={sev} className={s.scaleCol}>
            <span className={s.stickers}>
              {voters
                .filter((o) => o.severity === sev)
                .map((o) => (
                  <span key={o.seat} title={`${memberLabel(o.persona as PersonaId)}: ${SEVERITY_NAME[o.severity].en}`}>
                    <CouncilAvatar persona={o.persona as PersonaId} size={30} />
                  </span>
                ))}
            </span>
            <span className={s.scalePill} data-sev={sev}>
              {SEVERITY_NAME[sev][lang]}
            </span>
          </div>
        ))}
      </div>
      <p className={s.voteLine}>
        {bench.agreement ? T.agreement[bench.agreement][lang] : ""} {digits(bench.vote, lang)}
      </p>
    </>
  );
}
