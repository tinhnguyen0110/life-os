# End Sprint GRAPH-POLISH-B — degree hierarchy (hub spread + big + readable labels)

Board task: #175. Reactive follow-up to #174. User screenshot: global graph "can't distinguish anything, don't understand it" — too dense, nodes same size, gray labels unreadable.

## What shipped
The global graph is now glance-understandable: hubs spread apart + ~3× bigger (instant recognition), leaves small + clustered around them, breathing room, and readable halo labels. Pure FE, deterministic, #173/#174 intact, BE untouched.

### Changes implemented (4-step verified on disk + independent test re-run; team-lead Chrome-gate eyes-on)
- **F1 — degree-scaled charge** — `chargeMul(id) = 1 + 0.5√deg`, applied ASYMMETRICALLY in the symmetric pairwise loop: `di += f·mulj; dj -= f·muli` (node i pushed by j's charge, j by i's). A hub shoves a leaf hard; the leaf barely moves the hub → hubs carve personal space, leaves bunch near them. The cube CHARGE base + soft collide kept; edge springs still pull clusters together (hubs spread BUT stay connected — not a scatter).
- **F2/F5 — bold size hierarchy** — render radius `max(6, min(4 + 6√deg, 30))` (leaf deg0→6px, hub→up to ~28px; team-lead measured 3.2× live on the real degrees). The ≥6px floor keeps leaves clickable (verified: click a leaf → opens the note). Collide bubble (layoutR) tracks the new wider radius → hubs separate proportionally (the Obsidian-true mechanism).
- **F3 — breathing room** — CENTER 0.055→0.035, SPRING_LEN 16→22 → the graph spreads instead of piling; the #174 auto-fit viewBox re-frames it snug (no fly-off).
- **F4 — readable labels** — bright fill (`--tx-0`) + a `paint-order:stroke` halo (bg-colored stroke behind the glyphs) so labels read over a dense cluster (vs the old gray-blends-in); label y-offset scales with the node radius so it clears the (bigger) node, not on it; global label cap lowered (E collision-cull 8→5) — few-and-readable beats many-and-piled.

### Verification (pass/fail)
- tsc exit 0; vitest graph 36/36 (architect re-ran; +6 over #174's 30). Full suite 1144 per FE report. 0 errors. ✅
- Determinism (grep): no Math.random; chargeMul + size are pure fns of degree. ✅
- F1 asymmetry correct (di+=f·mulj / dj-=f·muli) — read on disk; springs keep clusters connected (not scatter). ✅
- F2/F5 size monotonic in degree + ≥6px floor; collide tracks it. ✅
- F4 halo = paint-order:stroke + bright fill (DOM: stroke rgb(10,10,12) + fill rgb(236,234,227)); 5 labels (cull 8→5); y by radius. ✅
- tokens.css scoped `.wgnode-lbl*` — no global token. ✅
- team-lead Chrome-gate FULL PASS F1-F5 (eyes-on the screenshot scenario): hub 3× a leaf (nhìn phát biết) · labels white-on-dark readable over the cluster · breathing, no middle-pile · leaf clickable · #173/#174 A-E all kept · console clean. ✅

### 3 Quality Gates
- **Gate 1 (API)**: ✅ N/A — pure FE.
- **Gate 2 (Function)**: ✅ tests assert observable behavior (size spread ratio, halo present, deterministic, #173/#174 not regressed); tsc clean; 0 errors; F1 asymmetry + clusters-stay-connected verified; leaf clickable (≥6px).
- **Gate 3 (Sprint)**: ✅ this report w/ verified counts; architect read the force-apply + size + halo on disk + re-ran tests; team-lead Chrome-gate pass (eyes-on); commit format match.

## Risks / potential errors identified
- F1 strength (K=0.5) is tuned so hubs spread but the adaptive link spring still holds clusters — verified connected (not scatter). If a future vault has an extreme hub, K is a 1-constant tune.
- Size cap at 30 (a huge hub won't grow unboundedly) + floor at 6 (leaf clickable) — both deliberate. Logged.
- The deterministic layout means the SAME vault always looks the same — a feature (stable mental map), not a bug.

## Assumptions (user-review)
- **Degree-charge lever K=0.5 + size 4+6√deg (6..~28px, ~3× spread)** — *why*: makes hubs visibly dominant + spread for instant recognition while staying connected; ≥6px keeps leaves clickable — *how to change*: tune the chargeMul K and the size coefficient/cap constants in globalLayout/the render-radius.
- **Global labels capped low (5) with halo** — *why*: few-and-readable beats many-and-piled (the user's core complaint); hover/zoom reveals more — *how to change*: the cull cap constant.
- **CENTER 0.035 / SPRING 22 (breathing)** — tunable.

## Commit
`feat(sprint-graph-polish-b): degree hierarchy — hub spread+big (3.2×) + readable halo labels + breathing → glance-understandable`
Explicit-paths only (graph/page.tsx + graph test + tokens.css + 2 sprint docs; NOT template/Life Command/* or docs or projects-tests).
