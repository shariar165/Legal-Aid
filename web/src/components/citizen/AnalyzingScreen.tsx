"use client";

import { useRef, useState } from "react";
import { STEPS } from "@/lib/citizen/analysis";
import { formatNumber, STRINGS, type Lang } from "@/lib/citizen/i18n";
import type { useAnalysis } from "@/lib/useAnalysis";
import { ERROR_UI, ERRORS, errorDetail, type ErrorAction } from "@/lib/errors";
import { Icon } from "@/components/shared/Icons";
import { useScreenFocus } from "./useScreenFocus";
import styles from "./citizen.module.css";

const T = STRINGS.analyzing;

type OcrState = "pending" | "editing" | "confirmed";

interface Props {
  lang: Lang;
  analysis: ReturnType<typeof useAnalysis>;
  onResult: () => void;
  onRetry: () => void;
  /** a new photo taken from the error screen starts a new run (spec 29 step 1.4) */
  onPhoto: (file: File) => void;
  /** back to the samples on the home screen */
  onSample: () => void;
}

export function AnalyzingScreen({ lang, analysis, onResult, onRetry, onPhoto, onSample }: Props) {
  const { stepsDone, ocrCheck, events, status, name, error, deviceOcr } = analysis;
  const [ocr, setOcr] = useState<OcrState>("pending");
  const [value, setValue] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const heading = useScreenFocus<HTMLHeadingElement>();
  const photoInput = useRef<HTMLInputElement>(null);

  /** Index of the step currently running; STEPS.length when all are done. */
  const current = STEPS.findIndex((s) => !stepsDone.includes(s.id));
  const done = status === "done";
  const stepIndex = current === -1 ? STEPS.length : current;
  // while the photo is read on the device, the bar fills the first step with that progress (spec 28)
  const pct = Math.round(((stepIndex + (done ? 0 : deviceOcr !== null ? deviceOcr * 0.9 : 0.5)) / STEPS.length) * 100);
  const shown = value ?? ocrCheck?.value ?? "";
  const canContinue = done && (!ocrCheck || ocr === "confirmed");

  // the latest progress line from the agents working on the current step
  const runningAgents = STEPS[Math.min(stepIndex, STEPS.length - 1)].agents;
  const latest = [...events]
    .reverse()
    .find((e) => (e.type === "agent_done" || e.type === "risk_found" || e.type === "agent_start") && e.agent && runningAgents.some((a) => e.agent!.startsWith(a)));

  const send = async (v: string) => {
    setSending(true);
    try {
      await analysis.confirm(v);
      setValue(v);
      setOcr("confirmed");
    } finally {
      setSending(false);
    }
  };

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    const v = draft.trim();
    if (v) void send(v);
  };

  if (status === "error") {
    const code = analysis.errorCode ?? (error === "offline" ? "offline" : "failed");
    const copy = ERRORS[code];
    const detail = errorDetail(error, code);
    const act = (a: ErrorAction, primary: boolean) => {
      const cls = primary ? styles.btnDark : styles.btnSolid;
      if (a === "photo")
        return (
          <button key={a} type="button" className={cls} onClick={() => photoInput.current?.click()}>
            <span className={styles.withIcon}>
              <Icon name="camera" size={20} strokeWidth={2} />
              {ERROR_UI.photo[lang]}
            </span>
          </button>
        );
      return (
        <button key={a} type="button" className={cls} onClick={a === "sample" ? onSample : onRetry}>
          {ERROR_UI[a][lang]}
        </button>
      );
    };
    return (
      <div className={styles.screen}>
        <div className={styles.analyzingBody}>
          <div className={styles.intro}>
            <h1 ref={heading} tabIndex={-1} className={styles.h2}>
              {copy.title[lang]}
            </h1>
            <p className={styles.subtle}>{copy.body[lang]}</p>
            {detail && (
              <details className={styles.errorDetails}>
                <summary>{ERROR_UI.details[lang]}</summary>
                <p lang="en">{detail}</p>
              </details>
            )}
          </div>
          <div className={styles.nextArea}>
            {copy.actions.map((a, i) => act(a, i === 0))}
            {copy.actions.includes("photo") && (
              <input
                ref={photoInput}
                type="file"
                accept="image/*"
                capture="environment"
                className={styles.visuallyHidden}
                tabIndex={-1}
                aria-hidden="true"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  e.target.value = "";
                  if (f) onPhoto(f);
                }}
              />
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.screen}>
      <div className={styles.analyzingBody}>
        <div className={styles.intro}>
          <h1 ref={heading} tabIndex={-1} className={styles.h2}>
            {done ? T.titleDone[lang] : T.title[lang]}
          </h1>
          <span className={styles.subtle}>{done ? T.etaDone[lang] : T.eta[lang]}</span>
          {name && <span className={styles.fileName}>{name}</span>}
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
            const state = stepsDone.includes(step.id) ? "done" : i === stepIndex ? "run" : "wait";
            const label = state === "done" ? step.done[lang] : step.running[lang];
            return (
              <li key={step.id} className={styles.step} data-state={state}>
                <span className={styles.stepDot} aria-hidden="true">
                  {state === "done" ? <Icon name="check" size={16} strokeWidth={3} /> : state === "run" ? <span className={styles.runDot} /> : null}
                </span>
                <span>{state === "wait" ? label.replace(/…$/, "") : label}</span>
              </li>
            );
          })}
        </ol>

        {deviceOcr !== null && (
          <p className={styles.liveFeed} aria-live="polite">
            <span className={styles.liveDot} aria-hidden="true" />
            <span className={styles.liveAgent}>
              {T.deviceOcr[lang]} · {Math.round(deviceOcr * 100)}%
            </span>{" "}
            {T.deviceOcrNote[lang]}
          </p>
        )}

        {!done && latest && (
          <p className={styles.liveFeed} aria-live="polite">
            <span className={styles.liveDot} aria-hidden="true" />
            <span className={styles.liveAgent}>{latest.agent}</span> {latest.message}
          </p>
        )}

        {ocrCheck && (
          <section className={styles.ocrCard} data-confirmed={ocr === "confirmed"} aria-labelledby="ocr-title">
            <h2 id="ocr-title" className={styles.ocrTitle}>
              <Icon name="alert" size={20} strokeWidth={2.25} />
              {T.ocrTitle[lang]}
            </h2>
            <p className={styles.ocrBody}>
              {T.ocrBody[lang]}{" "}
              <span className={styles.subtle}>
                ({T.ocrLowConf[lang]}: {formatNumber(Math.round(ocrCheck.confidence * 100), lang)}%)
              </span>
            </p>

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
                <button type="submit" className={styles.btnSolid} disabled={sending}>
                  {T.ocrSave[lang]}
                </button>
              </form>
            ) : (
              <>
                <span className={styles.ocrValue}>
                  {ocrCheck.currency} {shown}
                </span>
                <div className={styles.twoUp}>
                  <button
                    type="button"
                    className={styles.btnSolid}
                    data-confirmed={ocr === "confirmed"}
                    aria-pressed={ocr === "confirmed"}
                    disabled={sending || ocr === "confirmed"}
                    onClick={() => void send(shown)}
                  >
                    {ocr === "confirmed" ? (
                      <span className={styles.withIcon}>
                        <Icon name="check" size={18} strokeWidth={2.5} />
                        {T.ocrConfirmed[lang]}
                      </span>
                    ) : (
                      T.ocrYes[lang]
                    )}
                  </button>
                  <button
                    type="button"
                    className={styles.btnOutline}
                    disabled={sending || ocr === "confirmed"}
                    onClick={() => {
                      setDraft(shown);
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
          {ocrCheck && ocr !== "confirmed" && <p className={styles.hint}>{T.ocrNeeded[lang]}</p>}
          <button type="button" className={styles.btnDark} disabled={!canContinue} onClick={onResult}>
            <span className={styles.withIcon}>
              {T.seeResult[lang]}
              <Icon name="arrowRight" size={20} strokeWidth={2.25} />
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
