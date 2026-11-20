/* Light / dark theme (spec 26). The choice is "system", "light" or "dark", kept in localStorage; <html data-theme>
   always holds the resolved value ("light" or "dark"), so the CSS has one dark block (app/globals.css).
   THEME_SCRIPT runs inline in <head> before first paint; applyTheme does the same work from React. */

export type ThemePref = "system" | "light" | "dark";

export const THEME_KEY = "jukti-theme";
/* fired on every change, so each toggle on the page (and the docs charts) can follow */
export const THEME_EVENT = "jukti-theme-change";
export const THEME_PREFS: ThemePref[] = ["system", "light", "dark"];
const DARK_QUERY = "(prefers-color-scheme: dark)";

export function readThemePref(): ThemePref {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

export function resolveTheme(pref: ThemePref): "light" | "dark" {
  if (pref !== "system") return pref;
  return window.matchMedia(DARK_QUERY).matches ? "dark" : "light";
}

export function applyTheme(pref: ThemePref = readThemePref()) {
  document.documentElement.setAttribute("data-theme", resolveTheme(pref));
}

export function saveThemePref(pref: ThemePref) {
  try {
    if (pref === "system") localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, pref);
  } catch {
    /* private mode: the choice lasts for this page only */
  }
  applyTheme(pref);
  window.dispatchEvent(new Event(THEME_EVENT));
}

/* the same logic as readThemePref + applyTheme, as a string for the inline <head> script; it also follows the OS
   while the choice is "system" */
export const THEME_SCRIPT = `(function(){var d=document.documentElement,q=window.matchMedia("${DARK_QUERY}");function a(){var t=null;try{t=localStorage.getItem("${THEME_KEY}")}catch(e){}d.setAttribute("data-theme",t==="light"||t==="dark"?t:q.matches?"dark":"light")}a();try{q.addEventListener("change",a)}catch(e){}})()`;
