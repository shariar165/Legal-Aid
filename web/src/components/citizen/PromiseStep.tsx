"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, type AnalysisResult, type Party, type Promises } from "@/lib/api";
import { STRINGS, type Lang } from "@/lib/citizen/i18n";
import { TERM_NAME } from "@/lib/desk/i18n";
import { Icon } from "@/components/shared/Icons";
import styles from "./citizen.module.css";

/* "What did the agent tell you?" (spec 20, phase 2): four questions, typed or tapped, posted to POST /promises with
   no model call. The answers are merged into the promises already saved, so fields the step does not ask about
   (hours, exchange rate, the date) are kept. The comparison is the backend's: this shows each said_vs_paper mismatch
   as it comes back, and a promise-gap risk stays "not verified yet" (Citizen has no Verify: that makes model calls). */

const T = STRINGS.promise;

type Tri = "yes" | "no" | "";
type Who = Party | "";

const PARTIES: Party[] = ["employer", "agency", "worker"];

interface Props {
  lang: Lang;
  result: AnalysisResult;
  reload: () => Promise<void>;
}

export function PromiseStep({ lang, result, reload }: Props) {
  const four = result.four_ledgers;
  const saved = four?.promises ?? null;
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const first = useRef<HTMLInputElement>(null);
  const results = useRef<HTMLHeadingElement>(null);
  const [justSaved, setJustSaved] = useState(false);

  const cur = result.wage?.currency ?? "";
  const initial = () => ({
    salary: saved?.salary_amount?.toString() ?? "",
    salaryCur: saved?.salary_currency ?? cur,
    noDed: (saved?.no_deductions == null ? "" : saved.no_deductions ? "yes" : "no") as Tri,
    ticket: (saved?.ticket_paid_by ?? "") as Who,
    passport: (saved?.passport_kept_by ?? "") as Who,
  });
  const [f, setF] = useState(initial);

  useEffect(() => {
    if (open) first.current?.focus();
  }, [open]);
  useEffect(() => {
    if (justSaved && !open) results.current?.focus();
  }, [justSaved, open]);

  if (!four) return null; // Four Ledgers is off: the step is not offered

  const mismatches = four.rows.flatMap((row) => row.mismatches.filter((m) => m.type === "said_vs_paper").map((m) => ({ term: row.term, m })));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const amount = f.salary.trim() === "" || Number.isNaN(Number(f.salary)) ? null : Number(f.salary);
    const body: Promises = {
      ...(saved ?? {}),
      salary_amount: amount,
      salary_currency: amount != null ? f.salaryCur.trim().toUpperCase() || null : null,
      no_deductions: f.noDed === "" ? null : f.noDed === "yes",
      ticket_paid_by: f.ticket || null,
      passport_kept_by: f.passport || null,
    };
    setBusy(true);
    setError(false);
    try {
      await api.promises(result.job_id, body);
      await reload();
      setOpen(false);
      setJustSaved(true);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  const choice = <K extends "noDed" | "ticket" | "passport">(k: K, legend: string, options: { v: (typeof f)[K]; label: string }[]) => (
    <fieldset className={styles.question}>
      <legend className={styles.questionLabel}>{legend}</legend>
      <div className={styles.choices} data-n={options.length}>
        {options.map((o) => (
          <label key={o.v || "unsure"} className={styles.choice}>
            <input type="radio" name={`ps-${k}`} value={o.v} checked={f[k] === o.v} onChange={() => setF((x) => ({ ...x, [k]: o.v }))} />
            <span>{o.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
  const parties: { v: Who; label: string }[] = [...PARTIES.map((v) => ({ v, label: T[v === "worker" ? "me" : v][lang] as string })), { v: "", label: T.unsure[lang] }];

  return (
    <section className={styles.card} data-kind="promise" aria-labelledby="title-promise">
      <div className={styles.cardHead}>
        <h2 id="title-promise" className={styles.cardTitle}>
          {T.title[lang]}
        </h2>
      </div>

      {open ? (
        <form className={styles.cardBody} onSubmit={submit}>
          <div className={styles.question}>
            <label htmlFor="ps-salary" className={styles.questionLabel}>
              {T.salary[lang]}
            </label>
            <div className={styles.amountRow}>
              <input
                ref={first}
                id="ps-salary"
                className={styles.bigInput}
                type="number"
                inputMode="decimal"
                min={0}
                aria-label={`${T.salary[lang]} ${T.amount[lang]}`}
                value={f.salary}
                onChange={(e) => setF((x) => ({ ...x, salary: e.target.value }))}
              />
              <input
                className={styles.curInput}
                aria-label={T.currency[lang]}
                maxLength={8}
                value={f.salaryCur}
                onChange={(e) => setF((x) => ({ ...x, salaryCur: e.target.value }))}
              />
            </div>
          </div>
          {/* "yes" = told nothing would be taken (no_deductions true); "no" = told some would be */}
          {choice("noDed", T.noDeductions[lang], [
            { v: "yes", label: T.dedNone[lang] },
            { v: "no", label: T.dedSome[lang] },
            { v: "", label: T.unsure[lang] },
          ])}
          {choice("ticket", T.ticket[lang], parties)}
          {choice("passport", T.passport[lang], parties)}
          <p className={styles.formNote}>{T.kept[lang]}</p>
          {error && (
            <p className={styles.formError} role="alert">
              <Icon name="alert" size={18} strokeWidth={2.25} />
              {T.failed[lang]}
            </p>
          )}
          <div className={styles.twoUp}>
            <button type="submit" className={styles.btnSolid} disabled={busy}>
              {busy ? T.saving[lang] : T.save[lang]}
            </button>
            <button
              type="button"
              className={styles.btnOutline}
              onClick={() => {
                setF(initial());
                setError(false);
                setOpen(false);
              }}
            >
              {T.cancel[lang]}
            </button>
          </div>
        </form>
      ) : (
        <div className={styles.cardBody}>
          {saved ? (
            <>
              <h3 ref={results} tabIndex={-1} className={styles.subTitle}>
                {T.resultsTitle[lang]}
              </h3>
              {mismatches.length === 0 ? (
                <p className={styles.promiseLead}>{T.none[lang]}</p>
              ) : (
                <ul className={styles.gapList}>
                  {mismatches.map(({ term, m }) => {
                    const st = m.risk_status ?? null;
                    return (
                      <li key={term} className={styles.gap} data-status={st ?? "none"}>
                        <span className={styles.gapTerm}>{TERM_NAME[term]?.[lang] ?? term}</span>
                        <span className={styles.gapDetail}>{m.detail[lang]}</span>
                        {m.title && <span className={styles.gapLaw}>{m.title[lang]}</span>}
                        {st && (
                          <span className={styles.gapStatus} data-status={st}>
                            <Icon name={st === "verified" ? "check" : "alert"} size={16} strokeWidth={2.5} />
                            {T.status[st][lang]}
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
              {mismatches.some(({ m }) => m.risk_status === "not_verified_yet") && <p className={styles.gapNote}>{T.pendingNote[lang]}</p>}
            </>
          ) : (
            <p className={styles.promiseLead}>{T.lead[lang]}</p>
          )}
          <button
            type="button"
            className={styles.btnOutline}
            onClick={() => {
              setF(initial());
              setJustSaved(false);
              setOpen(true);
            }}
          >
            {saved ? T.edit[lang] : T.open[lang]}
          </button>
        </div>
      )}
    </section>
  );
}
