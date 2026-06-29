# Sprint GRAPH-CLUSTER — color-by-cluster (A) + cluster-aware force / islands (B)

Board task: #177. User CHỐT A+B (from the DISCUSS), DEFER Louvain.

## Kickoff — 2026-06-29

### Topology (measured at DISCUSS)
19 connected components over resolved edges: 1×28 (main) + 1×5 + 1×4 + 2×2 + 14 isolated orphans (deg 0). The grouping already exists; the layout just doesn't use it.

### Decisions (architect)
- **D1 — CC computed CLIENT-SIDE (FE), NO BE.** The FE already has nodes+edges in the graph payload; a BFS/union-find flood-fill over the rendered edges is ~15 lines, deterministic, zero dep. BE `detect_clusters` FILTERS (size≥min & density≥min → returns only 2 of the 19) so it is NOT a full component-id source for coloring ALL nodes. → FE computes the full component map. Component-id = a STABLE label: assign by the MIN node-id in each component (deterministic — reload-stable; sorting components by their min member id gives a fixed palette index).
- **D2 — color UX: cluster = FILL, status = thin RING (border) on the node; orphan = grey.** This keeps BOTH signals: the dominant visual (fill) is the cluster the user asked for; status (green/blue/amber) moves to a thin stroke on the main circle (r). The existing center-ring (r+6) + orphan-ring (r+3, red dashed) are SEPARATE concentric rings → no conflict with a status stroke on the r circle. Orphans (deg 0, their own singleton component) render GREY fill (not a fake group color) — honest. Legend: update to show "fill = cụm · viền = status" (keep the status colors in the legend, add a cluster note). No toggle needed (one coherent encoding); if it reads busy at gate, a toggle is the fallback.
- **D3 — (B) cluster-aware force (the islands):** add two terms to the force loop — same-component attraction (members get an extra pull toward their component's centroid) + cross-component separation (a node feels extra repulsion from nodes in OTHER components). Tune GENTLY so it composes with #176 spacing (4.79×) + #175 hierarchy + #174 organic — don't blow those up. The component centroid pull is cheap + deterministic. CENTER + auto-fit keep the islands in-frame (no infinite drift); auto-fit must frame ALL islands (its bounds already cover all nodes → fine).
- KEEP: deterministic hash-seed, SVG, #173/#174/#175/#176 (zoom/pan/organic/hierarchy/halo/spacing), no new dep, auto-fit frames all islands.

### Defensive
- Orphans grey + at the rim, NOT gathered into a fake group (they're singleton components — honest). Islands separate BUT stay in the viewBox (auto-fit + CENTER). Component-id stable across reloads (min-id labeling → deterministic palette). Don't regress #176 spacing / #175 hierarchy (the cluster force is ADDITIVE + gentle).

### BE/FE split
- **FE only.** graph/page.tsx: client-side CC + palette + fill/ring render + the cluster force terms; tokens.css for any cluster-palette tokens (scoped). BE untouched.

### Final task list
- **T1 (FE):** (a) client-side connected-components (deterministic component-id by min member-id) + a deterministic color palette per component, orphan grey; node render cluster=fill + status=ring; legend update. (b) cluster-aware force: same-component centroid attraction + cross-component repulsion, tuned to preserve #176 spacing + #175 hierarchy; auto-fit frames all islands. Tests: same-component nodes share a color + a real component computed from edges; orphan grey; islands measurably more separated cross-cluster than within (deterministic layout assertion); #173-176 + deterministic not regressed.

### Dispatch plan
- frontend ← T1. tester + team-lead Chrome-gate: same-cluster same-color · tụ-thành-đảo (eyes-on "cụm đi với nhau") · orphan grey rim · auto-fit frames all · #173-176 kept · deterministic · console clean.

## Assumptions (user-review) — filled in end_sprint
