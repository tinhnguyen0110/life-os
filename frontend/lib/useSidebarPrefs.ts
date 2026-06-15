"use client";
/* ============================================================
   useSidebarPrefs — FE-1 sidebar customization state.
   Pure client-side (no backend): reads localStorage["lifeos.sidebar"] once on
   mount, then every setter re-persists immediately. Mirrors useTweaks().

   CROSS-INSTANCE SYNC: the live Sidebar and the SidebarCustomizer panel each
   call this hook → two independent React states. A write in the panel must
   immediately reflect in the live sidebar (same tab). So every commit both
   persists to localStorage AND broadcasts the new value on a window CustomEvent;
   all mounted instances subscribe and adopt it. The native `storage` event
   (cross-TAB only — does NOT fire in the writing tab) covers other tabs.

   SSR + first client render start from DEFAULT_PREFS (the canonical NAV order,
   nothing hidden) so the server and client first paint agree; the real persisted
   value loads in the mount effect, after hydration — avoids a className/markup
   hydration mismatch (same approach as useTweaks / the Sidebar mounted-gate).
   ============================================================ */
import { useCallback, useEffect, useMemo, useState } from "react";
import { NAV, type NavGroup } from "@/lib/nav";
import {
  DEFAULT_PREFS,
  STORAGE_KEY,
  loadPrefs,
  savePrefs,
  normalizePrefs,
  applyPrefs,
  toggleHidden as toggleHiddenPure,
  moveItem as moveItemPure,
  resetPrefs as resetPrefsPure,
  type SidebarPrefs,
} from "@/lib/sidebar-prefs";
import {
  DEFAULT_MODULE_PREFS,
  STORAGE_KEY as MODULE_STORAGE_KEY,
  loadModulePrefs,
  saveModulePrefs,
  normalizeModulePrefs,
  applyModulePrefs,
  toggleModule as toggleModulePure,
  moveModule as moveModulePure,
  resetModulePrefs as resetModulePrefsPure,
  type ModulePrefs,
} from "@/lib/module-catalog";

/** Same-tab broadcast channel — `storage` events don't fire in the writing tab. */
const SYNC_EVENT = "lifeos:sidebar-prefs";
const MODULE_SYNC_EVENT = "lifeos:module-prefs";

/** Persist + broadcast to every mounted hook instance in this tab. */
function commit(next: SidebarPrefs): void {
  savePrefs(next);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent<SidebarPrefs>(SYNC_EVENT, { detail: next }));
  }
}

function commitModules(next: ModulePrefs): void {
  saveModulePrefs(next);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent<ModulePrefs>(MODULE_SYNC_EVENT, { detail: next }));
  }
}

export interface UseSidebarPrefs {
  prefs: SidebarPrefs;
  /** True once the persisted value has loaded (post-mount). */
  ready: boolean;
  /** Hide/show a single route (pinned routes are no-ops). */
  toggleHidden: (route: string) => void;
  /** Move a route up/down within its section. */
  move: (sec: string, route: string, dir: "up" | "down") => void;
  /** Reset to the canonical NAV (all visible, default order). */
  reset: () => void;
}

