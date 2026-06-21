# Sprint WIKI-REINDEX-FTS — reindex_note rebuild syncs FTS+links (Cairn #68)

> Created 2026-06-21 by architect (value-safe, NEVER-FREE ∥ while backend does #69). LOW but real bug — a desync class DIFFERENT from #61 (orphan-row). HOLD dispatch until #69 commits (sequential, 1 backend/tree; same wiki module). backend EDITS; architect commits (§3).

## The bug (Rule#0-grounded — admin-lead verified, architect re-confirmed)
`reindex_note`'s "rebuilt" branch (reader/reindex.py:65-73) ONLY `upsert_note_cache` (cache row + aliases-in-row). It does NOT refresh the other 3 indexes that `_commit_note` (service/apply.py:43-52) refreshes on a normal write:
- `replace_aliases` (alias→id resolver index)
- `_derive_links` (outbound edges)
- `_resolve_ghosts_for` (ghost auto-resolve)
- `fts_upsert` (full-text search index)
→ After a reindex-rebuild (md changed out-of-band → reindex), FTS + links + alias-resolver go STALE: `wiki_search` won't find the reindexed note's new content; backlinks wrong. The W1c comment (reindex.py:29-30 "Full FTS5 + link-graph reindex hooks in HERE when tables exist") was never wired — but the tables exist + are used. Different from #61 (orphan-row, fixed by reindex_all prune).

## The fix (DRY — extract a shared index-refresh helper)
1. **Extract `_refresh_indexes(note)` from `_commit_note`** (apply.py) — the 4 post-write steps: `replace_aliases` + `_derive_links` + `_resolve_ghosts_for` + `fts_upsert`. `_commit_note` calls it (no behavior change — pure extract); the reindex rebuild branch calls it too. DRY — NO duplication of the index logic.
2. **reindex_note "rebuilt" branch** (reindex.py:73, after upsert_note_cache) → call `_refresh_indexes(note)` so all 4 indexes sync with the md. (cache already upserted above; the helper does the other 4.)
3. **reindex_all** (bulk) — inherits the fix automatically (it calls reindex_note per id; a "rebuilt" action now refreshes indexes). Confirm no extra change needed.

## Defensive
- action="rebuilt" → indexes refreshed; action="unchanged" → NOT touched (no needless FTS churn); action="missing_dropped" → cache deleted (the #61 path, unchanged — don't refresh a dropped note).
- a link to a now-missing note after rebuild → ghostify (via _derive_links/_resolve_ghosts_for, same as _commit_note).
- #61 regression: reindex_all still prunes orphan rows.

## HARD GATE (distinguishing — MUST assert via search/backlink, NOT tree-row)
1. Create a note → edit its md DIRECTLY (change title/body) → reindex_note → `wiki_search(new-title/body)` FINDS it (FTS synced). **A test asserting only the tree-row/cache PASSES against the stale-FTS bug → MUST assert via wiki_search + backlinks (only a real fix passes).**
2. A note with an inbound link → reindex → backlinks still correct (links synced).
3. #61 regression: reindex_all still prunes orphans.
- pytest 0-failed, mypy clean. Verify on LIVE HTTP (wiki_search after a reindex).

## Baseline
pytest = post-#69 count (confirm at dispatch). Keep 0-failed.

## Assumptions (user-review)
- **reindex_note rebuild now syncs all 4 indexes** (cache + aliases + links + ghosts + fts) via a `_refresh_indexes` helper extracted from `_commit_note` (DRY). **How to change:** the helper / the reindex rebuild call.

## Notes
- Cairn #68. Theme = wiki-index-integrity (with #53/#61). The DRY extract means _commit_note + reindex share ONE index-refresh path (no drift). The distinguishing MUST be search/backlink-based (the whole bug is that the tree-row looks right while FTS/links are stale). backend EDITS apply.py + reindex.py; architect commits fix(sprint-WIKI-REINDEX-FTS). HOLD until #69 commits. Verify LIVE HTTP.
