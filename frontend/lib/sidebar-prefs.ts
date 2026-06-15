/* ============================================================
   SIDEBAR PREFS — user customization of the nav (FE-1).
   Lets the user hide/show each module and reorder them. Pure client-side
   preference (no backend), persisted to localStorage["lifeos.sidebar"],
   mirroring the tweaks.ts pattern (load/save/normalize + SSR-safe).

   DESIGN:
   - Prefs are keyed by `route` (stable id), NOT array index, so adding a NEW
     nav item to lib/nav.ts later does NOT corrupt a saved pref — unknown routes
     simply fall back to default (visible, in their NAV order). This is
     forward-compatible by construction.
   - `hidden`: set of routes the user toggled off.
   - `order`: per-section ordered list of routes. A section/route absent from
     `order` keeps its natural NAV position; `applyPrefs` appends any NAV route
     not in `order` after the ordered ones (so new modules show up at the end of
     their section, never silently dropped).
   - Home ("/") is PINNED visible + first — it's the dashboard root; hiding it
     would strand the user. The customizer never offers a toggle for it.
   ============================================================ */
import { NAV, type NavGroup, type NavItem } from "./nav";

export const STORAGE_KEY = "lifeos.sidebar";

/** Routes that can never be hidden (would strand the user). */
export const PINNED_ROUTES: readonly string[] = ["/"];

export interface SidebarPrefs {
  /** Routes toggled OFF by the user (hidden from the sidebar). */
  hidden: string[];
  /** Per-section custom order: section name → ordered route list. */
  order: Record<string, string[]>;
}

export const DEFAULT_PREFS: SidebarPrefs = { hidden: [], order: {} };

/** Coerce an unknown parsed value into a valid SidebarPrefs (per-field fallback). */
export function normalizePrefs(raw: unknown): SidebarPrefs {
  if (!raw || typeof raw !== "object") return { hidden: [], order: {} };
  const r = raw as Record<string, unknown>;

  // hidden → array of strings, never including a pinned route.
  const hidden = Array.isArray(r.hidden)
    ? r.hidden.filter((x): x is string => typeof x === "string" && !PINNED_ROUTES.includes(x))
    : [];

  // order → Record<string, string[]>; drop any non-array / non-string entries.
  const order: Record<string, string[]> = {};
  if (r.order && typeof r.order === "object") {
    for (const [sec, list] of Object.entries(r.order as Record<string, unknown>)) {
      if (Array.isArray(list)) {
        order[sec] = list.filter((x): x is string => typeof x === "string");
      }
    }
  }
  // de-dupe hidden
  return { hidden: Array.from(new Set(hidden)), order };
}

/** Read persisted prefs from localStorage. SSR-safe (returns default when no window). */
export function loadPrefs(): SidebarPrefs {
  if (typeof window === "undefined") return { hidden: [], order: {} };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { hidden: [], order: {} };
    return normalizePrefs(JSON.parse(raw));
  } catch {
    return { hidden: [], order: {} };
  }
}

/** Persist prefs to localStorage. No-op + swallow on SSR / quota / private-mode failure. */
export function savePrefs(p: SidebarPrefs): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
  } catch {
    /* quota exceeded / disabled storage — sidebar layout is non-critical, fail soft */
  }
}

/**
 * Order a section's items per `prefs.order[sec]`, then append any NAV item not
 * listed (forward-compat for newly-added modules). Stale routes in `order` that
 * no longer exist in NAV are ignored.
 */
function orderItems(sec: string, items: NavItem[], order: Record<string, string[]>): NavItem[] {
  const desired = order[sec];
  if (!desired || desired.length === 0) return items;
  const byRoute = new Map(items.map((i) => [i.route, i]));
  const out: NavItem[] = [];
  for (const route of desired) {
    const item = byRoute.get(route);
    if (item) {
      out.push(item);
      byRoute.delete(route);
    }
  }
  // append NAV items not in the saved order (new modules) in their natural order
  for (const item of items) {
    if (byRoute.has(item.route)) out.push(item);
  }
  return out;
}

/**
 * Apply prefs to the canonical NAV → the sidebar's render list:
 *   1. reorder each section's items per prefs.order
 *   2. drop hidden routes (pinned routes are never dropped)
 *   3. drop sections left with zero visible items
 * Pure — does not mutate NAV. Defaults to `NAV` when no source given.
 */
export function applyPrefs(prefs: SidebarPrefs, source: NavGroup[] = NAV): NavGroup[] {
  const hidden = new Set(prefs.hidden);
  const out: NavGroup[] = [];
  for (const group of source) {
    const ordered = orderItems(group.sec, group.items, prefs.order);
    const visible = ordered.filter((i) => PINNED_ROUTES.includes(i.route) || !hidden.has(i.route));
    if (visible.length > 0) out.push({ sec: group.sec, items: visible });
  }
  return out;
}

/** Toggle a route's hidden state (pinned routes can't be hidden → no-op). */
export function toggleHidden(prefs: SidebarPrefs, route: string): SidebarPrefs {
  if (PINNED_ROUTES.includes(route)) return prefs;
  const set = new Set(prefs.hidden);
  if (set.has(route)) set.delete(route);
  else set.add(route);
  return { ...prefs, hidden: Array.from(set) };
}

/**
 * Move a route up/down WITHIN its section. Materializes the section's current
 * effective order (so a first move from default NAV order works), swaps the item
 * with its neighbor, and writes it back to `order[sec]`. No-op at the boundary or
 * if the route/section isn't found.
 */
export function moveItem(
  prefs: SidebarPrefs,
  sec: string,
  route: string,
  dir: "up" | "down",
  source: NavGroup[] = NAV,
): SidebarPrefs {
  const group = source.find((g) => g.sec === sec);
  if (!group) return prefs;
  // current effective order for this section (saved order, or natural NAV order)
  const current = orderItems(sec, group.items, prefs.order).map((i) => i.route);
  const idx = current.indexOf(route);
  if (idx === -1) return prefs;
  const target = dir === "up" ? idx - 1 : idx + 1;
  if (target < 0 || target >= current.length) return prefs; // boundary
  const next = current.slice();
  [next[idx], next[target]] = [next[target], next[idx]];
  return { ...prefs, order: { ...prefs.order, [sec]: next } };
}

/** Reset to the canonical NAV (all visible, default order). */
export function resetPrefs(): SidebarPrefs {
  return { hidden: [], order: {} };
}