export function useSidebarPrefs(): UseSidebarPrefs {
  const [prefs, setPrefs] = useState<SidebarPrefs>(DEFAULT_PREFS);
  const [ready, setReady] = useState(false);

  // Load persisted value post-mount + subscribe to same-tab + cross-tab updates.
  useEffect(() => {
    setPrefs(loadPrefs());
    setReady(true);

    // Same-tab: another instance committed a change → adopt the broadcast value.
    function onSync(e: Event) {
      const detail = (e as CustomEvent<SidebarPrefs>).detail;
      if (detail) setPrefs(detail);
    }
    // Cross-tab: localStorage changed in ANOTHER tab → re-read (storage event
    // doesn't fire in the writing tab, so this never double-handles our own write).
    function onStorage(e: StorageEvent) {
      if (e.key !== STORAGE_KEY) return;
      try {
        setPrefs(e.newValue ? normalizePrefs(JSON.parse(e.newValue)) : DEFAULT_PREFS);
      } catch {
        setPrefs(DEFAULT_PREFS); // malformed cross-tab write → safe default
      }
    }

    window.addEventListener(SYNC_EVENT, onSync);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(SYNC_EVENT, onSync);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  // Setters compute from the current `prefs` (closure) so the side-effect (commit:
  // persist + broadcast) runs OUTSIDE React's render, then setPrefs adopts it.
  // The broadcast re-syncs every OTHER instance; this one updates via setPrefs.
  const toggleHidden = useCallback((route: string) => {
    const next = toggleHiddenPure(prefs, route);
    commit(next);
    setPrefs(next);
  }, [prefs]);

  const move = useCallback((sec: string, route: string, dir: "up" | "down") => {
    const next = moveItemPure(prefs, sec, route, dir);
    commit(next);
    setPrefs(next);
  }, [prefs]);

  const reset = useCallback(() => {
    const next = resetPrefsPure();
    commit(next);
    setPrefs(next);
  }, []);

  return { prefs, ready, toggleHidden, move, reset };
}

// ─────────────────────────────────────────────────────────────────────────────
// useModulePrefs — coarse per-MODULE registry (FE-1 extended): enable/disable +
// reorder whole modules (NAV groups). Same cross-instance broadcast pattern as
// useSidebarPrefs, separate storage key ("lifeos.modules") + event channel.
// ─────────────────────────────────────────────────────────────────────────────

export interface UseModulePrefs {
  modulePrefs: ModulePrefs;
  ready: boolean;
  /** Enable/disable a whole module (pinned modules are no-ops). */
  toggleModule: (key: string) => void;
  /** Reorder a module up/down in the catalog. */
  moveModule: (key: string, dir: "up" | "down") => void;
  /** Reset to default (all enabled, NAV order). */
  resetModules: () => void;
}

export function useModulePrefs(): UseModulePrefs {
  const [modulePrefs, setModulePrefs] = useState<ModulePrefs>(DEFAULT_MODULE_PREFS);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setModulePrefs(loadModulePrefs());
    setReady(true);

    function onSync(e: Event) {
      const detail = (e as CustomEvent<ModulePrefs>).detail;
      if (detail) setModulePrefs(detail);
    }
    function onStorage(e: StorageEvent) {
      if (e.key !== MODULE_STORAGE_KEY) return;
      try {
        setModulePrefs(e.newValue ? normalizeModulePrefs(JSON.parse(e.newValue)) : DEFAULT_MODULE_PREFS);
      } catch {
        setModulePrefs(DEFAULT_MODULE_PREFS);
      }
    }

    window.addEventListener(MODULE_SYNC_EVENT, onSync);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(MODULE_SYNC_EVENT, onSync);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  const toggleModule = useCallback((key: string) => {
    const next = toggleModulePure(modulePrefs, key);
    commitModules(next);
    setModulePrefs(next);
  }, [modulePrefs]);

  const moveModule = useCallback((key: string, dir: "up" | "down") => {
    const next = moveModulePure(modulePrefs, key, dir);
    commitModules(next);
    setModulePrefs(next);
  }, [modulePrefs]);

  const resetModules = useCallback(() => {
    const next = resetModulePrefsPure();
    commitModules(next);
    setModulePrefs(next);
  }, []);

  return { modulePrefs, ready, toggleModule, moveModule, resetModules };
}

// ─────────────────────────────────────────────────────────────────────────────
// useNavGroups — the COMPOSED sidebar render list. Applies the two layers in
// order: (1) module-level enable/order (coarse), then (2) route-level hide/order
// (fine) on top. `ready` is true only once BOTH pref sets have loaded so the
// sidebar renders the canonical NAV until then (hydration-safe, no flash/mismatch).
// ─────────────────────────────────────────────────────────────────────────────

export function useNavGroups(): { navGroups: NavGroup[]; ready: boolean } {
  const { prefs, ready: routeReady } = useSidebarPrefs();
  const { modulePrefs, ready: modReady } = useModulePrefs();

  const ready = routeReady && modReady;

  const navGroups = useMemo(() => {
    if (!ready) return NAV;
    // 1) module layer: order + drop disabled modules (whole NAV groups)
    const afterModules = applyModulePrefs(modulePrefs, NAV);
    // 2) route layer: per-item hide + reorder within each surviving group
    return applyPrefs(prefs, afterModules);
  }, [ready, modulePrefs, prefs]);

  return { navGroups, ready };
}
