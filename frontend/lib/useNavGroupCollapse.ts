"use client";
/* ============================================================
   useNavGroupCollapse — collapsible sidebar sections (#74 change 4).
   localStorage["lifeos.navgroups"] (device-local), same cross-instance broadcast pattern
   as usePrivacy/useSidebarPrefs. DEFAULT = all collapsed; the user expands groups; the
   active route's group + "📌 Ghim" auto-expand (computed, not persisted).

   SSR + first paint start from DEFAULT (nothing manually open) so server/client agree;
   the persisted set loads post-mount (hydration-safe). isOpen(sec, activeSection) folds
   in the auto-expands.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import {
  DEFAULT_NAVGROUP_PREFS,
  STORAGE_KEY,
  loadNavGroupPrefs,
  saveNavGroupPrefs,
  normalizeNavGroupPrefs,
  toggleSection as toggleSectionPure,
  isSectionOpen,
  type NavGroupPrefs,
} from "@/lib/nav-groups-prefs";

const SYNC_EVENT = "lifeos:navgroups";

function commit(next: NavGroupPrefs): void {
  saveNavGroupPrefs(next);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent<NavGroupPrefs>(SYNC_EVENT, { detail: next }));
  }
}

export interface UseNavGroupCollapse {
  prefs: NavGroupPrefs;
  /** True once the persisted value has loaded (post-mount). */
  ready: boolean;
  /** Effective open state: manual-open OR the active group OR Ghim. */
  isOpen: (sec: string, activeSection: string | null) => boolean;
  /** Toggle a section's manual-open state (persist + broadcast). */
  toggle: (sec: string) => void;
}

export function useNavGroupCollapse(): UseNavGroupCollapse {
  const [prefs, setPrefs] = useState<NavGroupPrefs>(DEFAULT_NAVGROUP_PREFS);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setPrefs(loadNavGroupPrefs());
    setReady(true);

    function onSync(e: Event) {
      const detail = (e as CustomEvent<NavGroupPrefs>).detail;
      if (detail) setPrefs(detail);
    }
    function onStorage(e: StorageEvent) {
      if (e.key !== STORAGE_KEY) return;
      try {
        setPrefs(e.newValue ? normalizeNavGroupPrefs(JSON.parse(e.newValue)) : DEFAULT_NAVGROUP_PREFS);
      } catch {
        setPrefs(DEFAULT_NAVGROUP_PREFS);
      }
    }

    window.addEventListener(SYNC_EVENT, onSync);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(SYNC_EVENT, onSync);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  const isOpen = useCallback(
    (sec: string, activeSection: string | null) => isSectionOpen(prefs, sec, activeSection),
    [prefs],
  );

  const toggle = useCallback((sec: string) => {
    setPrefs((cur) => {
      const next = toggleSectionPure(cur, sec);
      commit(next);
      return next;
    });
  }, []);

  return { prefs, ready, isOpen, toggle };
}
