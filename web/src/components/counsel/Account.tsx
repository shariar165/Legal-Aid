"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, use, useEffect, useRef, useState, type ReactNode } from "react";
import { api, type JobSummary, type Me } from "@/lib/api";
import { useSession } from "@/lib/useSession";
import { Icon } from "./Icons";
import styles from "./counsel.module.css";

const AccountContext = createContext<Me | null>(null);

/** Counsel mode is for signed-in accounts: anyone else is sent to sign in, then brought back here. */
export function AccountGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { me, offline } = useSession((m) => {
    if (m.kind !== "account") router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  });
  const allowed = me?.kind === "account";

  // backend unreachable: let the page show its own "server not reachable" message
  if (allowed || offline) return <AccountContext value={me}>{children}</AccountContext>;
  return (
    <div className={styles.page}>
      <main className={styles.narrow}>
        <p className={styles.gateNote} role="status">
          Checking your sign-in…
        </p>
      </main>
    </div>
  );
}

const shortDate = (unix: number) => new Date(unix * 1000).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

/** Topbar account chip: saved analyses, sign out, and erasure of the account with all its data. */
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

  if (!me?.email) return null;

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
      <button type="button" className={styles.accountBtn} aria-expanded={open} aria-haspopup="dialog" onClick={toggle} title={me.email}>
        <span className={styles.avatar} aria-hidden="true">
          {me.email[0].toUpperCase()}
        </span>
        <span className={styles.srOnly}>Your account</span>
        <Icon name="chevronDown" size={14} className={styles.chevron} />
      </button>
      {open && (
        <div className={styles.accountPanel} role="dialog" aria-label="Your account">
          <p className={styles.accountEmail}>
            <Icon name="lock" size={14} />
            <span>{me.email}</span>
          </p>

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

          {confirming ? (
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
