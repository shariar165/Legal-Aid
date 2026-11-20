"use client";

import { STRINGS, type Lang } from "@/lib/citizen/i18n";
import styles from "./citizen.module.css";

/** Desktop browsers other than Edge: Chrome and Firefox on a computer have no Bangla voice, Edge has natural ones. */
function edgeWouldHelp(lang: Lang): boolean {
  if (lang !== "bn" || typeof navigator === "undefined") return false;
  const ua = navigator.userAgent;
  return !/Android|iPhone|iPad|Mobile/i.test(ua) && !/\bEdg\//.test(ua);
}

/** The honest line shown when read-aloud has no voice for the language (spec 28). Only rendered after a click. */
export function VoiceNote({ lang }: { lang: Lang }) {
  return (
    <p className={styles.voiceNote} role="status">
      {STRINGS.voice.none[lang]}
      {edgeWouldHelp(lang) && ` ${STRINGS.voice.edge.bn}`}
    </p>
  );
}
