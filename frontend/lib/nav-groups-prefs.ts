/* ============================================================
   NAV-GROUP COLLAPSE PREFS — #74 change 4. Each sidebar SECTION (sb-sec) is
   collapsible; DEFAULT = all collapsed (compact sidebar), the user expands the groups
   they want. PERSIST = localStorage["lifeos.navgroups"] (device-local display pref, like
   privacy / sidebar-prefs — NOT backend). Stores the SET of manually-expanded section
   names. SSR-safe (load/save/normalize); the hook reads it post-mount.

   AUTO-EXPAND (not persisted, computed at render): the group containing the CURRENTLY
   ACTIVE route is always open (so the active screen is never hidden), and the "📌 Ghim"
   group is always open (the user's shortlist). So the effective open-set =
   {persisted manual opens} ∪ {active group} ∪ {Ghim}.
   ============================================================ */

export const STORAGE_KEY = "lifeos.navgroups";

/** The always-open Ghim section label (rendered above the normal groups). */
export const PINNED_SECTION = "📌 Ghim";

/** Persisted shape: the section names the user manually expanded. */
export interface NavGroupPrefs {
  /** section names (sb-sec labels) the user has toggled OPEN. */
  open: string[];
}

export const DEFAULT_NAVGROUP_PREFS: NavGroupPrefs = { open: [] };

/** Coerce an unknown parsed value into a valid NavGroupPrefs (per-field fallback). */
export function normalizeNavGroupPrefs(raw: unknown): NavGroupPrefs {
  if (!raw || typeof raw !== "object") return { open: [] };
  const r = raw as Record<string, unknown>;
  const open = Array.isArray(r.open)
    ? Array.from(new Set(r.open.filter((x): x is string => typeof x === "string")))
    : [];
  return { open };
}

/** Read persisted prefs from localStorage. SSR-safe (returns default when no window). */
export function loadNavGroupPrefs(): NavGroupPrefs {
  if (typeof window === "undefined") return { open: [] };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { open: [] };
    return normalizeNavGroupPrefs(JSON.parse(raw));
  } catch {
    return { open: [] };
  }
}

/** Persist prefs. No-op + swallow on SSR / quota / private-mode failure. */
export function saveNavGroupPrefs(p: NavGroupPrefs): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
  } catch {
    /* quota / disabled storage — nav layout is non-critical, fail soft */
  }
}

/** Toggle a section's manual-open state (pure). */
export function toggleSection(prefs: NavGroupPrefs, sec: string): NavGroupPrefs {
  const set = new Set(prefs.open);
  if (set.has(sec)) set.delete(sec);
  else set.add(sec);
  return { open: Array.from(set) };
}

/** Effective open? = manually-open OR the active group OR Ghim (always open). Pure —
 *  the auto-expands are computed, never persisted (so navigating elsewhere re-closes a
 *  non-manually-opened group). */
export function isSectionOpen(
  prefs: NavGroupPrefs,
  sec: string,
  activeSection: string | null,
): boolean {
  if (sec === PINNED_SECTION) return true; // Ghim always open
  if (activeSection != null && sec === activeSection) return true; // active group always open
  return prefs.open.includes(sec);
}
