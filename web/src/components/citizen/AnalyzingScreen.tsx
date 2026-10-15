"use client";

import { useState } from "react";
import { STEPS } from "@/lib/citizen/analysis";
import { formatNumber, STRINGS, type Lang } from "@/lib/citizen/i18n";
import type { useAnalysis } from "@/lib/useAnalysis";
import { useScreenFocus } from "./useScreenFocus";
import styles from "./citizen.module.css";

const T = STRINGS.analyzing;

type OcrState = "pending" | "editing" | "confirmed";

interface Props {
  lang: Lang;
  analysis: ReturnType<typeof useAnalysis>;
  onResult: () => void;
  onRetry: () => void;
}

export function AnalyzingScreen({ lang, analysis, onResult, onRetry }: Props) {
  const { stepsDone, ocrCheck, events, status, name, error } = analysis;
  const [ocr, setOcr] = useState<OcrState>("pending");
  const [value, setValue] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const heading = useScreenFocus<HTMLHeadingElement>();

  /** Index of the step currently running; STEPS.length when all are done. */
  const current = STEPS.findIndex((s) => !stepsDone.includes(s.id));
  const done = status === "done";
  const stepIndex = current === -1 ? STEPS.length : current;
  const pct = Math.round(((stepIndex + (done ? 0 : 0.5)) / STEPS.length) * 100);
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
    return (
      <div className={styles.screen}>
        <div className={styles.analyzingBody}>
          <div className={styles.intro}>
            <h1 ref={heading} tabIndex={-1} className={styles.h2}>
              {T.failed[lang]}
            </h1>
            <p className={styles.subtle}>{error === "offline" ? STRINGS.home.offline[lang] : error}</p>
          </div>
          <div className={styles.nextArea}>
            <button type="button" className={styles.btnDark} onClick={onRetry}>
              {T.retry[lang]}
            </button>
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
                  {state === "done" ? "✓" : state === "run" ? "•" : ""}
                </span>
                <span>{state === "wait" ? label.replace(/…$/, "") : label}</span>
              </li>
            );
          })}
        </ol>

        {!done && latest && (
          <p className={styles.liveFeed} aria-live="polite">
            <span className={styles.liveDot} aria-hidden="true" />
            <span className={styles.liveAgent}>{latest.agent}</span> {latest.message}
          </p>
        )}

        {ocrCheck && (
          <section className={styles.ocrCard} data-confirmed={ocr === "confirmed"} aria-labelledby="ocr-title">
            <h2 id="ocr-title" className={styles.ocrTitle}>
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
                    {ocr === "confirmed" ? T.ocrConfirmed[lang] : T.ocrYes[lang]}
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
            {T.seeResult[lang]}
          </button>
        </div>
      </div>
    </div>
  );
}
