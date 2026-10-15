"use client";

import { useEffect, useState } from "react";
import { STEPS, type OcrCheck } from "@/lib/citizen/analysis";
import { STRINGS, type Lang } from "@/lib/citizen/i18n";
import { useScreenFocus } from "./useScreenFocus";
import styles from "./citizen.module.css";

const T = STRINGS.analyzing;

type OcrState = "pending" | "editing" | "confirmed";

interface Props {
  lang: Lang;
  fileName: string | null;
  ocrCheck: OcrCheck;
  onResult: () => void;
}

export function AnalyzingScreen({ lang, fileName, ocrCheck, onResult }: Props) {
  /** Index of the step currently running; STEPS.length when all are done. */
  const [current, setCurrent] = useState(0);
  const [ocr, setOcr] = useState<OcrState>("pending");
  const [value, setValue] = useState(ocrCheck.value);
  const [draft, setDraft] = useState(ocrCheck.value);
  const heading = useScreenFocus<HTMLHeadingElement>();

  useEffect(() => {
    if (current >= STEPS.length) return;
    const t = setTimeout(() => setCurrent((c) => c + 1), STEPS[current].ms);
    return () => clearTimeout(t);
  }, [current]);

  const done = current >= STEPS.length;
  const pct = Math.round(((current + (done ? 0 : 0.5)) / STEPS.length) * 100);
  // The OCR question can only be asked once the photo has been read.
  const showOcr = current > 0;
  const canContinue = done && ocr === "confirmed";

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    const v = draft.trim();
    if (!v) return;
    setValue(v);
    setOcr("confirmed");
  };

  return (
    <div className={styles.screen}>
      <div className={styles.analyzingBody}>
        <div className={styles.intro}>
          <h1 ref={heading} tabIndex={-1} className={styles.h2}>
            {done ? T.titleDone[lang] : T.title[lang]}
          </h1>
          <span className={styles.subtle}>{done ? T.etaDone[lang] : T.eta[lang]}</span>
          {fileName && <span className={styles.fileName}>{fileName}</span>}
        </div>

        <div
          className={styles.track}
          role="progressbar"
          aria-label={T.progressLabel[lang]}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
        >
          <div className={styles.trackFill} style={{ width: `${pct}%` }} />
        </div>

        <ol className={styles.steps} aria-live="polite">
          {STEPS.map((step, i) => {
            const state = i < current ? "done" : i === current ? "run" : "wait";
            const label = state === "done" ? step.done[lang] : step.running[lang];
            return (
              <li key={step.id} className={styles.step} data-state={state}>
                <span className={styles.stepDot} aria-hidden="true">
                  {state === "done" ? "✓" : state === "run" ? "•" : ""}
                </span>
                <span>{state === "wait" ? label.replace(/…$/, "") : label}</span>
              </li>
            );
          })}
        </ol>

        {showOcr && (
          <section className={styles.ocrCard} data-confirmed={ocr === "confirmed"} aria-labelledby="ocr-title">
            <h2 id="ocr-title" className={styles.ocrTitle}>
              {T.ocrTitle[lang]}
            </h2>
            <p className={styles.ocrBody}>{T.ocrBody[lang]}</p>

            {ocr === "editing" ? (
              <form className={styles.ocrEdit} onSubmit={save}>
                <label htmlFor="ocr-input">{T.ocrInput[lang]}</label>
                <div className={styles.ocrInputRow}>
                  <span aria-hidden="true">{ocrCheck.currency}</span>
                  <input
                    id="ocr-input"
                    className={styles.ocrInput}
                    inputMode="decimal"
                    autoComplete="off"
                    autoFocus
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                  />
                </div>
                <button type="submit" className={styles.btnSolid}>
                  {T.ocrSave[lang]}
                </button>
              </form>
            ) : (
              <>
                <span className={styles.ocrValue}>
                  {ocrCheck.currency} {value}
                </span>
                <div className={styles.twoUp}>
                  <button
                    type="button"
                    className={styles.btnSolid}
                    data-confirmed={ocr === "confirmed"}
                    aria-pressed={ocr === "confirmed"}
                    onClick={() => setOcr("confirmed")}
                  >
                    {ocr === "confirmed" ? T.ocrConfirmed[lang] : T.ocrYes[lang]}
                  </button>
                  <button
                    type="button"
                    className={styles.btnOutline}
                    onClick={() => {
                      setDraft(value);
                      setOcr("editing");
                    }}
                  >
                    {T.ocrFix[lang]}
                  </button>
                </div>
              </>
            )}
          </section>
        )}

        <div className={styles.nextArea}>
          {done && ocr !== "confirmed" && <p className={styles.hint}>{T.ocrNeeded[lang]}</p>}
          <button type="button" className={styles.btnDark} disabled={!canContinue} onClick={onResult}>
            {T.seeResult[lang]}
          </button>
        </div>
      </div>
    </div>
  );
}
