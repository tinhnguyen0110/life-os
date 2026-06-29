# End Sprint GRAPH-POLISH — Graph Explorer responsive + zoom/pan + label declutter

Board task: #173. User: Graph Explorer feels limited — responsive full-width + Obsidian-style zoom/pan + labels not overlapping. Pure FE.

## What shipped
The Graph Explorer is now responsive (fills the panel), supports wheel-zoom + drag-pan via a stateful viewBox (with a reset button), guards click-vs-drag so panning doesn't open a note, and declutters labels zoom-aware. The deterministic layout is untouched. BE: 0 change.

### Changes implemented (4-step verified on disk + live Chrome via team-lead)
- **Responsive full-width** — the SVG is `width:100%` + a stateful `viewBox`; W=760/H=460 are now the coordinate-space (the viewBox dims + the 0..100→W/H layout scaling), not a pinned pixel width. Renders at clientW (e.g. 884) scaled from the 760 coord-space.
- **Zoom/pan via viewBox** (graph/page.tsx) — `view={x,y,w,h}` state. Wheel = zoom toward the cursor (the pointed-at viewBox point stays fixed: `nx = cx - (cx-view.x)*ratio`), clamped `view.w ∈ [W*0.25, W*2.5]`. Drag on the SVG bg = pan (pixel delta × `view.w/clientWidth` → viewBox units; drag-right moves the camera left). A ⟲ reset button restores the default view. No heavy lib — plain viewBox math. The deterministic layout (hash-seeded, no Math.random) is UNTOUCHED — the camera sits on top.
- **🔴 Click-vs-drag threshold (the regression risk)** — `onMouseDown` resets `didPanRef=false` + records the anchor; `onMouseMove` only sets `didPan=true` + pans once movement ≥ 4px (under = still a click); the node `onClick` does `if (didPanRef.current) return` before focusNote. So a clean click opens the note; a drag pans without opening. didPan resets on every mousedown → a click after a drag works.
- **Zoom-aware labels** — `showLabel` now shows MORE labels when zoomed in (`view.w < LABEL_ZOOM_W`, e.g. degree≥2) and keeps the declutter (hovered/degree≥4) at default/zoomed-out; ego mode keeps all. Edge nodes reachable by panning.
- Scoped `.wgraph-reset` CSS (no global token). Ego/local mode, hover-highlight, search all preserved.

### Verification (pass/fail)
- tsc exit 0; vitest graph 22/22 (+7 new: responsive viewBox, wheel-zoom changes viewBox, drag-pans + suppresses node click, clean-click opens note, reset, zoom-aware labels). Full suite 1130 per FE report. ✅
- BE: 0 files changed. ✅
- team-lead Chrome-gate FULL PASS (live — jsdom can't see pan/zoom, so live is the gate): responsive (clientW 884 vs coord-space 760) · wheel-zoom 760→684 toward cursor + reset → "0 0 760 460" · 🔴 drag-pan keeps URL /wiki/graph (no ?note=) · 🔴 clean click → ?note=29 local mode · local/ego OK · console clean. The click-vs-drag risk verified BOTH ways live. ✅

### 3 Quality Gates
- **Gate 1 (API)**: ✅ N/A — pure FE, no API change.
- **Gate 2 (Function)**: ✅ unit tests assert observable behavior incl. the click-vs-drag both-ways (the regression guard); tsc clean; 0 errors; the didPan lifecycle correct (reset on mousedown, suppress on drag, open on clean click); zoom math fixed-point + clamped.
- **Gate 3 (Sprint)**: ✅ this report w/ verified counts; architect read the full pan/zoom/didPan handlers on disk + confirmed the deterministic layout untouched; team-lead Chrome-gate pass (both click-vs-drag directions live); commit format match.

## Risks / potential errors identified
- The didPan flag stays true between mouseup and the node onClick (correct — that's how the suppression works); it resets on the next mousedown. No stuck state. Verified.
- Pre-existing graph.test act() warnings (~12) are NOT from #173 (pre-existing); macro.test is an env flake. Full suite 0 fail. Noted, not introduced here.
- Zoom clamp [W*0.25, W*2.5] is a sensible range; if a user wants deeper zoom it's a 1-line constant change.

## Assumptions (user-review)
- **Zoom/pan via viewBox (no d3-zoom lib)** — *why*: lean, keeps the deterministic layout, no dependency; Obsidian-feel (scroll-zoom, drag-pan) achieved with plain math — *how to change*: adjust ZOOM_MIN_W/ZOOM_MAX_W (zoom range) or DRAG_THRESHOLD (click-vs-drag sensitivity) constants.
- **Zoom clamp = [0.25×, 2.5×] of the coord-space** — sensible default; editable via the constants.
- **Click-vs-drag threshold = 4px** — under = click (opens note), over = pan; editable.

## Commit
`feat(sprint-graph-polish): responsive full-width + viewBox zoom/pan + click-vs-drag + zoom-aware labels`
Explicit-paths only (graph/page.tsx + graph test + tokens.css + 2 sprint docs; NOT template/Life Command/* or docs or projects-tests).
