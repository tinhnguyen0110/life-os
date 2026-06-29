# Sprint GRAPH-NODE-ACTION — click-node menu (2 visible buttons) + docs side-panel

Board task: #178. User CHỐT: click a node → a small VISIBLE menu (📄 Xem docs / 🎯 Focus); docs = a right side-panel. No hidden 1-click/double-click mechanics.

## Kickoff — 2026-06-29

### Reusable pieces (confirmed on disk — build on these, don't rebuild)
- **Popover.tsx** — the portaled anchored-overlay (#142-P1 fix: portal avoids transform-clip + click-away/Escape). API `<Popover open anchorRef onClose>{menu}</Popover>`. Reuse for the 2-button menu.
- **useWikiNote(id)** → `{note, backlinks, status, errMsg, warning, reload, save, remove}` — loading/error honest built in. Reuse for the docs panel.
- **WikiMarkdown** + **BacklinksPanel** + **StatusPill** (components/shared) — reuse for the panel body.
- Graph click: currently `onClick={() => { if (didPanRef.current) return; focusNote(n.id); }}` (L587) — the click-vs-drag gate (#173 didPanRef) STAYS; only the action changes (open menu instead of straight focus).
- Layout: `.wgraph-canvas` > `.wgraph-stage` (SVG). auto-fit (#174) re-frames on width change.

### Decisions (architect)
- **D1 — menu = portaled Popover at the node.** On a real click (didPanRef false), open a Popover with 2 buttons: "📄 Xem docs" + "🎯 Focus". Anchor: a positioned anchor element at the clicked node's SCREEN point (compute from the node's viewBox coords → screen px via the SVG's CTM/clientRect + the current view). The Popover handles click-away/Escape + collision. (Portal avoids the #142 transform-clip.) Track the clicked node id in state.
  - "Xem docs" → open the docs side-panel for that id.
  - "Focus" → the existing focusNote(id) (ego mode ?note=id).
- **D2 — docs side-panel (right), graph shrinks left.** Wrap `.wgraph-canvas` + a new `.wg-docs-panel` in a flex row. Panel ~360-420px, slides in from the right when a node's docs are open. Body: `useWikiNote(id)` → StatusPill + title + WikiMarkdown(note.content) + a compact BacklinksPanel (outbound/backlinks) + "mở full → /wiki/[id]" link + ✕ close. Honest loading/error (useWikiNote states). On open, the graph canvas shrinks → auto-fit (#174) re-frames to the new width (still fully interactive: zoom/pan/click). On close → graph full width again. Scoped `.wg-docs-*`.
- KEEP: #173-177 (zoom/pan/click-vs-drag/organic/hierarchy/spacing/cluster), deterministic, SVG, no new dep.

### Defensive
- Menu opens ONLY on a real click (drag/pan must NOT open it — the didPanRef gate). Escape/click-away closes the menu; ✕/Escape closes the panel.
- Panel open → graph shrinks + auto-fit re-frames (not clipped/squished); close → full. The panel mount must NOT break zoom/pan/click on the (narrower) graph.
- Portal (Popover) avoids the transform-clip (#142 lesson — the graph's animated container would clip a non-portaled overlay).
- useWikiNote loading/error honest (panel shows a spinner/error, never a blank or a fabricated note).

### BE/FE split
- **FE only.** graph/page.tsx (click→menu, the docs panel, the flex layout) + scoped CSS. Reuses Popover + useWikiNote + WikiMarkdown + BacklinksPanel. BE untouched.

### Final task list
- **T1 (FE):** (a) click→portaled Popover menu (2 buttons, anchored at node screen-point, click-away/Escape, only on real click via didPanRef); (b) "Focus"→focusNote, "Xem docs"→open the right side-panel; (c) docs panel reusing useWikiNote + WikiMarkdown + BacklinksPanel + StatusPill + full-link + close; (d) flex layout: graph shrinks when panel open, auto-fit re-frames, full on close. Tests: click opens the 2-button menu (not straight focus); drag does NOT open it; Focus→focusNote; Xem docs→panel renders the note (mock useWikiNote); panel close→graph full; #173-177 not regressed.

### Dispatch plan
- frontend ← T1. tester + team-lead Chrome-gate: menu 2 buttons visible at node · Xem docs→right panel renders (title/status/markdown/backlinks/full-link) · Focus→ego · graph shrinks + still interactive · drag doesn't open menu · #173-177 kept · console clean.

## Assumptions (user-review) — filled in end_sprint
