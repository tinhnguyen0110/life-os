# Sprint WIKI-RECONCILE — bulk reindex-prune tree↔store divergence (Cairn #53)

> Created 2026-06-21 by architect. HIGH (honest-mirror: the wiki tree LIES — lists 12 ghost notes that 404 on GET). #53-ONLY (#47 DROPPED — dissolved, fixed by #25/38b920d; see below). DESIGN now (parallel-safe, design ≠ tree-edit); **HOLD dispatch until F&G commits** (1-editor-per-tree — backend-w3 is editing the tree for FNG-HONEST).

## #47 — DROPPED (dissolved, live-verified by the prior architect via team-lead)
MCP `propose_note` (wikiAgentAutonomous=ON) returns the correct write-through shape `{noteId:54, applied:true, status:"accepted", proposalId:125, decidedBy:"agent:auto"}` — leads with a real noteId, GET-able immediately (200). Fixed by #25 (38b920d); the board "still pending" claim was STALE. The MCP-proposal-wrapper ({noteId,applied,status,proposalId}) vs REST-full-note ({id,title,noteType}) difference is an INTENTIONAL contract (MCP = audited proposal chokepoint; REST = human direct-create) — acceptable per AGENT-FIRST, NOT a bug. If strict parity is ever wanted → a separate low-pri note, NOT this sprint.

## The bug (#53 — grounded Rule#0, root-caused by team-lead + re-verified)
**tree↔store divergence = the disposable SQLite `wiki_notes` cache lists rows whose md file is GONE.**
- `all_notes()` (store/queries.py:16) reads the `wiki_notes` cache → has ghost rows (e.g. ids 40-51).
- `read_note_file(id)` (store/files.py:18) reads `data/wiki/notes/<id>.md` → those files are GONE.
- So the **tree lists 12, GET fetches 1** → an agent reading the tree sees notes that 404. The cache LIES.
- **Orphan source:** NOT normal DELETE (`_apply_delete` removes BOTH file + cache — verified clean). The 11-12 ghosts came from TEST WRITES that deleted the .md directly / md_store reset WITHOUT going through `_apply_delete` → leaked into the PROD store (the recurring [[test-writes-pollute-prod-runtime-store]]).
- **Blast radius (one fix heals all):** `all_notes()` feeds tree.py (32,91), graph.py (131), stale.py (64), overview.py (35) → ghosts pollute the tree, graph, stale-detector, AND overview counts. A bulk prune fixes EVERY consumer at once (one source of truth).

## The fix (DECIDED — decide-and-log; reindex-prune, the agent-first safe one)
The per-note primitive ALREADY exists: `reader/reindex.py reindex_note(id)` → md-absent + cache-present → `delete_note_cache(id)` → action `"missing_dropped"`; md-present-but-stale → rebuild; match → no-op. **The GAP = no BULK sweep.** Build it:

