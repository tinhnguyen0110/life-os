# end_sprint_85-DEV-TRACING-DOUBLE-COUNT — dev_activity stale-row double-count FIXED (Cairn #85)

> Result. dev_activity showed the same commits in BOTH source="you" AND source="other" (life-os: you 74 + other 73, all authored by the identity-email). Root cause (architect Rule#0, REFUTING the dispatch hypothesis): NOT a dedup-key/source-tag bug (both correct) — STALE ROWS from the #84 fix. The store keys on `(date, repo, source)`; pre-#84 the colon-split bug tagged every commit "other", post-#84 the same commits tag "you", and the upsert (keyed on source) never overwrote the orphaned "other" rows → double-count. Fix: a scan is AUTHORITATIVE for its (date-window × scanned-repos) — a SCOPED delete-before-upsert clears the orphans. Commit `<hash>` `fix(sprint-85-dev-tracing): authoritative-window delete clears stale source rows (#85)`. Status: ✅ verified (backend-w3 built; architect 4-step led with the DELETE SQL read + INDEPENDENT both-teeth + non-destructive live other 73→0). BUG (admin-lead raised, follow-up #84). LIVE: life-os other 73→0, you preserved.

## What shipped (service.py + store.py + 6 tests)
| File | Change |
|---|---|
| `dev_activity/store.py` | NEW `delete_window(since_date, repos) -> int` — **SCOPED** `DELETE FROM dev_activity WHERE date >= ? AND repo IN (<placeholders>)` (params bound). 🔴 **empty repos → return 0 (delete NOTHING)** — the snapshot-wipe guard (#72): a 0-commit/unreachable scan can NOT wipe. Repos not scanned this run keep their rows (honest). |
| `dev_activity/service.py` | `scan()`: build `scanned_repos` = LOCAL repo basenames (incl. 0-commit, so a now-empty (date,repo) stale row still clears) ∪ remote agg-key repos; call `store.delete_window(since_day, scanned_repos)` BEFORE the upsert loop → re-upsert fresh aggregates. So an attribution change (#84 'other'→'you') leaves NO orphan source row. |
| `tests/test_dev_activity.py` (+6) | the stale-clear teeth (revert delete → RED) + no-(date,repo)-both-sources + scoped-delete-doesn't-wipe-unscanned + empty-repos-deletes-nothing + **unreachable-root-doesn't-wipe-existing (the #72 guard)** + idempotent-no-double-count-on-rescan. |

## Design (LOCKED — authoritative-window, #72-safe scoped delete)
- **Root (Rule#0, hypothesis CORRECTED):** the dispatch guessed "dedup-key-includes-source" / "source-per-scanner-pass" — BOTH refuted in code (dedup is sha-only; source IS by author-identity on local+remote). The real bug = stale rows orphaned by #84's attribution flip (upsert keys on source → old "other" rows never overwritten).
- **Fix = authoritative-window:** a scan re-derives [since_day..today] × scanned-repos, so it's authoritative for that window — DELETE those rows first, then upsert fresh. A (date,repo) now all-"you" loses its stale "other".
- **🔴 #72-safe DELETE (the load-bearing safety):** SCOPED to BOTH date>=since AND repo IN the explicit scanned set (never blanket, never date-only). EMPTY scanned set → delete 0 (a 0-commit/unreachable scan can't wipe). Un-scanned repos keep their rows. (the verify-cleanup-scope-delete-not-blanket / #72 portfolio_snapshot lesson.)

## Verification (Rule#0 — architect INDEPENDENT, led with the DELETE SQL)
- **🔴 read the FULL DELETE SQL first:** `DELETE FROM dev_activity WHERE date >= ? AND repo IN (<placeholders>)` — pins BOTH date AND repo-set, params bound, empty-repos→return-0. NO bare/date-only delete. #72-safe. ✅ (team-lead independently re-read it in the push window.)
- **architect 4-step:** scanned_repos correctly = local basenames (incl 0-commit) ∪ remote agg-keys; delete called before upsert; scoped + empty-guard ✅.
- **INDEPENDENT teeth 1 (stale-clear):** reverted the `delete_window` call → `test_scan_clears_stale_other_row_after_attribution_flip` went RED (stale "other" survives without the delete); restored → green. ✅
- **INDEPENDENT teeth 2 (the #72 snapshot-wipe guard):** BROKE the empty-guard (made empty-repos do a blanket date-delete, simulating the #72 mistake) → `test_delete_window_empty_repos_deletes_nothing` + `test_scan_unreachable_root_does_not_wipe_existing` BOTH went RED; restored → green. → the guard tests have REAL teeth (they'd catch a future blanket-delete regression). ✅
- **NON-DESTRUCTIVE live check:** ran the actual fixed `scan(days=3)` on the container (NO hand-delete) + READ the result → life-os other **73→0**, you preserved (76), 0 (date,repo) with both sources for life-os. (the #72 + test-writes-pollute-prod lesson: run the real path + read, don't hand-delete to "see it work".)
- **Suite:** dev_activity 37 passed; DEFAULT (`-m 'not slow'` deterministic) = **2132 passed / 6 skipped / 3 deselected / 0 failed** forward AND reverse (no isolation leak); mypy clean.
- **backend live (90d):** life-os other 73→0, yourCommits 1690; ⚠️ 9 (date,repo) pairs STILL both-source = LEGIT multi-author company repos (GAE/*, intent-mirror) — NOT stale (the feature working: your-vs-team attribution); life-os NOT among them.

## 3 Gates
- **Gate 1 (store):** delete_window scoped (date+repo IN), empty-guard, params bound — #72-safe; honest (un-scanned repos survive). ✅
- **Gate 2 (Function):** the stale-clear teeth + the snapshot-wipe-guard teeth (both independently re-run, both RED-on-break); no-both-sources; idempotent; scoped-delete-safety; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step led with DELETE SQL + independent both-teeth + non-destructive live; counts 2126→2132; staged set EXACTLY service.py + store.py + test (#84 split fix already landed 4cd5d04 — not re-staged); commit format. ✅

## Assumptions (user-review)
- **A scan is AUTHORITATIVE for (since_day..today × scanned-repos)** — it deletes+re-derives those rows. **Why:** the scan reads the live repos/remotes fresh, so its window is the source of truth; this clears stale attribution. **How to change:** the scanned_repos set / the delete_window call in scan().
- **delete_window is SCOPED + empty-guarded (never blanket)** — a 0-commit/unreachable scan deletes nothing; un-scanned repos keep their rows. **Why:** the #72 wipe lesson. **How to change:** delete_window's WHERE / the empty-return-0 guard (DON'T — this is the safety).
- **9 multi-author company repos legitimately carry both you+other** — that's the feature (your-vs-team), not a bug. **How to change:** N/A (correct behavior).

## Notes
- Cairn #85 BUG (admin-lead raised; backend-w3 built; follow-up to #84). The architect Rule#0 catch — refuting BOTH dispatch hypotheses in code+live before backend coded the wrong (dedup-key) fix — is the dispatch-as-hypothesis approach working: team-lead gives symptom+guess, architect verifies the guess. The DELETE is the #72-hazard zone; it's scoped + empty-guarded + double-verified (architect + team-lead both read the SQL). #84+#85 both touched dev_activity/service.py but serially (84 landed 4cd5d04, 85 builds on it — disjoint diffs). After #85 → the dev-tracing feature is correct end-to-end (you=0 fixed in #84, double-count fixed in #85).
