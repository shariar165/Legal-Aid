"use client";

import { useEffect, useRef, useState } from "react";
import type { PersonaId, Section } from "@/lib/api";
import { SPEECH_LANG, type Lang } from "@/lib/citizen/i18n";
import { useDictation } from "@/lib/citizen/useDictation";
import type { useSpeech } from "@/lib/citizen/useSpeech";
import { rehearsalApi, type CoachHint, type RehearsalTurn, type WorkerAction } from "@/lib/rehearsal/api";
import { R } from "@/lib/rehearsal/i18n";
import type { useRehearsal } from "@/lib/rehearsal/useRehearsal";
import { PixelSticker } from "../counsel/PixelSticker";
import { DalalAvatar } from "./DalalAvatar";
import styles from "./rehearsal.module.css";

const T = R.bench;
const SEATS: PersonaId[] = ["happy", "proud", "gloomy"];
const NAMES: Record<PersonaId, string> = { happy: "Sunny", proud: "Regal", gloomy: "Grey" };

interface Props {
  lang: Lang;
  r: ReturnType<typeof useRehearsal>;
  speech: ReturnType<typeof useSpeech>;
  onExit: () => void;
}

export function BenchScreen({ lang, r, speech, onExit }: Props) {
  const [draft, setDraft] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const turns = r.session?.turns ?? [];
  const current = turns[turns.length - 1];
  const yourTurn = r.status === "yourTurn";
  const dictation = useDictation(SPEECH_LANG.bn, (t) => setDraft((d) => (d ? `${d} ${t}` : t)));

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, r.liveHints.length, r.status]);

  const send = (action: WorkerAction = "none") => {
    if (!yourTurn || (!draft.trim() && action === "none")) return;
    speech.stop();
    dictation.stop();
    void r.reply(draft.trim(), action);
    setDraft("");
  };

  const stopRehearsal = () => {
    speech.stop();
    dictation.stop();
    void r.finish();
    onExit();
  };

  return (
    <div className={styles.bench}>
      <div className={styles.benchBar}>
        <span className={styles.turnCount}>
          {T.turn[lang]} {turns.length || 1} / {r.maxTurns}
        </span>
        <button type="button" className={styles.ghost} onClick={stopRehearsal} disabled={!r.id}>
          {T.stop[lang]}
        </button>
      </div>
      <p className={styles.note}>{R.roleplay[lang]}</p>

      <ol className={styles.transcript}>
        {turns.map((t) => (
          <TurnView key={t.n} turn={t} lang={lang} speech={speech} live={t === current && r.status === "coaching" ? r.liveHints : null} onSay={setDraft} />
        ))}
      </ol>

      {(r.status === "dalal" || r.status === "starting") && <p className={styles.thinking}>{T.dalalThinking[lang]}</p>}
      {r.status === "coaching" && <p className={styles.thinking}>{T.thinking[lang]}</p>}
      {r.error && (
        <p className={styles.error} role="alert">
          {r.error}
        </p>
      )}

      {yourTurn && (
        <div className={styles.composer}>
          <label className={styles.visuallyHidden} htmlFor="reply">
            {T.placeholder[lang]}
          </label>
          <textarea
            id="reply"
            className={styles.reply}
            value={draft}
            maxLength={600}
            rows={2}
            placeholder={T.placeholder[lang]}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
          />
          <div className={styles.sendRow}>
            <Mic lang={lang} d={dictation} />
            <button type="button" className={styles.primary} onClick={() => send()} disabled={!draft.trim()}>
              {T.send[lang]}
            </button>
          </div>
          <div className={styles.actions} role="group" aria-label={T.actionNote[lang]} title={T.actionNote[lang]}>
            <button type="button" className={styles.small} onClick={() => send("paid")}>
              {T.actionPaid[lang]}
            </button>
            <button type="button" className={styles.small} onClick={() => send("gave_passport")}>
              {T.actionPassport[lang]}
            </button>
          </div>
          <p className={styles.tiny}>{T.actionNote[lang]}</p>
        </div>
      )}
      <div ref={end} />
    </div>
  );
}

