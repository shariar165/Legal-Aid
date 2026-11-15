"use client";

import { useState, type FormEvent } from "react";
import { api, type AnalysisResult, type Party, type Promises } from "@/lib/api";
import { DESK, PARTY_NAME, type Lang } from "@/lib/desk/i18n";
import { Icon } from "@/components/shared/Icons";
import s from "./desk.module.css";

/* What the agent told the worker, typed in as structured fields and posted to POST /promises: no model call. The
   backend redacts the note, recomputes the Four Ledgers and holds any new promise-gap risk as "not verified yet". */

type Tri = "yes" | "no" | "";

const numOrNull = (v: string) => (v.trim() === "" || Number.isNaN(Number(v)) ? null : Number(v));

interface Props {
  result: AnalysisResult;
  lang: Lang;
  onClose: () => void;
  onSaved: () => Promise<void>;
}

export function PromiseForm({ result, lang, onClose, onSaved }: Props) {
  const T = DESK.form;
  const p = result.four_ledgers?.promises ?? {};
  const cur = result.wage?.currency ?? "";
  const [f, setF] = useState({
    salary: p.salary_amount?.toString() ?? "",
    salaryCur: p.salary_currency ?? cur,
    noDed: (p.no_deductions == null ? "" : p.no_deductions ? "yes" : "no") as Tri,
    paid: p.recruitment_cost_paid?.toString() ?? "",
    paidCur: p.recruitment_cost_currency ?? "",
    hours: p.hours_per_day?.toString() ?? "",
    ticket: (p.ticket_paid_by ?? "") as Party | "",
    passport: (p.passport_kept_by ?? "") as Party | "",
    months: p.contract_months?.toString() ?? "",
    saidOn: p.said_on ?? "",
    note: p.note ?? "",
    ratePer: p.exchange_rate?.per ?? cur,
    rateValue: p.exchange_rate?.value?.toString() ?? "",
    rateCur: p.exchange_rate?.currency ?? "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((x) => ({ ...x, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const rate = numOrNull(f.rateValue);
    const body: Promises = {
      salary_amount: numOrNull(f.salary),
      salary_currency: f.salary ? f.salaryCur.trim() || null : null,
      no_deductions: f.noDed === "" ? null : f.noDed === "yes",
      recruitment_cost_paid: numOrNull(f.paid),
      recruitment_cost_currency: f.paid ? f.paidCur.trim() || null : null,
      hours_per_day: numOrNull(f.hours),
      ticket_paid_by: f.ticket || null,
      passport_kept_by: f.passport || null,
      contract_months: numOrNull(f.months),
      said_on: f.saidOn || null,
      note: f.note,
      exchange_rate: rate && f.ratePer.trim() && f.rateCur.trim() ? { per: f.ratePer.trim(), value: rate, currency: f.rateCur.trim() } : null,
    };
    setBusy(true);
    setError(null);
    try {
      await api.promises(result.job_id, body);
      await onSaved();
    } catch (x) {
      setError((x as Error).message.replace(/^\d+: /, ""));
      setBusy(false);
    }
  };

  const parties = (k: "ticket" | "passport", legend: string) => (
    <fieldset className={s.field}>
      <legend>{legend}</legend>
      <div className={s.segmented}>
        {(["employer", "agency", "worker", ""] as const).map((v) => (
          <label key={v || "none"}>
            <input type="radio" name={k} value={v} checked={f[k] === v} onChange={set(k)} />
            <span>{v ? PARTY_NAME[v][lang] : T.unknown[lang]}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );

  return (
    <form className={s.promiseForm} onSubmit={submit} aria-labelledby="promise-title" lang={lang}>
      <div className={s.formHead}>
        <h2 id="promise-title" className={s.paneTitle}>
          {T.title[lang]}
        </h2>
        <p className={s.muted}>{T.lead[lang]}</p>
      </div>
      <div className={s.formGrid}>
        <div className={s.field}>
          <label htmlFor="pf-salary">{T.salary[lang]}</label>
          <div className={s.amount}>
            <input id="pf-salary" type="number" inputMode="decimal" min={0} value={f.salary} onChange={set("salary")} />
            <input aria-label={T.currency[lang]} value={f.salaryCur} onChange={set("salaryCur")} maxLength={8} className={s.cur} />
          </div>
        </div>
        <fieldset className={s.field}>
          <legend>{T.noDeductions[lang]}</legend>
          <div className={s.segmented}>
            {(["yes", "no", ""] as const).map((v) => (
              <label key={v || "none"}>
                <input type="radio" name="noDed" value={v} checked={f.noDed === v} onChange={set("noDed")} />
                <span>{v === "yes" ? T.yes[lang] : v === "no" ? T.no[lang] : T.unknown[lang]}</span>
              </label>
            ))}
          </div>
        </fieldset>
        <div className={s.field}>
          <label htmlFor="pf-paid">{T.recruitment[lang]}</label>
          <div className={s.amount}>
            <input id="pf-paid" type="number" inputMode="decimal" min={0} value={f.paid} onChange={set("paid")} />
            <input aria-label={T.currency[lang]} value={f.paidCur} onChange={set("paidCur")} maxLength={8} className={s.cur} placeholder="BDT" />
          </div>
        </div>
        <div className={s.field}>
          <label htmlFor="pf-hours">{T.hours[lang]}</label>
          <input id="pf-hours" type="number" inputMode="numeric" min={1} max={24} value={f.hours} onChange={set("hours")} />
        </div>
        {parties("ticket", T.ticket[lang])}
        {parties("passport", T.passport[lang])}
        <div className={s.field}>
          <label htmlFor="pf-months">{T.months[lang]}</label>
          <input id="pf-months" type="number" inputMode="numeric" min={1} max={240} value={f.months} onChange={set("months")} />
        </div>
        <div className={s.field}>
          <label htmlFor="pf-on">{T.saidOn[lang]}</label>
          <input id="pf-on" type="date" value={f.saidOn} onChange={set("saidOn")} />
        </div>
        <fieldset className={s.field} data-span="2">
          <legend>{T.rate[lang]}</legend>
          <div className={s.rate}>
            <span>{T.rateOne[lang]}</span>
            <input aria-label={lang === "bn" ? "যে মুদ্রার ১ একক" : "Currency of one unit"} value={f.ratePer} onChange={set("ratePer")} maxLength={8} className={s.cur} />
            <span aria-hidden="true">=</span>
            <input aria-label={lang === "bn" ? "হার" : "Rate"} type="number" inputMode="decimal" min={0} step="any" value={f.rateValue} onChange={set("rateValue")} />
            <input aria-label={lang === "bn" ? "যে মুদ্রায় হার" : "Currency of the rate"} value={f.rateCur} onChange={set("rateCur")} maxLength={8} className={s.cur} placeholder="BDT" />
          </div>
          <p className={s.hint}>{T.rateHint[lang]}</p>
        </fieldset>
        <div className={s.field} data-span="2">
          <label htmlFor="pf-note">{T.note[lang]}</label>
          <textarea id="pf-note" rows={3} maxLength={1000} value={f.note} onChange={set("note")} />
          <p className={s.hint}>{T.noteHint[lang]}</p>
        </div>
      </div>
      {error && (
        <p className={s.error} role="alert">
          <Icon name="alert" size={16} />
          {error}
        </p>
      )}
      <div className={s.formActions}>
        <button type="submit" className={s.btnPrimary} disabled={busy}>
          {busy ? T.saving[lang] : T.save[lang]}
        </button>
        <button type="button" className={s.btnSecondary} onClick={onClose}>
          {T.cancel[lang]}
        </button>
      </div>
    </form>
  );
}
