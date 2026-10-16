"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api, type AnalysisResult, type BenchOpinion, type BenchResult, type ChatTurn, type CouncilMember, type PersonaId, type Section } from "@/lib/api";
import { citeLabel, SEVERITY_LABEL } from "./format";
import styles from "./counsel.module.css";

/* The three council members. Names and titles mirror backend/ain/agents/bench.py PERSONAS;
   the API adds each member's live model. */
export const PERSONA_IDS: PersonaId[] = ["happy", "proud", "gloomy"];

const FALLBACK: Record<PersonaId, CouncilMember> = {
  happy: { id: "happy", name: "Sunny", title: "the Happy AI", tagline: "Every bad clause has a fix. Let's find it.", seat: "Justice A", model: "" },
  proud: { id: "proud", name: "Regal", title: "the Proud AI", tagline: "The text is clear. I have read it correctly.", seat: "Justice B", model: "" },
  gloomy: { id: "gloomy", name: "Grey", title: "the Gloomy AI", tagline: "Assume it will go wrong. It usually does.", seat: "Justice C", model: "" },
};

export type CouncilTarget = PersonaId | "all";

export interface CouncilNav {
  target: CouncilTarget;
  riskId: string | null;
  setTarget: (t: CouncilTarget) => void;
  setRiskId: (id: string | null) => void;
  /* switch to the Council tab, pick who answers and what about, and scroll to the chat */
  open: (target: CouncilTarget, riskId?: string | null) => void;
}

export function memberName(id: PersonaId) {
  return FALLBACK[id].name;
}

/* ------------------------------------------------------------------ Avatar */

export function CouncilAvatar({ persona, size = 36 }: { persona: PersonaId; size?: number }) {
  return (
    <svg className={styles.avatar} data-persona={persona} width={size} height={size} viewBox="0 0 40 40" role="img" aria-label={`${FALLBACK[persona].name}, ${FALLBACK[persona].title}`}>
      {persona === "proud" && <path d="M11 9 L14 3 L17 8 L20 2 L23 8 L26 3 L29 9 Z" className={styles.avCrown} />}
      {persona === "gloomy" && (
        <g className={styles.avCloud}>
          <ellipse cx="15" cy="5.5" rx="5" ry="3.2" />
          <ellipse cx="22" cy="4.5" rx="6" ry="3.8" />
          <ellipse cx="27.5" cy="6" rx="4" ry="2.8" />
          <path d="M14 10.5 l-1 2.5 M20 10.5 l-1 2.5 M26 10.5 l-1 2.5" className={styles.avRain} />
        </g>
      )}
      <circle cx="20" cy="24" r="14" className={styles.avFace} />
      {persona === "happy" && (
        <>
          <path d="M13 21.5 q2.5 -3 5 0 M22 21.5 q2.5 -3 5 0" className={styles.avLine} />
          <circle cx="12.5" cy="26" r="2" className={styles.avCheek} />
          <circle cx="27.5" cy="26" r="2" className={styles.avCheek} />
          <path d="M13.5 27 q6.5 7 13 0" className={styles.avLine} />
        </>
      )}
      {persona === "proud" && (
        <>
          <path d="M12.5 20 l5 1 M27.5 20 l-5 1" className={styles.avLine} />
          <path d="M13.5 23 h4 M22.5 23 h4" className={styles.avLine} />
          <path d="M16 30 q5 2 9 -1.5" className={styles.avLine} />
        </>
      )}
      {persona === "gloomy" && (
        <>
          <path d="M12.5 19.5 l5 -1.5 M27.5 19.5 l-5 -1.5" className={styles.avLine} />
          <circle cx="15.5" cy="23" r="1.4" className={styles.avDot} />
          <circle cx="24.5" cy="23" r="1.4" className={styles.avDot} />
          <path d="M15 31 q5 -4 10 0" className={styles.avLine} />
          <path d="M26.5 25.5 q-0.9 2 0 2.6 q0.9 -0.6 0 -2.6" className={styles.avTear} />
        </>
      )}
    </svg>
  );
}

/* Three small faces, used in the toolbar and on risk cards. */
export function CouncilFaces({ size = 22 }: { size?: number }) {
  return (
    <span className={styles.faces}>
      {PERSONA_IDS.map((p) => (
        <CouncilAvatar key={p} persona={p} size={size} />
      ))}
    </span>
  );
}

function dissents(o: BenchOpinion, b: BenchResult) {
  return o.verdict !== b.majority_verdict || o.severity !== b.majority_severity;
}

