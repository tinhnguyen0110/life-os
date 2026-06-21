# end_sprint_WIKI-RECONCILE — bulk reindex-prune + agent-readable note-404 (Cairn #53 + #61)

> Result. The wiki tree no longer LIES: orphan cache rows (md gone) are pruned; note-id GET 404s are agent-readable. Commit `34d6bb8` `fix(sprint-WIKI-RECONCILE)`. Status: ✅ all gates pass. backend-w3 EDITED (wiki reader/router/mcp + automation hook + tests); architect 4-step + committed (§3). team-lead pre-verified 3 routes + reconcile + tool-count; architect caught the 4th GET route pre-commit.

## The bug (Rule#0-grounded — admin-lead dogfood + team-lead + architect)
`wiki_tree`/`GET /wiki/tree` listed notes 40-51 (root) but `wiki_get_note`/`GET /notes/{id}` → 404/found:false for all. Root: `all_notes()` reads the disposable SQLite `wiki_notes` cache; `read_note_file()` reads the md. The 40-51 .md files were GONE (test-writes deleting .md without `_apply_delete`) but the cache rows stayed → the tree listed phantom notes an agent then 404s on = honest-mirror breach in the memory layer. (Delete-PATH itself was already fixed — `_apply_delete` apply.py:183 deletes file+cache; the 40-51 were pre-fix orphans needing reconcile.)

