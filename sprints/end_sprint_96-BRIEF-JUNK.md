# end_sprint_96-BRIEF-JUNK — recentActivity dedup + exclude soft-deleted/empty (Cairn #96, HIGH)

> Result. The user's personal daily_brief.wikiContext.recentNotes was noisy (the same note N times + soft-deleted/empty-title trash leaking in). Fixed at the SHARED source `_recent_activity`: exclude soft-deleted (deletedAt-set, checked at READ time) + empty-title + dedup by noteId (keep newest) → over-scan → exclude → dedup → cap. ONE fix → every consumer clean (the #36 brief wikiContext AND the wiki overview). Commit `<hash>` `fix(sprint-96-brief-junk): recentActivity dedup + exclude soft-deleted/empty (#96)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT durable teeth + limit-after-filter + LIVE brief clean on the container). Cairn #96 HIGH — the recheck-all-consumers miss #94 exposed.

## What shipped (1 file + test)
| File | Change |
|---|---|
| `wiki/reader/oplog.py` | `_recent_activity` rewritten: over-scan the op_log (≥ limit, bounded by `_RECENT_OVERSCAN=200`) → for each op resolve the note's CURRENT cache row → EXCLUDE if no-row (hard-deleted) / `deleted_at` NOT NULL (soft-deleted — matches #94's tree/search hide) / empty-title → DEDUP by noteId (rows seq-DESC → first-seen is newest, via a `seen` set) → cap to `limit`. So the limit returns N REAL LIVE notes, not N pre-filter. |
| `tests/test_wiki_recent_activity.py` (NEW, 7) | exclude-soft-deleted · dedup-by-noteId · not-over-broad (live note kept) · empty-title-skip · limit-returns-N-live · the durable teeth. |

## Design (LOCKED — durable read-surface filter, one shared source, read-time status)
- **🔴 durable read-surface filter (the right architecture):** the op_log is append-only → a soft-deleted note's ops PERSIST in it → that's WHY recentActivity leaked them. The fix checks the note's CURRENT status (the #94 `deleted_at` cache field) at READ time + excludes — so junk is hidden BY CONSTRUCTION, even a future leaked throwaway never reaches the user's brief (durable, not cleanup-discipline-dependent). Matches #94's tree/search/all_notes hide-points (recentActivity was the missed consumer).
- **one shared source:** `_recent_activity` feeds BOTH the #36 brief wikiContext AND the wiki overview → ONE fix → every consumer clean (the recheck-all-consumers principle, fixed at the source not per-consumer).
- **order: over-scan → exclude → dedup → cap** — so `limit` returns N LIVE entries (not N pre-filter that then shrinks). dedup keeps the newest op per noteId (seq-DESC first-seen).
- **NOT a hard-purge** (the 13 trash notes stay correctly soft-deleted — user-decision); **NOT a pytest-teardown** (the #93/#94 tests are already isolated — the part-3 framing was corrected at kickoff; the real pollution source was manual live-verify, the durable fix is this read-surface filter).

## Verification (Rule#0 — architect INDEPENDENT)
- **architect 4-step (read FULL):** the over-scan→exclude→dedup→cap order; read-time deleted_at check (correct — op_log append-only); pre-migration tolerant (`"deleted_at" in keys`); one shared source. ✅
- **architect INDEPENDENT durable teeth (own behavior-test):** seed live + a note edited 3× (dup-ops) + a soft-deleted → recentActivity EXCLUDES the soft-deleted, DEDUPS the 3-op note to 1 entry, KEEPS the live note (not over-broad), 0 empty-title, 0 dup. ✅
- **architect INDEPENDENT limit-after-filter:** 3-newer-deleted + 2-live, limit=2 → returns the 2 LIVE (over-scan→exclude→cap, not 2-pre-filter). ✅
- **🔴 LIVE brief (the user's actual brief — the real proof):** `GET /brief` → wikiContext.recentNotes: count 7, dup-noteIds FALSE, empty-titles FALSE, **trash-ids-leaked = []** (the 13 trash notes NO LONGER reach the brief). ✅
- **Suite:** the 7-test file green; DEFAULT (`-m 'not slow'` deterministic) = **2206 passed / 6 skipped / 3 deselected / 0 failed** forward AND reverse (2199→2206 = +7 tests); never staged backend/data/.

## 3 Gates
- **Gate 1 (read surface):** recentActivity excludes soft-deleted/empty + dedups; agent-readable (the brief consumer gets clean live notes); one source. ✅
- **Gate 2 (Function):** the durable teeth (exclude + dedup + not-over-broad + limit-after-filter); independent re-run; LIVE brief clean; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent + LIVE; staged set EXACTLY oplog.py + test + end doc (no FE/data/.env/template); commit format. ✅

## Assumptions (user-review)
- **recentActivity excludes soft-deleted (deletedAt-set) + empty-title; dedups by noteId (newest op).** **Why:** the user's brief should show real live notes once each. **How to change:** the filter/dedup in `_recent_activity`.
- **over-scan bound = 200** (`_RECENT_OVERSCAN`) — enough to fill `limit` live entries past many deleted/dup ops without unbounded scan. **How to change:** `_RECENT_OVERSCAN`.
- **the 13 trash notes are HIDDEN (not purged)** — correctly soft-deleted, recoverable. A hard-purge is a separate user-decision (not #96).

## Notes
- Cairn #96 HIGH — the recheck-all-consumers miss #94 exposed (deletedAt hid tree/search/all_notes/count_by_status but MISSED recentActivity → the #36 brief leaked trash). Fixed durably at the shared `_recent_activity` source (one fix, every consumer clean). backend-w3 built; architect committed (§3 sole-committer). **Kickoff Rule#0 catch:** the dispatch's part-3 ("the tests pollute prod, add teardown") was corrected — the #93/#94 pytest tests are already isolated (a teardown = no-op); the real pollution was manual live-verify, and the durable fix is THIS read-surface filter (hides junk by construction). The live-verify-cleanup-by-id rule is the going-forward complement (logged to memory: durable-read-surface-filter-over-cleanup-discipline). Next: the agent-first tool-hardening batch (#91 dev_activity cap/dedup [token-overflow, most painful] first → #92/#99/#98 + hash-validate).
