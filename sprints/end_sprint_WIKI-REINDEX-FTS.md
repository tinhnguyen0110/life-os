# end_sprint_WIKI-REINDEX-FTS — reindex-rebuild resyncs FTS+links (Cairn #68)

> Result. reindex_note's rebuild branch now resyncs ALL 4 secondary indexes (not just the cache row) → wiki_search + backlinks never go stale after an out-of-band md change. Commit `<hash>` `fix(sprint-WIKI-REINDEX-FTS)`. Status: ✅ all gates pass. backend-w3 EDITED (apply.py + reindex.py + __init__ + test); architect 4-step + committed (§3).

## The bug (Rule#0-grounded)
reindex_note's "rebuilt" branch only `upsert_note_cache` (cache row + aliases-in-row). It did NOT refresh the other 3 index-refreshes `_commit_note` does on a write (replace_aliases + _derive_links + _resolve_ghosts_for + fts_upsert). → after a reindex-rebuild (md changed out-of-band → reindex), wiki_search missed the note's new content + backlinks stale. A desync class DIFFERENT from #61 (orphan-row, fixed by reindex_all prune). The W1c "hooks in HERE" comment was never wired.

## What shipped (4 files — DRY, no new index logic)
| File | Change |
|---|---|
| `service/apply.py` (+38) | Extracted `_refresh_indexes(note)` from `_commit_note` — the 4 post-write index steps (replace_aliases + _derive_links + _resolve_ghosts_for + fts_upsert). `_commit_note` now CALLS it (PURE behavior-preserving extract — same order; md+cache stay write-specific). Documented as the index-only half shared by write + reindex. |
| `reader/reindex.py` (+9) | the "rebuilt" branch calls `wiki_service._refresh_indexes(note)` after the cache upsert (lazy via the existing handle). unchanged/missing_dropped UNTOUCHED (return before it — no churn, no resync on a dropped note). |
| `service/__init__.py` (+3) | export `_refresh_indexes` so the reader reaches it. |
| `tests/test_wiki.py` (+70, 4 tests) | co-located with the existing reindex tests. |

## Design (LOCKED — DRY shared helper)
- ONE `_refresh_indexes(note)` index-refresh path shared by `_commit_note` (write) AND reindex-rebuild → no drift; the indexes always match the md on EVERY path that makes a note current. The extract from _commit_note is byte-equivalent (same 4 steps, same order, just delegated).

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step:** `_refresh_indexes` = exactly the 4 steps (read the body); `_commit_note` now delegates (the 4 GONE inline → the call, same order — behavior-preserving); reindex rebuild calls it after the cache upsert; unchanged/missing_dropped untouched; scope exactly 4 files.
- **backend-w3 evidence:** RED-PROVEN (disable the call → the 2 search-based tests FAIL search("zeta")==[]; restore → pass — real teeth); FULL pytest 1982/0 (baseline 1978 + 4; count reconciled — 4 tests + 1 helper, not 5, via --collect-only); mypy clean (43 wiki files); LIVE round-trip on :8686 — out-of-band md edit ("zetareplaced") → search stale [] → POST /wiki/reindex {rebuilt:1} → search FINDS new term + old gone (the fix is live); test note cleaned up (no prod pollution).
- **Distinguishing is search/backlink-based** (not cache-row) — exactly as specced: a cache-only test passes against the stale-FTS bug; only a real fix passes the search assert.

## 3 Gates — ALL PASS
- **Gate 1 (API):** wiki_search + backlinks now correct after a reindex (the agent-facing search surface is honest). ✅
- **Gate 2 (Function):** the search-based distinguishing (RED-proven) + backlinks-after-reindex + unchanged-no-churn + #61-prune regression; mypy clean; 0 errors. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step (extract behavior-preserving verified) + backend RED-proof + live round-trip; commit format; git-status clean; #68-only (4 files). ✅

## Assumptions (user-review)
- **reindex-rebuild resyncs all 4 secondary indexes** (aliases + links + ghosts + fts) via a `_refresh_indexes` helper shared with _commit_note (DRY — one index path, no drift). **How to change:** the helper / the reindex call.

## Notes
- Cairn #68 (wiki-index-integrity theme with #53/#61). The DRY extract means write + reindex share ONE index-refresh path. backend-w3 EDITS; architect commits (§3). Next (auto-run): #65-P1 (Daily Tracing BE — designed, full derivation spec ready) → #65 P2/P3/P4 → #63 → #64.
