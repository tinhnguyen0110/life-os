# End Sprint GRAPH-POLISH-C — graph spacing (ratio 2.84× → 4.79×)

Board task: #176. Reactive follow-up to #175. User: "vẫn dày quá" (still too dense). team-lead measured: nearest-dist/radius = 2.84× (gap ~10px). Target ~4-5×.

## What shipped
A force-parameter tune that spreads the global graph: nearest-dist/radius rose from 2.84× → **4.79×** (independently measured), gap ~1.9× a node's diameter — visibly thoáng while staying one connected cluster. Pure FE, deterministic, F1-F5 + #173/#174 intact, BE untouched, no CSS change.

### Changes implemented (4-step verified on disk + independent test re-run; team-lead DOM re-measure)
- **Primary lever — wider collide bubble**: `layoutR = renderRpx(id)/(W/100)` (the collide bubble now mirrors the RENDER radius in layout space) + `minD = (layoutR_i + layoutR_j) × COLLIDE_GAP` with **COLLIDE_GAP=1.8** + firmer **COLLIDE_STR 0.5→0.7**. So every node keeps a measurable gap ≥ ~1.8× its summed radii from neighbors → the ratio target is enforced directly.
- **Stronger charge**: REPEL 9.7→**14** (CHARGE = REPEL³/1000 ≈ 2.7, ~3× the global separation pressure) → nodes don't re-clump between bubbles.
- **Longer spring**: SPRING_LEN 22→**36** → connected nodes sit farther apart while still tethered (spreading doesn't fight the links).
- **Settle**: iters 120→**150** (n≤60) so the wider layout converges deterministically.
- The #174 auto-fit viewBox re-frames the wider spread → still snug (no fly-off). F1 chargeMul (hub asymmetry) + the adaptive springs untouched → hubs stay spread + connected.

### Verification (pass/fail)
- tsc exit 0; vitest graph 37/37 (architect re-ran; +1 over #175's 36). Full suite 1145 per FE report. 0 errors. ✅
- Deterministic (grep): no Math.random; all force terms pure fns of degree/position. ✅
- Constants on disk match the cited tune (REPEL 14, SPRING_LEN 36, COLLIDE_STR 0.7, COLLIDE_GAP 1.8, iters 150). ✅
- team-lead Chrome-gate FULL PASS (independent DOM re-measure): **avgNN 60.0 / avgR 12.5 = 4.79×** (vs 2.84×, target met) · 74 edges, ONE connected cluster (not scatter), auto-fit snug · eyes-on thoáng (clear gaps, no touching) · F1-F5 hierarchy (3.8×) + halo labels kept · #173/#174 (click/drag/zoom/reset/local/organic/toolbar/auto-fit) kept · leaf clickable · console clean. ✅

### 3 Quality Gates
- **Gate 1 (API)**: ✅ N/A — pure FE.
- **Gate 2 (Function)**: ✅ tests assert observable behavior (spacing ratio > baseline, connected, deterministic, hierarchy + #173/#174 not regressed); tsc clean; 0 errors; connected-not-scattered verified (springs untouched + the new spacing test); leaf clickable (≥6px floor from #175).
- **Gate 3 (Sprint)**: ✅ this report w/ verified counts; architect read the tuned constants + collide on disk + audited the test retarget + re-ran tests; team-lead Chrome-gate pass (re-measured 4.79×); commit format match.

## Risks / potential errors identified
- **Test-retarget coverage note (audited per the test-count-drop lesson):** the old "F1 hub carves MORE space than a leaf" SPATIAL assertion was REPLACED by the C spacing-ratio assertion. The F1 degree-charge *lever* (chargeMul) code is unchanged, and its visible effect (hubs bigger + spread) stays covered by the F2 (radius monotonic in degree) + F5 (bold ≥2.5× size) + deterministic tests. So the narrow loss (hub spatial-separation > leaf) is redundant with the surviving size-hierarchy + new spacing coverage — acceptable, not a load-bearing untested behavior. Noted for transparency.
- Spacing constants are a tuned balance — if a future vault has a very different edge density it may need a re-tune; all four are single-constant levers (logged below).

## Assumptions (user-review)
- **Spacing constants: COLLIDE_GAP 1.8 / COLLIDE_STR 0.7 / REPEL 14 / SPRING_LEN 36 / iters 150** — *why*: tuned to hit nearest-dist/radius ~4-5× (got 4.79×) while keeping one connected cluster — *how to change*: each is a single constant in globalLayout; raise COLLIDE_GAP/REPEL for more spread, lower for tighter.
- **Collide bubble = render-radius × gap** (layoutR mirrors the visual size) — so spacing scales with node size; tunable via COLLIDE_GAP.

## Commit
`fix(sprint-graph-polish-c): nới spacing (collide-gap 1.8 + charge×3 + spring 36) → ratio 2.84×→4.79×, hết dày`
Explicit-paths only (graph/page.tsx + graph test + 2 sprint docs; NO tokens.css this sprint; NOT template/Life Command/* or docs or projects-tests).
