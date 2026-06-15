/* ============================================================
   MODULE CATALOG — per-user module registry (FE-1 extended).
   THE architectural layer: life-os has ~15 feature modules; showing every one
   to every user is overwhelming. This derives a togglable CATALOG of modules
   from the canonical NAV registry (lib/nav.ts) — NOT a hardcoded second list —
   so a NEW module auto-appears here the moment it's added to NAV.

   GRAIN (decided):
   - One catalog "module" = one NAV GROUP (section). The groups ARE the natural
     feature clusters: "Dự án" / "Tài chính" / "Hằng ngày" / "Tri thức" / "Hệ thống".
     Toggling a module off hides ALL its routes from the nav (routes still EXIST —
     deep links work — they're just removed from the sidebar UI).
   - This matches the user need ("đừng ngợp"): users switch off whole feature
     AREAS, not individual screens. Per-screen hide/reorder still lives in
     sidebar-prefs (the finer customizer); this is the coarse on/off registry.

   AUTO-DISCOVERY CONTRACT (mirror of backend core/registry.py):
   - Adding a module = adding it to NAV (a new group, or an item in a group).
     A new GROUP → a new catalog module (default ON). A new ITEM in an existing
     group → folds into that module automatically. No edit here is ever required.
   - `key` = the section name (stable id from NAV). Persisted prefs key on it, so
     reordering NAV groups or adding modules never corrupts a saved toggle.

   PINNED modules (core — can never be disabled, would strand the user):
   - "Tổng quan" (Home dashboard) and "Cấu hình" (Settings — where this very panel
     lives). Disabling Settings would lock the user out of re-enabling anything.
   ============================================================ */
import { NAV, type NavGroup } from "./nav";
import type { IconKey } from "./icons";

export const STORAGE_KEY = "lifeos.modules";

/** Core module sections that can never be turned off (Home + Settings host). */
export const PINNED_MODULES: readonly string[] = ["Tổng quan", "Cấu hình"];

export interface ModuleMeta {
  /** Stable id = the NAV section name. */
  key: string;
  /** Display label (= section name). */
  label: string;
  /** Representative icon (the first item's icon in the group). */
  icon: IconKey;
  /** Routes this module owns (for hiding from nav when disabled). */
  routes: string[];
  /** Number of screens in the module (shown in the panel). */
  count: number;
  /** Core module — always on, no toggle. */
  pinned: boolean;
}

/**
 * Derive the module catalog from NAV. Pure — one entry per NAV group, in NAV
 * order. Forward-compatible: a new group appears automatically; a new item folds
 * into its group's `routes`/`count`.
 */
export function buildCatalog(source: NavGroup[] = NAV): ModuleMeta[] {
  return source.map((group) => ({
    key: group.sec,
    label: group.sec,
    icon: group.items[0]?.icon ?? "i-home",
    routes: group.items.map((i) => i.route),
    count: group.items.length,
    pinned: PINNED_MODULES.includes(group.sec),
  }));
}

export interface ModulePrefs {
  /** Module keys (section names) the user turned OFF. */
  disabled: string[];
  /** Custom module order: ordered list of section names. */
  order: string[];
}

export const DEFAULT_MODULE_PREFS: ModulePrefs = { disabled: [], order: [] };

/** Coerce an unknown parsed value into valid ModulePrefs (strips pinned from disabled). */
export function normalizeModulePrefs(raw: unknown): ModulePrefs {
  if (!raw || typeof raw !== "object") return { disabled: [], order: [] };
  const r = raw as Record<string, unknown>;
  const disabled = Array.isArray(r.disabled)
    ? r.disabled.filter((x): x is string => typeof x === "string" && !PINNED_MODULES.includes(x))
    : [];
  const order = Array.isArray(r.order)
    ? r.order.filter((x): x is string => typeof x === "string")
    : [];
  return { disabled: Array.from(new Set(disabled)), order };
}

/** SSR-safe read from localStorage. */
export function loadModulePrefs(): ModulePrefs {
  if (typeof window === "undefined") return { disabled: [], order: [] };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { disabled: [], order: [] };
    return normalizeModulePrefs(JSON.parse(raw));
  } catch {
    return { disabled: [], order: [] };
  }
}

/** SSR-safe persist; fail-soft on quota/private-mode. */
export function saveModulePrefs(p: ModulePrefs): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
  } catch {
    /* non-critical preference — fail soft */
  }
}

/** A module is enabled unless explicitly disabled (default ON — preserves current UX). */
export function isModuleEnabled(prefs: ModulePrefs, key: string): boolean {
  if (PINNED_MODULES.includes(key)) return true;
  return !prefs.disabled.includes(key);
}

/** The set of routes to HIDE from nav because their owning module is disabled. */
export function hiddenRoutesFromModules(prefs: ModulePrefs, source: NavGroup[] = NAV): Set<string> {
  const hidden = new Set<string>();
  for (const group of source) {
    if (!isModuleEnabled(prefs, group.sec)) {
      for (const item of group.items) hidden.add(item.route);
    }
  }
  return hidden;
}

/**
 * Order the catalog per prefs.order, appending any module not in the saved order
 * (new modules surface at the end). Stale keys (module removed from NAV) are
 * ignored. Pure.
 */
export function orderCatalog(catalog: ModuleMeta[], order: string[]): ModuleMeta[] {
  if (order.length === 0) return catalog;
  const byKey = new Map(catalog.map((m) => [m.key, m]));
  const out: ModuleMeta[] = [];
  for (const key of order) {
    const m = byKey.get(key);
    if (m) { out.push(m); byKey.delete(key); }
  }
  for (const m of catalog) if (byKey.has(m.key)) out.push(m);
  return out;
}

/** Toggle a module's enabled state (pinned → no-op). */
export function toggleModule(prefs: ModulePrefs, key: string): ModulePrefs {
  if (PINNED_MODULES.includes(key)) return prefs;
  const set = new Set(prefs.disabled);
  if (set.has(key)) set.delete(key);
  else set.add(key);
  return { ...prefs, disabled: Array.from(set) };
}

/** Move a module up/down in the catalog order. Materializes current order first. */
export function moveModule(
  prefs: ModulePrefs,
  key: string,
  dir: "up" | "down",
  source: NavGroup[] = NAV,
): ModulePrefs {
  const current = orderCatalog(buildCatalog(source), prefs.order).map((m) => m.key);
  const idx = current.indexOf(key);
  if (idx === -1) return prefs;
  const target = dir === "up" ? idx - 1 : idx + 1;
  if (target < 0 || target >= current.length) return prefs;
  const next = current.slice();
  [next[idx], next[target]] = [next[target], next[idx]];
  return { ...prefs, order: next };
}

/** Reset to default (all enabled, NAV order). */
export function resetModulePrefs(): ModulePrefs {
  return { disabled: [], order: [] };
}

/**
 * Apply module prefs to NAV → the ordered + filtered group list for the sidebar:
 *   1. order groups per prefs.order
 *   2. drop groups whose module is disabled
 * Pure. (Per-route hide/reorder from sidebar-prefs is applied SEPARATELY on top.)
 */
export function applyModulePrefs(prefs: ModulePrefs, source: NavGroup[] = NAV): NavGroup[] {
  const ordered = orderCatalog(buildCatalog(source), prefs.order);
  const out: NavGroup[] = [];
  for (const meta of ordered) {
    if (!isModuleEnabled(prefs, meta.key)) continue;
    const group = source.find((g) => g.sec === meta.key);
    if (group) out.push(group);
  }
  return out;
}
