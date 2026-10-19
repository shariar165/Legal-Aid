"use client";

import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import {
  api,
  type AnalysisResult,
  type BenchOpinion,
  type BenchResult,
  type ChatTurn,
  type CouncilLanguage,
  type CouncilMember,
  type CouncilReply,
  type CouncilRuling,
  type PersonaId,
  type Section,
} from "@/lib/api";
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
const ROLE_LINE: Record<PersonaId, string> = {
  happy: "Looks for the fix",
  proud: "Reads the statute strictly",
  gloomy: "Asks what can go wrong",
};
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

/* ------------------------------------------------------------------ copy */

const COPY = {
  en: {
    whole: ["Should I sign this contract as it stands?", "What should I negotiate first?", "Where do you disagree with each other, and why?"],
    risk: ["How do I fix this clause?", "What happens if I sign it anyway?", "How serious is this, really?"],
    placeholder: (who: string, phone: boolean) => (phone ? `Ask ${who}…` : `Ask ${who} a question…`),
  },
  bn: {
    whole: ["এই চুক্তিতে কি এখনই সই করা উচিত?", "আগে কোন শর্ত নিয়ে দর-কষাকষি করব?", "আপনারা কোথায় একমত নন, আর কেন?"],
    risk: ["এই শর্তটি কীভাবে ঠিক করব?", "তবুও সই করলে কী হতে পারে?", "এটা আসলে কতটা গুরুতর?"],
    placeholder: (_who: string, phone: boolean) => (phone ? "বাংলায় প্রশ্ন করুন…" : "কাউন্সিলকে বাংলায় প্রশ্ন করুন…"),
  },
} as const;

/* the phone breakpoint from counsel.module.css: the composer is one short line there, so its placeholder must be too */
const PHONE = "(max-width: 640px)";

function useIsPhone() {
  return useSyncExternalStore(
    (onChange) => {
      const mq = window.matchMedia(PHONE);
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    },
    () => window.matchMedia(PHONE).matches,
    () => false,
  );
}

const AGREEMENT: Record<CouncilRuling["agreement"], { label: string; detail: string; votes: number }> = {
  unanimous: { label: "Unanimous", detail: "All three members agree", votes: 3 },
  majority: { label: "Majority", detail: "Two of three members agree", votes: 2 },
  split: { label: "Split", detail: "The members did not agree", votes: 1 },
};

const CONFIDENCE_LABEL = { high: "High confidence", medium: "Medium confidence", low: "Low confidence" } as const;

/* ------------------------------------------------------------------ state */

interface Exchange {
  id: number;
  question: string;
  members: PersonaId[];
  riskId: string | null;
  topic: string;
  language: CouncilLanguage;
  round1: CouncilReply[];
  round2: CouncilReply[];
  ruling: CouncilRuling | null;
  status: "asking" | "answered" | "deliberating" | "ruled";
}

function historyOf(exchanges: Exchange[]): ChatTurn[] {
  const turns: ChatTurn[] = [];
  for (const x of exchanges) {
    if (x.status === "asking") continue;
    turns.push({ speaker: "user", text: x.question });
    for (const r of [...x.round1, ...x.round2]) turns.push({ speaker: r.member, text: (r.position ? `${r.position}. ` : "") + r.text });
  }
  return turns.slice(-8);
}

function errorText(e: unknown) {
  const err = (e as Error).message.replace(/^\d+: /, "");
  return err === "Failed to fetch" ? "The analysis server is not reachable." : err;
}

/* ------------------------------------------------------------------ Panel */