function TurnView({ turn, lang, speech, live, onSay }: { turn: RehearsalTurn; lang: Lang; speech: ReturnType<typeof useSpeech>; live: CoachHint[] | null; onSay: (text: string) => void }) {
  const id = `dalal-${turn.n}`;
  const playing = speech.playingId === id;
  const answered = !!turn.worker_reply || turn.action !== "none";
  const hints = turn.hints.length ? turn.hints : (live ?? []);
  return (
    <li className={styles.turn}>
      <div className={styles.dalalRow}>
        <DalalAvatar size={40} />
        <div className={styles.dalalBubble}>
          <span className={styles.who}>{T.dalal[lang]}</span>
          <p lang="bn">{turn.dalal_line}</p>
          <div className={styles.bubbleFoot}>
            <button type="button" className={styles.listen} aria-pressed={playing} onClick={() => speech.toggle(id, turn.dalal_line, SPEECH_LANG.bn)}>
              {playing ? "■" : "▶"} {T.listen[lang]}
            </button>
            {answered && turn.label && (
              <span className={styles.tactic}>
                {T.tactic[lang]}: {turn.label[lang]}
              </span>
            )}
          </div>
          {turn.guardrail && <p className={styles.guardrail}>{T.replaced[lang]}</p>}
        </div>
      </div>

      {answered && (
        <div className={styles.youRow}>
          <div className={styles.youBubble}>
            <span className={styles.who}>{T.you[lang]}</span>
            {turn.worker_reply && <p>{turn.worker_reply}</p>}
            {turn.action === "paid" && <p className={styles.actionTag}>{T.actionPaid[lang]}</p>}
            {turn.action === "gave_passport" && <p className={styles.actionTag}>{T.actionPassport[lang]}</p>}
            {turn.hits.length > 0 && (
              <p className={styles.hits}>
                {T.asked[lang]} {turn.hits.map((h) => `✓ ${R.hits[h]?.[lang] ?? h}`).join(" · ")}
              </p>
            )}
          </div>
        </div>
      )}

      {hints.length > 0 && (
        <ul className={styles.coaches} aria-label="Coaches">
          {SEATS.map((m) => {
            const h = hints.find((x) => x.member === m);
            return h ? <HintCard key={m} hint={h} lang={lang} onSay={onSay} /> : <li key={m} className={styles.hintPending} aria-hidden="true" />;
          })}
        </ul>
      )}
    </li>
  );
}

function HintCard({ hint, lang, onSay }: { hint: CoachHint; lang: Lang; onSay: (text: string) => void }) {
  const m = hint.member;
  return (
    <li className={styles.hint} data-seat={m}>
      <div className={styles.hintHead}>
        <PixelSticker persona={m} size={30} />
        <span>
          <b>{NAMES[m]}</b> · {T.lenses[m][lang]}
        </span>
      </div>
      <p lang="bn">{hint.text}</p>
      {m === "proud" &&
        (hint.citations.length ? hint.citations.map((c) => <CiteChip key={c} id={c} lang={lang} />) : <span className={styles.noLaw}>{T.noLaw[lang]}</span>)}
      {m === "happy" && hint.say && (
        <button type="button" className={styles.sayChip} onClick={() => onSay(hint.say)}>
          <span>{T.tapToSay[lang]}:</span> “{hint.say}”
        </button>
      )}
    </li>
  );
}

export function CiteChip({ id, lang }: { id: string; lang: Lang }) {
  const [sec, setSec] = useState<Section | null>(null);
  useEffect(() => {
    let alive = true;
    void rehearsalApi.section(id).then((s) => alive && setSec(s));
    return () => {
      alive = false;
    };
  }, [id]);
  const text = sec ? (lang === "bn" ? `${sec.act}, ধারা ${sec.section}` : `${sec.act_en}, s.${sec.section}`) : id;
  return (
    <a className={styles.cite} href={sec?.url} target="_blank" rel="noreferrer">
      ✔ {R.bench.verified[lang]}: {text}
    </a>
  );
}

function Mic({ lang, d }: { lang: Lang; d: ReturnType<typeof useDictation> }) {
  const [asking, setAsking] = useState(false);
  if (d.mode === "none" || d.mode === "checking") return null;
  if (d.mode === "cloud" && !d.consented) {
    return asking ? (
      <div className={styles.micNotice} role="dialog" aria-label={T.micCloud[lang]}>
        <p>{T.micNotice[lang]}</p>
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.action}
            onClick={() => {
              d.consent();
              setAsking(false);
            }}
          >
            {T.micAgree[lang]}
          </button>
          <button type="button" className={styles.ghost} onClick={() => setAsking(false)}>
            {T.micNo[lang]}
          </button>
        </div>
      </div>
    ) : (
      <button type="button" className={styles.ghost} onClick={() => setAsking(true)}>
        <MicGlyph /> {T.micCloud[lang]}
      </button>
    );
  }
  return (
    <button type="button" className={styles.ghost} aria-pressed={d.listening} onClick={() => (d.listening ? d.stop() : d.start())}>
      <MicGlyph /> {d.listening ? T.micListening[lang] : d.mode === "local" ? T.micLocal[lang] : T.micCloud[lang]}
    </button>
  );
}

function MicGlyph() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
    </svg>
  );
}
