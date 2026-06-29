# Sprint GRAPH-POLISH-C — graph spacing (nearest-dist/radius 2.84× → ~4-5×)

Board task: #176. Reactive follow-up to #175. User: "vẫn dày quá" (still too dense). team-lead measured live (global 55 nodes): avg nearest-dist=35.6px, avg radius=12.5px → **ratio 2.84×** (gap ≈10px, nodes nearly touching). #175's bigger sizes made it tighter.

## Kickoff — 2026-06-29

### Root cause (team-lead diagnosed, confirmed on disk)
Force L93-98: REPEL=9.7 → CHARGE≈0.91 (repulsion WEAK) vs the edge-spring (LINK_FORCE 0.9, SPRING_LEN 22) → edges pull nodes into a tight clump. COLLIDE_STR=0.5 + a small layoutR (L107: `0.9 + 0.5·…/3` ≈ 1-3 in 0..100 space) → the personal-bubble is narrow → nodes settle close.

### Key insight on the metric
The measured ratio is in PIXELS (nearest-dist 35.6 / radius 12.5). The LAYOUT is 0..100 space + the #174 auto-fit viewBox. Render radius is fixed px (not viewBox-scaled); layout distances scale with auto-fit. So a wider px gap needs the layout to spread nodes MORE in 0..100 (auto-fit then frames the wider spread). The most CONTROLLABLE lever for a measurable min-gap = the COLLIDE minD: if collide enforces a min separation ∝ the node radii × a gap factor, the ratio target is met directly. Charge + spring-length are the secondary spreaders.

### Decisions (architect)
- **Primary lever — wider collide minD (the measurable gap):** make `minD = (layoutR_i + layoutR_j) × GAP` with GAP ~1.6-2.0, AND widen layoutR so it's proportional to the render radius (the render r = `max(6,min(4+6√deg,30))` px; layoutR should mirror that shape so a node's bubble ≈ its visual size + breathing). Result: every node keeps a gap ≥ ~1.5-2× its diameter from neighbors → the px ratio rises to the ~4-5× target. Raise COLLIDE_STR a bit (0.5→~0.7) so the bubble is actually enforced (not just nudged).
- **Charge stronger:** REPEL 9.7→~13-15 (CHARGE = REPEL³/1000 → ~2.2-3.4, i.e. 2-3× current) → global separation pressure rises so nodes don't re-clump between collide bubbles.
- **Spring longer:** SPRING_LEN 22→~32-40 → edges allow connected nodes to sit farther apart while still tethered (so spreading doesn't fight the links).
- **Balance (the trade-off):** thoáng BUT one connected cluster — charge/collide must NOT overwhelm the spring so hard that a cluster flies apart/disconnects. Keep LINK_FORCE adaptive (per min-degree). May raise `iters` (120→~150) so the wider layout settles. The #174 auto-fit re-frames → still snug, no fly-off.
- **Measurable target:** nearest-dist/radius ~4-5× (vs 2.84), gap ≥ 1.5-2× node diameter. team-lead re-measures the DOM ratio at the gate.
- KEEP: F1-F5 (#175 hub-hierarchy + halo + ~3.8× size), deterministic hash-seed, SVG, #173/#174 A-E, no new dep.

### Defensive
- Connected, not scattered (charge/collide vs spring balance — verify a cluster still holds, no orphan-fling). Deterministic (all pure fns of degree; no Math.random). auto-fit still frames (no fly-off). Hub-hierarchy + halo labels from #175 preserved.

### BE/FE split
- **FE only.** graph/page.tsx force constants + collide minD/layoutR. BE untouched.

### Final task list
- **T1 (FE):** raise CHARGE (REPEL→~14), SPRING_LEN→~36, COLLIDE_STR→~0.7, widen layoutR to mirror render-radius × a gap factor (minD≈(r_i+r_j)×~1.7); bump iters if needed; keep clusters connected. Tests: nearest-dist/radius ratio ↑ vs baseline (a deterministic layout-spacing assertion), still connected (a cluster's nodes within spring reach), deterministic, F1-F5 + #173/#174 not regressed.

### Dispatch plan
- frontend ← T1. tester + team-lead Chrome-gate: re-measure DOM ratio (~4-5× target) + eyes-on thoáng + connected + hierarchy kept + console clean.

## Assumptions (user-review) — filled in end_sprint
