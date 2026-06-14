"use client";
/* ============================================================
   Sidebar — collapsible, 6 nav groups (D3), badge counts.
   Ported from mock shell.js renderShell() sidebar markup.
   Active state = current App Router pathname (longest-prefix match for detail routes).
   Collapse state lifted to ShellLayout (toggles #app.collapsed).
   ============================================================ */
import { useEffect, useState } from "react";
import Link from "next/link";
import { useSafePathname } from "@/lib/useNav";
import { NAV } from "@/lib/nav";
import { Icon } from "@/lib/icons";
import { getRoutines, getProjects, getMarket, getClaudeUsage } from "@/lib/api";

/** A nav item is active if pathname equals its route, or (for non-home) starts with it. */
function isActive(route: string, pathname: string): boolean {
  if (route === "/") return pathname === "/";
  return pathname === route || pathname.startsWith(route + "/");
}

export function Sidebar({ onToggleCollapse }: { onToggleCollapse?: () => void }) {
  const pathname = useSafePathname();
  // Active state is applied only after mount so server + client first paint agree
  // (the safe-pathname fallback can differ from the server value during hydration,
  // which would otherwise log a className mismatch). Post-hydration the real path wins.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // F2-M4: wire ALL 4 sidebar badges to LIVE data (was static placeholders per
  // sidebar-badges-static-placeholder — done all-together, not piecemeal). Each fetch
  // is FAIL-SOFT (null on error → falls back to the static badge text, never blocks
  // the sidebar) and runs in parallel. A badge whose live value is null keeps its
  // static fallback; market shows nothing when 0 alerts (a red "0" alert is noise).
  const [live, setLive] = useState<{
    routines: number | null; projects: number | null; marketAlerts: number | null; claudePct: number | null;
  }>({ routines: null, projects: null, marketAlerts: null, claudePct: null });

  useEffect(() => {
    let alive = true;
    const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
    Promise.allSettled([getRoutines(), getProjects(), getMarket(), getClaudeUsage()]).then((r) => {
      if (!alive) return;
      const [rt, pj, mk, cu] = r;
      setLive({
        routines: rt.status === "fulfilled" ? num(rt.value?.data?.activeCount) : null,
        projects: pj.status === "fulfilled" ? num(pj.value?.data?.summary?.total) : null,
        marketAlerts: mk.status === "fulfilled" ? num(mk.value?.data?.triggers?.length) : null,
        // MATCH the S9 screen + Home tile: they use pct5h (the 5h quota %) and fall
        // back to pct only without a snapshot — NOT raw pct, which overflows 100%
        // once today=all-project tokens (single source of truth, honest-mirror).
        claudePct: cu.status === "fulfilled" ? (num(cu.value?.data?.pct5h) ?? num(cu.value?.data?.pct)) : null,
      });
    });
    return () => { alive = false; };
  }, []);

  /** Live badge text per route; falls back to the static nav text when live is null. */
  function badgeText(route: string, fallback: string): string {
    switch (route) {
      case "/routines": return live.routines != null ? String(live.routines) : fallback;
      case "/projects": return live.projects != null ? String(live.projects) : fallback;
      case "/market": return live.marketAlerts != null ? String(live.marketAlerts) : fallback;
      case "/claude-usage": return live.claudePct != null ? `${Math.round(live.claudePct)}%` : fallback;
      default: return fallback;
    }
  }

  /** Hide a badge entirely when its live value is a "nothing to flag" zero (market
   *  alerts = 0 → no red badge). Other badges always show (0 projects is meaningful). */
  function showBadge(route: string): boolean {
    if (route === "/market" && live.marketAlerts === 0) return false;
    return true;
  }

  return (
    <aside className="sidebar" data-sidebar>
      <div className="sb-top">
        <div className="sb-logo">L</div>
        <div className="sb-word">
          LIFE·<b>OS</b>
        </div>
        <button
          type="button"
          className="sb-collapse"
          onClick={() => onToggleCollapse?.()}
          title="Thu gọn"
          aria-label="Thu gọn sidebar"
          data-collapse-toggle
        >
          <Icon name="i-chevron" />
        </button>
      </div>

      <nav className="sb-nav" aria-label="Điều hướng chính">
        {NAV.map((group) => (
          <div key={group.sec} data-nav-group>
            <div className="sb-sec">{group.sec}</div>
            {group.items.map((item) => {
              const active = mounted && isActive(item.route, pathname);
              return (
                <Link
                  key={item.route}
                  href={item.route}
                  className={`sb-item${active ? " on" : ""}`}
                  title={item.label}
                  aria-current={active ? "page" : undefined}
                  data-route={item.route}
                  data-nav-item
                >
                  <Icon name={item.icon} />
                  <span className="lbl">{item.label}</span>
                  {item.badge && showBadge(item.route) && (
                    <span className={`badge ${item.badge.cls}`} data-testid={`nav-badge-${item.route}`}>
                      {badgeText(item.route, item.badge.text)}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <Link href="/settings" className="sb-user" data-route="/settings" data-nav-item>
        <div className="avatar">CH</div>
        <div className="uinfo">
          <b>Chỉ huy</b>
          <span>pro · vira</span>
        </div>
      </Link>
    </aside>
  );
}
