"use client";

import { useEffect, useState } from "react";
import type { Lang } from "@/lib/citizen/i18n";
import { useSpeech } from "@/lib/citizen/useSpeech";
import { useAnalysis } from "@/lib/useAnalysis";
import { AnalyzingScreen } from "./AnalyzingScreen";
import { HomeScreen } from "./HomeScreen";
import { ResultScreen } from "./ResultScreen";
import styles from "./citizen.module.css";

type Screen = "home" | "analyzing" | "result";

export function CitizenApp() {
  const [lang, setLang] = useState<Lang>("bn");
  const [screen, setScreen] = useState<Screen>("home");
  const speech = useSpeech();
  const { stop } = speech;
  const analysis = useAnalysis();

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const go = (next: Screen) => {
    stop();
    setScreen(next);
  };

  const changeLang = (next: Lang) => {
    stop();
    setLang(next);
  };

  return (
    <main className={styles.app}>
      {screen === "home" && (
        <HomeScreen
          lang={lang}
          onLangChange={changeLang}
          speech={speech}
          onFile={(file) => {
            if (!file) return;
            void analysis.start({ file });
            go("analyzing");
          }}
          onSample={(sampleId) => {
            void analysis.start({ sampleId });
            go("analyzing");
          }}
        />
      )}
      {screen === "analyzing" && (
        <AnalyzingScreen
          lang={lang}
          analysis={analysis}
          onResult={() => go("result")}
          onRetry={() => {
            analysis.reset();
            go("home");
          }}
        />
      )}
      {screen === "result" && analysis.result && (
        <ResultScreen
          lang={lang}
          result={analysis.result}
          speech={speech}
          onBack={() => {
            analysis.reset();
            go("home");
          }}
        />
      )}
    </main>
  );
}
