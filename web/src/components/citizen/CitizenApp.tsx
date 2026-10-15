"use client";

import { useEffect, useState } from "react";
import { SAMPLE_OCR_CHECK, SAMPLE_RESULT } from "@/lib/citizen/analysis";
import type { Lang } from "@/lib/citizen/i18n";
import { useSpeech } from "@/lib/citizen/useSpeech";
import { AnalyzingScreen } from "./AnalyzingScreen";
import { HomeScreen } from "./HomeScreen";
import { ResultScreen } from "./ResultScreen";
import styles from "./citizen.module.css";

type Screen = "home" | "analyzing" | "result";

export function CitizenApp() {
  const [lang, setLang] = useState<Lang>("bn");
  const [screen, setScreen] = useState<Screen>("home");
  const [fileName, setFileName] = useState<string | null>(null);
  const speech = useSpeech();
  const { stop } = speech;

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
            setFileName(file?.name ?? null);
            go("analyzing");
          }}
        />
      )}
      {screen === "analyzing" && (
        <AnalyzingScreen lang={lang} fileName={fileName} ocrCheck={SAMPLE_OCR_CHECK} onResult={() => go("result")} />
      )}
      {screen === "result" && (
        <ResultScreen lang={lang} result={SAMPLE_RESULT} speech={speech} onBack={() => go("home")} />
      )}
    </main>
  );
}
