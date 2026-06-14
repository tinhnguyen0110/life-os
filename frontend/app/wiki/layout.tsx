"use client";
/* ============================================================
   Wiki layout (WEXP-FE) — 2-pane Obsidian shell wrapping ALL wiki routes
   (Vault/Note/Graph/Inbox/Proposals/MOC/Sync). Explorer pane LEFT | content outlet.

   Pane side = explorer LEFT (Obsidian convention; team-lead-approved). The user said
   "phải"/right — shipped LEFT + logged as a vetoable choice. The flip is a single
   CSS order: change `--wex-order` (the explorer's flex order) to swap sides — no
   structural change. Collapsible: hide the explorer for full-width reading.
   ============================================================ */
import { useState } from "react";
import { WikiExplorer } from "@/components/shared/WikiExplorer";
import { Icon } from "@/lib/icons";

export default function WikiLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className={`wiki-2pane ${collapsed ? "wex-collapsed" : ""}`} data-testid="wiki-2pane" data-collapsed={collapsed || undefined}>
      {/* LEFT: explorer pane (vetoable side via the .wiki-2pane flex order) */}
      <aside className="wiki-pane-left" data-testid="wiki-pane-left" hidden={collapsed}>
        <WikiExplorer />
      </aside>

      {/* collapse toggle — always visible so the pane can be reopened */}
      <button
        type="button"
        className="wiki-pane-toggle"
        onClick={() => setCollapsed((c) => !c)}
        title={collapsed ? "Hiện explorer" : "Ẩn explorer"}
        aria-label={collapsed ? "Hiện explorer" : "Ẩn explorer"}
        aria-expanded={!collapsed}
        data-testid="wiki-pane-toggle"
      >
        <Icon name="i-chevron" />
      </button>

      {/* RIGHT: the wiki route renders here */}
      <div className="wiki-pane-content" data-testid="wiki-pane-content">
        {children}
      </div>
    </div>
  );
}
