"use client";

import { useCallback, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { api, type AnalysisResult } from "@/lib/api";
import { DESK, type Lang } from "@/lib/desk/i18n";
import { deskRows, firstRow } from "@/lib/desk/rows";
import { HeroChip, MoneyHero } from "@/components/shared/MoneyHero";
import { Icon } from "@/components/shared/Icons";
import { ChainRows } from "./ChainRows";
import { ContractPane } from "./ContractPane";
import { EvidenceFile } from "./EvidenceFile";
import { MoneyStrip } from "./MoneyStrip";
import { PromiseForm } from "./PromiseForm";
import s from "./desk.module.css";

/* The Case Desk (spec 20): the money first, then three panes driven by one selection. The contract on the left, the
   chain rows (told · paper · paid · law) in the middle, the evidence file for the selected row on the right. */

const WIDE = "(min-width: 1100px)";

function useWide() {
  return useSyncExternalStore(
    (onChange) => {
      const mq = window.matchMedia(WIDE);
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    },
    () => window.matchMedia(WIDE).matches,
    () => true,
  );
}

interface Props {
  result: AnalysisResult;
  /** refetch the saved result after a change on the server */
  reload: () => Promise<void>;
  /** open the Council on one risk */
  onAsk: (riskId: string) => void;
  /** a clause to open on (e.g. "Show in the contract" from the memo) */
  clause?: string | null;
}

export function CaseDesk({ result, reload, onAsk, clause }: Props) {
  const [lang, setLang] = useState<Lang>("bn");
  const rows = useMemo(() => deskRows(result), [result]);
  const [picked, setPicked] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wide = useWide();
  const evidenceRef = useRef<HTMLElement>(null);

  // a clause asked for from elsewhere selects the row that holds it
  const fromClause = clause ? (rows.find((r) => r.clauseIds.includes(clause))?.key ?? null) : null;
  const selectedKey = picked && rows.some((r) => r.key === picked) ? picked : (fromClause ?? firstRow(rows));
  const selected = rows.find((r) => r.key === selectedKey) ?? null;

  const select = useCallback(
    (key: string) => {
      setPicked(key);
      if (!wide) requestAnimationFrame(() => evidenceRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    },
    [wide],
  );

  const four = result.four_ledgers ?? null;
  const pending = !!four?.pending_risks.length;
  const mismatches = four?.rows.reduce((n, r) => n + r.mismatches.length, 0) ?? 0;

  const verify = async () => {
    setVerifying(true);
    setError(null);
    try {
      await api.verifyPromises(result.job_id);
      await reload();
    } catch (e) {
      setError((e as Error).message.replace(/^\d+: /, ""));
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className={s.desk} lang={lang}>
      <MoneyHero
        result={result}
        lang={lang}
        layout="desk"
        headingId="desk-title"
        corner={
          <div className={s.langToggle} role="group" aria-label={DESK.langGroup[lang]}>
            <button type="button" lang="bn" aria-pressed={lang === "bn"} onClick={() => setLang("bn")}>
              বাংলা
            </button>
            <button type="button" lang="en" aria-pressed={lang === "en"} onClick={() => setLang("en")}>
              EN
            </button>
          </div>
        }
        chips={
          four && (
            <>
              <HeroChip n={four.rows.length} label={DESK.hero.terms[lang]} lang={lang} />
              <HeroChip n={mismatches} label={DESK.hero.mismatches[lang]} lang={lang} />
            </>
          )
        }
      >
        {four ? (
          <MoneyStrip result={result} lang={lang} reload={reload} onAddSaid={() => setFormOpen(true)} formOpen={formOpen} />
        ) : (
          <p className={s.flagOff}>
            <Icon name="info" size={16} />
            {DESK.hero.flagOff[lang]}
          </p>
        )}
      </MoneyHero>

      {four && formOpen && (
        <PromiseForm
          result={result}
          lang={lang}
          onClose={() => setFormOpen(false)}
          onSaved={async () => {
            await reload();
            setFormOpen(false);
          }}
        />
      )}

      {pending && (
        <div className={s.pendingBanner} role="status">
          <Icon name="alert" size={18} />
          <p>{DESK.rows.pendingBanner[lang]}</p>
          <button type="button" className={s.btnPrimary} onClick={verify} disabled={verifying}>
            <Icon name="shieldCheck" size={18} />
            {verifying ? DESK.rows.verifying[lang] : DESK.rows.verify[lang]}
          </button>
        </div>
      )}
      {error && (
        <p className={s.error} role="alert">
          <Icon name="alert" size={16} />
          {error}
        </p>
      )}

      <div className={s.panes}>
        <ContractPane result={result} rows={rows} selected={selected} onSelect={select} lang={lang} wide={wide} />
        <ChainRows result={result} rows={rows} selectedKey={selectedKey} onSelect={select} lang={lang} hasPromises={!!four?.promises} ledgerOn={!!four} />
        <EvidenceFile
          ref={evidenceRef}
          result={result}
          row={selected}
          lang={lang}
          onAsk={onAsk}
          onVerify={verify}
          verifying={verifying}
        />
      </div>
    </div>
  );
}
