# end_sprint_REMINDERS-3 — reminders notify engine (Cairn #29, the báo-thức payoff)

> Result. LANE A (priority). The GAP-4 core: reminders went from INERT (create/list/tick only) to FIRING. Commit `<hash>` `feat(sprint-REMINDERS-3)`. Status: ✅ all 3 gates pass.

## Objective (met)
Reminders were inert — nothing fired. #29 = the notify engine: due → Discord, re-notify cadence, cap, repeat-roll, overdue. "The alarm actually fires."

## What shipped
| File | Change |
|---|---|
| `modules/reminders/store.py` | +`last_notified` (ISO|None) column (additive) + an ALTER-TABLE migration for an existing table; the count-tuple updated. |
| `modules/reminders/service.py` | the notify engine: `_notify_scan` (first-fire/re-notify/cap), `_roll_due_at` (SEMANTIC 1), `_notify`/`_discord_webhook` (fail-soft, .env discord= mirror of notify.py), NOTIFY_ROUTINE_ID. |
| `modules/reminders/router.py` | `_notify_work` + `_NOTIFY_ROUTINE` (interval 1-min, run_scheduled-wrapped) + MODULE.routines wired. |
| `modules/reminders/reader.py` | derived `overdue` (SEMANTIC 2). |
| `modules/reminders/schema.py` | +`last_notified` + `overdue` on the Reminder view. |
| `modules/automation/service.py` | the reminders-notify routine catalog entry. |
| tests | test_reminders_notify.py (new, 14 tests, mockable clock) + reconciled automation count-tests. |

## The engine (both locked semantics — team-lead-confirmed)
- **first fire:** due + notified_count==0 → Discord, count=1, last_notified=now.
- **re-notify:** count≥1 + re_notify_every set + count<(max_times or 3) + (now−last_notified)≥re_notify_every → fire, count++.
- **cap:** count≥(max_times or 3) → stop Discord (overdue/RED in-app takes over).
- **double-fire avoidance:** last_notified + count gating → the 1-min scan is idempotent.
- **SEMANTIC 1 (roll-on-fire + tick-ends-series):** `_roll_due_at` rolls a repeat (daily/weekly) due_at forward PAST now (skips missed periods → no fire-storm — backend's sound refinement) + resets count; `once` never rolls; TICK (done_at) ENDS the series (done_at filters it from the scan).
- **SEMANTIC 2 (overdue = un-done AND past-due):** `_is_overdue` = done_at is None AND due_at < now — INDEPENDENT of notified_count. The cap only gates Discord, not the overdue state.
- **Discord:** in-app `_notify` reads `.env discord=` (mirror notify.py), fail-SOFT per reminder (one fail → log + continue; routine still records).

## Verification (Rule #0 — architect + team-lead, mockable clock)
- **architect 4-step:** read the engine — first-fire/re-notify/cap correct; `_roll_due_at` skips-missed-periods (no fire-storm); `_is_overdue` not-cap-gated; fail-soft `_notify`; routine 1-min interval registered. reminders+automation suites → **80 passed, 0 failed**. Confirmed reminders/store.py last_notified is IN #29 (the #20 commit had excluded it — now correctly here).
- **team-lead container + mockable clock:** SEMANTIC 2 live (freshly-past-due at count=0 → overdue=True; future→False; ticked→False+done); the 14 timing tests pass (fire-once/no-double-fire, re-notify-on-cadence, cap-stops-discord-at-3, tick-a-daily-ends-series, roll-on-fire/once-never-rolls, webhook-fail-no-crash, not-yet-due, routine-records-run); cleaned up.
- **suite:** 1773→1787 (+14), mypy clean.

## 3 Gates — ALL PASS
- **Gate 1 (API):** the routine + the reader's overdue; envelope intact. ✅
- **Gate 2 (Function):** 14 distinguishing tests incl. tick-daily-ends-series (S1) + overdue-not-cap-gated (S2) + double-fire-avoidance + webhook-fail-no-crash; mockable clock; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; full-function spot-check; architect + team-lead container; commit format; #20 wiki files NOT re-staged (already in 1bed37b). ✅

## Assumptions (user-review) — LOCKED
- **repeat → roll-on-fire + tick-ends-series** (team-lead-confirmed): a daily/weekly fires each period (due_at rolls forward on fire, past now, resets count) UNTIL ticked; tick ENDS the series; `once` never rolls. **How to change:** `_roll_due_at` + the done_at scan filter.
- **overdue = un-done AND past-due** (team-lead override of cap-gated): overdue the moment past-due + un-done, independent of notify count; the cap only stops Discord. **How to change:** `_is_overdue`.
- notify cadence = 1-min interval; re_notify_every in MINUTES; default cap = max_times or 3; Discord = one-way, fail-soft, .env discord=.

## Notes
- LANE A; separate commit (the #20 wiki files were committed in 1bed37b — not re-staged here). reminders/store.py last_notified was correctly held out of #20 + lands here.
- GAP-4 core: reminders FIRE now. Pipeline: #30 surfaces them in daily_brief ("what's on my plate") + #31 the FE tick UI.
