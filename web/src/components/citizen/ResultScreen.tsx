"use client";

import Link from "next/link";
import { Fragment, useState } from "react";
import type { AnalysisResult, CardKind } from "@/lib/api";
import { bannerTitle, countryCheckLine, formatNumber, SPEECH_LANG, STRINGS, type Lang } from "@/lib/citizen/i18n";
import type { useSpeech } from "@/lib/citizen/useSpeech";
import { Icon } from "@/components/shared/Icons";
import { HeroChip, MoneyHero } from "@/components/shared/MoneyHero";
import { PromiseStep } from "./PromiseStep";
import { useScreenFocus } from "./useScreenFocus";
import { VoiceNote } from "./VoiceNote";
import styles from "./citizen.module.css";

const T = STRINGS.result;
const LETTER_ID = "letter";

/** Optional override: one number the help button dials directly, e.g. "+8801XXXXXXXXX". */
const HELPDESK_PHONE = process.env.NEXT_PUBLIC_HELPDESK_PHONE;
/* Without the override, the button opens the Probash Bandhu call centre (Wage Earners' Welfare Board, Ministry of
   Expatriates' Welfare): 16135 toll-free from inside Bangladesh, +8809610102030 from abroad, 24 hours.
   Source: Dhaka Tribune, "Control room to remain open during Eid holidays" (March 2026); checked 2026-11-26. */
const PROBASH_BANDHU = [
  { tel: "16135", shown: "16135", where: "helpInBd" },
  { tel: "+8809610102030", shown: "+880 9610 102030", where: "helpAbroad" },
] as const;

interface Props {
  lang: Lang;
  result: AnalysisResult;
  speech: ReturnType<typeof useSpeech>;
  onBack: () => void;
  /** refetch the result after the worker adds what the agent said */
  reload: () => Promise<void>;
}

export function ResultScreen({ lang, result, speech, onBack, reload }: Props) {
  const [open, setOpen] = useState<Partial<Record<CardKind, boolean>>>({});
  const [helpOpen, setHelpOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const heading = useScreenFocus<HTMLHeadingElement>();
  const { citizen, destination } = result;
  const letter = citizen.letter[lang];
  const letterPlaying = speech.playingId === LETTER_ID;
  const saidGaps = (result.four_ledgers?.rows ?? []).filter((r) => r.mismatches.some((m) => m.type === "said_vs_paper")).length;

  const helpContent = (
    <>
      <span className={styles.helpMain}>{T.help[lang]}</span>
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
        {/* the money first; with no wage on the paper the danger count is the headline */}
        <div className={styles.heroWrap}>
          <MoneyHero
            result={result}
            lang={lang}
            layout="phone"
            voice="worker"
            level={2}
            headingId="money-title"
            fallback={bannerTitle(citizen.dangerCount, lang)}
            chips={
              <>
                {result.wage && <HeroChip n={citizen.dangerCount} label={T.dangers[lang]} lang={lang} tone={citizen.dangerCount > 0 ? "bad" : undefined} />}
                {saidGaps > 0 && <HeroChip n={saidGaps} label={T.mismatches[lang]} lang={lang} />}
              </>
            }
          >
            {citizen.dangerCount > 0 && <p className={styles.heroNote}>{T.bannerBody[lang]}</p>}
          </MoneyHero>
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

        {citizen.cards.map((card, i) => {
          // the step comes right after the dangers (and the employer-policy card), before pay, what to do and deadlines
          const stepHere = i === citizen.cards.findLastIndex((c) => c.kind === "danger" || c.kind === "policy");
          const playing = speech.playingId === card.kind;
          const isOpen = !!open[card.kind];
          const detailsId = `cits-${card.kind}`;
          const spoken = [card.title[lang], card.big?.[lang], ...card.lines.map((l) => l[lang])]
            .filter(Boolean)
            .join("। ");
          return (
            <Fragment key={card.kind}>
              <section className={styles.card} data-kind={card.kind} aria-labelledby={`title-${card.kind}`}>
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
                {speech.noVoice === card.kind && (
                  <VoiceNote lang={lang} />
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
              {stepHere && <PromiseStep lang={lang} result={result} reload={reload} />}
            </Fragment>
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
            {speech.noVoice === LETTER_ID && (
              <VoiceNote lang={lang} />
            )}
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
          <a className={styles.helpBtn} href={`tel:${HELPDESK_PHONE}`}>
            {helpContent}
          </a>
        ) : (
          <>
            {/* a call needs a tel: link: the sheet offers the two numbers, shown as text so a computer shows them too */}
            {helpOpen && (
              <div id="help-sheet" className={styles.helpSheet} role="group" aria-labelledby="help-sheet-title">
                <p id="help-sheet-title" className={styles.helpSheetTitle}>
                  {T.helpSheetTitle[lang]}
                </p>
                {PROBASH_BANDHU.map((n) => (
                  <a key={n.tel} className={styles.helpNumber} href={`tel:${n.tel}`}>
                    <span className={styles.helpNumberMain} lang="en">
                      {n.shown}
                    </span>
                    <span className={styles.helpNumberSub}>{T[n.where][lang]}</span>
                  </a>
                ))}
              </div>
            )}
            <button type="button" className={styles.helpBtn} aria-expanded={helpOpen} aria-controls="help-sheet" onClick={() => setHelpOpen((o) => !o)}>
              {helpContent}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
