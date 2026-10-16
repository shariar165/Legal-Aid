"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, type Health, type Sample } from "@/lib/api";
import { Icon, type IconName } from "./Icons";
import styles from "./counsel.module.css";

const TRUST: { icon: IconName; text: string }[] = [
  { icon: "shieldCheck", text: "Every citation checked against the statute book" },
  { icon: "lock", text: "Personal details hidden before any AI sees the text" },
  { icon: "users", text: "Reviewed by a council of three AI models" },
];

const STEPS = [
  { title: "Upload", text: "A PDF, Word file, text or a phone photo of the contract." },
  { title: "Verified analysis", text: "Agents find the risks; four checks prove the law behind each one." },
  { title: "Memo & council", text: "Download the memo, or question the council about any risk." },
];

export function CounselStart() {
  const router = useRouter();
  const [health, setHealth] = useState<Health | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
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

  const upload = (f: File | undefined) => {
    if (f && !busy) void go(() => api.analyzeFile(f), "upload");
  };

  return (
    <div className={styles.page}>
      <header className={styles.topbar}>
        <div className={styles.topRow}>
          <Link href="/" className={styles.brand} aria-label="Ain Copilot home">
            <span className={styles.brandMark}>আ</span>
            <span className={styles.brandText}>
              Ain Copilot <span>Counsel</span>
            </span>
          </Link>
          {health && health.llm_mode !== "live" && (
            <span className={styles.chip} data-tone="warn" title="No AI provider key is set, so answers come from saved or offline responses">
              {health.llm_mode === "fake" ? "Offline demo" : "Replay"}
            </span>
          )}
          <div className={styles.actions}>
            <Link href="/" className={styles.quietBtn}>
              Citizen app
            </Link>
          </div>
        </div>
      </header>

      <main className={styles.startMain}>
        <section className={styles.hero}>
          <p className={styles.kicker}>Counsel mode · Bangladesh &amp; migrant labour law</p>
          <h1 className={styles.heroTitle}>Review a contract for legal risk, with every citation verified.</h1>
          <p className={styles.heroLead}>
            Get a plain-language risk memo where each finding is backed by a statute we have checked, then discuss it with a council of three AI
            reviewers.
          </p>
          <ul className={styles.trust}>
            {TRUST.map((t) => (
              <li key={t.text}>
                <Icon name={t.icon} size={18} />
                {t.text}
              </li>
            ))}
          </ul>
        </section>

        {error && (
          <p className={styles.errorBox} role="alert">
            <Icon name="alert" size={16} />
            {error}
          </p>
        )}

        <button
          type="button"
          className={styles.dropzone}
          data-dragging={dragging}
          disabled={!!busy}
          onClick={() => input.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            upload(e.dataTransfer.files?.[0]);
          }}
        >
          <span className={styles.dropIcon}>
            <Icon name="upload" size={26} />
          </span>
          <span className={styles.dropTitle}>{busy === "upload" ? "Uploading…" : dragging ? "Drop to upload" : "Drop a contract here, or browse"}</span>
          <span className={styles.dropSub}>PDF, Word, plain text or a phone photo · names and ID numbers are hidden before any AI sees it</span>
          <span className={styles.secondaryBtn} aria-hidden="true">
            <Icon name="file" size={15} />
            Choose file
          </span>
        </button>
        <input
          ref={input}
          type="file"
          hidden
          accept=".pdf,.docx,.txt,image/*"
          onChange={(e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            upload(f);
          }}
        />

        {samples.length > 0 && (
          <section aria-labelledby="samples-title">
            <div className={styles.sectionHead}>
              <h2 id="samples-title" className={styles.sectionTitle}>
                Or try a sample contract
              </h2>
              <span className={styles.sectionMeta}>Real-world patterns, no personal data</span>
            </div>
            <div className={styles.startGrid}>
              {samples.map((s) => (
                <button key={s.id} type="button" className={styles.sampleCard} disabled={!!busy} onClick={() => go(() => api.analyzeSample(s.id), s.id)}>
                  <span className={styles.sampleKind}>
                    <Icon name={s.kind === "image" ? "camera" : "file"} size={13} />
                    {s.kind === "image" ? "Phone photo" : "Document"}
                  </span>
                  <span className={styles.sampleTitle}>{s.title.en}</span>
                  <span className={styles.sampleBn} lang="bn">
                    {s.title.bn}
                  </span>
                  <span className={styles.sampleSubline}>{s.subtitle.en}</span>
                  <span className={styles.sampleGo}>
                    {busy === s.id ? "Starting…" : "Analyse this sample"}
                    <Icon name="arrowRight" size={15} />
                  </span>
                </button>
              ))}
            </div>
          </section>
        )}

        <section aria-labelledby="how-title">
          <h2 id="how-title" className={styles.sectionTitle}>
            How it works
          </h2>
          <ol className={styles.howSteps}>
            {STEPS.map((s, i) => (
              <li key={s.title}>
                <span className={styles.howNum}>{i + 1}</span>
                <b>{s.title}</b>
                <span>{s.text}</span>
              </li>
            ))}
          </ol>
        </section>
      </main>
    </div>
  );
}