1. **`reindex_all()` in reader/reindex.py** — sweep `all_notes()` ids → `reindex_note(id)` each → aggregate `{scanned, dropped, rebuilt, unchanged, droppedIds:[...]}`. Lean, agent-readable (the agent sees WHAT was pruned). Reuses the existing per-note reconcile (zero new prune logic — `is`-identity safe).
2. **REST `POST /wiki/reindex`** (or `/wiki/reconcile`) → returns the aggregate. Envelope `{success,data,warning?}`.
3. **MCP twin `wiki_reindex`** → calls the SAME `reindex_all()` → byte-identical (#24). Registers in `modules/wiki/mcp/read_server.py` TOOLS (line 258, where wiki_stale lives) → wiki-read count **13 → 14**.
   - **🔴 #34 broken-intermediate gate (team-lead-flagged) — ALL tool-count asserts move in the SAME commit, grepped exhaustively:**
     - `tests/test_mcp_http.py:167` — `assert len(wr._tool_manager.list_tools()) == 13` → **14**.
     - `mcp_servers/CATALOG.md:12` — "**13** wiki-read" → "**14** wiki-read" + ADD the `wiki_reindex` row in the Wiki-tools table (~line 105).
     - `tests/test_mcp_http.py:21` — docstring `len(TOOLS) == 40/4/11/6/15` (verify whether the `11` is a stale wiki-read ref; update if so).
     - SAFE (auto-derived, no edit): `test_mcp_read.py:879-880 test_catalog_count_matches_real_servers` reads `len(rs.TOOLS)`/`len(ws.TOOLS)` dynamically (SHARED read/write only — NOT wiki-read), so it self-adjusts. The wiki-read 13→14 is the MANUAL one that bites.
   - Backend: `grep -rn "== 13\|13 wiki-read\|wiki-read.*13"` across tests + CATALOG before commit; my 4-step re-greps + confirms the committed blob has 14 everywhere (git-status-after-stage + grep the staged diff). NO commit where the server has 14 but a test expects 13 (the exact #34 trap).
4. **Self-healing hook (decide-and-log):** hook `reindex_all()` into the existing `wiki-refresh` routine (automation/service.py:240, interval) so the tree self-reconciles periodically — NO new routine (no over-engineering). Fail-soft add-on (the routine's primary work isn't failed by a reconcile error — [[fail-closed-write-fail-soft-addon]]).

## honest-mirror / USER-flag (surface, low-risk)
Pruning the 11-12 ghost cache rows = removing INDEX rows that point at already-deleted files → it does NOT delete any real note (the .md is already gone; the row points at nothing). It only STOPS the index from lying. So it's safe + agent-first (prune-orphan-INDEX, not purge-real-data). Per CLAUDE.md "purge user data = USER decision" — but this is index-reconcile, not data-purge. SURFACE to user via team-lead (notify): "wiki-reconcile pruned N orphan index rows (files already gone, no note lost)" — courtesy, not a gate.

## HARD GATE (distinguishing)
- Before: tree lists ≥1 ghost id whose GET /notes/{id} → 404. After reindex: tree count == GET-able count (no ghost). The distinguishing test: seed a cache row WITHOUT its md file (the orphan) + a real note WITH its md → `reindex_all()` drops ONLY the orphan (droppedIds == [orphan], the real note survives, `unchanged`). A collapsed impl that drops everything OR nothing FAILS this.
- Idempotent: a 2nd `reindex_all()` immediately after → `dropped:0` (nothing left to prune). 
- REST≡MCP byte-identical (#24); pytest 0-failed; mypy clean; count consumers (3) updated.
- The real-note rebuild path still works (md present, cache stale → rebuilt, not dropped) — don't regress reindex_note's other actions.

## Baseline
pytest = post-FNG-HONEST count (confirm at dispatch). Keep 0-failed. (Was 1922 post-#46-P2; +F&G tests; + these reconcile tests.)

## Assumptions (user-review)
- **#53 fix = bulk reindex-prune** (`reindex_all()` sweeps the cache, drops rows whose md is gone via the existing `reindex_note`), exposed REST + MCP + hooked into the wiki-refresh routine for self-healing. **How to change:** reindex_all in reader/reindex.py + the routine hook.
- Pruning orphan INDEX rows is NOT a data-purge (files already gone) — done autonomously + surfaced to user, not gated. **How to change:** make the prune a dry-run-by-default + an explicit apply flag if the user wants a gate.
- #47 DROPPED (dissolved); the MCP-wrapper vs REST-full-note difference is intentional contract, not a parity bug.

## Scope expansion — closes Cairn #61 (== #53, broader; Rule#0 read the full board task 2026-06-21)
#61 has 3 items; WIKI-RECONCILE closes ALL 3 in one commit:
1. **Fix DELETE path → ALREADY DONE** (admin-lead correction event 1944: `_apply_delete` apply.py:183 deletes file + cache + fts + ghostify; new deletes are clean). NOT re-doing — skip.
2. **Reconcile orphan 40-51 → the reindex_all bulk sweep** (the core, below).
3. **GET /wiki/notes/{id} 404 → agent-readable error-shape** (#61 item#3, FOLDED — team-lead-confirmed decide-and-log): router.py:257 `raise HTTPException(404, detail=f"wiki note {id} not found")` → use the EXISTING `core/agent_errors.agent_error("NOT_FOUND", f"wiki note {id} not found", hint="check the id via wiki_tree or wiki_search")` (the #46-P1 closed-6 enum — code is **NOT_FOUND**, NOT a new shape; retryable auto-False, omit it). Body must be FLAT `{error:{code,message,hint,retryable}}` → `JSONResponse(404, content=agent_error(...))` (NOT `HTTPException(detail=...)` which double-nests under "detail"). MCP wiki_get_note `{found:false}` UNCHANGED (existence-contract). Siblings (router.py:266 backlinks + ~270 /context) = same raw-detail pattern → team-lead-CONFIRMED fold all 3 note-id-404 routes (GET /notes/{id} + /backlinks + /context) for agent-first consistency (locked, not optional); do NOT touch conflict/sync 404s router.py:138-147 (different entity). Test: GET /notes/9999 → 404 + `{error:{code:"NOT_FOUND",retryable:false}}`.
+ **F6 reconcile-test** (admin-lead edge): a cache row whose md EXISTS (stale/half-state) → reindex_note REBUILDS not drops → confirms reindex_all only drops TRUE orphans (md truly absent), never a note mid-operation (the "missing vs unreadable" defensive case).

> Scope-fold flagged to team-lead (fold-vs-split decision) — leaning FOLD (item#3 ~10 lines, same module). If team-lead says SPLIT, item#3 becomes a separate slice + #61 stays open on it.

## Grounded insertion points (Rule#0, confirmed 2026-06-21)
- **`reindex_all()`** → `modules/wiki/reader/reindex.py` (beside `reindex_note`) + export in `reader/__init__.py` (the `from .reindex import` line + `__all__`).
- **REST `POST /wiki/reindex`** → `modules/wiki/router.py` (APIRouter tags=["wiki"], mirror the `@router.post("/citations/verify")` pattern at line 151). Envelope {success,data,warning?}.
- **MCP `wiki_reindex`** → `modules/wiki/mcp/read_server.py` TOOLS dict (line 258, after wiki_list_proposals) → wiki-read **13 → 14** (CONFIRMED: counted the dict = 13 now).
- **Self-heal hook** → `modules/automation/service.py:240` wiki-refresh routine / `_wiki_refresh_work` (projects/router.py:129) — call reindex_all() fail-soft.

## Notes
- #53-ONLY. backend EDITS (wiki reader/reindex + router + read_server + automation hook) → architect 4-step + commits `fix(sprint-WIKI-RECONCILE)`. HOLD dispatch until FNG-HONEST PUSH LANDS (1-editor-per-tree). Parallel-unsafe with F&G (both could touch read_server count tests) → sequential after F&G.
- Distinct from the #41 WIKI-STALE-DETECTOR sprint (evergreen/outdated note DETECTION) — THIS is tree↔store cache reconcile. Named WIKI-RECONCILE to avoid confusion.