/* Each member's severity vote on one benched risk (risk card). */
export function MemberVotes({ bench }: { bench: BenchResult }) {
  return (
    <span className={styles.memberVotes}>
      {bench.opinions
        .filter((o) => o.persona)
        .map((o) => (
          <span key={o.seat} className={styles.memberVote} data-dissent={dissents(o, bench)} title={`${o.name}: ${o.verdict}, ${o.severity}`}>
            <CouncilAvatar persona={o.persona as PersonaId} size={20} />
            {SEVERITY_LABEL[o.severity]}
          </span>
        ))}
    </span>
  );
}

/* ------------------------------------------------------------------ Panel */

interface Msg {
  id: number;
  speaker: "user" | PersonaId | "error";
  text: string;
  citations?: string[];
}

const PROMPTS = ["Should I sign this?", "What should I negotiate first?", "Why do you disagree with the others?"];

export function CouncilPanel({ result, nav }: { result: AnalysisResult; nav: CouncilNav }) {
  const [members, setMembers] = useState<CouncilMember[]>(PERSONA_IDS.map((p) => FALLBACK[p]));
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [pending, setPending] = useState<PersonaId[]>([]);
  const [draft, setDraft] = useState("");
  const logRef = useRef<HTMLDivElement>(null);
  const nextId = useRef(0);

  useEffect(() => {
    let alive = true;
    api
      .council()
      .then((m) => alive && setMembers(m))
      .catch(() => {
        /* keep the built-in names; models stay blank */
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    // scroll the log box itself, never the page (the panel stays mounted while other views show)
    const log = logRef.current;
    if (log) log.scrollTo({ top: log.scrollHeight, behavior: "smooth" });
  }, [msgs, pending]);

  const benched = result.risks.filter((r) => r.bench);
  const live = result.risks.filter((r) => r.status !== "dropped");
  const sections = useMemo(() => {
    const m = new Map<string, Section>();
    for (const v of result.ledger) if (v.section) m.set(v.section.citation_id, v.section);
    return m;
  }, [result.ledger]);


  const send = async (text: string) => {
    const message = text.trim();
    if (!message || pending.length) return;
    const targets = nav.target === "all" ? PERSONA_IDS : [nav.target];
    const history: ChatTurn[] = msgs
      .filter((m): m is Msg & { speaker: ChatTurn["speaker"] } => m.speaker !== "error")
      .slice(-8)
      .map((m) => ({ speaker: m.speaker, text: m.text }));
    const userId = nextId.current++;
    setMsgs((cur) => [...cur.filter((m) => m.speaker !== "error"), { id: userId, speaker: "user", text: message }]);
    setDraft("");
    setPending(targets);
    try {
      const { replies } = await api.councilChat(result.job_id, { message, members: targets, risk_id: nav.riskId, history });
      setMsgs((cur) => [...cur, ...replies.map((r) => ({ id: nextId.current++, speaker: r.member, text: r.text, citations: r.citations }))]);
    } catch (e) {
      const err = (e as Error).message.replace(/^\d+: /, "");
      // a rejected question (e.g. it contained an identifier) must not stay in the history sent with the next one
      setMsgs((cur) => [
        ...cur.filter((m) => m.id !== userId),
        { id: nextId.current++, speaker: "error", text: err === "Failed to fetch" ? "The analysis server is not reachable." : err },
      ]);
      setDraft(message);
    } finally {
      setPending([]);
    }
  };

  const who = nav.target === "all" ? "all three" : FALLBACK[nav.target].name;
  const model = (id: PersonaId) => members.find((m) => m.id === id)?.model;

  return (
    <div className={styles.council}>
      <h1 className={styles.viewTitle}>Ask the council</h1>
      <p className={styles.viewLead}>
        Three AI reviewers with different temperaments. They only use the law that passed our checks, so their answers stay grounded.
      </p>

      {/* ---------------- who answers: tap a face */}
      <div className={styles.picker} role="radiogroup" aria-label="Who should answer">
        <button type="button" role="radio" aria-checked={nav.target === "all"} className={styles.pick} onClick={() => nav.setTarget("all")}>
          <CouncilFaces size={34} />
          <b>All three</b>
          <span>Hear every view</span>
        </button>
        {members.map((m) => (
          <button
            key={m.id}
            type="button"
            role="radio"
            aria-checked={nav.target === m.id}
            className={styles.pick}
            data-persona={m.id}
            title={m.model ? `Runs on ${m.model}` : undefined}
            onClick={() => nav.setTarget(m.id)}
          >
            <CouncilAvatar persona={m.id} size={44} />
            <b>{m.name}</b>
            <span>{m.tagline}</span>
          </button>
        ))}
      </div>

      {/* ---------------- chat */}
      <section id="council-chat" className={styles.chat} aria-label="Council chat">
        <label className={styles.about}>
          Talking about
          <select value={nav.riskId ?? ""} onChange={(e) => nav.setRiskId(e.target.value || null)}>
            <option value="">the whole contract</option>
            {live.map((r) => (
              <option key={r.id} value={r.id}>
                {r.title.en}
              </option>
            ))}
          </select>
        </label>

        <div ref={logRef} className={styles.chatLog} aria-live="polite">
          {msgs.length === 0 && (
            <div className={styles.prompts}>
              <span>Try asking:</span>
              {PROMPTS.map((p) => (
                <button key={p} type="button" className={styles.prompt} onClick={() => void send(p)}>
                  {p}
                </button>
              ))}
            </div>
          )}
          {msgs.map((m) =>
            m.speaker === "user" ? (
              <p key={m.id} className={styles.bubbleUser}>
                {m.text}
              </p>
            ) : m.speaker === "error" ? (
              <p key={m.id} className={styles.errorBox}>
                {m.text}
              </p>
            ) : (
              <div key={m.id} className={styles.bubbleRow}>
                <CouncilAvatar persona={m.speaker} size={32} />
                <div className={styles.bubble} data-persona={m.speaker}>
                  <b className={styles.bubbleName}>
                    {FALLBACK[m.speaker].name} <span>· {FALLBACK[m.speaker].title}</span>
                  </b>
                  <p>{m.text}</p>
                  {!!m.citations?.length && (
                    <span className={styles.bubbleCites}>
                      {m.citations.map((c) => {
                        const s = sections.get(c);
                        return s ? (
                          <a key={c} href={s.url} target="_blank" rel="noreferrer" className={styles.chip}>
                            {citeLabel(s)}
                          </a>
                        ) : (
                          <code key={c}>{c}</code>
                        );
                      })}
                    </span>
                  )}
                </div>
              </div>
            ),
          )}
          {pending.map((p) => (
            <div key={p} className={styles.bubbleRow}>
              <CouncilAvatar persona={p} size={32} />
              <span className={styles.typing} data-persona={p} aria-label={`${FALLBACK[p].name} is thinking`}>
                <i />
                <i />
                <i />
              </span>
            </div>
          ))}
        </div>

        <form
          className={styles.chatForm}
          onSubmit={(e) => {
            e.preventDefault();
            void send(draft);
          }}
        >
          <textarea
            value={draft}
            rows={2}
            maxLength={1000}
            placeholder={`Ask ${who} a question…`}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send(draft);
              }
            }}
            aria-label="Your question to the council"
          />
          <button type="submit" className={styles.primaryBtn} disabled={!draft.trim() || pending.length > 0}>
            Send
          </button>
        </form>
        <p className={styles.paneNote}>Please don&apos;t type names, phone numbers or ID numbers. This is information, not formal legal advice.</p>
      </section>

      {/* ---------------- past votes, folded */}
      {benched.length > 0 && (
        <section className={styles.votes}>
          <h2 className={styles.sectionTitle}>How the council voted on the serious risks</h2>
          {benched.map((r) => {
            const b = r.bench!;
            const against = b.opinions.filter((o) => dissents(o, b) && o.name).map((o) => o.name);
            return (
              <details key={r.id} className={styles.voteCase}>
                <summary>
                  <span className={styles.voteTitle}>{r.title.en}</span>
                  <MemberVotes bench={b} />
                  <span className={styles.voteNote}>{against.length ? `${against.join(" and ")} disagreed` : "Everyone agreed"}</span>
                </summary>
                <p>{b.majority_opinion}</p>
                {b.opinions.map((o) => (
                  <div key={o.seat} className={styles.opinion}>
                    {o.persona && <CouncilAvatar persona={o.persona} size={26} />}
                    <div>
                      <b>{o.name || o.seat}</b>: rated it {SEVERITY_LABEL[o.severity].toLowerCase()}
                      {o.revised && " (changed their mind after hearing the others)"}
                      <p>{o.reasoning}</p>
                      <span className={styles.judgeModel}>{(o.persona && model(o.persona)) || o.model}</span>
                    </div>
                  </div>
                ))}
                <button type="button" className={styles.askLink} onClick={() => nav.open("all", r.id)}>
                  Ask the council about this →
                </button>
              </details>
            );
          })}
        </section>
      )}
    </div>
  );
}
