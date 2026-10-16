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
        <div className={styles.topRow}>
          <Link href="/" className={styles.brand}>
            <span className={styles.brandMark}>আ</span>
            <span>Ain Copilot</span>
          </Link>
          {health && health.llm_mode !== "live" && (
            <span className={styles.chip} data-tone="warn" title="No AI provider key is set, so answers come from saved or offline responses">
              {health.llm_mode === "fake" ? "Offline demo" : "Replay"}
            </span>
          )}
        </div>
      </header>

      <main className={styles.startMain}>
        <section className={styles.hero}>
          <h1 className={styles.heroTitle}>Check a contract for legal risks</h1>
          <p className={styles.heroLead}>
            Upload a contract or try a sample. You get a plain-language memo of the risks, each backed by a law we have checked
            against the statute book, and you can ask a council of three AI reviewers about it.
          </p>
        </section>

        {error && <p className={styles.errorBox}>{error}</p>}

        <section className={styles.startGrid} aria-label="Choose a document">
          <button type="button" className={styles.sampleCard} data-upload disabled={!!busy} onClick={() => input.current?.click()}>
            <span className={styles.sampleKind}>Your document</span>
            <span className={styles.sampleTitle}>Upload a contract</span>
            <span className={styles.sampleSubline}>PDF, Word, text or a phone photo. Names and ID numbers are hidden before any AI sees it.</span>
            <span className={styles.sampleGo}>{busy === "upload" ? "Uploading…" : "Choose file →"}</span>
          </button>
          {samples.map((s) => (
            <button key={s.id} type="button" className={styles.sampleCard} disabled={!!busy} onClick={() => go(() => api.analyzeSample(s.id), s.id)}>
              <span className={styles.sampleKind}>{s.kind === "image" ? "Sample · phone photo" : "Sample"}</span>
              <span className={styles.sampleTitle}>{s.title.en}</span>
              <span className={styles.sampleBn} lang="bn">
                {s.title.bn}
              </span>
              <span className={styles.sampleSubline}>{s.subtitle.en}</span>
              <span className={styles.sampleGo}>{busy === s.id ? "Starting…" : "Try it →"}</span>
            </button>
          ))}
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
