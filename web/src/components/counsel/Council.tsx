"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api, type AnalysisResult, type BenchOpinion, type BenchResult, type ChatTurn, type CouncilMember, type PersonaId, type Section } from "@/lib/api";
import { citeLabel, SEVERITY_LABEL } from "./format";
import { Icon, type IconName } from "./Icons";
import styles from "./counsel.module.css";

/* The three council members. Names and titles mirror backend/ain/agents/bench.py PERSONAS;
   the API adds each member's live model. */
export const PERSONA_IDS: PersonaId[] = ["happy", "proud", "gloomy"];

const FALLBACK: Record<PersonaId, CouncilMember> = {
  happy: { id: "happy", name: "Sunny", title: "the Happy AI", tagline: "Every bad clause has a fix. Let's find it.", seat: "Justice A", model: "" },
  proud: { id: "proud", name: "Regal", title: "the Proud AI", tagline: "The text is clear. I have read it correctly.", seat: "Justice B", model: "" },
  gloomy: { id: "gloomy", name: "Grey", title: "the Gloomy AI", tagline: "Assume it will go wrong. It usually does.", seat: "Justice C", model: "" },
};

/* temperament in one word, shown under each name */
const TEMPERAMENT: Record<PersonaId, string> = { happy: "Optimist", proud: "Textualist", gloomy: "Sceptic" };
const GLYPH: Record<PersonaId, IconName> = { happy: "sun", proud: "shield", gloomy: "cloud" };

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

/* A monogram badge: initial on the persona's tint, with a small temperament glyph. */
export function CouncilAvatar({ persona, size = 36 }: { persona: PersonaId; size?: number }) {
  const m = FALLBACK[persona];
  const glyph = Math.max(10, Math.round(size * 0.42));
  return (
    <span
      className={styles.avatar}
      data-persona={persona}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.44) }}
      role="img"
      aria-label={`${m.name}, ${m.title}`}
    >
      {m.name[0]}
      {size >= 28 && (
        <span className={styles.avGlyph} style={{ width: glyph, height: glyph }} aria-hidden="true">
          <Icon name={GLYPH[persona]} size={glyph - 4} />
        </span>
      )}
    </span>
  );
}

/* Three overlapping badges, used in the toolbar and on risk cards. */
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

const PROMPTS = ["Should I sign this contract as it stands?", "What should I negotiate first?", "Where do you disagree with each other, and why?"];

