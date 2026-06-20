/* ============================================================
   PRIVACY MODE — a DEVICE-LOCAL display veil (#72 SIDEBAR-UX, feature A).
   "Someone's watching THIS screen" → BLUR money totals (#74: blur-only — the
   hide-finance-group behavior was removed per the user's refined spec; every screen
   stays visible in the sidebar).

   PERSIST = localStorage["lifeos.privacy"], NOT /settings. This is intentional and
   load-bearing: privacy is per-DEVICE (a phone in public shouldn't blur the home
   desktop). Mirrors the sidebar-prefs localStorage pattern (load/save/normalize,
   SSR-safe). Pure functions here; the hook (usePrivacy) wraps with broadcast.

   The veil is DISPLAY-ONLY: money values stay in the DOM (real, recoverable) — the
   blur is CSS on [data-privacy="on"] [data-amount]. Toggle OFF → numbers back, NO reload.
   ============================================================ */

export const STORAGE_KEY = "lifeos.privacy";

/** Default OFF — money visible. */
export const DEFAULT_PRIVACY = false;

/** Coerce an unknown parsed value into a bool (per the stored shape `{on:boolean}`). */
export function normalizePrivacy(raw: unknown): boolean {
  if (typeof raw === "boolean") return raw;
  if (raw && typeof raw === "object" && typeof (raw as { on?: unknown }).on === "boolean") {
    return (raw as { on: boolean }).on;
  }
  return DEFAULT_PRIVACY;
}

/** Read persisted privacy flag. SSR-safe (returns default when no window). */
export function loadPrivacy(): boolean {
  if (typeof window === "undefined") return DEFAULT_PRIVACY;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_PRIVACY;
    return normalizePrivacy(JSON.parse(raw));
  } catch {
    return DEFAULT_PRIVACY;
  }
}

/** Persist the flag. No-op + swallow on SSR / quota / private-mode failure. */
export function savePrivacy(on: boolean): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ on }));
  } catch {
    /* quota / disabled storage — privacy is non-critical UI, fail soft */
  }
}

// NOTE (#74): privacy is BLUR-ONLY — it no longer hides any nav route. The previous
// hide-finance-group helpers (isPrivacyHidden / PRIVACY_HIDDEN_ROUTES) were removed; the
// veil is purely the [data-privacy="on"] [data-amount] blur on money totals.
