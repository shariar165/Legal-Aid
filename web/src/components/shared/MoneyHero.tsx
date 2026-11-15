"use client";

import type { ReactNode } from "react";
import type { AnalysisResult } from "@/lib/api";
import { DESK, num, type Lang } from "@/lib/desk/i18n";
import styles from "./moneyHero.module.css";

/* The money first (spec 20): what the worker was told, what the paper says, and what reaches their hand on paper,
   with the legal minimum as a line. Every number is the backend's (wage calculator, Four Ledgers); the frontend only
   draws them, and works out one display difference: told minus take-home on paper, in the same currency. */

const money = (currency: string, n: number) => `${currency} ${Math.round(n).toLocaleString("en-US")}`;

interface Bar {
  key: "said" | "paper" | "take";
  title: string;
  sub: string;
  value: string;
  /** % of the scale, or null when the amount is in another currency and is not drawn to scale */
  width: number | null;
  delta: string | null;
}

interface Props {
  result: AnalysisResult;
  lang: Lang;
  layout: "desk" | "phone";
  /** top-right corner, e.g. the language toggle */
  corner?: ReactNode;
  /** the chips under the headline */
  chips?: ReactNode;
  /** under the bars: the projection strip, or the button to add what was said */
  children?: ReactNode;
  headingId?: string;
}

export function MoneyHero({ result, lang, layout, corner, chips, children, headingId }: Props) {
  const T = DESK.hero;
  const w = result.wage;
  const four = result.four_ledgers;
  const said = four?.rows.find((r) => r.term === "salary")?.said ?? null;
  const saidComparable = !!(w && said?.amount != null && said.currency === w.currency);
  const termMonths = four?.rows.find((r) => r.term === "contract_months")?.paper?.amount ?? four?.claim_projection.term?.months ?? null;
  const live = result.risks.filter((r) => r.status !== "dropped").length;

  let headline: ReactNode;
  if (w && saidComparable && said?.amount != null) {
    const less = said.amount - w.net;
    headline = less > 0 ? (
      <>
        {T.toldLess[lang][0]}
        <span className={styles.amount}>{money(w.currency, less)}</span>
        {T.toldLess[lang][1]}
      </>
    ) : (
      T.toldMet[lang]
    );
  } else if (w) {
    headline =
      w.monthly_deductions > 0 ? (
        <>
          {T.deducted[lang][0]}
          <span className={styles.amount}>{money(w.currency, w.monthly_deductions)}</span>
          {T.deducted[lang][1]}
        </>
      ) : (
        T.nothingDeducted[lang]
      );
  } else {
    headline = T.risks(live, lang);
  }

  const bars: Bar[] = [];
  let minAt: number | null = null;
  if (w) {
    const scale = Math.max(saidComparable && said?.amount ? said.amount : 0, w.promised, w.minimum_wage ?? 0) || 1;
    const pct = (n: number) => Math.max(0, Math.min(100, (100 * n) / scale));
    if (said?.amount != null && said.currency) {
      bars.push({ key: "said", title: T.said[lang], sub: T.saidSub[lang], value: money(said.currency, said.amount), width: saidComparable ? pct(said.amount) : null, delta: null });
    }
    const gap = four?.promise_gap;
    bars.push({
      key: "paper",
      title: T.paper[lang],
      sub: T.paperSub[lang],
      value: money(w.currency, w.promised),
      width: pct(w.promised),
      delta: gap && saidComparable ? `− ${money(gap.currency, gap.monthly)}` : null,
    });
    bars.push({
      key: "take",
      title: T.takeHome[lang],
      sub: T.takeHomeSub[lang],
      value: money(w.currency, w.net),
      width: pct(w.net),
      delta: w.monthly_deductions > 0 ? `− ${money(w.currency, w.monthly_deductions)}` : null,
    });
    if (w.minimum_wage != null) minAt = pct(w.minimum_wage);
  }
  const steps = four?.break_even?.steps ?? [];

  const eyebrow = [result.destination?.name[lang], termMonths ? T.term(termMonths, lang) : null].filter(Boolean).join(" · ");

  return (
    <section className={styles.hero} data-layout={layout} aria-labelledby={headingId} lang={lang}>
      <div className={styles.lead}>
        <div className={styles.eyebrowRow}>
          {eyebrow && <span className={styles.eyebrow}>{eyebrow}</span>}
          {corner}
        </div>
        <h1 id={headingId} className={styles.headline}>
          {headline}
        </h1>
        {chips && <div className={styles.chips}>{chips}</div>}
      </div>

      {bars.length > 0 && (
        <div className={styles.chart}>
          <ul className={styles.bars} aria-label={lang === "bn" ? "মাসিক বেতন" : "Monthly pay"}>
            {bars.map((b) => (
              <li key={b.key} className={styles.barRow}>
                <span className={styles.barLabel}>
                  <b>{b.title}</b>
                  <span>{b.sub}</span>
                </span>
                <span className={styles.barTrack} style={{ ["--w" as string]: `${b.width ?? 100}%` }}>
                  <span className={styles.bar} data-k={b.key} data-free={b.width === null}>
                    {b.value}
                  </span>
                  {b.delta && <span className={styles.delta}>{b.delta}</span>}
                  {b.width === null && <span className={styles.offScale}>{T.otherCurrency[lang]}</span>}
                  {/* the legal minimum, drawn in every track so it lines up with the bars on both layouts */}
                  {minAt !== null && <span className={styles.minLine} style={{ left: `${minAt}%` }} aria-hidden="true" />}
                </span>
              </li>
            ))}
          </ul>
          {w?.minimum_wage != null && (
            <span className={styles.minTag}>
              {T.minimum[lang]} {money(w.currency, w.minimum_wage)}
            </span>
          )}
          {steps.length > 1 && w && (
            <p className={styles.steps}>
              {T.stepsLead[lang]}:{" "}
              {steps.map((s, i) => (
                <span key={s.from_month}>
                  {i > 0 && " · "}
                  {T.stepFrom(s.from_month, s.to_month, lang)} {money(w.currency, s.net)}
                </span>
              ))}
            </p>
          )}
        </div>
      )}

      {children && <div className={styles.foot}>{children}</div>}
    </section>
  );
}

/** A count chip for the hero: a serif number and a label. */
export function HeroChip({ n, label, lang, tone }: { n: number; label: string; lang: Lang; tone?: "bad" }) {
  return (
    <span className={styles.chip} data-tone={tone}>
      <b>{num(n, lang)}</b> {label}
    </span>
  );
}
