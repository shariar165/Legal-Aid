"use client";

import { useCallback, useSyncExternalStore } from "react";

/* Small UI choices kept on this device (spec 29 step 1.2): Citizen's language and the Case Desk's. Read through
   useSyncExternalStore, so the server render and hydration use the default and the stored choice follows at once,
   with no mismatch. Storage can throw (private mode): the choice then lasts for this page only, as in lib/theme.ts. */

export const CITIZEN_LANG_KEY = "jukti-lang";
export const DESK_LANG_KEY = "jukti-desk-lang";
const EVENT = "jukti-pref-change";

export function readPref(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function savePref(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* private mode: kept in memory below for this page */
  }
  memory.set(key, value);
  window.dispatchEvent(new Event(EVENT));
}

const memory = new Map<string, string>();

function subscribe(onChange: () => void) {
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onChange); // another tab changed it
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

/** A stored choice from `allowed`, or `fallback`; the setter stores it. */
export function usePref<T extends string>(key: string, allowed: readonly T[], fallback: T): [T, (value: T) => void] {
  const raw = useSyncExternalStore(
    subscribe,
    () => readPref(key) ?? memory.get(key) ?? null,
    () => null,
  );
  const value = (allowed as readonly string[]).includes(raw ?? "") ? (raw as T) : fallback;
  const set = useCallback((v: T) => savePref(key, v), [key]);
  return [value, set];
}
