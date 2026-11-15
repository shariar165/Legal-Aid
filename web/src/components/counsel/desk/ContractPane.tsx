"use client";

import { useEffect, useMemo, useRef } from "react";
import type { AnalysisResult, Clause } from "@/lib/api";
import { DESK, type Lang } from "@/lib/desk/i18n";
import type { DeskRow } from "@/lib/desk/rows";
import { Icon } from "@/components/shared/Icons";
import { isBangla } from "./util";
import s from "./desk.module.css";

/* The contract as the AI saw it (redacted), on a paper sheet. The selected row's clauses are highlighted; a clause
   that belongs to a row selects it. Under 1100px the sheet folds into a disclosure, closed by default. */

const HEADING = /^(\s*[0-9০-৯]{1,3}[.)]\s*[^.\n]{1,48}\.)\s*/;

function ClauseText({ c }: { c: Clause }) {
  const m = c.text.match(HEADING);
  return (
    <>
      {m && <b>{m[1].trim()} </b>}
      {m ? c.text.slice(m[0].length) : c.text}
    </>
  );
}

interface Props {
  result: AnalysisResult;
  rows: DeskRow[];
  selected: DeskRow | null;
  onSelect: (key: string) => void;
  lang: Lang;
  wide: boolean;
}

export function ContractPane({ result, rows, selected, onSelect, lang, wide }: Props) {
  const pane = useRef<HTMLElement>(null);
  const rowOf = useMemo(() => {
    const m = new Map<string, string>();
    for (const r of rows) for (const id of r.clauseIds) if (!m.has(id)) m.set(id, r.key);
    return m;
  }, [rows]);
  const lit = useMemo(() => new Set(selected?.clauseIds ?? []), [selected]);

  // bring the highlighted clause into the pane's own view, without moving the page
  useEffect(() => {
    const box = pane.current;
    const first = box?.querySelector<HTMLElement>("[data-on='true']");
    if (!wide || !box || !first) return;
    const a = box.getBoundingClientRect();
    const b = first.getBoundingClientRect();
    if (b.top < a.top || b.bottom > a.bottom) box.scrollBy({ top: b.top - a.top - 24, behavior: "smooth" });
  }, [lit, wide]);

  const sheet = (
    <div className={s.sheet}>
      {result.document.clauses.map((c) => {
        const key = rowOf.get(c.id);
        const on = lit.has(c.id);
        const lang = isBangla(c.text) ? "bn" : "en";
        return key ? (
          <button key={c.id} type="button" className={s.clause} data-on={on} aria-pressed={on} lang={lang} onClick={() => onSelect(key)}>
            <ClauseText c={c} />
          </button>
        ) : (
          <p key={c.id} className={s.clause} data-on={on} lang={lang}>
            <ClauseText c={c} />
          </p>
        );
      })}
    </div>
  );

  if (!wide) {
    return (
      <details className={s.contractFold}>
        <summary>
          <Icon name="chevronRight" size={18} className={s.foldChevron} />
          <Icon name="file" size={18} />
          {DESK.contract.full[lang]}
        </summary>
        <p className={s.muted}>{DESK.contract.redacted[lang]}</p>
        {sheet}
      </details>
    );
  }
  return (
    <section ref={pane} className={s.contract} aria-labelledby="contract-title">
      <h2 id="contract-title" className={s.paneTitle}>
        {DESK.contract.title[lang]}
      </h2>
      <p className={s.muted}>{DESK.contract.redacted[lang]}</p>
      {sheet}
    </section>
  );
}
