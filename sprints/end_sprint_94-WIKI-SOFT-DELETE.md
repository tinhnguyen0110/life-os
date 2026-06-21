# end_sprint_94-WIKI-SOFT-DELETE — wiki soft-delete + restore + bulk + MCP (Cairn #94 BE, subsumes #90-GAP2)

> Result. User CHỐT "a" + pain "xoá nhầm" fixed: `DELETE /wiki/notes/{id}` is now SOFT (recoverable) — sets a `deletedAt` tombstone, KEEPS the .md (reconcile-safe), hides from live views; `POST /wiki/notes/{id}/restore` brings it fully back; `POST /wiki/notes/bulk-delete` (per-id fail-soft); `GET /wiki/trash` lists the soft-deleted; MCP `wiki_delete_note`/`wiki_restore_note` (subsumes #90-GAP2). Commit `<hash>` `feat(sprint-94-wiki-soft-delete): soft-delete+restore+bulk+MCP, reconcile-safe (#94, subsumes #90-GAP2)`. Status: ✅ verified (backend-w3 built; architect 4-step led with the #72 scoped-SQL read + INDEPENDENT reconcile-safe/restore behavior-test + live delete→trash→restore + MCP-tools-present). Cairn #94 BE (FE-#94 trash/restore UI follows). The SERIAL-second of the #93/#94 wiki batch.

## What shipped (BE wiki files + tests)
| File | Change |
|---|---|
| `store/_base.py` | `deleted_at TEXT` column on wiki_notes + the idempotent migration (`if "deleted_at" not in cols: ALTER TABLE ADD COLUMN`; existing notes → NULL=live — the #75 migration pattern). |
| `store/notes.py` | NEW `set_deleted_at(note_id, deleted_at) -> bool` — **SCOPED `UPDATE wiki_notes SET deleted_at = ? WHERE id = ?`** (single id, params bound; the #72 wipe lesson — NEVER a blanket UPDATE). |
| `store/queries.py` | `all_notes` + `count_*` now `WHERE deleted_at IS NULL` (live EXCLUDES soft-deleted); NEW trash query `WHERE deleted_at IS NOT NULL`. |
| `service/apply.py` | `_apply_delete` HARD→SOFT: `model_copy(deletedAt=now)` → `write_note_file` with the tombstone (KEEPS the .md, 1 commit) → `set_deleted_at` cache → `fts_delete` (hide from search); aliases/links/cache row KEPT. NEW `_apply_restore`: clear deletedAt → rewrite .md w/o tombstone → set_deleted_at(None) → re-add fts + refresh resolver/edges. |
| `service/crud.py` | NEW `soft_delete_note` + `restore_note` (the OLD hard `delete_note` KEPT but now has NO user-reachable caller — see Notes). |
| `router.py` | `DELETE /wiki/notes/{id}` now calls `service.soft_delete_note` (returns `{deleted, deletedAt}`) + NEW `POST /notes/{id}/restore` + `POST /notes/bulk-delete` (per-id fail-soft) + `GET /wiki/trash`. |
| `mcp/write_server.py` | NEW `wiki_delete_note` (kind `note_softdelete`) + `wiki_restore_note` (kind `note_restore`) — proposal-gated, mirror REST (subsumes #90-GAP2). |
| `schema.py` | Note += `deletedAt: str | None`; `BulkDeleteInput {ids:[int]}`. |
| `proposals_schema.py` / `proposals_service.py` / `service/__init__.py` / `service/errors.py` / `store/__init__.py` | wire the note_softdelete/note_restore op-kinds + exports. |
| tests | `test_wiki_soft_delete.py` (NEW, 13) — soft-delete-hides-keeps-md, reconcile-safe-reindex-keeps-row, restore-value-by-value, bulk, MCP, excluded-from-counts; + test_wiki/test_mcp_*/test_wiki_mcp_write updated (the 2 behavior-changes below). |

## Design (LOCKED — reconcile-safe by construction, #72-scoped, orthogonal tombstone)
- **🔴 reconcile-safe (THE #61 constraint):** soft-delete KEEPS the .md (writes it WITH the tombstone) → the reindex prunes a cache row ONLY when its .md is GONE → a soft-deleted note's row SURVIVES reindex (reindex_note action != "missing_dropped") → NO note-ma by construction. Set-tombstone-NOT-delete-row.
- **deletedAt tombstone (NOT Status="deleted") — architect decision, DIVERGED from the admin-lead spec's status-overload suggestion (decide-and-log, team-lead-approved):** a SEPARATE `deletedAt` field, orthogonal to the Status Literal [fleeting/developing/evergreen]. Overloading Status with "deleted" would ripple through every status consumer (count_by_status, the lifecycle UI, brief's status-filters). A separate tombstone keeps soft-delete clean.
- **#72-scoped:** every delete/restore is `WHERE id = ?` (single id); bulk loops per-id. NO blanket UPDATE/DELETE on wiki_notes.
- **restore = full inverse:** clear deletedAt + rewrite .md + re-add fts + refresh indexes → the note is back value-by-value (title/content/links/aliases).
- **MCP = proposal-gated soft-delete/restore** (mirrors REST, subsumes #90-GAP2).

## Verification (Rule#0 — architect INDEPENDENT, led with the SQL + a self-caught test)
- **🔴 read the scoped SQL first:** `set_deleted_at` = `UPDATE ... WHERE id = ?` (single id, params bound), live queries `WHERE deleted_at IS NULL`, trash `WHERE deleted_at IS NOT NULL`, the bulk loops per-id. NO blanket op. #72-safe. ✅
- **architect INDEPENDENT behavior-test:** soft-delete → HIDDEN from all_notes/search but .md + cache row KEPT (deleted_at set); reindex_note action != "missing_dropped" (reconcile-safe); restore → back value-by-value (title/tags/[[link]] intact). ✅
- **🔴 a self-caught Rule#0 moment:** my FIRST independent test called the OLD hard `delete_note` (wrong fn) → the .md was gone → I investigated rather than assuming a bug → confirmed the ROUTER's DELETE endpoint calls `soft_delete_note` (the real user path is soft) + verified NO user-reachable caller of the hard `delete_note` remains (grep = 0). Re-ran with the correct `soft_delete_note` → green. (The hard fn is dead-but-exported — harmless, a future cleanup.)
- **live delete→trash→restore (container):** soft-delete → /wiki/trash count +1 (the note IS in trash) + EXCLUDED from /wiki/tree; restore → no longer in trash (back to live), deletedAt cleared, GET 200. ✅
- **MCP:** wiki_delete_note + wiki_restore_note present on the live /mcp/wiki-write tools/list (after restart). ✅
- **the 2 behavior-changes (verified intentional-correct, not masking):** (a) the old roundtrip "DELETE→404" updated to soft semantics (GET 200 + deletedAt + /trash + restore) — correct new behavior. (b) #35 _override_feedback_detail softdelete → overrideKind "delete" — correct (a soft-delete IS a delete from the feedback POV). ✅
- **Suite:** the 13-test soft-delete file green; DEFAULT (`-m 'not slow'` deterministic) = **2193 passed / 6 skipped / 3 deselected / 0 failed** forward AND reverse (2180→2193 = +13 soft-delete tests); never staged backend/data/.

## 3 Gates
- **Gate 1 (API/MCP):** soft-delete/restore/bulk/trash REST + MCP delete/restore (proposal-gated, REST≡MCP); agent_error 404; `{deleted,deletedAt}` / `{results,deletedCount}` / `{trash,count}` shapes. ✅
- **Gate 2 (Function):** the reconcile-safe teeth (reindex keeps the row) + restore-round-trip + bulk + the #72-scoped SQL; independent behavior-test + the self-caught routing verification; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step led with the SQL + independent + live; staged set EXACTLY the BE wiki files + tests + end doc (NO #97-FE frontend, no data/.env/template); commit format. ✅

## Assumptions (user-review)
- **deletedAt tombstone (separate field), NOT Status="deleted"** — orthogonal to the workflow lifecycle (diverged from the admin-lead spec's status-overload; team-lead-approved). **How to change:** revert to a Status enum value (NOT recommended — ripples through consumers).
- **soft-delete is recoverable via /wiki/trash + restore; nothing is ever hard-deleted via the user path.** A true purge (permanent) is NOT in #94 (a future "empty trash" if the user wants it). **How to change:** add a purge endpoint (gated).
- the OLD hard `delete_note` is dead-but-exported (no user-reachable caller). **How to change:** remove it in a cleanup (harmless now).

## Notes
- Cairn #94 BE (user CHỐT "a" soft-delete + pain "xoá nhầm"). The SERIAL-second of the #93/#94 wiki batch (#93 landed b5f2fd5). backend-w3 built; architect committed (§3 sole-committer). Committed from an intermixed tree (#97-FE dev-activity in flight on frontend/) — BE-only surgical stage. The reconcile-safe (.md kept) is the load-bearing #61 constraint; the #72-scoped SQL the load-bearing safety. NB: my live-verification left ~7 throwaway test notes soft-deleted in /wiki/trash (recoverable, hidden from live — a tidy-up if a purge lands; flagged to team-lead). Next: FE-#94 (trash/restore UI) + #51 (overdue→mail, BE flows #94→#51).
