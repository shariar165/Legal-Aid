"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { safeNext, useSession } from "@/lib/useSession";
import { Icon } from "./Icons";
import styles from "./counsel.module.css";

const COPY = {
  login: {
    title: "Sign in",
    lead: "Open your saved analyses and Counsel mode.",
    submit: "Sign in",
    busy: "Signing in…",
    switchText: "New here?",
    switchLink: "Create an account",
    switchHref: "/signup",
    password: "current-password",
  },
  signup: {
    title: "Create your account",
    lead: "Keep your analyses private to you and open them on any device.",
    submit: "Create account",
    busy: "Creating account…",
    switchText: "Already have an account?",
    switchLink: "Sign in",
    switchHref: "/login",
    password: "new-password",
  },
} as const;

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const t = COPY[mode];
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const { me } = useSession((m) => {
    if (m.kind === "account") router.replace(next);
  });
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await (mode === "login" ? api.login(email, password) : api.signup(email, password));
      router.replace(next);
    } catch (err) {
      const msg = (err as Error).message;
      setError(msg.includes("Failed to fetch") ? "The server is not reachable. Check that the backend is running, then try again." : msg.replace(/^\d+: /, ""));
      setBusy(false);
    }
  };

  return (
    <div className={styles.page}>
      <header className={styles.topbar}>
        <div className={styles.topRow}>
          <Link href="/" className={styles.brand} aria-label="Ain Copilot home">
            <span className={styles.brandMark}>আ</span>
            <span className={styles.brandText}>Ain Copilot</span>
          </Link>
        </div>
      </header>

      <main className={styles.authMain}>
        <form className={styles.authCard} onSubmit={submit}>
          <span className={styles.authIcon} aria-hidden="true">
            <Icon name="shieldCheck" size={22} />
          </span>
          <h1 className={styles.stateTitle}>{t.title}</h1>
          <p className={styles.stateText}>{t.lead}</p>

          {me?.kind === "guest" && (
            <p className={styles.authNote}>
              <Icon name="info" size={15} />
              <span>The analyses you ran on this device will move into your account.</span>
            </p>
          )}

          <label className={styles.authField}>
            <span>Email</span>
            <input type="email" name="email" autoComplete="email" required maxLength={254} value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className={styles.authField}>
            <span>Password</span>
            <span className={styles.authPassword}>
              <input
                type={show ? "text" : "password"}
                name="password"
                autoComplete={t.password}
                required
                minLength={mode === "signup" ? 10 : undefined}
                maxLength={128}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-describedby={mode === "signup" ? "pw-hint" : undefined}
              />
              <button type="button" className={styles.linkBtn} onClick={() => setShow((s) => !s)} aria-pressed={show}>
                {show ? "Hide" : "Show"}
              </button>
            </span>
            {mode === "signup" && (
              <small id="pw-hint" className={styles.authHint}>
                At least 10 characters. There is no password reset yet, so keep it somewhere safe.
              </small>
            )}
          </label>

          {error && (
            <p className={styles.errorBox} role="alert">
              <Icon name="alert" size={16} />
              <span>{error}</span>
            </p>
          )}

          <button type="submit" className={`${styles.primaryBtn} ${styles.authSubmit}`} disabled={busy}>
            {busy ? t.busy : t.submit}
          </button>

          <p className={styles.authSwitch}>
            {t.switchText} <Link href={`${t.switchHref}?next=${encodeURIComponent(next)}`}>{t.switchLink}</Link>
          </p>
          <p className={styles.authSmall}>
            <Icon name="lock" size={13} />
            <span>Passwords are stored only as a salted hash. Your analyses are encrypted on the server and only you can open them.</span>
          </p>
        </form>
      </main>
    </div>
  );
}
