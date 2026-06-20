"use client";
/* ============================================================
   usePins — pinned nav routes (#72 SIDEBAR-UX, feature B). BACKEND-persisted via
   /settings (config.pinnedRoutes), NOT localStorage — this is the multi-device-sync
   point (a pin set on the desktop appears on the phone via Tailscale).

   Reads pinnedRoutes from GET /settings (useSettings); a pin/unpin is a PATCH
   (save({pinnedRoutes:[...]})) — FAIL-CLOSED (the underlying useSettings.save trusts
   the SERVER-returned config, not the local edit). A pin is an ADD, not a MOVE: the
   route shows in BOTH the "Ghim" group AND its home section.

   built-but-not-wired: the round-trip is REAL — togglePin actually PATCHes and the next
   GET reflects it. fail-soft on render: a pinnedRoute that doesn't resolve to a real nav
   item is skipped by the consumer (resolvePins), never crashes the sidebar.
   ============================================================ */
import { useCallback, useMemo } from "react";
import { useSettings } from "@/lib/useSettings";
import { NAV, type NavItem } from "@/lib/nav";

export interface UsePins {
  /** the user's pinned routes (in order); [] until settings load / when none. */
  pinned: string[];
  /** the pinned routes resolved to real NavItems (fail-soft: unknown routes dropped). */
  pinnedItems: NavItem[];
  /** True once settings have loaded. */
  ready: boolean;
  /** is this route currently pinned? */
  isPinned: (route: string) => boolean;
  /** add/remove a route from pinnedRoutes (PATCH /settings; fail-closed). Returns the
   *  save outcome so the caller can surface an error (ok / formError). */
  togglePin: (route: string) => Promise<{ ok: boolean; error?: string }>;
}

/** Flatten NAV → route→item map (the source of truth for resolving a pinned route). */
function navItemByRoute(): Map<string, NavItem> {
  const m = new Map<string, NavItem>();
  for (const g of NAV) for (const it of g.items) m.set(it.route, it);
  return m;
}

export function usePins(): UsePins {
  const { config, status, save } = useSettings();

  const pinned = useMemo<string[]>(
    () => (Array.isArray(config?.pinnedRoutes) ? config!.pinnedRoutes : []),
    [config],
  );

  // resolve to real nav items; SKIP any pinned route with no matching item (fail-soft).
  const pinnedItems = useMemo<NavItem[]>(() => {
    const byRoute = navItemByRoute();
    const out: NavItem[] = [];
    for (const route of pinned) {
      const item = byRoute.get(route);
      if (item) out.push(item); // unknown/stale route → skipped, never crashes
    }
    return out;
  }, [pinned]);

  const isPinned = useCallback((route: string) => pinned.includes(route), [pinned]);

  const togglePin = useCallback(
    async (route: string): Promise<{ ok: boolean; error?: string }> => {
      const next = pinned.includes(route)
        ? pinned.filter((r) => r !== route)
        : [...pinned, route];
      const res = await save({ pinnedRoutes: next });
      if (res.ok) return { ok: true };
      return { ok: false, error: res.formError ?? res.fieldErrors?.pinnedRoutes ?? "lưu pin thất bại" };
    },
    [pinned, save],
  );

  return { pinned, pinnedItems, ready: status === "ready", isPinned, togglePin };
}
