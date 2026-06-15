# Sprint GLOBAL-GRAPH — whole-vault graph (Obsidian-style) as the DEFAULT /wiki/graph view

> USER-REQUESTED (2026-06-15): "/wiki/graph không thấy gì" — landing on /wiki/graph with no ?note= shows the IDLE state (Nodes 0 / Edges 0, blank canvas, "pick a center note"). Reads as broken. Reference: Obsidian graph view (global + local modes). team-lead verified live.

## Kickoff — 2026-06-15 (architect)

### The gap (verified on disk + team-lead live)
- Current `/wiki/graph` is LOCAL-only: `GET /wiki/graph?note=X&depth=N` → `ego_graph(note, depth)` (depth-2 BFS neighborhood around ONE center). No center → FE shows blank "Chọn 1 note tâm" idle state (Nodes 0/Edges 0).
- A user landing on the Graph screen with no center sees NOTHING. The fix: a GLOBAL (whole-vault) graph as the DEFAULT view, with the existing ego-graph kept as a "local/focus" mode (Obsidian has both).

### What exists (reuse — verified on disk)
- **BE data is all there:** `wiki_store.all_notes()` (queries.py:16), `all_resolved_edges()` (queries.py:116), `degree(id)` (queries.py:71), `get_note_cache(id)` (notes.py:45), `count_notes()` (queries.py:26). `detect_clusters()` (graph.py:37) already scans the whole-vault edge set + components.
- **The node/edge shape is already defined** by `ego_graph`: `{nodes:[{id,title,status,degree}], edges:[{source,target,type,isResolved}], clusters:[...]}`. The global graph returns the SAME shape over the whole vault (center omitted/null).
- **FE** (`frontend/app/wiki/graph/page.tsx`, 340 lines): today does a deterministic RADIAL ego-layout client-side from `useWikiGraph(center, depth)`, custom SVG (no heavy lib), with status-filter + orphan-highlight + deep-link from `?note=`. The global view needs a many-node layout (radial is ego-only) — deterministic (NO Math.random, per the constraint).

### 🔑 DECISIONS (architect calls — decide-and-log)

**BE — global graph endpoint + reader fn:**
- Add `reader.global_graph()` → `{center: None, nodes: [ALL notes as {id,title,status,degree}], edges: [ALL resolved edges as {source,target,type,isResolved}], clusters: detect_clusters()}`. Reuse the exact ego node/edge dict shape so the FE renders both modes from one schema. Include the FULL cluster list (not ego-restricted) so the FE can color-group by cluster (Obsidian "Groups").
- Endpoint: `GET /wiki/graph` with **no `note` param → global** (note becomes optional); `?note=X` → ego (unchanged). So the existing deep-link still works, and the bare `/wiki/graph` now returns the whole vault. (Alternative `GET /wiki/graph/all` — but overloading the existing route by making `note` optional is cleaner + matches "default view".) **DECISION: make `note` optional on `GET /wiki/graph`; absent → global_graph(), present → ego_graph().**
- Honest-empty: 0 notes → `{center:None, nodes:[], edges:[], clusters:[]}` (FE renders a friendly empty, not a blank-that-looks-broken).
- Perf: single-user vault ~21 notes — NO perf concern now. Keep the existing ">5k notes = Phase 2" note; if `count_notes()` ever exceeds a cap (e.g. 2000), the endpoint MAY return a `warning` + the top-N-by-degree subgraph (log it; not built now, just leave the seam + the comment).

**FE — global as default + local reachable:**
- DEFAULT view (no `?note=`): fetch the global graph → render ALL nodes with a **deterministic force-directed-ish layout** for N nodes (NOT the ego-radial — that's center-anchored). Deterministic seeding (e.g. seed positions by a hash of node id, then a fixed number of force-relaxation iterations — NO Math.random, NO per-frame randomness; same vault → same layout). Custom SVG, no heavy lib (match the existing no-dependency approach) — UNLESS the team decides a tiny deterministic force lib is worth it (FE's call at kickoff; deterministic is the hard constraint).
- **Two modes (Obsidian-parity):** Global (default) ↔ Local/ego (pick a center). Click a node in global → focus it (switch to ego mode / `?note=id`); a toggle or back-button returns to global. Keep the existing ego mode + its radial layout intact.
- **Obsidian-parity touches (include the high-value, cheap ones):** node size ∝ degree (already have `degree`); color by status (already have `status`) AND/OR by cluster (Groups); hover-highlight neighbors; click → open note; the existing status-filter + orphan-highlight carried into global. Labels on nodes (toggle if cluttered).
- Honest-empty: 0 notes → friendly "vault empty — create your first note" panel, not blank canvas.

### Task split (BE + FE parallel — minimal overlap; BE endpoint gates FE's real data but FE can scaffold against the known shape)
- **T1 [backend]** — `reader.global_graph()` + make `note` optional on `GET /wiki/graph` (absent → global). Reuse all_notes/all_resolved_edges/degree/detect_clusters. Honest-empty. Same node/edge shape as ego. Tests: global returns all nodes+edges+clusters; empty vault → empty shape; ego path (`?note=X`) UNCHANGED (regression). NO perf work (leave the >cap seam + comment).
- **T2 [frontend]** — global graph as DEFAULT `/wiki/graph` view: deterministic many-node layout, global↔local toggle (click node → ego focus), node-size∝degree + color-by-status/cluster + hover-neighbors + click-open + carry status-filter/orphan-highlight, honest-empty. Port any relevant mock styling (screens-wiki.js graph block). Chrome self-verify (Gate 2): global view renders nodes on load, toggle works, dark mode, console clean.

### Dependencies
- T2 needs T1's endpoint shape — but it's the SAME shape as today's ego (`{center,nodes,edges,clusters}`, center now nullable), so FE can build against the known schema and wire the real global endpoint as soon as T1 lands. Dispatch T1 first (gating), T2 right after (it can scaffold immediately from the frozen shape).

## Assumptions (user-review)
- Global (whole-vault) graph is the DEFAULT `/wiki/graph` view; the existing ego/local graph is kept as a focus mode (click a node or `?note=X`). Mirrors Obsidian's global+local modes.
- `GET /wiki/graph` `note` param made OPTIONAL: absent → whole-vault `global_graph()`, present → `ego_graph()` (unchanged — existing deep-links still work).
- Global graph returns the SAME node/edge shape as ego (`{id,title,status,degree}` / `{source,target,type,isResolved}`) + the full cluster list for color-grouping.
- FE layout is DETERMINISTic (seed by node-id hash + fixed force iterations — no Math.random, same vault → same layout). Node size ∝ degree, color by status/cluster, hover-highlight neighbors, click → open/focus.
- No perf work now (~21 notes); the >cap (e.g. 2000) top-N-by-degree fallback is a documented seam, not built. ">5k = Phase 2" comment preserved.
- Honest-empty: 0 notes → friendly empty panel, not a blank canvas.
