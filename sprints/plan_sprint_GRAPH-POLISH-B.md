# Sprint GRAPH-POLISH-B — hierarchical graph (hub spread + size hierarchy)

Board task: #175. Reactive follow-up to #174. User: global graph STILL too dense/overlapping. Wants hierarchy: hubs (high-degree) far apart + big; leaves (low-degree) small + clustered around their hub.

## Kickoff — 2026-06-29

### Root cause (team-lead diagnosed, confirmed on disk)
`globalLayout` L110: `f = CHARGE / d2` — **CHARGE is a constant** (≈0.91), so every node repels every other EQUALLY regardless of degree → no hub gets extra personal space → dense pile in the middle. The render-radius is degree-scaled but lightly (×0.32 layoutR / the render r) → hierarchy is faint. CENTER=0.055 pulls everything inward.

### Reference insight (repo_ref/webobsidian GraphView.tsx)
Real Obsidian uses **UNIFORM charge** (`chargeStrength = (_n) => charge(s)` L76 — degree-independent). Its hierarchy comes from **node SIZE (getSize = max(8,min(3√(deg+1),30))) + forceCollide(radius scaled by size) + adaptive link strength** — NOT degree-scaled charge. The bigger collide radius on a hub is what carves its space. So the faithful fix is SIZE-led + collide-by-render-radius; a light degree-charge multiplier is an acceptable extra lever for the explicit "hubs far apart" the user asked.

### Decisions (architect)
- **F1 — degree-scaled charge (the explicit hub-spread lever):** make pairwise repulsion depend on each node's degree. In the pairwise loop, each node EXERTS force scaled by its own charge-multiplier: node i pushes j by `f * chargeMul(i)`, j pushes i by `f * chargeMul(j)`, where `chargeMul(deg) = 1 + K*sqrt(deg)` (K ~0.4-0.8, tune). Effect: a hub repels everyone strongly (personal space) but a leaf repels weakly (settles near its hub). Symmetric loop → apply the OTHER node's multiplier to each node's displacement (di += force×chargeMul(j); dj -= force×chargeMul(i)). Keep the cube CHARGE base.
- **F2 — clearer size hierarchy:** widen the render-radius spread — increase the degree coefficient so a high-degree hub is clearly bigger and a leaf clearly smaller (e.g. `r = base + k·√(deg)` with a wider range, OR raise the 3√(deg+1) coefficient). Keep a **min radius ≥ ~6px** so a leaf is still clickable/hoverable (defensive — don't shrink below the click target). Make the COLLIDE radius use this render radius (so bigger hubs separate more — the Obsidian-true mechanism).
- **F3 — breathing room:** gentler CENTER (e.g. 0.055 → ~0.03-0.04) and/or longer SPRING_LEN so the graph spreads; collide by the new radii prevents stacking. The auto-fit viewBox (#174) re-frames the wider spread → still "ôm gọn" (won't fly off — centering + auto-fit bound it).
- KEEP: deterministic hash-seed, SVG, all of #174 (A-E: organic/auto-fit/zoom-lerp/toolbar/collision-cull) + #173 (click/drag/zoom/reset/local), no new dep.

### Defensive
- Hubs spread but STAY CONNECTED (the adaptive link spring still pulls their cluster — don't let charge overwhelm the spring → a disconnected scatter). Tune so clusters hold.
- Leaves small but CLICKABLE (min render radius ≥ ~6px; the click/hover hit-area must remain).
- No infinite drift (CENTER + auto-fit bound it).
- Deterministic (charge-mul is a pure fn of degree; no Math.random).

### BE/FE split
- **FE only.** graph/page.tsx force loop (F1 charge-mul + F3 tuning) + render-radius/collide (F2). BE untouched.

### Final task list
- **T1 (FE):** F1 degree-scaled charge-mul in the pairwise repulsion; F2 wider size hierarchy + min-clickable-size + collide-by-render-radius; F3 gentler center / longer spring for breathing room; auto-fit re-frames. Tests: hub (high-deg) ends farther from others than a leaf does (spread by degree); render radius monotonic in degree with a min floor; deterministic (same input → same layout); #173+#174 (click/drag/zoom/reset/local/auto-fit/collision-cull) still pass.

### Dispatch plan
- frontend ← T1. tester: hierarchy (hub spread + size) + click-leaf-still-works + not-regressed. team-lead Chrome-gate (hub far+big · leaf small+clustered · no middle-pile · breathing · leaf clickable · auto-fit snug · A-E+#173 kept · console clean).

## Assumptions (user-review) — filled in end_sprint
