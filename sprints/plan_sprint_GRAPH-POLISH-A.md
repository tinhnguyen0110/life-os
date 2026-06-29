# Sprint GRAPH-POLISH-A — organic graph (remove box-clamp + auto-fit viewBox)

Board task: #174. Reactive follow-up to #173. User: zoom/pan shipped but the graph still looks "limited / rectangular-framed".

## Kickoff — 2026-06-29

### Root cause (team-lead diagnosed, confirmed on disk)
`globalLayout` L118-119: `p.x = Math.max(3, Math.min(97, p.x))` + `p.y = Math.max(4, Math.min(96, p.y))` — a HARD clamp. Nodes pushed past the box edge by repulsion get PINNED onto the edge → they pile along the 4 sides → the "rectangular frame" the user sees. #173 added the camera (viewBox) but never touched this layout clamp.

### Decisions (architect)
- **(1) Remove the hard clamp (L118-119).** The `CENTER=0.012` pull already bounds the cluster (each node is pulled toward 50,50 every iter) → without the clamp, nodes settle organically (clusters, not a box). They won't drift infinitely — centering is the soft bound. Orphans (degree 0) get only repulsion + centering → they sit a bit out but centering reins them in (not infinite). Keep CENTER (maybe nudge slightly if orphans fly — but L87 CENTER=0.012 + the seed radius cap should hold; the implementer tunes if a live orphan flies unreasonably).
- **(2) Auto-fit viewBox** — after layout, compute the real node bounding box in the RENDERED coordinate space (each node renders at `(p.x/100)*W, (p.y/100)*H` — so bounds = min/max over those) + a padding margin → that becomes the DEFAULT view (`{x,y,w,h}` = the fitted box) AND the reset target. Replaces the hardcoded `{0,0,W,H}`. The graph fills its natural shape, not a forced 760×460 rectangle. Guard: if bounds are degenerate (1 node / all-same) fall back to a sensible default centered on the node.
- **(3) Keep #173 intact** — zoom/pan/click-vs-drag/wheel all unchanged; ONLY the default-view + reset target change (now = fitted bounds, computed from the layout). reset ⟲ → the new fitted bounds (not "0 0 760 460").
- **(4) Ego/local (egoLayout L47-58)** — no hard clamp there (radial ring r=34 around 50,48 → ~16..84, naturally inside) but apply the SAME auto-fit so local mode frames its ego tightly too. Deterministic preserved.
- Deterministic: removing the clamp keeps determinism (the layout is still a pure fn of nodes/edges, no Math.random); same vault → same organic positions → same fitted viewBox.

### Coordinate-space note for the implementer
Node positions may now exceed 0..100 (no clamp). The render `(p.x/100)*W` still works (a node at p.x=108 → 1.08*W). The auto-fit viewBox must be computed in the SAME rendered space (×W/H) so it includes the out-of-0..100 nodes. The viewBox is what makes "outside the old box" visible — that's the point.

### BE/FE split
- **FE only.** graph/page.tsx (layout L112-120 clamp removal + an auto-fit-bounds helper + default-view/reset wiring). BE untouched.

### Final task list
- **T1 (FE):** remove the hard clamp (L118-119); add `fitBounds(pos)` → bounding box (in W/H space) + padding → ViewBox; set DEFAULT_VIEW / the initial view + reset to the fitted bounds (memoized from the layout, deterministic); apply auto-fit to both global + ego; keep CENTER cohesion (tune only if a live orphan flies); keep all #173 zoom/pan/click. Tests: no clamp (a node can be outside 0..100 / not all pinned to edges), auto-fit viewBox = node bounds + padding (not 0,0,760,460 when bounds differ), reset → fitted bounds, deterministic (same input → same fit), #173 zoom/pan/click still pass.

### Dispatch plan
- frontend ← T1. tester: organic (no edge-pile) + fit + #173-not-regressed. team-lead Chrome-gate (no rectangular frame, fit, zoom/pan/click OK, local OK, deterministic, console clean).

## UPGRADE — adapt Obsidian force + zoom-lerp from repo_ref/webobsidian (user CHỐT)
Reference (READ-ONLY, LIFT LOGIC — keep our SVG + deterministic seed, NO PixiJS/d3 dep): `repo_ref/webobsidian/web/src/components/GraphView.tsx`. Studied L60-93 (force) + L233-253/865-898 (zoom-lerp).

### Obsidian force formulas (extracted — apply to our manual SVG force loop, keep hash-seed)
- charge (repulsion) = `−repelForce³` per node (Obsidian default repelForce=10 → −1000 in d3 world units; SCALE to our 0..100 space — the implementer tunes the constant so clusters spread nicely, NOT a literal −1000 which would explode a 0..100 layout).
- link strength = `linkForce / min(deg_source, deg_target)` (adaptive: high-degree hubs pull less per-edge → organic). linkForce default ~1.
- link distance = a constant (Obsidian 250 world units → scale to our space, ~14-18 like the current SPRING_LEN).
- center pull = `easeStrength(centerForce)`; centerForce 0.52 → 0.1. (Our current CENTER=0.012 is gentler; bumping toward ~0.05-0.1 via the formula keeps the cluster centered without a box.)
- collide: a soft radius-based separation (Obsidian forceCollide radius 60 strength 0.5) so nodes don't overlap — adapt as a min-distance push in our loop.
- node radius (render) = `max(8, min(3·√(deg+1), 30))` — replaces the current `(isGlobal?5:8)+degree*…` so hubs are bigger, leaves smaller (Obsidian feel).
- ⚠️ Lift the FORMULAS/coefficients ONLY. KEEP our deterministic hash-seed init (the ref uses d3 random → would change every load; we must stay deterministic). No new dep.

### Zoom-lerp (smooth, cursor-anchored — adapt to our viewBox model)
- The ref uses a cam {x,y,k} (translate+scale); OUR model is viewBox {x,y,w,h} where smaller w = zoomed in. Map: the ref's `k` (scale up) ↔ our `view.w` (down). 
- wheel → set a `targetW` = `view.w / 1.5^(−ΔY/120)` (i.e. wheel-in shrinks targetW), clamped to [W*0.25, W*2.5] (our existing clamp). Anchor: zoom-IN → cursor; zoom-OUT → viewport center.
- a requestAnimationFrame loop lerps the ACTUAL view.w 15%/frame toward targetW (`w = w*0.85 + targetW*0.15`), each frame recomputing x/y so the anchor's viewBox-point stays fixed (the same fixed-point math as #173's wheel, but applied per-frame toward the target). Stop the loop when |w−targetW|/targetW < ~0.01. 🔴 cleanup the rAF on unmount (no leak).
- This REPLACES #173's instant per-wheel viewBox jump with a smooth eased zoom; pan + click-vs-drag + reset stay as #173.

### (optional, if fast) degree-declutter labels + hover-fade lerp — nice-to-have, not required this sprint.

### Upgrade guardrails
- KEEP SVG (no PixiJS), KEEP deterministic hash-seed (no d3 random), KEEP #173 pan/click-vs-drag/reset(→fit-bounds)/local-ego. rAF cleanup on unmount. Lift logic only — do NOT copy the file (different stack). No new dep (d3/pixi).

## Assumptions (user-review) — filled in end_sprint
