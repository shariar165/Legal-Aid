"use client";

import { useLayoutEffect, useSyncExternalStore } from "react";
import { Icon } from "@/components/shared/Icons";
import { THEME_EVENT, THEME_KEY, THEME_PREFS, applyTheme, readThemePref, saveThemePref, type ThemePref } from "@/lib/theme";

function subscribe(onChange: () => void) {
  const onStorage = (e: StorageEvent) => {
    if (e.key === THEME_KEY) {
      applyTheme();
      onChange();
    }
  };
  window.addEventListener(THEME_EVENT, onChange);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(THEME_EVENT, onChange);
    window.removeEventListener("storage", onStorage);
  };
}

/* the server has no stored choice: it renders "system", and React swaps in the real one after hydration */
const useThemePref = () => useSyncExternalStore(subscribe, readThemePref, () => "system" as ThemePref);

/* In the root layout: puts data-theme back after React's dev Strict-Mode remount clears <html>'s attributes
   (the inline script already set it in production, so this is a no-op there). */
export function ThemeSync() {
  useLayoutEffect(() => applyTheme(), []);
  return null;
}

const ICON = { system: "monitor", light: "sun", dark: "moon" } as const;
const NAME = {
  en: { system: "system", light: "light", dark: "dark" },
  bn: { system: "সিস্টেম", light: "আলো", dark: "অন্ধকার" },
};

/* One button that cycles System → Light → Dark; its label says what it is now and what a press does. */
export function ThemeToggle({ className, lang = "en" }: { className?: string; lang?: "en" | "bn" }) {
  const pref = useThemePref();
  const next = THEME_PREFS[(THEME_PREFS.indexOf(pref) + 1) % THEME_PREFS.length];
  const n = NAME[lang];
  const label = lang === "bn" ? `রং: ${n[pref]} (চাপলে ${n[next]})` : `Theme: ${n[pref]} (switch to ${n[next]})`;
  return (
    <button type="button" className={className} onClick={() => saveThemePref(next)} aria-label={label} title={label}>
      <Icon name={ICON[pref]} size={18} />
    </button>
  );
}
