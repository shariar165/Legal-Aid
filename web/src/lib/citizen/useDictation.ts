"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/*
 * Voice typing with the Web Speech API, privacy first (docs/specs/2026-11-14-19-rehearsal-council.md, "Privacy").
 * In Chrome, plain SpeechRecognition sends the audio to Google's servers. So:
 *   - "local": the browser can recognise the language on the device (`processLocally`), so the mic works at once;
 *   - "cloud": only server recognition exists, so the mic stays off until the worker accepts a plain notice;
 *   - "none": no speech recognition at all; typing only.
 * The transcript is only put in the text box: it reaches the backend like typed text, through the PII Shield.
 */

type Availability = "available" | "downloadable" | "downloading" | "unavailable";

interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  processLocally?: boolean;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  start(): void;
  stop(): void;
}

interface RecognitionCtor {
  new (): Recognition;
  available?: (opts: { langs: string[]; processLocally: boolean }) => Promise<Availability>;
}

export type DictationMode = "checking" | "local" | "cloud" | "none";

function ctor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function useDictation(lang: string, onText: (text: string) => void) {
  const [mode, setMode] = useState<DictationMode>("checking");
  const [consented, setConsented] = useState(false);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<Recognition | null>(null);
  const textCb = useRef(onText);

  useEffect(() => {
    textCb.current = onText;
  }, [onText]);

  useEffect(() => {
    let alive = true;
    const C = ctor();
    const decide = async (): Promise<DictationMode> => {
      if (!C) return "none";
      try {
        if (C.available && (await C.available({ langs: [lang], processLocally: true })) === "available") return "local";
      } catch {
        /* an older browser without on-device recognition */
      }
      return "cloud";
    };
    void decide().then((m) => alive && setMode(m));
    return () => {
      alive = false;
    };
  }, [lang]);

  const stop = useCallback(() => {
    rec.current?.stop();
    rec.current = null;
    setListening(false);
  }, []);

  const start = useCallback(() => {
    const C = ctor();
    if (!C || mode === "none" || (mode === "cloud" && !consented)) return;
    stop();
    const r = new C();
    r.lang = lang;
    r.interimResults = false;
    r.continuous = false;
    if (mode === "local") r.processLocally = true;
    r.onresult = (e) => {
      const text = Array.from(e.results)
        .map((res) => res[0]?.transcript ?? "")
        .join(" ")
        .trim();
      if (text) textCb.current(text);
    };
    r.onerror = (e) => setError(e.error);
    r.onend = () => setListening(false);
    rec.current = r;
    setError(null);
    try {
      r.start();
      setListening(true);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [lang, mode, consented, stop]);

  useEffect(() => stop, [stop]);

  return { mode, consented, consent: () => setConsented(true), listening, error, start, stop };
}
