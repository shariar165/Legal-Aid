"use client";

import { useEffect, useState } from "react";
import type { L10n, Lang } from "@/lib/citizen/i18n";
import { rehearsalApi, type PromiseContacts, type RecordPrint, type RehearsalSession } from "@/lib/rehearsal/api";
import { R } from "@/lib/rehearsal/i18n";
import base from "../citizen/citizen.module.css";
import { useScreenFocus } from "../citizen/useScreenFocus";
import styles from "./rehearsal.module.css";

const T = R.record;
const FIELDS: (keyof PromiseContacts)[] = ["agent_name", "agent_phone", "agency_name", "place", "notes"];
const LABEL: Record<keyof PromiseContacts, L10n> = { agent_name: T.agentName, agent_phone: T.agentPhone, agency_name: T.agency, place: T.place, notes: T.notes };
const EMPTY: PromiseContacts = { agent_name: "", agent_phone: "", agency_name: "", place: "", notes: "" };

interface Props {
  lang: Lang;
  session: RehearsalSession;
  onSaved: (s: RehearsalSession) => void;
  onBack: () => void;
}

/**
 * The Promise Record. The worker's own values (names, phones, what was promised) come back from /record/print, which
 * puts them back on this machine; the session itself only ever holds placeholders. Print gives the PDF.
 */
export function PromiseRecordScreen({ lang, session, onSaved, onBack }: Props) {
  const heading = useScreenFocus<HTMLHeadingElement>();
  const [form, setForm] = useState<PromiseContacts>(EMPTY);
  const [real, setReal] = useState<RecordPrint | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const record = session.record;

  useEffect(() => {
    let alive = true;
    void rehearsalApi
      .print(session.id)
      .then((p) => {
        if (!alive) return;
        setReal(p);
        setForm(p.contacts);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [session.id]);

  if (!record) return null;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      onSaved(await rehearsalApi.saveContacts(session.id, form));
      setReal(await rehearsalApi.print(session.id));
      setSaved(true);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const promisedText = (field: string, i: number) => real?.rows[i]?.field === field ? real.rows[i].promised : record.rows[i].promised;

  return (
    <div className={styles.stack}>
      <button type="button" className={`${styles.ghost} ${styles.noPrint}`} onClick={onBack}>
        {R.back[lang]}
      </button>

      <article className={styles.printArea}>
        <h1 ref={heading} tabIndex={-1} className={base.h1}>
          {T.title[lang]}
        </h1>
        <p className={styles.muted}>
          {T.date[lang]}: <b>{record.created_at}</b>
          {real?.job && (
            <>
              {" · "}
              {real.job}
            </>
          )}
        </p>
        <p className={base.lead}>{T.lead[lang]}</p>

        <form className={`${styles.card} ${styles.stack}`} onSubmit={save}>
          <h2 className={styles.h2}>{T.who[lang]}</h2>
          {FIELDS.map((f) => (
            <label key={f} className={styles.field}>
              <span>{LABEL[f][lang]}</span>
              {f === "notes" ? (
                <textarea value={form[f]} maxLength={1000} rows={3} onChange={(e) => setForm({ ...form, [f]: e.target.value })} />
              ) : (
                <input value={form[f]} maxLength={f === "agent_phone" ? 40 : 160} inputMode={f === "agent_phone" ? "tel" : "text"} onChange={(e) => setForm({ ...form, [f]: e.target.value })} />
              )}
            </label>
          ))}
          <p className={`${styles.muted} ${styles.noPrint}`}>{T.privacy[lang]}</p>
          <button type="submit" className={`${styles.action} ${styles.noPrint}`}>
            {saved ? `✓ ${T.saved[lang]}` : T.save[lang]}
          </button>
          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}
        </form>

        <section className={styles.stack}>
          {record.rows.map((row, i) => (
            <div key={`${row.field}-${i}`} className={styles.card}>
              <h3 className={styles.h3}>{row.label[lang]}</h3>
              <p>
                <span className={styles.muted}>{T.promised[lang]}: </span>
                <b>{promisedText(row.field, i)}</b>
              </p>
              {row.checks.length > 0 && <p className={styles.muted}>{T.law[lang]}:</p>}
              {row.checks.map((v) => (
                <blockquote key={v.claim.id} className={styles.law}>
                  <p>{v.claim.proposition}</p>
                  {v.claim.quote && <p className={styles.quote}>“{v.claim.quote}”</p>}
                  {v.section && (
                    <a href={v.section.url} target="_blank" rel="noreferrer" className={styles.cite}>
                      ✔ {lang === "bn" ? `${v.section.act}, ধারা ${v.section.section}` : `${v.section.act_en}, s.${v.section.section}`}
                    </a>
                  )}
                </blockquote>
              ))}
              {row.note && <p className={styles.note}>{row.note[lang]}</p>}
              {row.unverified.length > 0 && <p className={styles.muted}>{T.notShown[lang]}</p>}
            </div>
          ))}
        </section>

        <section className={styles.stack}>
          <h2 className={styles.h2}>{T.paths[lang]}</h2>
          {record.paths.map((p) => (
            <div key={p.id} className={styles.card}>
              <h3 className={styles.h3}>{p.label[lang]}</h3>
              <p>{p.check.claim.proposition}</p>
              {p.check.section && (
                <a href={p.check.section.url} target="_blank" rel="noreferrer" className={styles.cite}>
                  ✔ {lang === "bn" ? `${p.check.section.act}, ধারা ${p.check.section.section}` : `${p.check.section.act_en}, s.${p.check.section.section}`}
                </a>
              )}
            </div>
          ))}
        </section>

        <section className={styles.signatures}>
          <p>{T.signAgent[lang]}: ______________________</p>
          <p>{T.signWitness[lang]}: ______________________</p>
          <p className={styles.muted}>{R.disclaimer[lang]}</p>
        </section>
      </article>

      <div className={`${styles.actions} ${styles.noPrint}`}>
        <a className={styles.action} href={rehearsalApi.docxUrl(session.id)}>
          {T.docx[lang]}
        </a>
        <button type="button" className={styles.action} onClick={() => window.print()}>
          {T.pdf[lang]}
        </button>
      </div>
    </div>
  );
}
