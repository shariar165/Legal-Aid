"use client";

import { useEffect, useRef, useState } from "react";
import { STRINGS, type Lang } from "@/lib/citizen/i18n";
import { useSpeech } from "@/lib/citizen/useSpeech";
import { useAnalysis } from "@/lib/useAnalysis";
import { AnalyzingScreen } from "./AnalyzingScreen";
import { HomeScreen } from "./HomeScreen";
import { ResultScreen } from "./ResultScreen";
import styles from "./citizen.module.css";

type Screen = "home" | "analyzing" | "result";

/* Each run gets its own URL, /r/<id> (?s=<sample> for a sample, so it can be run again). replaceState keeps this
   page mounted: Next syncs its router with the native history API (spec 28). */
const showUrl = (path: string) => window.history.replaceState(null, "", path);
const resultPath = (id: string, sampleId?: string) => `/r/${id}${sampleId ? `?s=${encodeURIComponent(sampleId)}` : ""}`;

/** `jobId`: opened from a /r/<id> link, so attach to that job instead of starting at home. */
export function CitizenApp({ jobId }: { jobId?: string }) {
  const [lang, setLang] = useState<Lang>("bn");
  const [screen, setScreen] = useState<Screen>(jobId ? "analyzing" : "home");
  const speech = useSpeech();
  const { stop } = speech;
  const analysis = useAnalysis(jobId);
  // a finished result opened from its link shows at once; a run started here waits for "See result"
  const openedFromLink = useRef(Boolean(jobId));

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  useEffect(() => {
    if (openedFromLink.current && analysis.result && screen === "analyzing") {
      openedFromLink.current = false;
      setScreen("result");
    }
  }, [analysis.result, screen]);

  const go = (next: Screen) => {
    stop();
    setScreen(next);
  };

  const changeLang = (next: Lang) => {
    stop();
    setLang(next);
  };

  const run = (input: Parameters<typeof analysis.start>[0]) => {
    openedFromLink.current = false;
    go("analyzing");
    void analysis.start(input).then((id) => id && showUrl(resultPath(id, "sampleId" in input ? input.sampleId : undefined)));
  };

  const home = () => {
    analysis.reset();
    showUrl("/");
    go("home");
  };

  // the link's job is not this device's, was purged after 7 days, or is gone: say so, offer to run it again
  const gone = Boolean(jobId) && analysis.status === "error" && /^404\b/.test(analysis.error ?? "") && screen === "analyzing";
  if (gone) {
    const sample = new URLSearchParams(window.location.search).get("s");
    return (
      <main className={styles.app}>
        <div className={styles.screen}>
          <div className={styles.analyzingBody}>
            <div className={styles.intro}>
              <h1 className={styles.h2}>{STRINGS.gone.title[lang]}</h1>
              <p className={styles.subtle}>{STRINGS.gone.body[lang]}</p>
            </div>
            <div className={styles.nextArea}>
              {sample ? (
                <button type="button" className={styles.btnDark} onClick={() => run({ sampleId: sample })}>
                  {STRINGS.gone.rerun[lang]}
                </button>
              ) : (
                <button type="button" className={styles.btnDark} onClick={home}>
                  {STRINGS.gone.home[lang]}
                </button>
              )}
            </div>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className={styles.app}>
      {screen === "home" && (
        <HomeScreen
          lang={lang}
          onLangChange={changeLang}
          speech={speech}
          onFile={(file, destination, policy) => {
            if (!file) return;
            run({ file, destination, policy });
          }}
          onSample={(sampleId) => run({ sampleId })}
        />
      )}
      {screen === "analyzing" && <AnalyzingScreen lang={lang} analysis={analysis} onResult={() => go("result")} onRetry={home} />}
      {screen === "result" && analysis.result && (
        <ResultScreen lang={lang} result={analysis.result} speech={speech} reload={analysis.reload} onBack={home} />
      )}
    </main>
  );
}
