# End Sprint GRAPH-POLISH-A — organic graph (Obsidian force) + smooth zoom + filter-toolbar

Board task: #174. Reactive follow-up to #173, then upgraded (user pointed to repo_ref/webobsidian). User: graph still "rectangular-framed" + (upgrade) adapt Obsidian force/zoom + (D) filter on top, graph full-width.

## What shipped
The graph now lays out organically (no box-frame) using Obsidian's force formulas (adapted, deterministic seed kept), zooms smoothly (cursor-anchored rAF lerp), shows the filter as a thin top toolbar with the graph full-width, and de-overlaps labels via a deterministic collision-cull. Pure FE, BE untouched, no new dep.

### Changes implemented (4-step verified on disk + independent test re-run; team-lead Chrome-gate)
- **(A) Remove box-clamp + auto-fit viewBox** — the hard `Math.max(3,min(97))`/`(4,min(96))` clamp (the rectangular-frame root cause) is GONE; nodes spread organically, can exceed 0..100, and the viewBox auto-fits the real node bounds (×W/H + padding) as the default + reset target. Reset ⟲ → the fitted bounds.
- **(B) Obsidian force** (lifted formulas, scaled to 0..100, KEEP our hash-seed — NO d3, NO Math.random): charge = −repel³ (CHARGE=REPEL³/1000≈0.91, the cube = strong separation); adaptive link strength = LINK_FORCE/min(deg_s,deg_t) (hubs pull less per-edge → clusters); soft collide (push apart when within layout radii); center via easeStrength≈0.055 (centers without a box); node render radius = max(8,min(3√(deg+1),30)) (hubs bigger). The ±6 per-frame step-clamp + cooling kept (stability, NOT a box-clamp).
- **(C) Smooth zoom-lerp** — wheel sets a target view.w (×1.5^(dy/120)), clamped RELATIVE to the fitted box (0.12×–3× fit, not the fixed W — so a small organic graph can still zoom in); a rAF loop eases view.w 0.85/0.15 toward target, cursor-anchor on zoom-in / center on zoom-out. Native non-passive wheel listener (preventDefault works, console clean). `viewRef` updated synchronously each frame so the lerp converges (avoids a stuck-loop). rAF cleaned up on unmount + on reset.
- **(D) Filter toolbar on top + full-width** — `.wgraph-grid` 2-col → single column, graph full-width; the filter is a thin `.wgtoolbar` above the canvas (status chips + orphan toggle + Nodes·Edges + compact mode/center/depth); the cluster panel moved to a `.wcluster-pop` popover ("Cụm(N)" — kept, not deleted, honest-scope). Same filter state/handlers/testids — only relocated.
- **(E, fe-added) Label collision-cull** — global labels were overlapping in the tight cluster; a GREEDY cull sorts by degree desc with an **id tiebreak (deterministic)** + places a label only if its bbox doesn't overlap an already-placed one, capped. Zoom-in widens the culled set. Pure fn of (pos, nodes, zoom).

### Verification (pass/fail)
- tsc exit 0; vitest graph 30/30 (architect re-ran; +8 over the #173 22 — incl. E collision tests). Full suite 1138 per FE report. 0 errors. ✅
- Hard constraints (architect grep-verified): box-clamp GONE · NO Math.random (deterministic) · rAF cleanup present (4 cancel sites incl. unmount) · NO d3/pixi dep · lift-logic-not-copy. ✅
- Collision-cull determinism (the flagged risk): the sort has an id tiebreak (`b.degree-a.degree || a.id-b.id`) → fully deterministic, no unstable-order ambiguity. ✅
- tokens.css all scoped `.wg*`/`.wcluster-pop` — no global token. ✅
- team-lead Chrome-gate FULL PASS A-E: organic (no frame, hubs central/orphans outer) · smooth zoom logic (rAF 0.85/0.15, native wheel, fit-relative clamp — ease not observable in a hidden tab = env limit, not a bug) · filter toolbar on top + full-width + filter works from toolbar (DOM-verified) · 7 distinct labels no overlap · #173 click/drag/reset/local kept · console clean. ✅

### 3 Quality Gates
- **Gate 1 (API)**: ✅ N/A — pure FE.
- **Gate 2 (Function)**: ✅ tests assert observable behavior (no-clamp, auto-fit, deterministic layout+fit, zoom target+ease, collision-cull, #173 intact); tsc clean; 0 errors; deterministic preserved; rAF leak-safe.
- **Gate 3 (Sprint)**: ✅ this report w/ verified counts; architect read the force loop + zoom-lerp + collision-cull on disk + grep-verified the hard constraints + re-ran the tests; team-lead Chrome-gate pass; commit format match.

## Risks / potential errors identified
- The zoom ease isn't observable in a backgrounded tab (rAF throttles when hidden) — that's an environment limitation, NOT a bug (the logic is verified: rAF loop, sync-ref convergence, clamp). Documented.
- The SWC console line in an earlier gate was a STALE log (team-lead verified tsc + served-HTML + render are clean) — not a syntax bug; do not touch the syntax.
- Collision-cull caps labels (8 global / 24 zoomed per the impl) — a deliberate de-clutter, not a silent drop (zoom-in reveals more). Logged.

## Assumptions (user-review)
- **Box-clamp removed → organic layout** — *why*: the clamp pinned nodes to the 4 edges (the rectangular frame); removing it + centering gives Obsidian-style clusters — *how to change*: n/a (it's the fix).
- **Force params adapted from webobsidian (lift logic, SVG kept, deterministic seed)** — *why*: user-pointed reference; we lift the formulas (charge cube, adaptive link, collide, node-size, easeStrength) but keep our SVG + hash-seed (no d3 random → stays deterministic) — *how to change*: tune REPEL/LINK_FORCE/CENTER/SPRING_LEN constants in globalLayout.
- **Label collision-cull cap (8 global / wider on zoom)** — *why*: the tight cluster overlapped labels; greedy degree-priority cull keeps the readable few, zoom reveals more — *how to change*: edit the cap constant.
- **Zoom = rAF ease (tab-hidden not observable = env, not bug)** — documented.

## Commit
`feat(sprint-graph-polish-a): organic layout (Obsidian force, no box-clamp) + auto-fit + smooth zoom-lerp + filter-toolbar-on-top full-width + label collision-cull`
Explicit-paths only (graph/page.tsx + graph test + tokens.css + 2 sprint docs; NOT template/Life Command/* or docs or projects-tests).
