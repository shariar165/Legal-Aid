"use client";

import Link from "next/link";
import { useState } from "react";
import type { AnalysisResult, CardKind } from "@/lib/api";
import { bannerTitle, countryCheckLine, formatNumber, SPEECH_LANG, STRINGS, type Lang } from "@/lib/citizen/i18n";
import type { useSpeech } from "@/lib/citizen/useSpeech";
import { useScreenFocus } from "./useScreenFocus";
import styles from "./citizen.module.css";

const T = STRINGS.result;
const LETTER_ID = "letter";

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
  const [copied, setCopied] = useState(false);
  const heading = useScreenFocus<HTMLHeadingElement>();
  const { citizen, destination } = result;
  const letter = citizen.letter[lang];
  const letterPlaying = speech.playingId === LETTER_ID;

  const helpContent = (
    <>
      <span className={styles.helpMain}>{helpTapped ? T.calling[lang] : T.help[lang]}</span>
      <span className={styles.helpSub} lang={lang === "bn" ? "en" : "bn"}>
        {T.helpSub[lang]}
      </span>
    </>
  );

  const copyLetter = async () => {
    try {
      await navigator.clipboard.writeText(letter);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      /* clipboard blocked: nothing to do */
    }
  };

  const shareLetter = async () => {
    if (navigator.share) {
      try {
        await navigator.share({ text: letter });
      } catch {
        /* user cancelled */
      }
    } else {
      void copyLetter();
    }
  };

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
        <div className={styles.banner} data-safe={citizen.dangerCount === 0} role="alert">
          <p className={styles.bannerTitle}>{bannerTitle(citizen.dangerCount, lang)}</p>
          <p className={styles.bannerBody}>{T.bannerBody[lang]}</p>
        </div>

        {destination && (
          <section className={styles.countryCard} data-supported={destination.supported} aria-label={T.workIn[lang]}>
            <p className={styles.countryName}>
              <PinGlyph /> {destination.name[lang]}
            </p>
            <p className={styles.countryLine}>{countryCheckLine(destination, lang)}</p>
            {destination.help && (
              <p className={styles.countryLine}>
                {T.helpThere[lang]} <strong>{destination.help[lang]}</strong>
              </p>
            )}
          </section>
        )}

        {result.route.scope_note && (
          <section className={styles.countryCard} data-supported={false}>
            <p className={styles.countryLine}>{result.route.scope_note[lang]}</p>
          </section>
        )}

        {citizen.cards.map((card) => {
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

              {card.citations.length > 0 && (
                <>
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
                        {card.citations.map((cit) => (
                          <li key={cit.citation_id} className={styles.cit} data-status={cit.status}>
                            <span className={styles.citSym} aria-hidden="true">
                              {cit.status === "verified" ? "✓" : "⚠"}
                            </span>
                            <a className={styles.citName} href={cit.url || undefined} target="_blank" rel="noreferrer" title={cit.url ? T.openSource[lang] : undefined}>
                              {cit.name[lang]}
                            </a>
                            <span className={styles.citStatus}>{cit.status === "verified" ? T.verified[lang] : T.partial[lang]}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              )}
            </section>
          );
        })}

        {citizen.dangerCount > 0 && (
          <section className={styles.card} data-kind="letter" aria-labelledby="title-letter">
            <div className={styles.cardHead}>
              <h2 id="title-letter" className={styles.cardTitle}>
                {T.letterTitle[lang]}
              </h2>
              <button
                type="button"
                className={styles.playBtn}
                aria-label={letterPlaying ? T.pauseAria[lang] : T.playAria[lang]}
                aria-pressed={letterPlaying}
                onClick={() => speech.toggle(LETTER_ID, letter, SPEECH_LANG[lang])}
              >
                <span aria-hidden="true">{letterPlaying ? "❚❚" : "▶"}</span> {letterPlaying ? T.stop[lang] : T.listen[lang]}
              </button>
            </div>
            <div className={styles.cardBody}>
              <p className={styles.letterSub}>{T.letterSub[lang]}</p>
              <pre className={styles.letterText}>{letter}</pre>
              <div className={styles.twoUp}>
                <button type="button" className={styles.btnSolid} onClick={copyLetter}>
                  {copied ? T.copied[lang] : T.copy[lang]}
                </button>
                <button type="button" className={styles.btnOutline} onClick={shareLetter}>
                  {T.share[lang]}
                </button>
              </div>
            </div>
          </section>
        )}

        <Link href={`/counsel/${result.job_id}`} className={styles.memoLink}>
          <span className={styles.memoMain}>{T.memoLink[lang]}</span>
          <span className={styles.memoSub}>{T.memoSub[lang]}</span>
        </Link>

        <p className={styles.resultFoot}>
          {T.disclaimer[lang]}
          {result.llm_mode === "fake" && (
            <>
              <br />
              {T.offlineMode[lang]}
            </>
          )}
        </p>
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

/* Inline SVG instead of a flag emoji: Windows and many Android fonts have no flag glyphs. */
function PinGlyph() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21Z" />
      <circle cx="12" cy="9.5" r="2.5" />
    </svg>
  );
}
