"use client";

import { useState, type FormEvent } from "react";
import { api, type AnalysisResult } from "@/lib/api";
import { DESK, num, type Lang } from "@/lib/desk/i18n";
import { Icon } from "@/components/shared/Icons";
import { citeName, money } from "./util";
import s from "./desk.module.css";

/* Under the hero: the projected claim with the contract term it runs over (confirm or correct it, no model call),
   the promise gap and the break-even. Every figure and label is the backend's own. */

interface Props {
  result: AnalysisResult;
  lang: Lang;
  reload: () => Promise<void>;
  onAddSaid: () => void;
  formOpen: boolean;
}

export function MoneyStrip({ result, lang, reload, onAddSaid, formOpen }: Props) {
  const T = DESK.money;
  const four = result.four_ledgers!;
  const cp = four.claim_projection;
  const gap = four.promise_gap;
  const be = four.break_even;

  return (
    <div className={s.strip}>
      <div className={s.stripCard} data-wide="true">
        <div className={s.stripHead}>
          <span className={s.stripTitle}>{T.projected[lang]}</span>
          <span className={s.tag}>{T.projection[lang]}</span>
        </div>
        {cp.lines.length > 0 ? (
          <>
            <span className={s.stripNum}>{money(cp.currency ?? "", cp.projected_total)}</span>
            <ul className={s.stripLines}>
              {cp.lines.map((l) => (
                <li key={`${l.risk_id}-${l.citation_id}`}>
                  <span>
                    {l.label[lang]} · <span className={s.stripCite}>{citeName(result, l.citation_id, lang)}</span>
                  </span>
                  <b>{money(l.currency, l.amount)}</b>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className={s.stripNote}>{T.noLines[lang]}</p>
        )}
        <p className={s.stripNote}>{cp.label[lang]}</p>
        <TermControl result={result} lang={lang} reload={reload} />
      </div>

      {gap && (
        <div className={s.stripCard}>
          <div className={s.stripHead}>
            <span className={s.stripTitle}>{T.gap[lang]}</span>
          </div>
          <span className={s.stripNum}>{money(gap.currency, gap.total)}</span>
          <p className={s.stripNote}>{gap.label[lang]}</p>
        </div>
      )}

      {be && (
        <div className={s.stripCard}>
          <div className={s.stripHead}>
            <span className={s.stripTitle}>{T.breakEven[lang]}</span>
            {be.is_minimum && be.months !== null && <span className={s.tag}>{T.minimum[lang]}</span>}
          </div>
          <span className={s.stripNum}>{be.months !== null ? T.atLeast(be.months, lang) : T.notWithin[lang]}</span>
          {be.rate && (
            <span className={s.tag} data-tone="rate">
              {T.rate[lang]}: 1 {be.rate.per} = {be.rate.value} {be.rate.currency}
            </span>
          )}
          {be.note && <p className={s.stripNote}>{be.note[lang]}</p>}
          {be.assumption && <p className={s.stripNote}>{be.assumption[lang]}</p>}
        </div>
      )}

      {!formOpen && (
        <button type="button" className={s.addSaid} onClick={onAddSaid}>
          <Icon name={four.promises ? "repeat" : "plus"} size={18} strokeWidth={2.25} />
          {four.promises ? DESK.hero.editSaid[lang] : DESK.hero.addSaid[lang]}
        </button>
      )}
    </div>
  );
}

/* The term the projection runs over, with where it came from; confirm or correct it like the OCR salary. */
function TermControl({ result, lang, reload }: { result: AnalysisResult; lang: Lang; reload: () => Promise<void> }) {
  const T = DESK.money;
  const term = result.four_ledgers!.claim_projection.term ?? null;
  const [editing, setEditing] = useState(!term);
  const [value, setValue] = useState(term ? String(term.months) : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = async (months: number) => {
    setBusy(true);
    setError(null);
    try {
      await api.confirmTerm(result.job_id, months);
      await reload();
      setEditing(false);
    } catch (e) {
      setError((e as Error).message.replace(/^\d+: /, ""));
    } finally {
      setBusy(false);
    }
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const n = Number(value);
    if (Number.isInteger(n) && n > 0 && n <= 240) void send(n);
    else setError(lang === "bn" ? "১ থেকে ২৪০ মাসের মধ্যে লিখুন।" : "Enter 1 to 240 months.");
  };

  return (
    <div className={s.term}>
      <span className={s.termLabel}>{T.term[lang]}</span>
      {!editing && term ? (
        <>
          <span className={s.termValue}>
            {num(term.months, lang)} {T.months[lang]}
            <span className={s.termSource} data-source={term.source}>
              {term.source === "user" && <Icon name="check" size={14} strokeWidth={2.75} />}
              {term.label[lang]}
            </span>
          </span>
          <span className={s.termActions}>
            {term.source !== "user" && (
              <button type="button" className={s.btnOnDeep} disabled={busy} onClick={() => void send(term.months)}>
                <Icon name="check" size={16} strokeWidth={2.5} />
                {T.confirm[lang]}
              </button>
            )}
            <button type="button" className={s.btnOnDeepQuiet} disabled={busy} onClick={() => setEditing(true)}>
              {T.change[lang]}
            </button>
          </span>
        </>
      ) : (
        <form className={s.termForm} onSubmit={submit}>
          {!term && <span className={s.termSource}>{T.noTerm[lang]}</span>}
          <label className={s.termInput}>
            <span className={s.srOnly}>{T.termInput[lang]}</span>
            <input type="number" inputMode="numeric" min={1} max={240} value={value} onChange={(e) => setValue(e.target.value)} />
            <span aria-hidden="true">{T.months[lang]}</span>
          </label>
          <button type="submit" className={s.btnOnDeep} disabled={busy}>
            {T.save[lang]}
          </button>
          {term && (
            <button type="button" className={s.btnOnDeepQuiet} onClick={() => setEditing(false)}>
              {T.cancel[lang]}
            </button>
          )}
        </form>
      )}
      {error && (
        <p className={s.stripError} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
