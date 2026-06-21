# end_sprint_TRACING-REMINDERS-BE — the tracing→reminder wire (Cairn #75 BE-half)

> Result. An activity with `remind_at` set now materializes a reminder (source=tracing) that the EXISTING #29 notify engine fires — ONE-WAY (activity = source-of-truth). Commit `<hash>` `fix(sprint-TRACING-REMINDERS-BE)`. Status: ✅ all gates pass. backend-w3 BUILT (tracing+reminders schema/store/service + reader + test); architect 4-step + committed (§3). The BE half of #75 (FE = #75-FE, building ∥). Reuses the engine — no new scheduler.

## What shipped (8 files: 7 mod + 1 new test)
| File | Change |
|---|---|
| `tracing/schema.py` | +`remind_at` (HH:MM VN, validated) +`remind_repeat` (Literal daily\|weekdays\|off, default off) on ActivityInput/Update/Activity/ActivityView. |
| `tracing/store.py` | +remind_at/remind_repeat cols + idempotent migration + carry in create. |
| `tracing/service.py` | `_sync_reminder(act)` wired into create/update/archive — upsert the linked reminder on remind-set, delete on off/clear/archive. Fail-soft (a reminder-sync failure never breaks the activity write). |
| `reminders/schema.py` | +`source` (Literal manual\|tracing, default manual) +`activity_id` on Reminder — NOT on ReminderInput (forge-guard: a manual POST can't set source=tracing). |
| `reminders/store.py` | +source/activity_id cols + idempotent migration + `find_by_activity` + `update_reminder`. **The activity_id index created AFTER the ALTER** (the migration-order fix, below). |
| `reminders/service.py` | `upsert_for_activity` + `delete_for_activity` (internal-only, set source=tracing; reuse the #29 create/engine). |
| `reminders/reader.py` | map the new cols, pre-migration-tolerant. |
| `tests/test_tracing_reminders.py` (NEW, 12) | the EXERCISE distinguishing set. |

## ⚠️ MIGRATION-ORDERING BUG — live-caught + fixed (the value of live-verify)
`REMINDERS_SCHEMA` had `CREATE INDEX ON reminders(activity_id, source)` in the executescript block, with the `ALTER ADD COLUMN activity_id` in a LATER migration step. On a FRESH db (pytest) CREATE TABLE makes all cols → all tests passed. On the LIVE container (pre-#75 reminders table) CREATE-TABLE-IF-NOT-EXISTS is a no-op → the index hit `no such column: activity_id` → CRASH. **Caught ONLY by the live round-trip** (fresh-green ≠ migrated-correct). FIX: the activity_id index moved OUT of the schema-script to AFTER the ALTER (`CREATE INDEX IF NOT EXISTS` post-migration). Re-verified on the live MIGRATED table. Lesson saved (alter-migration-index-order). This is exactly why we live-verify schema changes on the real existing db.

## Design (LOCKED — one-way, reuse the engine, forge-guarded)
- ONE-WAY tracing→reminder (activity = source-of-truth; deleting the reminder doesn't touch the activity). source=tracing set ONLY by the tracing service (forge-guard — not a ReminderInput field). clear via remind_repeat=off; archive deletes the reminder (activity stays, archived). due_at = today-VN @ remind_at → UTC. fail-soft (sync never breaks the activity write). **Reuses the #29 notify engine + APScheduler — no new scheduler.**
- weekdays maps to the #29 daily engine (no weekday-mask yet — honest limitation, surfaced as "weekdays" on the activity).

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step (read full settled files):** the migration-order fix correct (index post-ALTER, idempotent `if col not in cols`) ✅; `_sync_reminder` wired into create/update/archive (upsert/delete) ✅; forge-guard (source defaults manual on user path; service sets tracing) ✅; due_at today-VN→UTC ✅; 8-file surface, schema = the pre-frozen shape (no churn) ✅.
- **backend-w3 evidence:** 12 EXERCISE tests (create-with-remind→reminder(source=tracing/activity_id/daily/title); no-remind/off→none; update→SAME no-dup; rename→title updates; clear-via-off→deleted; archive→deleted; archive-no-reminder→no-crash; forge-guard→stays manual; reminders_list consumer-recheck; weekdays→daily honest; invalid HH:MM→422). mypy clean (153). DEFAULT suite 2041/0 (= 2029 + 12). LIVE round-trip (post-fix): create remind_at=07:30 daily → reminder (source=tracing, due 00:30 UTC=07:30 VN) → off → GONE → forge stays manual. SCOPED cleanup (WHERE id=, the #72 lesson).
- **architect re-run:** test_tracing_reminders + test_reminders + test_tracing 53/0.

## 3 Gates — ALL PASS
- **Gate 1 (API):** the new fields additive; forge-guard; reuse the engine; pre-migration-tolerant reader. ✅
- **Gate 2 (Function):** the EXERCISE distinguishing set + the migration-order fix (live-caught) + forge-guard + consumer-recheck; DEFAULT 2041/0; mypy clean. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step + backend evidence + live round-trip; 8-file surgical stage (no FE/#75-FE leak — FE files landing kept OUT); commit format. ✅

## Assumptions (user-review)
- ONE-WAY tracing→reminder (activity source-of-truth). source=tracing service-set only (forge-guarded). clear via remind_repeat=off; archive deletes the reminder. due_at = today-VN @ remind_at → UTC. weekdays → the #29 daily engine (no weekday-mask yet — honest limitation). fail-soft. **How to change:** _sync_reminder / the engine for a weekday-mask.

## Notes
- #75 BE-half (FE = #75-FE building ∥). backend BUILT; architect committed (§3). The migration-order bug (fresh-green ≠ migrated-correct) was live-caught + fixed — a real win for the live-verify discipline. Schema = the pre-frozen snake shape (source/activity_id + remind_at/remind_repeat — all snake, the convention-fix confirmed). Committed from an intermixed tree (#75-FE landing on disk) — 8-file surgical stage, FE kept out. When #75-FE lands → #75 module DONE (habits can nudge). Next: #73 → #77 → #64.
