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
import { useCallback, useEffect, useState } from "react";
import {
  DEFAULT_PREFS,
  STORAGE_KEY,
  loadPrefs,
  savePrefs,
  normalizePrefs,
  toggleHidden as toggleHiddenPure,
  moveItem as moveItemPure,
  resetPrefs as resetPrefsPure,
  type SidebarPrefs,
} from "@/lib/sidebar-prefs";

/** Same-tab broadcast channel — `storage` events don't fire in the writing tab. */
const SYNC_EVENT = "lifeos:sidebar-prefs";

/** Persist + broadcast to every mounted hook instance in this tab. */
function commit(next: SidebarPrefs): void {
  savePrefs(next);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent<SidebarPrefs>(SYNC_EVENT, { detail: next }));
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
