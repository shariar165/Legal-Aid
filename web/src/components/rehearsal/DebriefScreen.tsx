"use client";

import type { Lang } from "@/lib/citizen/i18n";
import { formatNumber } from "@/lib/citizen/i18n";
import type { RubricItem } from "@/lib/rehearsal/api";
import { R } from "@/lib/rehearsal/i18n";
import type { useRehearsal } from "@/lib/rehearsal/useRehearsal";
import base from "../citizen/citizen.module.css";
import { useScreenFocus } from "../citizen/useScreenFocus";
import { CiteChip } from "./BenchScreen";
import styles from "./rehearsal.module.css";

const T = R.debrief;
const MARK: Record<RubricItem["status"], string> = { met: "✓", missed: "✗", not_tested: "–" };

interface Props {
  lang: Lang;
  r: ReturnType<typeof useRehearsal>;
  onRecord: () => void;
  onAgain: () => void;
}

export function DebriefScreen({ lang, r, onRecord, onAgain }: Props) {
  const heading = useScreenFocus<HTMLHeadingElement>();
  const d = r.session?.debrief;
  if (!d) {
    return (
      <div className={styles.stack}>
        <h1 ref={heading} tabIndex={-1} className={base.h1}>
          {T.title[lang]}
        </h1>
        <p className={styles.thinking}>{T.wait[lang]}</p>
        {r.error && (
          <p className={styles.error} role="alert">
            {r.error}
          </p>
        )}
      </div>
    );
  }
  const band = d.score >= 80 ? "good" : d.score >= 50 ? "fair" : "low";
  return (
    <div className={styles.stack}>
      <h1 ref={heading} tabIndex={-1} className={base.h1}>
        {T.title[lang]}
      </h1>

      <section className={styles.meter} data-band={band} aria-label={T.score[lang]}>
        <div className={styles.meterHead}>
          <span>{T.score[lang]}</span>
          <b>{formatNumber(d.score, lang)}%</b>
        </div>
        <div className={styles.meterTrack} role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={d.score}>
          {[0, 1, 2, 3, 4].map((i) => (
            <span key={i} className={styles.meterCell} data-on={d.score >= (i + 1) * 20 ? "1" : "0"} />
          ))}
        </div>
        <p className={styles.muted}>{T.scoreNote[lang]}</p>
      </section>

      <ul className={styles.rubric}>
        {d.items.map((i) => (
          <li key={i.id} data-status={i.status}>
            <span className={styles.mark} aria-hidden="true">
              {MARK[i.status]}
            </span>
            <span>{i.label[lang]}</span>
            <span className={styles.status}>{i.status === "met" ? T.met[lang] : i.status === "missed" ? T.missed[lang] : T.notTested[lang]}</span>
          </li>
        ))}
      </ul>

      <section className={styles.chief}>
        <h2>{T.chief[lang]}</h2>
        <p>{d.note}</p>
        {d.citations.map((c) => (
          <CiteChip key={c} id={c} lang={lang} />
        ))}
      </section>

      <section>
        <h2 className={styles.h2}>{T.checklist[lang]}</h2>
        <ol className={styles.checklist}>
          {d.checklist.map((q, i) => (
            <li key={i}>{q[lang]}</li>
          ))}
        </ol>
      </section>

      <button type="button" className={styles.primary} onClick={onRecord} disabled={!r.session?.record}>
        {T.record[lang]}
      </button>
      <button type="button" className={styles.ghost} onClick={onAgain}>
        {T.again[lang]}
      </button>
    </div>
  );
}
