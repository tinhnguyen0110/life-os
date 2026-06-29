# Sprint GRAPH-FIX — 3 fixes (explorer-click in-graph + menu offset bug + wider docs panel)

Board task: #179. Follow-up #178. 3 user-flagged graph fixes.

## Kickoff — 2026-06-29

### Findings on disk
1. **Explorer click leaves the page.** WikiExplorer (layout.tsx, shared across ALL /wiki routes) onOpen = hardcoded `(id) => router.push(\`/wiki/${id}\`)` (L280/284). On the graph route the user wants click-file → focusNote+docs IN the graph, not navigate away. WikiExplorer is in the LAYOUT, the graph is a separate PAGE → they don't share state directly.
2. **Menu offset bug (confirmed):** openNodeMenu (L557-558) `sx = rect.left + ((nodeX-view.x)/view.w)*rect.width` assumes the viewBox maps linearly to the full rect — but `preserveAspectRatio="xMidYMid meet"` (#173) LETTERBOXES the viewBox into the rect when aspect differs → there's a margin → the computed point is off. Root cause = ignoring the letterbox.
3. **Docs panel** `.wg-docs-panel { width:380px }` (tokens L775) — user wants wider.

### Decisions (architect)
- **D1 — explorer-click in-graph via a CustomEvent (pathname-aware, decoupled).** WikiExplorer's onOpen becomes pathname-aware: when `pathname === "/wiki/graph"`, dispatch a `window` CustomEvent `wiki:graph-open-note` `{detail:{id}}` INSTEAD of router.push; on every OTHER route keep `router.push(\`/wiki/${id}\`)`. The graph page adds a `useEffect` listener for that event → `focusNote(id) + setOpenDocsId(id)` (exactly like clicking a node's "Xem docs"+focus). This keeps WikiExplorer (a layout component) decoupled from the graph page (no prop-drill/context for one signal), and ONLY changes behavior on /wiki/graph — /wiki, /wiki/[id], /wiki/proposals etc. still navigate normally. Clean unmount of the listener.
- **D2 — menu offset fix via getScreenCTM (exact, letterbox-proof).** Replace the manual rect math with the SVG's own coordinate transform: `pt = svg.createSVGPoint(); pt.x = nodeX; pt.y = nodeY; const screen = pt.matrixTransform(svg.getScreenCTM())`. getScreenCTM accounts for the viewBox + preserveAspectRatio letterbox + the current pan/zoom automatically → the screen point is exact at ANY zoom/pan state. (Fallback to the manual calc only if getScreenCTM is null — jsdom.) Test: open the menu AFTER zoom + pan → it lands on the node.
- **D3 — wider docs panel.** `.wg-docs-panel` 380 → 460px (flex-basis too); keep the body readable + the @media stack. Graph shrinks more but #174 auto-fit re-frames (already wired #178).
- KEEP: #173-178 (zoom/pan/click-vs-drag/cluster/menu/docs), deterministic, SVG, no dep.

### Defensive
- D1: the override is pathname-gated — must NOT break /wiki, /wiki/[id], /wiki/proposals navigation (only /wiki/graph dispatches the event). Listener cleaned up on unmount (no leak/dup).
- D2: menu lands on the node at ALL zoom/pan states (the bug only shows after a zoom/pan that changes the aspect-fit) — getScreenCTM handles it; test post-zoom+pan.
- D3: wider panel → graph narrower but auto-fit still frames all nodes (no clip).

### BE/FE split
- **FE only.** WikiExplorer.tsx (pathname-aware onOpen), graph/page.tsx (event listener + getScreenCTM menu fix), tokens.css (panel width). BE untouched.

### Final task list
- **T1 (FE):** (1) WikiExplorer onOpen pathname-aware — /wiki/graph → dispatch `wiki:graph-open-note`, else router.push; graph page listens → focusNote+setOpenDocsId; (2) openNodeMenu via createSVGPoint+getScreenCTM (letterbox-exact, fallback for null); (3) `.wg-docs-panel` 380→460. Tests: explorer onOpen dispatches event on /wiki/graph + pushes elsewhere (pathname-mocked); graph listens → focus+docs; menu point uses getScreenCTM (mock CTM → correct px); other routes still push; #173-178 not regressed.

### Dispatch plan
- frontend ← T1. tester + team-lead Chrome-gate: explorer-click on /wiki/graph → focus+docs in-graph (other routes still navigate) · menu lands ON the node AFTER zoom+pan · panel wider · #173-178 kept · console clean.

## Assumptions (user-review) — filled in end_sprint
