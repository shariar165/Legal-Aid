"use client";

import { useId, useState, type FormEvent, type ReactNode } from "react";
import { api, type AnalysisResult } from "@/lib/api";
import { DESK, num, type Lang } from "@/lib/desk/i18n";
import { Icon } from "@/components/shared/Icons";
import { citeName, money } from "./util";
import s from "./desk.module.css";

/* Under the hero, three headed groups (spec 29 step 3.5): the worker's loss (projected loss · promise gap), break-even,
   and the contract term with its confirm control; then "details" for the full explanations. A short tag marks a figure
   whose label alone does not say what it is (worker's account, minimum). Every figure and label is the backend's own.
   (The button for what was said sits with the hero's chips, in CaseDesk.) */

interface Props {
  result: AnalysisResult;
  lang: Lang;
  reload: () => Promise<void>;
}

export function MoneyStrip({ result, lang, reload }: Props) {
  const T = DESK.money;
  const four = result.four_ledgers!;
  const cp = four.claim_projection;
  const gap = four.promise_gap;
  const be = four.break_even;
  const [open, setOpen] = useState(false);
  const detailsId = useId();

  return (
    <div className={s.strip}>
      <div className={s.stripRow}>
        <StripGroup id={`${detailsId}-loss`} head={T.loss[lang]} kind="loss">
          <span className={s.fig}>
            <span className={s.figLabel}>{T.claimShort[lang]}</span>
            <b className={s.figNum}>{cp.lines.length > 0 ? money(cp.currency ?? "", cp.projected_total) : "–"}</b>
          </span>
          {gap && (
            <span className={s.fig}>
              <span className={s.figLabel}>{T.gap[lang]}</span>
              <b className={s.figNum}>{money(gap.currency, gap.total)}</b>
              <span className={s.tag} data-tone="quiet">
                {T.account[lang]}
              </span>
            </span>
          )}
        </StripGroup>

        {be && (
          <StripGroup id={`${detailsId}-be`} head={T.breakEvenShort[lang]} kind="be">
            <span className={s.fig}>
              <b className={s.figNum}>{be.months !== null ? T.atLeast(be.months, lang) : T.notWithin[lang]}</b>
              {be.is_minimum && be.months !== null && <span className={s.tag}>{T.minimum[lang]}</span>}
            </span>
          </StripGroup>
        )}

        <StripGroup id={`${detailsId}-term`} head={T.term[lang]} kind="term">
          <TermControl result={result} lang={lang} reload={reload} />
        </StripGroup>

        <button type="button" className={`${s.btnOnDeepQuiet} ${s.detailsBtn}`} aria-expanded={open} aria-controls={detailsId} onClick={() => setOpen((o) => !o)}>
          {open ? T.detailsHide[lang] : T.details[lang]}
          <Icon name="chevronDown" size={16} strokeWidth={2.5} className={s.chev} />
        </button>
      </div>

      <div id={detailsId} className={s.stripDetails} hidden={!open}>
        <div className={s.detail}>
          <span className={s.figLabel}>{T.projected[lang]}</span>
          {cp.lines.length > 0 ? (
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
          ) : (
            <p className={s.stripNote}>{T.noLines[lang]}</p>
          )}
          <p className={s.stripNote}>{cp.label[lang]}</p>
          {cp.term && <p className={s.stripNote}>{cp.term.label[lang]}</p>}
        </div>
        {gap && (
          <div className={s.detail}>
            <span className={s.figLabel}>{T.gap[lang]}</span>
            <p className={s.stripNote}>{gap.label[lang]}</p>
          </div>
        )}
        {be && (
          <div className={s.detail}>
            <span className={s.figLabel}>{T.breakEven[lang]}</span>
            {be.rate && (
              <span className={s.tag} data-tone="rate">
                {T.rate[lang]}: 1 {be.rate.per} = {be.rate.value} {be.rate.currency}
              </span>
            )}
            {be.note && <p className={s.stripNote}>{be.note[lang]}</p>}
            {be.assumption && <p className={s.stripNote}>{be.assumption[lang]}</p>}
          </div>
        )}
      </div>
    </div>
  );
}

function StripGroup({ id, head, kind, children }: { id: string; head: string; kind: string; children: ReactNode }) {
  return (
    <div className={s.stripGroup} data-g={kind} role="group" aria-labelledby={id}>
      <span id={id} className={s.groupHead}>
        {head}
      </span>
      <div className={s.groupBody}>{children}</div>
    </div>
  );
}

/* The term the projection runs over; confirm or correct it like the OCR salary. Stays visible in the compact row;
   where the months came from is in the details. */
function TermControl({ result, lang, reload }: { result: AnalysisResult; lang: Lang; reload: () => Promise<void> }) {
  const T = DESK.money;
  const term = result.four_ledgers!.claim_projection.term ?? null;
  // no term found: a button that opens the input, not an empty input (spec 29 step 3.4)
  const [editing, setEditing] = useState(false);
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
    <span className={s.term}>
      {!editing && term ? (
        <>
          <span className={s.termValue}>
            {num(term.months, lang)} {T.months[lang]}
            {term.source === "user" && <Icon name="check" size={16} strokeWidth={2.75} label={term.label[lang]} />}
          </span>
          {term.source !== "user" && (
            <button type="button" className={s.btnOnDeep} disabled={busy} onClick={() => void send(term.months)} title={term.label[lang]}>
              <Icon name="check" size={16} strokeWidth={2.5} />
              {T.confirm(term.months, lang)}
            </button>
          )}
          <button type="button" className={s.btnOnDeepQuiet} disabled={busy} onClick={() => setEditing(true)}>
            {T.change[lang]}
          </button>
        </>
      ) : !editing ? (
        <button type="button" className={s.btnOnDeepQuiet} onClick={() => setEditing(true)}>
          <Icon name="plus" size={16} strokeWidth={2.5} />
          {T.noTermAdd[lang]}
        </button>
      ) : (
        <form className={s.termForm} onSubmit={submit}>
          {!term && <span className={s.termSource}>{T.noTerm[lang]}</span>}
          <label className={s.termInput}>
            <span className={s.srOnly}>{T.termInput[lang]}</span>
            {/* opened by a click on "Edit term" or "Add", so the caret goes where the reader is already looking */}
            <input type="number" inputMode="numeric" min={1} max={240} value={value} onChange={(e) => setValue(e.target.value)} autoFocus />
            <span aria-hidden="true">{T.months[lang]}</span>
          </label>
          <button type="submit" className={s.btnOnDeep} disabled={busy}>
            {T.save[lang]}
          </button>
          <button type="button" className={s.btnOnDeepQuiet} onClick={() => setEditing(false)}>
            {T.cancel[lang]}
          </button>
        </form>
      )}
      {error && (
        <span className={s.stripError} role="alert">
          {error}
        </span>
      )}
    </span>
  );
}
