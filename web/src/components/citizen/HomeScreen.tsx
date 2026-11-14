"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, type Destination, type Sample } from "@/lib/api";
import { useSession } from "@/lib/useSession";
import { SPEECH_LANG, STRINGS, type Lang } from "@/lib/citizen/i18n";
import type { useSpeech } from "@/lib/citizen/useSpeech";
import { Icon } from "@/components/shared/Icons";
import { useScreenFocus } from "./useScreenFocus";
import styles from "./citizen.module.css";

const T = STRINGS.home;
const HOW_TO_ID = "how-to";

interface Props {
  lang: Lang;
  onLangChange: (lang: Lang) => void;
  /** `destination` is the country code the worker picked (null: detect it); `policy` is the company's own policy, if added */
  onFile: (file: File | null, destination: string | null, policy: File | null) => void;
  onSample: (sampleId: string) => void;
  speech: ReturnType<typeof useSpeech>;
}

export function HomeScreen({ lang, onLangChange, onFile, onSample, speech }: Props) {
  const [samples, setSamples] = useState<Sample[] | null>(null);
  const [countries, setCountries] = useState<Destination[]>([]);
  const [country, setCountry] = useState("");
  const [policy, setPolicy] = useState<File | null>(null);
  const [offline, setOffline] = useState(false);
  const { me } = useSession();

  useEffect(() => {
    api
      .samples()
      .then((s) => setSamples(s.filter((x) => x.id !== "control")))
      .catch(() => setOffline(true));
    api
      .countries()
      .then(setCountries)
      .catch(() => {}); // without the list the contract alone decides the country
  }, []);

  const cameraInput = useRef<HTMLInputElement>(null);
  const uploadInput = useRef<HTMLInputElement>(null);
  const policyInput = useRef<HTMLInputElement>(null);
  const heading = useScreenFocus<HTMLHeadingElement>();
  const howToPlaying = speech.playingId === HOW_TO_ID;

  const pick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) onFile(file, country || null, policy);
  };

  return (
    <div className={styles.screen}>
      <header className={styles.topBar}>
        <div className={styles.brand}>
          <span className={styles.brandMark} aria-hidden="true">
            {STRINGS.brandMark[lang]}
          </span>
          <span className={styles.brandName}>{STRINGS.brand[lang]}</span>
        </div>
        <div className={styles.langToggle} role="group" aria-label={STRINGS.langSwitch[lang]}>
          <button type="button" lang="bn" aria-pressed={lang === "bn"} onClick={() => onLangChange("bn")}>
            বাংলা
          </button>
          <button type="button" lang="en" aria-pressed={lang === "en"} onClick={() => onLangChange("en")}>
            EN
          </button>
        </div>
      </header>

      <div className={styles.homeBody}>
        <div className={styles.intro}>
          <h1 ref={heading} tabIndex={-1} className={styles.h1}>
            {T.title[lang]}
          </h1>
          <p className={styles.lead}>{T.lead[lang]}</p>
        </div>

        {countries.length > 0 && (
          <label className={styles.countryPick}>
            <span className={styles.countryPickLabel}>{T.countryLabel[lang]}</span>
            <select className={styles.countrySelect} value={country} onChange={(e) => setCountry(e.target.value)}>
              <option value="">{T.countryAuto[lang]}</option>
              {countries.map((c) => (
                <option key={c.code} value={c.code ?? ""}>
                  {c.name[lang]}
                </option>
              ))}
            </select>
          </label>
        )}

        <button type="button" className={styles.cameraBtn} onClick={() => cameraInput.current?.click()}>
          <Icon name="camera" size={64} strokeWidth={1.75} className={styles.cameraIcon} />
          <span className={styles.cameraLabel}>{T.camera[lang]}</span>
          <span className={styles.cameraSub} lang={lang === "bn" ? "en" : "bn"}>
            {T.cameraSub[lang]}
          </span>
        </button>
        <input
          ref={cameraInput}
          type="file"
          accept="image/*"
          capture="environment"
          className={styles.visuallyHidden}
          tabIndex={-1}
          aria-hidden="true"
          onChange={pick}
        />

        <button type="button" className={styles.uploadBtn} onClick={() => uploadInput.current?.click()}>
          <span>{T.upload[lang]}</span>
          <span className={styles.uploadSub} lang={lang === "bn" ? "en" : "bn"}>
            {T.uploadSub[lang]}
          </span>
        </button>
        <input
          ref={uploadInput}
          type="file"
          accept="image/*,application/pdf"
          className={styles.visuallyHidden}
          tabIndex={-1}
          aria-hidden="true"
          onChange={pick}
        />

        {policy ? (
          <p className={styles.policyChosen}>
            <span>
              {T.policyChosen[lang]} <b>{policy.name}</b>
            </span>
            <button type="button" className={styles.policyRemove} onClick={() => setPolicy(null)}>
              {T.policyRemove[lang]}
            </button>
          </p>
        ) : (
          <button type="button" className={styles.policyBtn} onClick={() => policyInput.current?.click()}>
            <span className={styles.withIcon}>
              <Icon name="plus" size={18} strokeWidth={2.25} />
              {T.policyAdd[lang]}
            </span>
            <span className={styles.uploadSub}>{T.policySub[lang]}</span>
          </button>
        )}
        <input
          ref={policyInput}
          type="file"
          accept="image/*,application/pdf,.docx,.txt"
          className={styles.visuallyHidden}
          tabIndex={-1}
          aria-hidden="true"
          onChange={(e) => {
            setPolicy(e.target.files?.[0] ?? null);
            e.target.value = "";
          }}
        />

        <button
          type="button"
          className={styles.listenRow}
          aria-pressed={howToPlaying}
          onClick={() => speech.toggle(HOW_TO_ID, T.howToScript[lang], SPEECH_LANG[lang])}
        >
          <span className={styles.listenIcon} aria-hidden="true">
            <Icon name={howToPlaying ? "pause" : "play"} size={22} strokeWidth={2.5} />
          </span>
          <span>{howToPlaying ? `${T.howToStop[lang]} · ${T.howTo[lang]}` : T.howTo[lang]}</span>
          {howToPlaying && <span className={styles.listenProgress} style={{ width: `${speech.pct}%` }} />}
        </button>

        {offline && (
          <p className={styles.hint} role="status">
            {T.offline[lang]}
          </p>
        )}
        {samples && samples.length > 0 && (
          <section className={styles.samples} aria-labelledby="samples-title">
            <h2 id="samples-title" className={styles.samplesTitle}>
              {T.samplesTitle[lang]}
            </h2>
            <ul className={styles.sampleList}>
              {samples.map((smp) => (
                <li key={smp.id}>
                  <button type="button" className={styles.sampleBtn} onClick={() => onSample(smp.id)}>
                    <span className={styles.sampleIcon} data-kind={smp.kind} aria-hidden="true">
                      <Icon name={smp.kind === "image" ? "camera" : "file"} size={24} strokeWidth={1.8} />
                    </span>
                    <span className={styles.sampleText}>
                      <span className={styles.sampleName}>{smp.title[lang]}</span>
                      <span className={styles.sampleSub}>{smp.subtitle[lang]}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        <p className={styles.homeFoot}>
          {T.privacy[lang]}
          <br />
          {T.disclaimer[lang]}
          <br />
          <Link href="/counsel" className={styles.counselLink}>
            {T.counselLink[lang]}
            <Icon name="arrowRight" size={16} strokeWidth={2} />
          </Link>
          {me && me.kind !== "account" && (
            <>
              <br />
              <Link href="/signup?next=/" className={styles.counselLink}>
                {T.saveLink[lang]}
              </Link>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
