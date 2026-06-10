/* ============================================================
   TWEAKS — appearance/theme system (S13).
   PORTED VERBATIM from mock template/Life Command/app/shell.js
   (THEMES / BG / applyTweaks — lines 157–184). Two deviations from the
   mock, both per the S13 dispatch:
     1. DEFAULT bg = "cool" (neutral) instead of the mock's "warm".
     2. Persistence = localStorage["lifeos.tweaks"] instead of the mock's
        parent-frame postMessage (the mock ran inside an editor iframe).
   No backend — appearance is a pure client-side preference.
   ============================================================ */

export type ThemeKey = "copper" | "amber" | "solar" | "cyan" | "violet" | "rose";
export type BgKey = "cool" | "warm";

export interface TweakState {
  theme: ThemeKey;
  bg: BgKey;
  glow: boolean;
  scanline: boolean;
}
/** Back-compat alias — `TweakState` is the canonical name (matches T3 test scaffold). */
export type Tweaks = TweakState;

export interface ThemeDef {
  name: string;
  primary: string;
  soft: string;
  dim: string;
  grad: string;
}

/** 6 accent themes — ported verbatim from shell.js THEMES. */
export const THEMES: Record<ThemeKey, ThemeDef> = {
  copper: { name: "Copper Glow", primary: "#FF6A33", soft: "#ffb088", dim: "#5a2c14", grad: "linear-gradient(140deg,#ff9a5c,#e8451a)" },
  amber:  { name: "Amber",       primary: "#F5A623", soft: "#ffce7a", dim: "#5c4318", grad: "linear-gradient(140deg,#FFB452,#ef7d22)" },
  solar:  { name: "Solar Gold",  primary: "#FFC53D", soft: "#ffe199", dim: "#5c4a12", grad: "linear-gradient(140deg,#ffe08a,#f0a818)" },
  cyan:   { name: "Cyan Tech",   primary: "#38BDF8", soft: "#a5e4ff", dim: "#11414f", grad: "linear-gradient(140deg,#7ad6ff,#1f9fe0)" },
  violet: { name: "Violet",      primary: "#A879FF", soft: "#d4baff", dim: "#3a2a5c", grad: "linear-gradient(140deg,#c7a3ff,#8b54f0)" },
  rose:   { name: "Crimson",     primary: "#FF5C7A", soft: "#ffaebd", dim: "#5a1f2c", grad: "linear-gradient(140deg,#ff8aa0,#e8324f)" },
};

/** Background palettes — ported verbatim from shell.js BG. cool = neutral, warm = copper base. */
export const BG: Record<BgKey, Record<string, string>> = {
  cool: { "--bg-0": "#0a0a0c", "--bg-1": "#0f0f13", "--bg-2": "#16161c", "--bg-3": "#1e1e26", "--line": "#23232c", "--line-2": "#30303a", "--tx-1": "#9b988e", "--tx-2": "#66645c" },
  warm: { "--bg-0": "#0f0a07", "--bg-1": "#15100b", "--bg-2": "#1c150e", "--bg-3": "#241a11", "--line": "#2c2319", "--line-2": "#392d20", "--tx-1": "#a39c8e", "--tx-2": "#6e665a" },
};

/** Default appearance — neutral background (per S13 dispatch), copper accent, glow on, scanline off. */
export const DEFAULT_TWEAKS: Tweaks = { theme: "copper", bg: "cool", glow: true, scanline: false };

export const STORAGE_KEY = "lifeos.tweaks";

/** Coerce an unknown parsed value into a valid Tweaks, falling back per-field to DEFAULT_TWEAKS. */
export function normalizeTweaks(raw: unknown): Tweaks {
  if (!raw || typeof raw !== "object") return { ...DEFAULT_TWEAKS };
  const r = raw as Record<string, unknown>;
  return {
    theme: typeof r.theme === "string" && r.theme in THEMES ? (r.theme as ThemeKey) : DEFAULT_TWEAKS.theme,
    bg: r.bg === "cool" || r.bg === "warm" ? (r.bg as BgKey) : DEFAULT_TWEAKS.bg,
    glow: typeof r.glow === "boolean" ? r.glow : DEFAULT_TWEAKS.glow,
    scanline: typeof r.scanline === "boolean" ? r.scanline : DEFAULT_TWEAKS.scanline,
  };
}

/** Read persisted tweaks from localStorage. SSR-safe (returns default when no window). */
export function loadTweaks(): Tweaks {
  if (typeof window === "undefined") return { ...DEFAULT_TWEAKS };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_TWEAKS };
    return normalizeTweaks(JSON.parse(raw));
  } catch {
    return { ...DEFAULT_TWEAKS };
  }
}

/** Persist tweaks to localStorage. No-op + swallow on SSR / quota / private-mode failure. */
export function saveTweaks(t: Tweaks): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(t));
  } catch {
    /* quota exceeded / disabled storage — appearance is non-critical, fail soft */
  }
}

/**
 * Apply tweaks to the live DOM by overriding :root CSS vars — ported from
 * shell.js applyTweaks (the CSS-var half; mock's panel-state sync lives in the
 * React component instead). SSR-safe no-op when no document.
 */
export function applyTweaks(t: Tweaks): void {
  if (typeof document === "undefined") return;
  const theme = THEMES[t.theme] ?? THEMES.copper;
  const r = document.documentElement.style;
  r.setProperty("--accent", theme.primary);
  r.setProperty("--accent-soft", theme.soft);
  r.setProperty("--accent-dim", theme.dim);
  r.setProperty("--accent-grad", theme.grad);
  r.setProperty(
    "--glow",
    t.glow
      ? `0 0 0 1px ${theme.primary}52, 0 0 22px -6px ${theme.primary}`
      : `0 0 0 1px ${theme.primary}30`,
  );
  const bg = BG[t.bg] ?? BG.cool;
  for (const k in bg) r.setProperty(k, bg[k]);
  // Scanline overlay. The no-flash <head> script sets html[data-scanline] pre-paint
  // (body doesn't exist yet there); body.scanline is the mock's runtime hook. The
  // CSS rule matches EITHER, so we keep both in sync to avoid a stale pre-paint attr.
  document.body.classList.toggle("scanline", t.scanline);
  if (t.scanline) document.documentElement.setAttribute("data-scanline", "1");
  else document.documentElement.removeAttribute("data-scanline");
}