## What shipped
| File | Change |
|---|---|
| `modules/wiki/reader/reindex.py` | `reindex_all()` — snapshots `all_notes()` ids FIRST (reindex_note mutates the cache; don't iterate-while-deleting), runs the existing `reindex_note` per id, aggregates `{scanned,dropped,rebuilt,unchanged,droppedIds}`. ZERO new prune logic (reuses the primitive). Lean + agent-readable (droppedIds names WHAT was pruned). |
| `modules/wiki/reader/__init__.py` | export `reindex_all`. |
| `modules/wiki/router.py` | REST `POST /wiki/reindex` → the aggregate. + `_note_not_found(id)` helper → `JSONResponse(404, agent_error("NOT_FOUND", msg, hint="check the id via wiki_tree or wiki_search"))` (FLAT body, not double-nested). Applied to ALL 4 GET note-id routes: `/notes/{id}`, `/backlinks`, `/context`, `/suggested-links` (the 4th caught by architect's 4-step pre-commit). |
| `modules/wiki/mcp/read_server.py` | MCP `wiki_reindex` → same `reindex_all()` (byte-identical #24, added to the parity gate). wiki-read 13→14. |
| `modules/projects/router.py` | `_wiki_refresh_work` runs `reindex_all()` FAIL-SOFT (primary status set BEFORE the add-on; a reconcile error only annotates detail — never fails the sweep). Self-healing. |
| `mcp_servers/CATALOG.md` + count tests | wiki-read 13→14 EVERYWHERE (test_mcp_http 167+docstring, test_wiki_mcp_read key-set, test_mcp_read byMount, CATALOG +row). count-grep `== 13\|13 wiki-read` → CLEAN. |
| `tests/test_wiki_reconcile.py` (NEW) | 15 tests: orphan-only-drop distinguishing, idempotent (2nd=0), rebuilt-not-regress, honest-empty, multi-orphan, F6 (md-present NEVER dropped), REST==MCP byte-identical, 4× item#3 404-shape (parametrized over the 4 GET routes), MCP-found-false-unchanged. |

## Design (LOCKED — team-lead-confirmed decide-and-log)
- **#53 fix = bulk reindex-prune** reusing the per-note `reindex_note` (md-absent→drop, md-stale→rebuild, match→unchanged). Exposed REST + MCP + wiki-refresh self-heal hook. Prunes ONLY orphan INDEX rows (md already gone) — never a real note.
- **#61 item#3 = agent-readable note-404** via the existing `agent_error` (#46, code=NOT_FOUND, retryable auto-False). FLAT `{error:{...}}` body via JSONResponse (not HTTPException(detail=) which double-nests). All 4 GET note-id routes (consistency). MCP `wiki_get_note {found:false}` UNCHANGED (existence-contract ≠ operation-failed, the #46 distinction).
- **BOUNDARY (no scope creep):** the 3 WRITE routes (PUT/DELETE/POST-refine note-id) stay raw `{detail}` → a separate #46-family follow-up slice (write-surface ≠ agent-read-surface, not #61). The graph/merge/conflict/proposal 404s untouched (different entities).
- **#47 DROPPED** (dissolved, fixed #25).

## Verification (Rule#0 — architect 4-step + team-lead pre-verify + backend evidence)
- **architect 4-step:** read `reindex_all` full (snapshots-ids-before-mutate = avoids iterate-while-delete; reuses reindex_note; lean return) ✅; the 3 item#3 routes ✅; **CAUGHT a 4th GET sibling** (`/suggested-links` router.py:306) still raw via grepping ALL note-id 404s (dissolved-finding-recheck-all-consumers) → folded pre-commit; confirmed the 3 WRITE routes correctly stay raw (boundary); count-grep no stray 13; stage scope = the 11 files + sprint docs (no frontend/template/data leak).
- **team-lead pre-verify (in-container):** 3 GET routes flat-404 + reconcile orphan-drop + tree-no-ghost + tool-count 13→14. (Push-window: route#4 + the real commit.)
- **backend-w3 evidence:** FULL pytest 1955/0 (baseline 1940 + 15) + mypy clean; LIVE :8686 — all 4 GET routes flat `{error:NOT_FOUND}`, WRITE routes raw (boundary), MCP found:false unchanged; **live reindex on the REAL store: scanned 42, dropped 11 (ids 40-51 minus 44, all md-ABSENT genuine orphans), unchanged 31; AFTER: all_notes 31 == GET-able 31 (tree stopped lying); 2nd run dropped 0 (idempotent).** The cache prune is a SQLite delete (no backend/data git change).

## 3 Gates — ALL PASS
- **Gate 1 (API):** POST /wiki/reindex + MCP wiki_reindex byte-identical (#24, in parity gate); 4 GET routes agent-readable 404 envelope; wiki-read 13→14 consistent. ✅
- **Gate 2 (Function):** orphan-only-drop distinguishing + idempotent + F6 (md-present never dropped) + 4× 404-shape; reindex_all snapshots-before-mutate; fail-soft self-heal; 0 errors; mypy clean. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step (caught route#4) + team-lead pre-verify + backend live evidence; commit format; git-status zero-left-dirty; WIKI-RECONCILE-only stage. ✅

## Assumptions (user-review)
- **#53 = bulk reindex-prune** (reindex_all over reindex_note; drops orphan cache rows whose md is gone) + REST + MCP + wiki-refresh self-heal. Pruning orphan INDEX rows is NOT a data-purge (files already gone) — done autonomously, surfaced. **How to change:** reindex_all + the routine hook.
- **#61 item#3 = agent_error NOT_FOUND on all 4 GET note-id routes** (flat JSONResponse body). **How to change:** the `_note_not_found` helper / which routes call it.
- **BOUNDARY: 3 WRITE-route 404s stay raw** → a follow-up slice (write-surface, #46-family). MCP found:false stays (existence-contract). **How to change:** the follow-up slice extends `_note_not_found` to the write routes if wanted.
- live reindex pruned 11 prod-store orphans (40-51 minus 44) — the actual #53 fix, not pollution.

## Notes
- Closes Cairn #53 + #61. backend-w3 EDITS; architect commits (§3). The 4th-GET-route catch (pre-commit, via recheck-all-consumers) avoided a reactive follow-up sprint. Next: #62 RSI-FLAT-HONEST (designed, held). Follow-ups: 3 write-route 404s (#46-family) + life_brief-F&G dogfood.
- honest-mirror pillar: a tree must not list notes that don't exist; a 404 must be agent-readable (a code to branch on + a hint), not a raw human string.
