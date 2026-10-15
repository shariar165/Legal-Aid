"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const TICK_MS = 200;
/** Rough speaking time per character, used to drive the progress bar. */
const MS_PER_CHAR = 75;

/**
 * Read text aloud with the browser's speech synthesis, exposing which item is
 * playing and an estimated progress percentage. When no voice is available
 * for the language, progress still runs so the UI behaves the same.
 */
export function useSpeech() {
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [pct, setPct] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const session = useRef(0);

  const stop = useCallback(() => {
    session.current++;
    clearInterval(timer.current);
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    setPlayingId(null);
    setPct(0);
  }, []);

  const toggle = useCallback(
    (id: string, text: string, lang: string) => {
      if (playingId === id) {
        stop();
        return;
      }
      stop();
      const mine = session.current;
      const estimate = Math.max(3000, text.length * MS_PER_CHAR);
      const start = performance.now();
      let voiced = false;
      const finish = () => {
        if (session.current !== mine) return;
        stop();
      };

      if ("speechSynthesis" in window) {
        const u = new SpeechSynthesisUtterance(text);
        u.lang = lang;
        u.rate = 0.9;
        u.onstart = () => {
          voiced = true;
        };
        u.onend = () => {
          // An utterance that ends almost immediately had no usable voice:
          // keep the simulated progress running instead of cutting it off.
          if (voiced && performance.now() - start > estimate * 0.25) finish();
        };
        window.speechSynthesis.speak(u);
      }

      setPlayingId(id);
      setPct(0);
      timer.current = setInterval(() => {
        const p = ((performance.now() - start) / estimate) * 100;
        if (p >= 100 && !(voiced && window.speechSynthesis?.speaking)) finish();
        else setPct(Math.min(p, 99));
      }, TICK_MS);
    },
    [playingId, stop],
  );

  useEffect(() => stop, [stop]);

  return { playingId, pct, toggle, stop };
}
