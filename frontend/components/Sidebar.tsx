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
import { getRoutines } from "@/lib/api";

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

  // Wire the /routines (Automation) nav badge to LIVE activeCount (was static "5").
  // Only this badge this sprint; the other 3 stay static (per dispatch). Fail-soft:
  // null on error → falls back to the static badge text, never blocks the sidebar.
  const [activeRoutines, setActiveRoutines] = useState<number | null>(null);
  useEffect(() => {
    getRoutines()
      .then((res) => setActiveRoutines(res?.data?.activeCount ?? null))
      .catch(() => setActiveRoutines(null));
  }, []);

  /** Live badge text for /routines; static badge for everything else. */
  function badgeText(route: string, fallback: string): string {
    if (route === "/routines" && activeRoutines != null) return String(activeRoutines);
    return fallback;
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
                  {item.badge && (
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
