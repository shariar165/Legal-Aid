"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const TICK_MS = 200;
/** Rough speaking time per character, used to move the bar inside the chunk being spoken. */
const MS_PER_CHAR = 75;
/** Chrome stops a single utterance after about 15 s, so long text is spoken in sentence-sized chunks. */
const CHUNK_CHARS = 200;

/** Sentence-sized pieces (Bangla dari, . ? ! and line breaks), each at most CHUNK_CHARS, split at spaces if longer. */
export function chunkText(text: string): string[] {
  const sentences = text.split(/(?<=[।.!?])\s+|\n+/).map((s) => s.trim()).filter(Boolean);
  const chunks: string[] = [];
  for (const s of sentences) {
    let rest = s;
    while (rest.length > CHUNK_CHARS) {
      const cut = rest.lastIndexOf(" ", CHUNK_CHARS);
      const at = cut > CHUNK_CHARS / 2 ? cut : CHUNK_CHARS;
      chunks.push(rest.slice(0, at).trim());
      rest = rest.slice(at).trim();
    }
    const last = chunks[chunks.length - 1];
    if (last && last.length + rest.length + 1 <= CHUNK_CHARS) chunks[chunks.length - 1] = `${last} ${rest}`;
    else if (rest) chunks.push(rest);
  }
  return chunks;
}

/** A voice for `lang` ("bn-BD"): the exact locale first, then any voice of that language ("bn-IN" for Bangla). */
function pickVoice(voices: SpeechSynthesisVoice[], lang: string): SpeechSynthesisVoice | null {
  const norm = (l: string) => l.replace("_", "-").toLowerCase();
  const want = norm(lang);
  const base = want.split("-")[0];
  return voices.find((v) => norm(v.lang) === want) ?? voices.find((v) => norm(v.lang).split("-")[0] === base) ?? null;
}

const hasSynth = () => typeof window !== "undefined" && "speechSynthesis" in window;

/**
 * Read text aloud with the browser's speech synthesis (spec 28): a real voice for the language, sentence chunks, and
 * progress by chunk. When the device has no voice for the language, nothing pretends to play: `noVoice` names the
 * item that was asked for, so the UI can say so.
 */
export function useSpeech() {
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [pct, setPct] = useState(0);
  const [noVoice, setNoVoice] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const session = useRef(0);
  const voices = useRef<SpeechSynthesisVoice[]>([]);

  useEffect(() => {
    if (!hasSynth()) return;
    const load = () => {
      voices.current = window.speechSynthesis.getVoices();
    };
    load();
    window.speechSynthesis.addEventListener("voiceschanged", load);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", load);
  }, []);

  const stop = useCallback(() => {
    session.current++;
    clearInterval(timer.current);
    if (hasSynth()) window.speechSynthesis.cancel();
    setPlayingId(null);
    setPct(0);
    setNoVoice(null);
  }, []);

  const toggle = useCallback(
    (id: string, text: string, lang: string) => {
      if (playingId === id) {
        stop();
        return;
      }
      stop();
      const mine = session.current;
      const live = () => session.current === mine;
      const fail = () => {
        if (!live()) return;
        stop();
        setNoVoice(id);
      };

      if (!hasSynth()) return fail();
      if (!voices.current.length) voices.current = window.speechSynthesis.getVoices();
      const voice = pickVoice(voices.current, lang);
      // An empty list can mean "not loaded yet" (some Android builds): try the language anyway and let onerror decide.
      // A loaded list without the language is a firm no.
      if (!voice && voices.current.length) return fail();

      const chunks = chunkText(text);
      if (!chunks.length) return;
      const total = chunks.reduce((n, c) => n + c.length, 0);
      let index = 0;
      let doneChars = 0;
      let chunkStart = performance.now();
      let started = false;

      const speak = () => {
        const u = new SpeechSynthesisUtterance(chunks[index]);
        u.lang = voice?.lang ?? lang;
        if (voice) u.voice = voice;
        u.rate = 0.9;
        u.onstart = () => {
          started = true;
          chunkStart = performance.now();
        };
        u.onend = () => {
          if (!live()) return;
          doneChars += chunks[index].length;
          index++;
          if (index < chunks.length) speak();
          else stop();
        };
        u.onerror = (e) => {
          if (!live() || e.error === "interrupted" || e.error === "canceled") return;
          if (!started) fail(); // nothing was ever spoken: no usable voice
          else stop();
        };
        window.speechSynthesis.speak(u);
      };

      setPlayingId(id);
      setPct(0);
      speak(); // the first speak() stays inside the click, which iOS Safari requires
      timer.current = setInterval(() => {
        if (!live()) return;
        const inChunk = started ? Math.min(0.95, (performance.now() - chunkStart) / Math.max(1500, chunks[index]?.length * MS_PER_CHAR)) : 0;
        setPct(Math.min(99, ((doneChars + inChunk * (chunks[index]?.length ?? 0)) / total) * 100));
      }, TICK_MS);
    },
    [playingId, stop],
  );

  // a hidden page (locked phone, other tab) stops speaking rather than talking on unseen
  useEffect(() => {
    const onHide = () => document.visibilityState === "hidden" && stop();
    document.addEventListener("visibilitychange", onHide);
    return () => document.removeEventListener("visibilitychange", onHide);
  }, [stop]);

  useEffect(() => stop, [stop]);

  return { playingId, pct, toggle, stop, noVoice };
}