export function CouncilPanel({ result, nav }: { result: AnalysisResult; nav: CouncilNav }) {
  const [members, setMembers] = useState<CouncilMember[]>(PERSONA_IDS.map((p) => FALLBACK[p]));
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [pending, setPending] = useState<PersonaId[]>([]);
  const [draft, setDraft] = useState("");
  const logRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLTextAreaElement>(null);
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

  useEffect(() => {
    // grow the composer with its content, up to the CSS max-height
    const box = boxRef.current;
    if (!box) return;
    box.style.height = "auto";
    // measuring while the panel is hidden gives 0, so an empty box keeps its natural one-row height
    if (draft && box.scrollHeight) box.style.height = `${box.scrollHeight}px`;
  }, [draft]);

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

  const who = nav.target === "all" ? "the entire council" : FALLBACK[nav.target].name;
  const topic = nav.riskId ? (live.find((r) => r.id === nav.riskId)?.title.en ?? "this risk") : "the whole contract";
  const model = (id: PersonaId) => members.find((m) => m.id === id)?.model;

  return (
    <div className={styles.council}>
      <header className={styles.viewHead}>
        <h1 className={styles.viewTitle}>Ask the council</h1>
        <p className={styles.viewLead}>
          Three AI reviewers with different temperaments discuss your contract. They may only cite law that passed verification, so every answer stays
          grounded in the statute.
        </p>
      </header>

      <div className={styles.councilGrid}>
        {/* ---------------- who answers and about what */}
        <aside className={styles.rail} aria-label="Council settings">
          <p className={styles.railLabel} id="council-who">
            Who answers
          </p>
          <div className={styles.memberList} role="radiogroup" aria-labelledby="council-who">
            <button type="button" role="radio" aria-checked={nav.target === "all"} className={styles.member} onClick={() => nav.setTarget("all")}>
              <span className={styles.memberAll}>
                <Icon name="users" size={18} />
              </span>
              <span className={styles.memberText}>
                <b>Entire council</b>
                <span>Hear all three views</span>
              </span>
            </button>
            {members.map((m) => (
              <button
                key={m.id}
                type="button"
                role="radio"
                aria-checked={nav.target === m.id}
                className={styles.member}
                data-persona={m.id}
                onClick={() => nav.setTarget(m.id)}
              >
                <CouncilAvatar persona={m.id} size={36} />
                <span className={styles.memberText}>
                  <b>
                    {m.name} <em>{TEMPERAMENT[m.id]}</em>
                  </b>
                  <span>{m.tagline}</span>
                  {m.model && <code>{m.model}</code>}
                </span>
              </button>
            ))}
          </div>

          <label className={styles.topic}>
            <span className={styles.railLabel}>Topic</span>
            <select value={nav.riskId ?? ""} onChange={(e) => nav.setRiskId(e.target.value || null)}>
              <option value="">The whole contract</option>
              {live.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.title.en}
                </option>
              ))}
            </select>
          </label>
        </aside>

        {/* ---------------- conversation */}
        <section id="council-chat" className={styles.chat} aria-label="Council conversation">
          <div className={styles.chatHead}>
            <Icon name="message" size={16} />
            <span>
              Asking <b>{who}</b> about <b>{topic}</b>
            </span>
          </div>

          <div ref={logRef} className={styles.chatLog} aria-live="polite">
            {msgs.length === 0 && pending.length === 0 && (
              <div className={styles.emptyChat}>
                <CouncilFaces size={40} />
                <p>Start with one of these, or write your own question below.</p>
                <div className={styles.prompts}>
                  {PROMPTS.map((p) => (
                    <button key={p} type="button" className={styles.prompt} onClick={() => void send(p)}>
                      <Icon name="sparkle" size={16} />
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {msgs.map((m) =>
              m.speaker === "user" ? (
                <p key={m.id} className={styles.msgUser}>
                  {m.text}
                </p>
              ) : m.speaker === "error" ? (
                <p key={m.id} className={styles.errorBox} role="alert">
                  <Icon name="alert" size={16} />
                  {m.text}
                </p>
              ) : (
                <article key={m.id} className={styles.msg} data-persona={m.speaker}>
                  <CouncilAvatar persona={m.speaker} size={32} />
                  <div className={styles.msgBody}>
                    <p className={styles.msgName}>
                      {FALLBACK[m.speaker].name} <span>{TEMPERAMENT[m.speaker]}</span>
                    </p>
                    <p className={styles.msgText}>{m.text}</p>
                    {!!m.citations?.length && (
                      <div className={styles.msgCites}>
                        {m.citations.map((c) => {
                          const s = sections.get(c);
                          return s ? (
                            <a key={c} href={s.url} target="_blank" rel="noreferrer" className={styles.citeChip} data-verdict="verified">
                              <Icon name="scale" size={13} />
                              {citeLabel(s)}
                            </a>
                          ) : (
                            <code key={c} className={styles.citeChip}>
                              {c}
                            </code>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </article>
              ),
            )}
            {pending.map((p) => (
              <div key={p} className={styles.msg} data-persona={p}>
                <CouncilAvatar persona={p} size={32} />
                <span className={styles.typing} aria-label={`${FALLBACK[p].name} is thinking`}>
                  <i />
                  <i />
                  <i />
                </span>
              </div>
            ))}
          </div>

          <form
            className={styles.composer}
            onSubmit={(e) => {
              e.preventDefault();
              void send(draft);
            }}
          >
            <div className={styles.composerBox}>
              <textarea
                ref={boxRef}
                value={draft}
                rows={1}
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
              <button type="submit" className={styles.sendBtn} disabled={!draft.trim() || pending.length > 0} aria-label="Send question">
                <Icon name="send" size={18} />
              </button>
            </div>
            <p className={styles.composerNote}>
              <Icon name="lock" size={13} />
              Don&apos;t type names, phone numbers or ID numbers. Enter to send, Shift+Enter for a new line. Information only, not formal legal advice.
            </p>
          </form>
        </section>
      </div>

      {/* ---------------- past votes */}
      {benched.length > 0 && (
        <section className={styles.votes} aria-labelledby="votes-title">
          <div className={styles.sectionHead}>
            <h2 id="votes-title" className={styles.sectionTitle}>
              How the council voted
            </h2>
            <span className={styles.sectionMeta}>{benched.length} serious {benched.length === 1 ? "risk" : "risks"} reviewed</span>
          </div>
          <div className={styles.voteTable}>
            <div className={styles.voteHeadRow} aria-hidden="true">
              <span>Risk</span>
              {PERSONA_IDS.map((p) => (
                <span key={p}>{FALLBACK[p].name}</span>
              ))}
              <span>Outcome</span>
            </div>
            {benched.map((r) => {
              const b = r.bench!;
              const against = b.opinions.filter((o) => dissents(o, b) && o.name).map((o) => o.name);
              return (
                <details key={r.id} className={styles.voteCase}>
                  <summary>
                    <span className={styles.voteTitle}>
                      <Icon name="chevronRight" size={16} className={styles.voteChevron} />
                      {r.title.en}
                    </span>
                    {PERSONA_IDS.map((p) => {
                      const o = b.opinions.find((x) => x.persona === p);
                      return (
                        <span key={p} className={styles.voteCell} data-dissent={o ? dissents(o, b) : undefined}>
                          {o ? (
                            <>
                              <span className={styles.voteWho}>{FALLBACK[p].name}: </span>
                              <span className={styles.sevDot} data-sev={o.severity} />
                              {SEVERITY_LABEL[o.severity]}
                            </>
                          ) : (
                            "—"
                          )}
                        </span>
                      );
                    })}
                    <span className={styles.voteOutcome} data-split={against.length > 0}>
                      {against.length ? `${against.join(" & ")} dissented` : "Unanimous"}
                    </span>
                  </summary>
                  <div className={styles.voteBody}>
                    <p className={styles.majority}>
                      <b>Majority opinion.</b> {b.majority_opinion}
                    </p>
                    {b.opinions.map((o) => (
                      <div key={o.seat} className={styles.opinion}>
                        {o.persona && <CouncilAvatar persona={o.persona} size={28} />}
                        <div>
                          <p className={styles.opinionHead}>
                            <b>{o.name || o.seat}</b> rated it <span className={styles.sevDot} data-sev={o.severity} />
                            {SEVERITY_LABEL[o.severity].toLowerCase()}
                            {o.revised && <span className={styles.revised}>Revised after deliberation</span>}
                          </p>
                          <p>{o.reasoning}</p>
                          <code className={styles.judgeModel}>{(o.persona && model(o.persona)) || o.model}</code>
                        </div>
                      </div>
                    ))}
                    <button type="button" className={styles.linkBtn} onClick={() => nav.open("all", r.id)}>
                      Discuss this risk with the council <Icon name="arrowRight" size={14} />
                    </button>
                  </div>
                </details>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
