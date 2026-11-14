"use client";

import Link from "next/link";
import { useState } from "react";
import type { AnalysisResult, CardKind } from "@/lib/api";
import { bannerTitle, countryCheckLine, formatNumber, SPEECH_LANG, STRINGS, type Lang } from "@/lib/citizen/i18n";
import type { useSpeech } from "@/lib/citizen/useSpeech";
import { Icon } from "@/components/shared/Icons";
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
          <Icon name="arrowLeft" size={24} strokeWidth={2.25} />
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
              <Icon name="pin" size={20} strokeWidth={2} /> {destination.name[lang]}
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
                  <Icon name={playing ? "pause" : "play"} size={18} strokeWidth={2.5} /> {playing ? T.stop[lang] : T.listen[lang]}
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
                        {card.lines.length > 1 ? `${formatNumber(i + 1, lang)}.` : <span className={styles.lineDot} />}
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
                    {T.details[lang]} <Icon name={isOpen ? "chevronDown" : "chevronRight"} size={18} strokeWidth={2.25} />
                  </button>
                  {isOpen && (
                    <div id={detailsId} className={styles.cits}>
                      <p className={styles.citsLabel}>{T.basis[lang]}</p>
                      <ul className={styles.citList}>
                        {card.citations.map((cit) => (
                          <li key={cit.citation_id} className={styles.cit} data-status={cit.status}>
                            <span className={styles.citSym} aria-hidden="true">
                              <Icon name={cit.status === "verified" ? "check" : "alert"} size={15} strokeWidth={2.5} />
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
                <Icon name={letterPlaying ? "pause" : "play"} size={18} strokeWidth={2.5} /> {letterPlaying ? T.stop[lang] : T.listen[lang]}
              </button>
            </div>
            <div className={styles.cardBody}>
              <p className={styles.letterSub}>{T.letterSub[lang]}</p>
              <pre className={styles.letterText}>{letter}</pre>
              <div className={styles.twoUp}>
                <button type="button" className={styles.btnSolid} onClick={copyLetter}>
                  {copied ? (
                    <span className={styles.withIcon}>
                      <Icon name="check" size={18} strokeWidth={2.5} />
                      {T.copied[lang]}
                    </span>
                  ) : (
                    T.copy[lang]
                  )}
                </button>
                <button type="button" className={styles.btnOutline} onClick={shareLetter}>
                  {T.share[lang]}
                </button>
              </div>
            </div>
          </section>
        )}

        <Link href={`/counsel/${result.job_id}`} className={styles.memoLink}>
          <span className={styles.memoMain}>
            {T.memoLink[lang]}
            <Icon name="arrowRight" size={18} strokeWidth={2.25} />
          </span>
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
