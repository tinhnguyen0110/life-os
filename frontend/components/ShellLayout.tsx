"use client";
/* ============================================================
   ShellLayout — the #app grid that wraps every screen (mock #app).
   Holds collapse state (toggles #app.collapsed → 228px ⇄ 64px grid).
   Composition: Sidebar | (TopBar · CommandBar · {children scroll region} · TickerTape).
   children = the active route's screen, rendered inside .view.
   ============================================================ */
import { useState } from "react";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { CommandBar } from "./CommandBar";
import { LiveTickerTape } from "./TickerTape";

export function ShellLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div id="app" className={collapsed ? "collapsed" : undefined}>
      <Sidebar onToggleCollapse={() => setCollapsed((c) => !c)} />
      <div className="main">
        <TopBar />
        <div className="view">
          <CommandBar />
          {children}
        </div>
        <LiveTickerTape />
      </div>
    </div>
  );
}