export function CouncilPanel({ result, nav }: { result: AnalysisResult; nav: CouncilNav }) {
  const [members, setMembers] = useState<CouncilMember[]>(PERSONA_IDS.map((p) => FALLBACK[p]));
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [language, setLanguage] = useState<CouncilLanguage>("en");
  const phone = useIsPhone();
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
    const log = logRef.current;
    if (!log || log.offsetParent === null) return; // the panel stays mounted (hidden) while other views show
    if (log.scrollHeight > log.clientHeight + 4) {
      // desktop: the log is its own scroll box; scroll it, never the page
      log.scrollTo({ top: log.scrollHeight, behavior: "smooth" });
    } else if (exchanges.length) {
      // phone: the conversation flows with the page; bring the newest part into view above the composer
      const last = log.lastElementChild?.lastElementChild;
      last?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [exchanges, error]);

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

  const busy = exchanges.some((x) => x.status === "asking" || x.status === "deliberating");
  const who = nav.target === "all" ? "the entire council" : FALLBACK[nav.target].name;
  const topic = nav.riskId ? (live.find((r) => r.id === nav.riskId)?.title.en ?? "this risk") : "the whole contract";
  const model = (id: PersonaId) => members.find((m) => m.id === id)?.model;
  const prompts = nav.riskId ? COPY[language].risk : COPY[language].whole;

  const patch = (id: number, p: Partial<Exchange>) => setExchanges((cur) => cur.map((x) => (x.id === id ? { ...x, ...p } : x)));

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;
    const targets = nav.target === "all" ? PERSONA_IDS : [nav.target];
    const id = nextId.current++;
    const history = historyOf(exchanges);
    setError(null);
    setExchanges((cur) => [
      ...cur,
      { id, question: message, members: targets, riskId: nav.riskId, topic, language, round1: [], round2: [], ruling: null, status: "asking" },
    ]);
    setDraft("");
    try {
      const { replies } = await api.councilChat(result.job_id, { message, members: targets, risk_id: nav.riskId, history, language });
      patch(id, { round1: replies, status: "answered" });
    } catch (e) {
      // a rejected question (e.g. it contained an identifier) must not stay in the history sent with the next one
      setExchanges((cur) => cur.filter((x) => x.id !== id));
      setError(errorText(e));
      setDraft(message);
    }
  };

  const deliberate = async (x: Exchange) => {
    if (busy) return;
    setError(null);
    patch(x.id, { status: "deliberating" });
    try {
      const history = historyOf(exchanges.filter((e) => e.id < x.id));
      const { rebuttals, ruling } = await api.councilDeliberate(result.job_id, {
        message: x.question,
        replies: x.round1,
        risk_id: x.riskId,
        history,
        language: x.language,
      });
      patch(x.id, { round2: rebuttals, ruling, status: "ruled" });
    } catch (e) {
      patch(x.id, { status: "answered" });
      setError(errorText(e));
    }
  };

  const reviewed = benched.length;
  const unanimous = benched.filter((r) => !r.bench!.opinions.some((o) => dissents(o, r.bench!))).length;
  const flagged = benched.filter((r) => r.bench!.human_review).length;

  return (
    <div className={styles.council}>
      <header className={styles.viewHead}>
        <h1 className={styles.viewTitle}>Ask the council</h1>
        <p className={`${styles.viewLead} ${styles.longOnly}`}>
          Three AI reviewers from different model families, each with a different temperament. Ask a question, then let them deliberate: they answer
          each other and the Chief Justice writes a ruling. They may only cite law that passed verification.
        </p>
        <p className={`${styles.viewLead} ${styles.shortOnly}`}>Ask a question, then let the three members deliberate. They cite only verified law.</p>
      </header>

      <div className={styles.councilGrid}>
        {/* ---------------- who answers and about what */}
        <aside className={styles.rail} aria-label="Council settings">
          <p className={`${styles.railLabel} ${styles.labelSm}`} id="council-who">
            Who answers
          </p>
          <div className={styles.memberList} role="radiogroup" aria-labelledby="council-who">
            <button type="button" role="radio" aria-checked={nav.target === "all"} className={styles.member} onClick={() => nav.setTarget("all")}>
              <span className={styles.memberAll}>
                <Icon name="users" size={18} />
              </span>
              <span className={styles.memberText}>
                <b>
                  <span className={styles.longOnly}>Entire council</span>
                  <span className={styles.shortOnly}>All</span>
                </b>
                <span>All three answer, then they can deliberate</span>
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
                  <span>{ROLE_LINE[m.id]}</span>
                  {m.model && <code title={m.model}>{m.model}</code>}
                </span>
              </button>
            ))}
          </div>

          <label className={styles.topic}>
            <span className={`${styles.railLabel} ${styles.labelSm}`}>Topic</span>
            <select value={nav.riskId ?? ""} onChange={(e) => nav.setRiskId(e.target.value || null)}>
              <option value="">The whole contract</option>
              {live.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.title.en}
                </option>
              ))}
            </select>
          </label>

          <div className={`${styles.topic} ${styles.langBox}`}>
            <span className={`${styles.railLabel} ${styles.labelSm}`} id="council-lang">
              Answer language
            </span>
            <div className={styles.langSwitch} role="radiogroup" aria-labelledby="council-lang">
              <button type="button" role="radio" aria-checked={language === "en"} aria-label="English" onClick={() => setLanguage("en")}>
                <span className={styles.longOnly}>English</span>
                <span className={styles.shortOnly}>EN</span>
              </button>
              <button type="button" role="radio" aria-checked={language === "bn"} lang="bn" aria-label="বাংলা" onClick={() => setLanguage("bn")}>
                বাংলা
              </button>
            </div>
          </div>

          {reviewed > 0 && (
            <div className={styles.railRecord}>
              <span className={styles.railLabel}>Council record</span>
              <dl>
                <div>
                  <dt>Serious risks reviewed</dt>
                  <dd>{reviewed}</dd>
                </div>
                <div>
                  <dt>Unanimous</dt>
                  <dd>{unanimous}</dd>
                </div>
                <div data-tone={flagged ? "warn" : undefined}>
                  <dt>Flagged for human review</dt>
                  <dd>{flagged}</dd>
                </div>
              </dl>
            </div>
          )}
        </aside>

        {/* ---------------- conversation */}
        <section id="council-chat" className={styles.chat} aria-label="Council conversation">
          <div className={styles.chatHead}>
            <Icon name="message" size={16} />
            <span>
              Asking <b>{who}</b> about <b>{topic}</b>
              {language === "bn" && (
                <span className={styles.chatLang} lang="bn">
                  বাংলায় উত্তর
                </span>
              )}
            </span>
          </div>

          <div ref={logRef} className={styles.chatLog} aria-live="polite">
            {exchanges.length === 0 && (
              <div className={styles.emptyChat}>
                <CouncilFaces size={40} />
                <p className={styles.emptyTitle}>The council is ready</p>
                <p>Pick a starting question, or write your own below. With the entire council, you can then ask them to deliberate.</p>
                <div className={styles.prompts}>
                  {prompts.map((p) => (
                    <button key={p} type="button" className={styles.prompt} lang={language} onClick={() => void send(p)}>
                      <Icon name="sparkle" size={16} />
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {exchanges.map((x) => (
              <ExchangeView key={x.id} x={x} sections={sections} busy={busy} onDeliberate={() => void deliberate(x)} />
            ))}

            {error && (
              <p className={styles.errorBox} role="alert">
                <Icon name="alert" size={16} />
                {error}
              </p>
            )}
          </div>

          <form
            className={styles.composer}
            onSubmit={(e) => {
              e.preventDefault();
              void send(draft);
            }}
          >
            {exchanges.length > 0 && (
              <div className={styles.quickRow} aria-label="Suggested questions">
                {prompts.map((p) => (
                  <button key={p} type="button" className={styles.quick} lang={language} disabled={busy} onClick={() => void send(p)}>
                    {p}
                  </button>
                ))}
              </div>
            )}
            <div className={styles.composerBox}>
              <textarea
                ref={boxRef}
                value={draft}
                rows={1}
                maxLength={1000}
                lang={language}
                placeholder={COPY[language].placeholder(who, phone)}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void send(draft);
                  }
                }}
                aria-label="Your question to the council"
              />
              <button type="submit" className={styles.sendBtn} disabled={!draft.trim() || busy} aria-label="Send question">
                <Icon name="send" size={18} />
              </button>
            </div>
            <p className={styles.composerNote}>
              <Icon name="lock" size={13} />
              <span>
                Don&apos;t type names, phone numbers or ID numbers.<span className={styles.longOnly}> Enter to send, Shift+Enter for a new line.</span>{" "}
                Information only, not formal legal advice.
              </span>
            </p>
          </form>
        </section>
      </div>

      {/* ---------------- past votes */}
      {benched.length > 0 && (
        <section className={styles.votes} aria-labelledby="votes-title">
          <div className={styles.sectionHead}>
            <h2 id="votes-title" className={styles.sectionTitle}>
              How the council voted on each serious risk
            </h2>
            <span className={styles.sectionMeta}>
              {unanimous} of {reviewed} unanimous{flagged ? ` · ${flagged} flagged for human review` : ""}
            </span>
          </div>
          <div className={styles.voteTable}>
            <div className={styles.voteHeadRow} aria-hidden="true">
              <span>Risk</span>
              {PERSONA_IDS.map((p) => (
                <span key={p} className={styles.voteHeadMember} data-persona={p}>
                  <CouncilAvatar persona={p} size={20} />
                  {FALLBACK[p].name}
                </span>
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
                            <span className={styles.sevPill} data-sev={o.severity} title={`${FALLBACK[p].name}: ${SEVERITY_LABEL[o.severity]}`}>
                              <span className={styles.voteWho}>
                                <CouncilAvatar persona={p} size={18} />
                              </span>
                              {SEVERITY_LABEL[o.severity]}
                            </span>
                          ) : (
                            "—"
                          )}
                        </span>
                      );
                    })}
                    <span className={styles.voteOutcome} data-split={against.length > 0}>
                      {against.length ? (
                        <>
                          <Icon name="flag" size={13} />
                          {b.vote} · {against.join(" & ")} dissented
                        </>
                      ) : (
                        <>
                          <Icon name="check" size={13} />
                          Unanimous {b.vote}
                        </>
                      )}
                    </span>
                  </summary>
                  <div className={styles.voteBody}>
                    <p className={styles.majority}>
                      <b>Majority opinion.</b> {b.majority_opinion}
                    </p>
                    {b.dissent && (
                      <p className={styles.dissentNote}>
                        <Icon name="flag" size={14} />
                        <span>
                          <b>Dissent.</b> {b.dissent} This risk is flagged for a human lawyer to review.
                        </span>
                      </p>
                    )}
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

/* ------------------------------------------------------------------ one question and its answers */

function ExchangeView({ x, sections, busy, onDeliberate }: { x: Exchange; sections: Map<string, Section>; busy: boolean; onDeliberate: () => void }) {
  const many = x.members.length > 1;
  return (
    <div className={styles.exchange}>
      <div className={styles.msgUserWrap}>
        <p className={styles.msgUser} lang={x.language}>
          {x.question}
        </p>
        {x.riskId && <span className={styles.msgTopic}>About: {x.topic}</span>}
      </div>

      {many && x.status !== "asking" && <RoundLabel n={1} text="First answers" />}
      {x.status === "asking" ? (
        <Thinking members={x.members} />
      ) : (
        x.round1.map((r) => <ReplyCard key={`1-${r.member}`} r={r} sections={sections} lang={x.language} />)
      )}

      {many && x.status === "answered" && (
        <div className={styles.deliberateBar}>
          <span>
            <b>Want a single answer?</b> Let the members respond to each other, then the Chief Justice writes the council&apos;s ruling.
          </span>
          <button type="button" className={styles.primaryBtn} disabled={busy} onClick={onDeliberate}>
            <Icon name="gavel" size={16} />
            Hold a deliberation
          </button>
        </div>
      )}

      {(x.status === "deliberating" || x.status === "ruled") && <RoundLabel n={2} text="Deliberation · the members answer each other" />}
      {x.status === "deliberating" && <Thinking members={x.members} />}
      {x.status === "ruled" && (
        <>
          {x.round2.map((r) => (
            <ReplyCard key={`2-${r.member}`} r={r} sections={sections} lang={x.language} />
          ))}
          {x.ruling && <RulingCard ruling={x.ruling} sections={sections} lang={x.language} />}
        </>
      )}
    </div>
  );
}

function RoundLabel({ n, text }: { n: number; text: string }) {
  return (
    <div className={styles.roundLabel}>
      <span>Round {n}</span>
      {text}
    </div>
  );
}

function Thinking({ members }: { members: PersonaId[] }) {
  return (
    <>
      {members.map((p) => (
        <div key={p} className={styles.msg} data-persona={p}>
          <CouncilAvatar persona={p} size={32} />
          <span className={styles.typing} aria-label={`${FALLBACK[p].name} is thinking`}>
            <i />
            <i />
            <i />
          </span>
        </div>
      ))}
    </>
  );
}

function Cites({ ids, sections }: { ids: string[]; sections: Map<string, Section> }) {
  if (!ids.length) return null;
  return (
    <div className={styles.msgCites}>
      {ids.map((c) => {
        const s = sections.get(c);
        return s ? (
          <a key={c} href={s.url || undefined} target="_blank" rel="noreferrer" className={styles.citeChip} data-verdict="verified" title="Verified section · opens the official text">
            <Icon name="scale" size={13} />
            {citeLabel(s)}
            <Icon name="external" size={12} />
          </a>
        ) : (
          <code key={c} className={styles.citeChip}>
            {c}
          </code>
        );
      })}
    </div>
  );
}

function ReplyCard({ r, sections, lang }: { r: CouncilReply; sections: Map<string, Section>; lang: CouncilLanguage }) {
  return (
    <article className={styles.msg} data-persona={r.member}>
      <span className={styles.msgAvatar}>
        <CouncilAvatar persona={r.member} size={32} />
      </span>
      <div className={styles.msgBody}>
        <div className={styles.msgMeta}>
          <span className={styles.metaAvatar}>
            <CouncilAvatar persona={r.member} size={24} />
          </span>
          <p className={styles.msgName}>
            {FALLBACK[r.member].name} <span>{TEMPERAMENT[r.member]}</span>
          </p>
          {r.round === 2 && r.responds_to && (
            <span className={styles.respondsTo}>
              <Icon name="cornerDownRight" size={13} />
              to {FALLBACK[r.responds_to].name}
            </span>
          )}
          {r.round === 2 && (
            <span className={styles.stanceTag} data-revised={r.revised}>
              {r.revised ? "Changed position" : "Kept position"}
            </span>
          )}
          <span className={styles.confidence} data-level={r.confidence} title={CONFIDENCE_LABEL[r.confidence]}>
            <i />
            <i />
            <i />
            <span>{CONFIDENCE_LABEL[r.confidence]}</span>
          </span>
        </div>
        {r.position && (
          <p className={styles.msgPosition} lang={lang}>
            {r.position}
          </p>
        )}
        <p className={styles.msgText} lang={lang}>
          {r.text}
        </p>
        <Cites ids={r.citations} sections={sections} />
      </div>
    </article>
  );
}

function RulingCard({ ruling, sections, lang }: { ruling: CouncilRuling; sections: Map<string, Section>; lang: CouncilLanguage }) {
  const [copied, setCopied] = useState(false);
  const a = AGREEMENT[ruling.agreement];
  const copy = async () => {
    const lines = [
      `Council ruling (${a.label})`,
      ruling.consensus,
      ...ruling.disagreements.map((d) => `In dispute: ${d.point}`),
      `Next step: ${ruling.next_step}`,
    ];
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard blocked; nothing to do */
    }
  };
  return (
    <section className={styles.ruling} data-agreement={ruling.agreement} aria-label="The Chief Justice's ruling">
      <header className={styles.rulingHead}>
        <span className={styles.rulingSeal} aria-hidden="true">
          <Icon name="gavel" size={18} />
        </span>
        <span className={styles.rulingTitle}>
          <b>The council&apos;s ruling</b>
          <span>Written by the Chief Justice from both rounds</span>
        </span>
        <span className={styles.agreement} data-agreement={ruling.agreement} title={a.detail}>
          <span className={styles.agreementDots} aria-hidden="true">
            {[0, 1, 2].map((i) => (
              <i key={i} data-on={i < a.votes} />
            ))}
          </span>
          {a.label}
        </span>
      </header>

      <p className={styles.rulingConsensus} lang={lang}>
        {ruling.consensus}
      </p>

      {ruling.disagreements.length > 0 && (
        <div className={styles.rulingBlock}>
          <span className={styles.insetLabel}>Still in dispute</span>
          <ul className={styles.disputes}>
            {ruling.disagreements.map((d) => (
              <li key={d.point}>
                <span className={styles.disputeWho}>
                  {d.members.map((m) => (
                    <CouncilAvatar key={m} persona={m} size={20} />
                  ))}
                </span>
                <span lang={lang}>{d.point}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className={styles.nextStep}>
        <Icon name="arrowRight" size={16} />
        <span>
          <b>Next step</b>
          <span lang={lang}>{ruling.next_step}</span>
        </span>
      </div>

      <Cites ids={ruling.citations} sections={sections} />

      <footer className={styles.rulingFoot}>
        {ruling.model && <code className={styles.judgeModel}>Chief Justice · {ruling.model}</code>}
        <button type="button" className={styles.linkBtn} onClick={() => void copy()}>
          <Icon name={copied ? "check" : "copy"} size={14} />
          {copied ? "Copied" : "Copy ruling"}
        </button>
      </footer>
    </section>
  );
}
