# Sprint GRAPH-POLISH — Graph Explorer responsive + zoom/pan + label declutter

Board task: #173. User: Graph Explorer feels limited (3 asks, NOT cap-node — 55 nodes render fine).

## Kickoff — 2026-06-29

### Current structure (graph/page.tsx, 393 lines)
- Fixed `W=760 H=460` (L25-26). Node coords = `(p.x/100)*W` (L191, L211) — layout is in a 0..100 normalized space scaled to W/H.
- Deterministic force layout (L59-, hash-seeded, NO Math.random — KEEP). ego (radial) + global (force) both deterministic + memoized (L159).
- Render: edges `<line>` (L188), nodes `<g transform=translate(x,y)> <circle> + <text label>` (L208), `onClick={focusNote}` (L229), hover-highlight via setHovered.
- Labels already declutter: global shows label only for hovered or degree≥4 (L223); ego shows all. No zoom awareness.
- The SVG is inside `.wgraph-canvas` panel (L296).

### Decisions (architect)
- **(1) Responsive full-width:** keep the internal coordinate space (0..W,0..H as the viewBox) but make the SVG `width="100%"` + `viewBox="0 0 W H"` + `preserveAspectRatio="xMidYMid meet"`. The layout math (0..100 → W/H) is UNCHANGED; the SVG just scales to the container. Drop the fixed pixel width on the `<svg>`. (W/H stay as the coordinate-space constants — they define the viewBox, not the rendered px.)
- **(2) Zoom/pan = mutate the viewBox** (the lean approach — no per-node transform recompute, layout stays deterministic): state `view = {x, y, w, h}` (init 0,0,W,H). Pan = drag → shift view.x/y by the drag delta (scaled by current zoom). Zoom = wheel → scale view.w/h around the cursor (clamp min/max zoom). Render `viewBox={`${x} ${y} ${w} ${h}`}`. A "reset view" button (⟲) to restore 0,0,W,H. This is Obsidian-like (scroll-zoom, drag-pan) without a heavy lib.
- **(3) Click-vs-drag threshold (don't let pan swallow click-open-note):** on the SVG, track mousedown (x,y) + a `didPan` flag; mousemove past a ~4px threshold sets dragging→didPan=true + pans; on a NODE onClick, if didPan → ignore (it was a pan, not a click). Reset didPan on next mousedown. So a clean click (movement <4px) opens the note; a drag pans without opening.
- **(4) Labels zoom-aware + edge nodes not clipped:** make `showLabel` zoom-aware — at higher zoom (view.w smaller than W → zoomed in) show more labels (e.g. degree≥2 or all when zoomed past a threshold); at default/zoomed-out keep the current declutter (hovered/degree≥4). Edge nodes: a small layout-bounds padding (keep nodes within ~5% margin so a high-degree node's radius+label isn't clipped at the viewBox edge) — OR rely on the pannable viewBox (user can pan to any edge node). Lean: the pannable viewBox already lets the user reach edge nodes; add a small label-collision avoidance only if cheap. Priority = zoom-aware label count.

### Defensive
- KEEP the deterministic layout (hash-seeded, no Math.random) — only the viewBox transform sits on top; same seed → same node positions.
- Local (ego) mode still works — zoom/pan applies to both modes.
- Click-open-note must still fire on a clean click (the #1 regression risk — test it).
- Scoped classes / inline — no global token change.

### BE/FE split
- **FE only.** graph/page.tsx + scoped CSS (tokens.css .wg-* if needed). BE untouched (graph endpoint returns all 55 nodes, no cap — confirmed).

### Final task list
- **T1 (FE):** responsive SVG (width 100% + viewBox) · zoom (wheel) + pan (drag) via viewBox state + reset button · click-vs-drag threshold (clean click opens note, drag pans) · zoom-aware label declutter · keep deterministic layout + ego mode + hover-highlight. Tests: viewBox responsive, wheel-zoom changes viewBox, drag pans + suppresses node click, clean-click opens note, zoom-aware labels, deterministic layout unchanged.

### Dispatch plan
- frontend ← T1 (whole thing). tester: zoom/pan behavior + click-not-swallowed. team-lead Chrome-gate (full-width, zoom/pan works, labels don't overlap, click opens note, local mode OK, console clean).

## Assumptions (user-review) — filled in end_sprint
