"use client";

import { useState } from "react";
import type { AnalysisResult, CardKind } from "@/lib/citizen/analysis";
import { bannerTitle, formatNumber, SPEECH_LANG, STRINGS, type Lang } from "@/lib/citizen/i18n";
import type { useSpeech } from "@/lib/citizen/useSpeech";
import { useScreenFocus } from "./useScreenFocus";
import styles from "./citizen.module.css";

const T = STRINGS.result;

/** Optional helpdesk number, e.g. "+8801XXXXXXXXX". Without it the button only shows the calling state. */
const HELPDESK_PHONE = process.env.NEXT_PUBLIC_HELPDESK_PHONE;

interface Props {
  lang: Lang;
  result: AnalysisResult;
  speech: ReturnType<typeof useSpeech>;
  onBack: () => void;
}

export function ResultScreen({ lang, result, speech, onBack }: Props) {
  const [open, setOpen] = useState<Partial<Record<CardKind, boolean>>>({});
  const [helpTapped, setHelpTapped] = useState(false);
  const heading = useScreenFocus<HTMLHeadingElement>();

  const helpContent = (
    <>
      <span className={styles.helpMain}>{helpTapped ? T.calling[lang] : T.help[lang]}</span>
      <span className={styles.helpSub} lang={lang === "bn" ? "en" : "bn"}>
        {T.helpSub[lang]}
      </span>
    </>
  );

  return (
    <div className={styles.screen}>
      <header className={styles.resultHead}>
        <button type="button" className={styles.backBtn} aria-label={T.back[lang]} onClick={onBack}>
          ←
        </button>
        <h1 ref={heading} tabIndex={-1} className={styles.resultTitle}>
          {T.title[lang]}
        </h1>
      </header>

      <div className={styles.resultScroll}>
        <div className={styles.banner} role="alert">
          <p className={styles.bannerTitle}>{bannerTitle(result.dangerCount, lang)}</p>
          <p className={styles.bannerBody}>{T.bannerBody[lang]}</p>
        </div>

        {result.cards.map((card) => {
          const playing = speech.playingId === card.kind;
          const isOpen = !!open[card.kind];
          const detailsId = `cits-${card.kind}`;
          const spoken = [card.title[lang], card.big?.[lang], ...card.lines.map((l) => l[lang])]
            .filter(Boolean)
            .join("। ");
          return (
            <section key={card.kind} className={styles.card} data-kind={card.kind} aria-labelledby={`title-${card.kind}`}>
              <div className={styles.cardHead}>
                <h2 id={`title-${card.kind}`} className={styles.cardTitle}>
                  {card.title[lang]}
                </h2>
                <button
                  type="button"
                  className={styles.playBtn}
                  aria-label={playing ? T.pauseAria[lang] : T.playAria[lang]}
                  aria-pressed={playing}
                  onClick={() => speech.toggle(card.kind, spoken, SPEECH_LANG[lang])}
                >
                  <span aria-hidden="true">{playing ? "❚❚" : "▶"}</span> {playing ? T.stop[lang] : T.listen[lang]}
                </button>
              </div>
              {playing && (
                <div className={styles.playTrack}>
                  <div className={styles.playFill} style={{ width: `${speech.pct}%` }} />
                </div>
              )}

              <div className={styles.cardBody}>
                {card.big && <span className={styles.big}>{card.big[lang]}</span>}
                <ul className={styles.lines}>
                  {card.lines.map((line, i) => (
                    <li key={i} className={styles.line}>
                      <span className={styles.lineMark} aria-hidden="true">
                        {card.lines.length > 1 ? `${formatNumber(i + 1, lang)}.` : "•"}
                      </span>
                      <span>{line[lang]}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <button
                type="button"
                className={styles.detailsBtn}
                aria-expanded={isOpen}
                aria-controls={detailsId}
                onClick={() => setOpen((p) => ({ ...p, [card.kind]: !p[card.kind] }))}
              >
                {T.details[lang]} {isOpen ? "▾" : "▸"}
              </button>
              {isOpen && (
                <div id={detailsId} className={styles.cits}>
                  <p className={styles.citsLabel}>{T.basis[lang]}</p>
                  <ul className={styles.citList}>
                    {card.citations.map((cit, i) => (
                      <li key={i} className={styles.cit} data-status={cit.status}>
                        <span className={styles.citSym} aria-hidden="true">
                          {cit.status === "verified" ? "✓" : "⚠"}
                        </span>
                        <span className={styles.citName}>{cit.name[lang]}</span>
                        <span className={styles.citStatus}>
                          {cit.status === "verified" ? T.verified[lang] : T.partial[lang]}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          );
        })}

        <p className={styles.resultFoot}>{T.disclaimer[lang]}</p>
      </div>

      <div className={styles.helpBar}>
        {HELPDESK_PHONE ? (
          <a className={styles.helpBtn} href={`tel:${HELPDESK_PHONE}`} onClick={() => setHelpTapped(true)}>
            {helpContent}
          </a>
        ) : (
          <button type="button" className={styles.helpBtn} onClick={() => setHelpTapped((t) => !t)}>
            {helpContent}
          </button>
        )}
      </div>
    </div>
  );
}
