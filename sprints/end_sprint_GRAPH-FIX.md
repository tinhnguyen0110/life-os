# End Sprint GRAPH-FIX — 3 fixes (explorer-click in-graph + menu offset + wider panel)

Board task: #179. Follow-up #178. 3 user-flagged graph fixes.

## What shipped
On /wiki/graph: clicking a file in the left explorer now focuses the node + opens its docs in-place (no navigation away); the node menu lands exactly on the node at any zoom/pan (letterbox bug fixed); the docs panel is wider (460). Pure FE, #173-178 intact, BE untouched, no dep.

### Changes implemented (4-step verified on disk + independent test re-run; team-lead Chrome-gate)
- **Fix 1 — explorer-click in-graph (pathname-gated CustomEvent, decoupled).** WikiExplorer (a LAYOUT component, shared across all /wiki routes) gets a `handleOpen(id)`: on `pathname === "/wiki/graph"` it `window.dispatchEvent(new CustomEvent("wiki:graph-open-note", {detail:{id}}))` and does NOT navigate; on EVERY other route it `router.push(\`/wiki/${id}\`)`. Both onOpen sites (folder L291 + root L295) repointed to handleOpen. The graph page adds a `useEffect` listener → `focusNote(id) + setOpenDocsId(id)`, cleaned up on unmount (removeEventListener — no leak/dup). 🔴 Verified the graph branch ONLY dispatches (no stray push → stays on the page) and the else branch preserves normal nav for /wiki, /wiki/[id], /wiki/proposals.
- **Fix 2 — menu offset bug (preserveAspectRatio letterbox).** openNodeMenu replaced the manual `rect.left + ((nodeX-view.x)/view.w)*rect.width` (which ignored the xMidYMid-meet letterbox margin → off after zoom/pan) with the SVG's own transform: `el.getScreenCTM?.()` + `createSVGPoint()` + `matrixTransform(ctm)` → exact at any viewBox/letterbox/pan/zoom state. jsdom fallback to the manual calc (no getScreenCTM there). FE measured matchDist 0.0px live.
- **Fix 3 — wider docs panel.** `.wg-docs-panel` 380 → 460 (width + flex-basis); @media stack kept. Graph shrinks more but #174 auto-fit re-frames (the #178 prevDocsRef effect).

### Verification (pass/fail)
- tsc exit 0; vitest graph 45 + WikiExplorer 28 = 73/73 (architect re-ran). Full suite 1155 per FE report. 0 errors. ✅
- Fix 1 pathname-gate (the cross-cutting risk — WikiExplorer is shared): graph branch dispatches-only (no push → stays); else branch pushes → /wiki, /wiki/[id], /wiki/proposals navigation NOT broken (read on disk + unit test). Listener cleanup present. ✅
- Fix 2 getScreenCTM letterbox-exact + jsdom fallback. ✅
- Fix 3 panel 460. ✅
- team-lead Chrome-gate FULL PASS (live + DOM + eyes-on): /wiki/graph explorer-click → ?note=5 ego + docs panel, stayedOnGraph=true (no nav away); other routes still push (unit) · menu "Xem docs/Focus" sits ON the node after wheel-zoom+ego (matchDist 0.0px) · panel 460 · #173-178 kept · console clean. ✅

### 3 Quality Gates
- **Gate 1 (API)**: ✅ N/A — pure FE.
- **Gate 2 (Function)**: ✅ tests assert observable behavior (onOpen dispatches on graph / pushes elsewhere, graph listens→focus+docs, menu uses getScreenCTM, panel width, #173-178 not regressed); tsc clean; 0 errors; pathname-gate doesn't break other-route nav; listener cleanup.
- **Gate 3 (Sprint)**: ✅ this report w/ verified counts; architect read the handleOpen branch + getScreenCTM + listener on disk + re-ran tests; team-lead Chrome-gate pass; commit format match.

## Risks / potential errors identified
- The CustomEvent is a global window event — if a future second graph-like consumer listened to the same name it'd double-handle. Single consumer today (the graph page); the event name is namespaced `wiki:graph-open-note`. Low risk, noted.
- getScreenCTM fallback path (jsdom) uses the old letterbox-unaware calc — only hit in tests (no real letterbox in jsdom), so the inaccuracy never reaches a user. Acceptable.

## Assumptions (user-review)
- **Explorer onOpen is pathname-aware** — graph route → in-place focus+docs via CustomEvent; all other routes → navigate to /wiki/[id] (unchanged). *how to change*: edit handleOpen's pathname check in WikiExplorer.
- **Menu position via getScreenCTM** (exact, letterbox-proof) — the correct way; no tuning.
- **Docs panel 460px** — tunable in .wg-docs-panel.

## Commit
`fix(sprint-graph-fix): explorer-click→focus+docs in-graph · menu getScreenCTM (letterbox) · docs panel 460`
Explicit-paths only (graph/page.tsx + graph test + WikiExplorer.tsx + WikiExplorer test + tokens.css + 2 sprint docs; NOT template/Life Command/* or docs or projects-tests).
