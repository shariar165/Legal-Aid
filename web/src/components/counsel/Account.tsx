"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, use, useEffect, useRef, useState, type ReactNode } from "react";
import { api, type JobSummary, type Me } from "@/lib/api";
import { useSession } from "@/lib/useSession";
import { Icon } from "@/components/shared/Icons";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import styles from "./counsel.module.css";

const AccountContext = createContext<Me | null>(null);

/**
 * Counsel opens for everyone (spec 29 step 1.1): an account, a guest (this device only, kept 7 days) or a first-time
 * visitor, whose first analysis creates the guest, as in Citizen. The API already limits each of them to the analyses
 * they own. The gate only waits for the session answer, so the account menu knows which of the three it is.
 */
export function AccountGate({ children }: { children: ReactNode }) {
  const { me, offline } = useSession();

  // backend unreachable: let the page show its own "server not reachable" message
  if (me || offline) return <AccountContext value={me}>{children}</AccountContext>;
  return (
    <div className={styles.page}>
      <main className={styles.narrow}>
        <p className={styles.gateNote} role="status">
          Checking your session…
        </p>
      </main>
    </div>
  );
}

/** The session the gate resolved: null while offline. */
export function useMe() {
  return use(AccountContext);
}

const shortDate = (unix: number) => new Date(unix * 1000).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

/**
 * Topbar account chip. An account: saved analyses, sign out, and erasure of the account with all its data.
 * A guest: this device's analyses, and a way to keep them (sign up or sign in moves them into the account).
 * No session yet: a "Sign in" link.
 */
export function AccountMenu() {
  const me = use(AccountContext);
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [jobs, setJobs] = useState<JobSummary[] | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    api
      .jobs()
      .then(setJobs)
      .catch(() => setJobs([]));
    const onPointer = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!me) return null;
  const next = encodeURIComponent(pathname);
  if (me.kind === null) {
    return (
      <Link href={`/login?next=${next}`} className={styles.quietBtn}>
        Sign in
      </Link>
    );
  }
  const guest = me.kind === "guest";

  const toggle = () => {
    setOpen((o) => !o);
    setConfirming(false);
    setError(null);
  };

  const signOut = async () => {
    setBusy(true);
    try {
      await api.logout();
    } finally {
      router.replace("/login");
    }
  };

  const removeJob = async (job: JobSummary) => {
    setError(null);
    try {
      await api.deleteJob(job.job_id);
      setJobs((js) => js?.filter((j) => j.job_id !== job.job_id) ?? null);
      if (pathname === `/counsel/${job.job_id}`) router.replace("/counsel");
    } catch (e) {
      setError((e as Error).message.replace(/^\d+: /, ""));
    }
  };

  const deleteAccount = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.deleteAccount();
      router.replace("/signup");
    } catch (e) {
      setError((e as Error).message.replace(/^\d+: /, ""));
      setBusy(false);
    }
  };

  return (
    <div className={styles.account} ref={root}>
      <button
        type="button"
        className={styles.accountBtn}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={toggle}
        title={guest ? "Guest on this device" : (me.email ?? undefined)}
      >
        <span className={styles.avatar} aria-hidden="true">
          {guest ? <Icon name="monitor" size={15} /> : (me.email ?? "?")[0].toUpperCase()}
        </span>
        <span className={styles.srOnly}>{guest ? "Guest session" : "Your account"}</span>
        <Icon name="chevronDown" size={14} className={styles.chevron} />
      </button>
      {open && (
        <div className={styles.accountPanel} role="dialog" aria-label={guest ? "Guest session" : "Your account"}>
          {guest ? (
            <div className={styles.accountGuest}>
              <p className={styles.accountEmail}>
                <Icon name="monitor" size={14} />
                <span>Guest · kept 7 days on this device</span>
              </p>
              <p className={styles.accountMuted}>Save to an account to keep your analyses and open them on any device.</p>
            </div>
          ) : (
            <p className={styles.accountEmail}>
              <Icon name="lock" size={14} />
              <span>{me.email}</span>
            </p>
          )}

          {/* the top bar's theme switch moves here on a tablet-wide job page (spec 29 step 1.3) */}
          <div className={styles.panelTheme}>
            <span>Theme</span>
            <ThemeToggle className={styles.themeBtn} />
          </div>

          <p className={styles.accountLabel}>My analyses</p>
          {jobs === null ? (
            <p className={styles.accountMuted}>Loading…</p>
          ) : jobs.length === 0 ? (
            <p className={styles.accountMuted}>No saved analyses yet.</p>
          ) : (
            <ul className={styles.accountJobs}>
              {jobs.map((j) => (
                <li key={j.job_id}>
                  <Link href={`/counsel/${j.job_id}`} onClick={() => setOpen(false)} aria-current={pathname === `/counsel/${j.job_id}` ? "page" : undefined}>
                    <Icon name="file" size={14} />
                    <span className={styles.accountJobName}>{j.name}</span>
                    <time dateTime={new Date(j.created_at * 1000).toISOString()}>{shortDate(j.created_at)}</time>
                  </Link>
                  <button type="button" className={styles.accountRemove} onClick={() => removeJob(j)} aria-label={`Delete analysis ${j.name}`} title="Delete this analysis">
                    <Icon name="x" size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}

          {guest ? (
            <div className={styles.accountActions}>
              <Link href={`/signup?next=${next}`} className={styles.primaryBtn}>
                Save to an account
              </Link>
              <Link href={`/login?next=${next}`} className={styles.quietBtn} data-size="sm">
                Sign in
              </Link>
            </div>
          ) : confirming ? (
            <div className={styles.accountConfirm} role="alert">
              <p>This permanently deletes your account and every saved analysis. It cannot be undone.</p>
              <div>
                <button type="button" className={styles.dangerBtn} onClick={deleteAccount} disabled={busy}>
                  Delete everything
                </button>
                <button type="button" className={styles.quietBtn} data-size="sm" onClick={() => setConfirming(false)} disabled={busy}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className={styles.accountActions}>
              <button type="button" className={styles.quietBtn} data-size="sm" onClick={signOut} disabled={busy}>
                Sign out
              </button>
              <button type="button" className={styles.dangerLink} onClick={() => setConfirming(true)}>
                Delete account…
              </button>
            </div>
          )}
          {error && (
            <p className={styles.errorBox} role="alert">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
