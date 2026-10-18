"use client";

import { useEffect, useEffectEvent, useState } from "react";
import { api, type Me } from "./api";

/**
 * Who the backend says this browser is: nobody, a guest (this device only) or a signed-in
 * account. `me` is null until the first answer; `offline` means the backend is unreachable,
 * so callers should not treat it as "signed out".
 *
 * Act on the session (redirects) in `onSession`, not on `me`: with Cache Components a visited
 * route is kept alive and re-shown later, so `me` can be a stale answer from that earlier
 * visit. `onSession` only ever receives the answer of the check made for this showing.
 */
export function useSession(onSession?: (me: Me) => void) {
  const [me, setMe] = useState<Me | null>(null);
  const [offline, setOffline] = useState(false);
  const resolved = useEffectEvent((m: Me) => {
    setMe(m);
    setOffline(false);
    onSession?.(m);
  });

  useEffect(() => {
    let cancelled = false;
    api
      .me()
      .then((m) => !cancelled && resolved(m))
      .catch(() => !cancelled && setOffline(true));
    return () => {
      cancelled = true;
    };
  }, []);

  return { me, offline };
}

/** Only same-site paths are accepted as a post-login destination (no open redirects). */
export function safeNext(next: string | null, fallback = "/counsel") {
  return next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\") ? next : fallback;
}
