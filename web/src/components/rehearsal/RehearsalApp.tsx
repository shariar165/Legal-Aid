"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Destination } from "@/lib/api";
import { STRINGS, type Lang } from "@/lib/citizen/i18n";
import { useSpeech } from "@/lib/citizen/useSpeech";
import { R } from "@/lib/rehearsal/i18n";
import { useRehearsal } from "@/lib/rehearsal/useRehearsal";
import base from "../citizen/citizen.module.css";
import { BenchScreen } from "./BenchScreen";
import { DebriefScreen } from "./DebriefScreen";
import { PromiseRecordScreen } from "./PromiseRecord";
import { SetupScreen } from "./SetupScreen";
import styles from "./rehearsal.module.css";

type Screen = "setup" | "bench" | "debrief" | "record";

const HELP = STRINGS.result;
/** Optional helpdesk number, as on the result screen. */
const HELPDESK_PHONE = process.env.NEXT_PUBLIC_HELPDESK_PHONE;

export function RehearsalApp() {
  const [lang, setLang] = useState<Lang>("bn");
  const [chosen, setScreen] = useState<Screen>("setup");
  const [countries, setCountries] = useState<Destination[]>([]);
  const [helpTapped, setHelpTapped] = useState(false);
  const speech = useSpeech();
  const r = useRehearsal();
  const { stop } = speech;

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  useEffect(() => {
    api
      .countries()
      .then(setCountries)
      .catch(() => {}); // without the list the worker can still rehearse with no country
  }, []);

  // the scheduler can end the rehearsal by itself: then the bench gives way to the debrief
  const screen: Screen = chosen === "bench" && r.status === "done" ? "debrief" : chosen;

  const go = (next: Screen) => {
    stop();
    setScreen(next);
  };

  const help = (
    <>
      <span className={base.helpMain}>{helpTapped ? HELP.calling[lang] : HELP.help[lang]}</span>
      <span className={base.helpSub} lang={lang === "bn" ? "en" : "bn"}>
        {HELP.helpSub[lang]}
      </span>
    </>
  );
  const destination = countries.find((c) => c.code && c.code === r.session?.setup.country) ?? null;

  return (
    <main className={`${base.app} ${styles.shell}`}>
      <div className={`${base.screen} ${styles.shellScreen}`}>
        <header className={`${base.topBar} ${styles.noPrint}`}>
          <Link href="/" className={base.brand} aria-label="Ain Copilot">
            <span className={base.brandMark} aria-hidden="true">
              আ
            </span>
            <span className={styles.brandStack}>
              <span className={base.brandName}>{R.brand[lang]}</span>
              <span className={styles.motto}>{R.motto[lang]}</span>
            </span>
          </Link>
          <div className={base.langToggle} role="group" aria-label="ভাষা / Language">
            <button type="button" lang="bn" aria-pressed={lang === "bn"} onClick={() => setLang("bn")}>
              বাংলা
            </button>
            <button type="button" lang="en" aria-pressed={lang === "en"} onClick={() => setLang("en")}>
              EN
            </button>
          </div>
        </header>

        <div className={styles.body}>
          {screen === "setup" && (
            <SetupScreen
              lang={lang}
              countries={countries}
              busy={r.status === "starting"}
              error={r.status === "error" ? r.error : null}
              onStart={(setup) => {
                void r.start({ ...setup, language: lang });
                go("bench");
              }}
            />
          )}
          {screen === "bench" && <BenchScreen lang={lang} r={r} speech={speech} onExit={() => go("debrief")} />}
          {screen === "debrief" && (
            <DebriefScreen
              lang={lang}
              r={r}
              onRecord={() => go("record")}
              onAgain={() => {
                r.reset();
                go("setup");
              }}
            />
          )}
          {screen === "record" && r.session && <PromiseRecordScreen lang={lang} session={r.session} onSaved={r.setSession} onBack={() => go("debrief")} />}

          <p className={styles.foot}>
            {R.disclaimer[lang]}
            {destination?.help && (
              <>
                <br />
                {R.record.helpThere[lang]} <strong>{destination.help[lang]}</strong>
              </>
            )}
          </p>
        </div>
      </div>
      {screen !== "bench" && (
        <div className={`${base.helpBar} ${styles.noPrint}`}>
          {HELPDESK_PHONE ? (
            <a className={base.helpBtn} href={`tel:${HELPDESK_PHONE}`} onClick={() => setHelpTapped(true)}>
              {help}
            </a>
          ) : (
            <button type="button" className={base.helpBtn} onClick={() => setHelpTapped((t) => !t)}>
              {help}
            </button>
          )}
        </div>
      )}
    </main>
  );
}
