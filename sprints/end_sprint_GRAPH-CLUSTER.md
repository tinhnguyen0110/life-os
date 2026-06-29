# End Sprint GRAPH-CLUSTER — color-by-cluster (A) + cluster-aware island force (B)

Board task: #177. User CHỐT A+B (from the DISCUSS analysis), DEFER Louvain.

## What shipped
Nodes are now colored by their connected-component (cluster) and a gentle cluster-aware force pulls each component into a visible "island" — same-cluster nodes sit together, components separate, orphans grey at the rim. Pure FE (client-side CC), deterministic, #173-176 intact, BE untouched, no new dep.

### Changes implemented (4-step verified on disk + independent test re-run; team-lead DOM + eyes-on gate)
- **D1 — client-side connected components** — union-find over the rendered edges (`union` sets parent[max]→min so the ROOT is always the MIN member-id → deterministic; components sorted by root → stable palette index). Pure fn, no Math.random, no BE (BE detect_clusters filters to 2 — not a full source). Returns node-id → {comp index, size}.
- **A — color by cluster** — `CLUSTER_PALETTE` (fixed distinct hues, cycled by component index) = node FILL; singleton/orphan components → grey `ORPHAN_FILL` (honest, not a fake group). Inline fill (no dead-CSS risk). Status moved to a thin ring on the node (green/blue/amber preserved). Legend updated "màu = cụm · viền = status".
- **B — cluster-aware force** — per-iter component CENTROIDS (mean position); each node pulled gently toward its OWN centroid (`SAME_CLUSTER_PULL=0.018`) — skipped for singletons (orphans get no fake pull); cross-component pairs repel harder (`CROSS_REPEL_MULT=1.5`) → components push into islands. ADDITIVE + gentle → composes with #176 spacing + #175 hierarchy + #174 organic (the step-clamp ±6 + cooling + center preserved). Deterministic (centroids are pure fns of positions).

### Verification (pass/fail)
- tsc exit 0; vitest graph 40/40 (architect re-ran; +3 over #176's 37). Full suite 1148 per FE report. 0 errors. ✅
- CC determinism (read on disk): union-find root = min member-id (parent[max]→min), sorted → stable palette → reload-stable colors. ✅
- Cluster force deterministic + gentle + honest (centroid pull only for n>1; orphans no fake pull). ✅
- Deterministic (no Math.random); no BE change; inline fill (no dead-CSS). ✅
- team-lead Chrome-gate FULL PASS (independent DOM + eyes-on): 6 fills matching the 19 components (#ff6a8a=28 main · amber=5 · blue=4 · green=2 · lime=2 · grey=14 orphans) · islands visibly separated (eyes-on "cụm đi với nhau") · status ring + legend kept · **#176 spacing 5.03×** (held, even ↑ from 4.79× — cluster force composes clean, no re-clump) · #173/#174/#175 (click/organic/auto-fit/hierarchy 3.8×/halo) kept · 74 edges connected · auto-fit frames all islands · deterministic · console clean. ✅

### 3 Quality Gates
- **Gate 1 (API)**: ✅ N/A — pure FE.
- **Gate 2 (Function)**: ✅ tests assert observable behavior (CC correctness, same-component same-color, orphan grey, island separation cross>within, deterministic, #173-176 not regressed); tsc clean; 0 errors; union-find determinism + honest orphan handling verified.
- **Gate 3 (Sprint)**: ✅ this report w/ verified counts; architect read the CC + cluster-force on disk + re-ran tests; team-lead Chrome-gate pass (DOM-measured 6 colors + 5.03× spacing held); commit format match.

## Risks / potential errors identified
- The cluster force is ADDITIVE on top of #174-176 — verified it didn't re-clump (spacing held at 5.03×, even slightly improved). If a future vault has a dominant giant component, the centroid pull on that one big component is just its own cohesion (fine). Tunable constants logged.
- Palette cycles if there are >palette-length components (currently 6 non-orphan components ≤ palette size) — a cycle would reuse a hue for two distant components, acceptable (they're spatially separated as islands anyway). Logged.

## Assumptions (user-review)
- **CC = client-side union-find (min-id root, stable)** — *why*: BE detect_clusters filters to 2; we need all-node membership; client-side is cheap + deterministic + no dep — *how to change*: n/a (correct for the need).
- **Encoding: fill = cluster · ring = status · orphan = grey** — *why*: keeps both signals, cluster is the dominant visual the user wanted — *how to change*: a "màu theo cụm" toggle could switch fill back to status (the documented fallback) if the user prefers.
- **Force: SAME_CLUSTER_PULL 0.018 + CROSS_REPEL_MULT 1.5** — tunable single constants; raise for tighter islands.
- **Louvain DEFERRED** — the single 28-node main component stays one island; community sub-division is a future option if the user wants it.

## Commit
`feat(sprint-graph-cluster): color-by-cluster (CC client-side) + cluster-aware island force — node cùng cụm tụ thành đảo`
Explicit-paths only (graph/page.tsx + graph test + 2 sprint docs; NO tokens.css; NOT template/Life Command/* or docs or projects-tests).
