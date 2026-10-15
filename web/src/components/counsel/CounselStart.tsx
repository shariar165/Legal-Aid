"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, type Health, type Sample } from "@/lib/api";
import styles from "./counsel.module.css";

export function CounselStart() {
  const router = useRouter();
  const [health, setHealth] = useState<Health | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    Promise.all([api.health(), api.samples()])
      .then(([h, s]) => {
        setHealth(h);
        setSamples(s);
      })
      .catch(() => setError("The analysis server is not reachable at the configured address. Start the backend and reload."));
  }, []);

  const go = async (run: () => Promise<{ job_id: string }>, key: string) => {
    setBusy(key);
    setError(null);
    try {
      const job = await run();
      router.push(`/counsel/${job.job_id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(null);
    }
  };

  return (
    <div className={styles.page}>
      <header className={styles.topbar}>
        <Link href="/" className={styles.brand}>
          <span className={styles.brandMark}>আ</span>
          <span>
            Ain Copilot <span className={styles.brandSub}>Counsel mode</span>
          </span>
        </Link>
        {health && (
          <div className={styles.healthRow}>
            <span className={styles.chip} data-tone={health.llm_mode === "live" ? "ok" : "warn"}>
              LLM: {health.llm_mode === "fake" ? "offline demo" : health.llm_mode}
            </span>
            <span className={styles.chip}>{health.corpus_sections.toLocaleString()} sections · {health.acts} instruments</span>
            <span className={styles.chip} data-tone={health.providers.groq ? "ok" : undefined}>Groq {health.providers.groq ? "✓" : "–"}</span>
            <span className={styles.chip} data-tone={health.providers.openrouter ? "ok" : undefined}>OpenRouter {health.providers.openrouter ? "✓" : "–"}</span>
          </div>
        )}
      </header>

      <main className={styles.startMain}>
        <section className={styles.hero}>
          <h1 className={styles.heroTitle}>Every legal claim, verified against the statute book.</h1>
          <p className={styles.heroLead}>
            Ten agents read the contract, route it to the right legal regime, hunt for non-obvious risks and draft a memorandum.
            A claim reaches the memo only after four gates confirm the section exists, applies, says what we claim, and is still in force.
            High-stakes claims go before a three-judge Virtual Bench.
          </p>
        </section>

        {error && <p className={styles.errorBox}>{error}</p>}

        <section className={styles.startGrid} aria-label="Choose a document">
          {samples.map((s) => (
            <button key={s.id} type="button" className={styles.sampleCard} disabled={!!busy} onClick={() => go(() => api.analyzeSample(s.id), s.id)}>
              <span className={styles.sampleKind}>{s.kind === "image" ? "Phone photo · OCR" : "Document"}</span>
              <span className={styles.sampleTitle}>{s.title.en}</span>
              <span className={styles.sampleBn} lang="bn">
                {s.title.bn}
              </span>
              <span className={styles.sampleSubline}>{s.subtitle.en}</span>
              <span className={styles.sampleGo}>{busy === s.id ? "Starting…" : "Analyse →"}</span>
            </button>
          ))}
          <button type="button" className={styles.sampleCard} data-upload disabled={!!busy} onClick={() => input.current?.click()}>
            <span className={styles.sampleKind}>Your document</span>
            <span className={styles.sampleTitle}>Upload a contract</span>
            <span className={styles.sampleSubline}>PDF, DOCX, TXT or a photo. Personal identifiers are redacted before any model sees the text.</span>
            <span className={styles.sampleGo}>{busy === "upload" ? "Uploading…" : "Choose file →"}</span>
          </button>
          <input
            ref={input}
            type="file"
            hidden
            accept=".pdf,.docx,.txt,image/*"
            onChange={(e) => {
              const f = e.target.files?.[0];
              e.target.value = "";
              if (f) void go(() => api.analyzeFile(f), "upload");
            }}
          />
        </section>
      </main>
    </div>
  );
}
