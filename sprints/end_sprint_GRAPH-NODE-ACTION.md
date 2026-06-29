# End Sprint GRAPH-NODE-ACTION — click-node menu (2 buttons) + docs side-panel

Board task: #178. User CHỐT: click a node → a small VISIBLE 2-button menu (📄 Xem docs / 🎯 Focus) — no hidden 1-click/double-click; docs = a right side-panel.

## What shipped
Clicking a graph node now opens a portaled 2-button menu at the node; "Xem docs" opens a right docs side-panel (reusing the /wiki/[id] pieces) with the graph shrinking + auto-fit re-framing; "Focus" is the existing ego mode. Pure FE, reuse-not-rebuild, #173-177 intact, BE untouched, no new dep.

### Changes implemented (4-step verified on disk + independent test re-run; team-lead Chrome-gate)
- **D1 — click → portaled 2-button menu** — node onClick is `if (didPanRef.current) return; openNodeMenu(n.id)` — the #173 click-vs-drag gate is PRESERVED (a drag/pan does NOT open the menu). Opens the shared `<Popover>` (portaled → no transform-clip, the #142 lesson) anchored at the node's screen-point (viewBox coords → px via the SVG rect + current view) with "📄 Xem docs" + "🎯 Focus". Click-away/Escape close.
- **D2 — docs side-panel (right)** — `.wg-row` flex wraps `.wgraph-canvas` (flex:1, min-width:0 → shrinks) + `.wg-docs-panel` (380px). Body reuses `useWikiNote(openDocsId)` → StatusPill + title + `WikiMarkdown(note.content)` + compact `BacklinksPanel` + "→ mở full /wiki/[id]" + ✕ (honest loading/error from useWikiNote). On open/close the graph width changes → a `prevDocsRef` effect re-snaps the view to the auto-fit bounds (cancels any in-flight zoom-lerp) so the graph re-centers cleanly at the new width, still fully interactive. Scoped `.wg-docs-*`/`.wg-nodemenu*` (panel overflow:hidden but the inner `.wg-docs-body` is overflow:auto → the body scrolls, not clipped).
- "Focus" → the existing focusNote (ego ?note=id).

### Verification (pass/fail)
- tsc exit 0; vitest graph 43/43 (architect re-ran; +3 over #177's 40). Full suite 1151 per FE report. 0 errors. ✅
- Menu real-click-only: didPanRef gate preserved (read on disk + FE DOM-verified menuAfterDrag:false). ✅
- Reuse confirmed: Popover (portaled), useWikiNote, WikiMarkdown/BacklinksPanel/StatusPill — no rebuild. ✅
- Auto-fit re-frame on width change: prevDocsRef effect re-snaps to fit on openDocsId toggle. ✅
- tokens scoped `.wg-row`/`.wg-docs-*`/`.wg-nodemenu*` — no global token; panel-overflow doesn't clip (inner body scrolls). ✅
- team-lead Chrome-gate FULL PASS (live + DOM + eyes-on): menu 2 buttons at node (portaled-to-body) · "Xem docs" → right panel renders note #26 (DOCS·#26 + status + full markdown + email link + mở-full + ✕) · graphW 1190→798px on open + auto-fit re-frame + cluster colors still visible · "Focus" → ego · drag does NOT open menu (didPan) · #173-177 (cluster/hierarchy/spacing/halo) kept · console clean (the SWC 2:45:40 line = stale, verified clean). ✅

### 3 Quality Gates
- **Gate 1 (API)**: ✅ N/A — pure FE (reuses existing /wiki read endpoints via useWikiNote).
- **Gate 2 (Function)**: ✅ tests assert observable behavior (menu opens on click not drag, Focus→focusNote, Xem docs→panel renders, close→full, #173-177 not regressed); tsc clean; 0 errors; useWikiNote honest states; portal-no-clip; auto-fit re-frame.
- **Gate 3 (Sprint)**: ✅ this report w/ verified counts; architect read the menu/panel/auto-fit on disk + re-ran tests; team-lead Chrome-gate pass (DOM + eyes-on); commit format match.

## Risks / potential errors identified
- Panel overflow:hidden on `.wg-docs-panel` is intentional (clips the slide), the inner `.wg-docs-body` is overflow:auto → the markdown body scrolls, not clipped (NOT the overflow-clips-content trap). Verified.
- The SWC console line at an earlier gate timestamp = stale hot-reload artifact (team-lead verified tsc clean + served-HTML has the graph + render works) — not a build bug; do not touch syntax. (Same pattern as #174.)
- Node screen-point anchor is computed from the current view — if the user pans while the menu is open, the anchor doesn't follow (the menu closes on click-away anyway). Acceptable.

## Assumptions (user-review)
- **Menu = 2 visible buttons (Xem docs / Focus), no hidden click/double-click** — *why*: user CHỐT "không ai biết cơ chế ẩn" → explicit buttons. *how to change*: edit the Popover menu contents.
- **Docs = right side-panel reusing /wiki/[id] pieces (useWikiNote + WikiMarkdown + BacklinksPanel)** — *why*: user agreed the side-panel; reuse avoids a second note-renderer. *how to change*: panel width / which fields shown are in graph/page.tsx + .wg-docs-* CSS.
- **Focus = existing ego mode (?note=id)** — unchanged.

## Commit
`feat(sprint-graph-node-action): click node → menu (Xem docs / Focus) + docs side-panel (reuse useWikiNote)`
Explicit-paths only (graph/page.tsx + graph test + tokens.css + 2 sprint docs; NOT template/Life Command/* or docs or projects-tests).
