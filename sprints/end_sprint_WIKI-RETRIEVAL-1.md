# end_sprint_WIKI-RETRIEVAL-1 — wiki_tree folder-meta + note kind/status (Cairn #20)

> Result. LANE B. Additive enrichment of the wiki_tree (f50ba34), kept MCP≡REST byte-identical (the #24 invariant). Commit `<hash>` `feat(sprint-WIKI-RETRIEVAL-1)`. Status: ✅ all 3 gates pass.

## Objective (met)
Enrich wiki_tree so an agent navigating the vault (like `ls`) understands folders + note kinds WITHOUT reading bodies (token-cheap retrieval). Additive; both REST + MCP stay byte-identical.

## What shipped
| File | Change |
|---|---|
| `modules/wiki/store/folder_meta.py` (NEW) | a light module-local `wiki_folder_meta` KV table (folder_path, desc) — honest-null when absent (decide-and-log: KV table over a readme-note convention, avoids body-parsing ambiguity). |
| `modules/wiki/reader/tree.py` | `folder_tree(folder, depth)` — per-folder `meta:{desc}|null` (from folder_meta, never fabricated) + `counts:{notes:N}` (direct, not subtree) + per-note `kind`(note_type)+`status` (real fields, NO body) + `depth` limiter (depth=0 → folder names + own notes only; None = unlimited) + `folder` subtree scope. |
| `modules/wiki/mcp/read_server.py` | `wiki_tree(folder, depth)` returns `reader.folder_tree(...)` DIRECTLY (no {tree:} wrapper — the #19/#24 byte-identical invariant preserved). |
| `modules/wiki/router.py`, `schema.py`, `store/__init__.py`, `store/_base.py` | the REST surface + the folder_meta store wiring. |
| tests | test_wiki_folder_meta.py (new) + test_wiki_folder.py + test_wiki_mcp_read.py. |

## Verification (Rule #0 — architect + team-lead container)
- **architect 4-step:** folder_tree meta honest-null (`metas.get(path)` → None when no row, never fabricated), counts direct-not-subtree, kind/status from real fields no-body, depth limiter; wiki_tree returns folder_tree directly (no wrapper). Confirmed reminders/store.py (the #29 last_notified, lane A) was EXCLUDED from this commit.
- **team-lead independent container:** REST /wiki/tree == MCP wiki_tree BYTE-IDENTICAL with the new fields (root keys [counts,folders,meta,name,notes,path] both sides, sort_keys dumps equal, NO `tree` wrapper re-introduced — the #19/#24 invariant held, the regression watched-for); folder meta present + honest-null when absent; note-stubs kind+status, no body; depth param works (depth=0 → folder skeleton/empty contents, depth=1 → +notes, depth≥2 → full — monotonic, not a no-op). 1773 suite green (+10), mypy clean.

## 3 Gates — ALL PASS
- **Gate 1 (API):** wiki_tree REST==MCP byte-identical WITH the new fields (parity preserved); folder_meta REST surface; envelope intact. ✅
- **Gate 2 (Function):** meta honest-null vs set, kind/status real fields, depth monotonic limiter, counts direct; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; full-function spot-check; architect + team-lead container; commit format; lane-A (#29) reminders/store.py correctly excluded. ✅

## Assumptions (user-review)
- **folder_meta = a light module-local KV table** (folder_path, desc), honest-null when absent — NOT a readme-note convention. **How to change:** the folder_meta store + the tree reader's meta-join.
- **kind/status read from the note's real fields** (note_type/status); tree is body-less (navigation). **depth=0 = folder names + own notes only** (monotonic limiter; None = unlimited).

## Notes
- LANE B; separate commit (reminders #29 last_notified excluded — that's lane A, in-progress).
- Kept the #24 byte-identical invariant (the regression team-lead watched for, given the #19 wrapper-drift history).
- Pipeline after: wiki #21(outline)/#22(search)/#23(consolidate)/#24(test-gate) — likely group #21+#22 (retrieval refinements, shared reader files).
