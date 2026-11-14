"use client";

import Link from "next/link";
import { useState } from "react";
import type { Destination } from "@/lib/api";
import type { Lang } from "@/lib/citizen/i18n";
import type { PassportKeeper, RehearsalSetup } from "@/lib/rehearsal/api";
import { R } from "@/lib/rehearsal/i18n";
import base from "../citizen/citizen.module.css";
import { useScreenFocus } from "../citizen/useScreenFocus";
import styles from "./rehearsal.module.css";

const T = R.setup;
const KEEPERS: PassportKeeper[] = ["me", "agent", "employer", "unsure"];

interface Props {
  lang: Lang;
  countries: Destination[];
  busy: boolean;
  error: string | null;
  onStart: (setup: RehearsalSetup) => void;
}

export function SetupScreen({ lang, countries, busy, error, onStart }: Props) {
  const heading = useScreenFocus<HTMLHeadingElement>();
  const [country, setCountry] = useState("");
  const [job, setJob] = useState("");
  const [salary, setSalary] = useState("");
  const [cost, setCost] = useState("");
  const [duration, setDuration] = useState("");
  const [paid, setPaid] = useState("");
  const [keeper, setKeeper] = useState<PassportKeeper>("unsure");
  const [hasContract, setHasContract] = useState(false);
  const [throughDalal, setThroughDalal] = useState(true);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    onStart({
      country: country || null,
      job,
      promises: { salary, total_cost: cost, job, duration, passport_keeper: keeper, paid_so_far: paid, extra: [] },
      has_contract: hasContract,
      through_dalal: throughDalal,
      job_id: null,
      language: lang,
    });
  };

  const text = (label: string, value: string, set: (v: string) => void, inputMode?: "text" | "numeric") => (
    <label className={styles.field}>
      <span>{label}</span>
      <input value={value} onChange={(e) => set(e.target.value)} maxLength={120} inputMode={inputMode} />
    </label>
  );

  return (
    <form className={styles.stack} onSubmit={submit}>
      <div>
        <h1 ref={heading} tabIndex={-1} className={base.h1}>
          {T.title[lang]}
        </h1>
        <p className={base.lead}>{T.lead[lang]}</p>
        <p className={styles.note}>{R.roleplay[lang]}</p>
      </div>
      <p className={styles.muted}>{T.optional[lang]}</p>

      <label className={styles.field}>
        <span>{T.country[lang]}</span>
        <select value={country} onChange={(e) => setCountry(e.target.value)}>
          <option value="">{T.countryNone[lang]}</option>
          {countries.map((c) => (
            <option key={c.code} value={c.code ?? ""}>
              {c.name[lang]}
            </option>
          ))}
        </select>
      </label>
      {text(T.job[lang], job, setJob)}
      {text(T.salary[lang], salary, setSalary)}
      {text(T.cost[lang], cost, setCost)}
      {text(T.duration[lang], duration, setDuration)}
      {text(T.paid[lang], paid, setPaid)}

      <fieldset className={styles.choices}>
        <legend>{T.passport[lang]}</legend>
        {KEEPERS.map((k) => (
          <label key={k} className={styles.choice}>
            <input type="radio" name="keeper" checked={keeper === k} onChange={() => setKeeper(k)} />
            <span>{T.passportOpts[k][lang]}</span>
          </label>
        ))}
      </fieldset>

      <label className={styles.check}>
        <input type="checkbox" checked={hasContract} onChange={(e) => setHasContract(e.target.checked)} />
        <span>{T.contract[lang]}</span>
      </label>
      <label className={styles.check}>
        <input type="checkbox" checked={throughDalal} onChange={(e) => setThroughDalal(e.target.checked)} />
        <span>{T.dalal[lang]}</span>
      </label>
      <Link href="/" className={styles.link}>
        {T.photo[lang]}
      </Link>

      {error && (
        <p className={base.hint} role="alert">
          {error}
        </p>
      )}
      <button type="submit" className={styles.primary} disabled={busy}>
        {busy ? T.starting[lang] : T.start[lang]}
      </button>
      <p className={styles.muted}>{T.privacy[lang]}</p>
    </form>
  );
}
