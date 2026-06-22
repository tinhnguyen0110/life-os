# end_sprint_127-W1-WIKI-FOLDERS — wiki folder lifecycle + empty-folder anchor (Cairn #127 W1 = #132)

> Result. The wiki gains a folder lifecycle (the dev work-dir foundation): create a NESTED folder (any depth, even empty), SOFT-delete a folder + its subtree (scoped, recoverable), move/rename. The empty-folder anchor = `folder_tree` UNIONs note-prefixes ∪ `wiki_folder_meta` keys (the design §3 option B). Commit `<hash>` `feat(sprint-127-w1-wiki-folders)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT live nested-create-in-tree + SCOPED-soft-delete-sibling-survives + move). Cairn #127 W1 (#132) — be-only, CLOSES on this commit → #133 (W2) unblocks. REST-only. Disjoint from #130 (tracing, landed).

## What shipped
| File | Change |
|---|---|
| `reader/tree.py` | 🔴 the empty-folder ANCHOR: `folder_tree` now UNIONs the note-prefix walk ∪ `all_folder_meta()` keys (seeds every ancestor segment of each meta path → "A/B/C" with no notes nests A→B→C). A meta-only/empty/nested folder shows as an honest node (counts:0). |
| `service/folders.py` (NEW) | `create_folder(path,desc)` (nested any depth, normalize_folder, dup→409, empty→422); `delete_folder(path)` (SCOPED soft-delete the subtree — #94 tombstone every LIVE note where folder==path OR startswith path+'/', + drop the subtree's folder_meta rows; recoverable; fail-soft per note); `move_folder(path,to)` (re-prefix subtree notes + move meta; target-exists→409, into-own-subtree→422). `_subtree_match` = the SCOPED matcher (#72). Notes route through the single-writer queue (git-per-write). |
| `store/folder_meta.py` + `store/__init__.py` | the folder_meta ops for create/delete/move-subtree. |
| `router.py` | POST /wiki/folders · DELETE /wiki/folders/{path:path} · PUT /wiki/folders/{path:path}/move. |
| `schema.py` + `service/errors.py` | the folder-op shapes (FROZEN for W2/W3) + the agent-errors (409/422). |
| `tests/test_wiki_folder_lifecycle.py` (NEW, 17) | create-nested-empty→counts:0-each-level / delete-subtree-soft+SCOPED-other-untouched / restorable / move-reprefix / dup→409 / subtree→422 / backward-compat. |

## Design (LOCKED — empty-folder anchor option B, SCOPED soft-delete, REST-only)
- **🔴 the empty-folder anchor (design §3 option B):** a folder EXISTS if it has notes (prefix) OR a `wiki_folder_meta` row. create-empty/nested = INSERT folder_meta rows; `folder_tree` UNIONs prefixes ∪ meta-keys → the nested empty folder shows. (NOT a .keep marker, NOT a new table — reuses the folder-keyed KV; git-clean.)
- **SCOPED soft-delete (#72 + #94):** delete a folder → #94-tombstone every LIVE note in EXACTLY that subtree (folder==path OR startswith path+'/') + drop the subtree's meta rows. Recoverable (notes → trash). OTHER folders untouched (verified — a sibling survives). NEVER a blanket. 422 on root.
- **move = re-prefix:** subtree notes' folder rewritten (path→to) + meta keys moved; 409 target-exists, 422 into-own-subtree.
- **REST-only** (user CHỐT #2 — folders are a human-curation surface, NOT MCP) → no read_server/count-assert.

## Verification (Rule#0 — architect INDEPENDENT, live)
- **architect 4-step (read FULL):** the tree-union anchor (seeds ancestor segments from meta-keys); `_subtree_match` SCOPED matcher; delete soft-tombstones the subtree + drops meta; move re-prefixes; dup→409/empty→422/root→422. Staged W1 wiki-only (NO tracing/frontend/read_server leak — #130 tracing already committed). ✅
- **🔴 INDEPENDENT LIVE (the load-bearing cases):** create `arch127/a/b` (no notes) → shows in /tree with counts:{notes:0} (nested empty — the headline "folder con trong folder"); dup→409; empty→422; **delete `arch127/a` → subtree gone from tree, the SIBLING `arch127/sibling` SURVIVES** (SCOPED, no leak — the #72 case); move works; scoped cleanup. ✅
- **mypy --no-incremental clean; 17 W1 tests passed** (independent); backend FORWARD 2437/0 == REVERSE; 36 existing wiki tests green. ✅

## 3 Gates
- **Gate 1 (API):** POST/DELETE/PUT folders (agent-readable 409/422 + hints); nested-create; SCOPED soft-delete; recoverable. ✅
- **Gate 2 (Function):** the 17 tests (nested-empty-in-tree / scoped-soft-delete-sibling-survives / restorable / move-reprefix / dup-409 / subtree-422 / backward-compat) + live + mypy. NOT self-confirming (the live sibling-survives + nested-in-tree are the real surfaces). ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent live; staged EXACTLY W1 wiki (NO tracing/FE/read_server leak); commit format; migration idempotent. ✅

## Assumptions (user-review)
- **empty/nested folder = a wiki_folder_meta row (anchor); folder_tree unions prefixes ∪ meta-keys** (design §3 B). **How to change:** the tree union + create_folder.
- **folder-delete = SOFT (subtree #94-tombstoned, recoverable); SCOPED to exactly the subtree.** **How to change:** the delete_folder scope/soft-vs-hard.
- **folder-ops REST-only (not MCP).** **How to change:** add an MCP tool (user CHỐT was REST/FE-only).

## Notes
- Cairn #127 W1 (= board #132) — be-only; the wiki-work-dir foundation. user-CHỐT (nested folders + delete, on the UI — W3). backend-w3 built; architect committed (§3 sole-committer). 🔴 **The empty-folder anchor (option B) is the load-bearing piece** — folders were pure path-prefixes (an empty folder couldn't exist); now `folder_tree` UNIONs the folder_meta keys so a nested empty folder shows (the headline "folder con trong folder"). SCOPED soft-delete verified live (sibling survives — the #72 case). **🔴 GOTCHA for W2/W3 (relayed):** `soft_delete_note` tombstones but `get_note` STILL returns the tombstone — "gone" is observed via all_notes/tree, NOT get_note. **Parallel-lane:** W1 wiki-only (tracing clean — #130 committed first; by-module). **#133 (W2: strict import + thin move/rename note) unblocks** (serial — same wiki/router.py; commit W1 first, done). W3/#134 FE after W2 freeze. REST-only, no restart.
