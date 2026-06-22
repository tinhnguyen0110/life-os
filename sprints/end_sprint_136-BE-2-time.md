# end_sprint_136-BE-2-time — per-activity scheduled `time` field (G3-(ii) independence)

> Reactive sprint (B-tier), parent #136 TRACING-TODO-REDESIGN. The #136-FE G3 finding: an activity had no time SEPARATE from its reminder — the FE could only schedule via remindAt, which forces a reminder. G3-(ii) needs a dedicated time-of-day that is INDEPENDENT of any reminder (a time on the timeline rail with NO nudge firing). FE flagged it; this is the BE half. Commit AFTER the un-tick (146f2ed) which is the other #136-BE half.

## What shipped
A per-activity `time` field (HH:MM VN), INDEPENDENT of the reminder:
- **schema.py:** `time: str|None` on ActivityInput / ActivityUpdate / Activity / ActivityView; the `_validate_hhmm` validator extended (`@field_validator("remindAt","time")`) so a malformed time is rejected at the boundary, same as remindAt.
- **store.py:** column `sched_time TEXT` (named to avoid the SQL `time` keyword), aliased back `sched_time AS time` in `_ACT_COLS`; idempotent migration `if "sched_time" not in cols: ALTER TABLE ADD COLUMN sched_time TEXT` (NULL default = backward-compat for pre-#136 rows); `create_activity(sched_time=)` param + INSERT placeholder.
- **service.py:** the camel↔snake thread-through at ALL 4 serializer sites — `_row_to_activity` (DB→model), `_derive_activity_view` (the #117 read-back trap — explicitly commented), `create_activity` (`sched_time=inp.time`), `_FIELD_TO_COL` for PUT (`"time":"sched_time"`). `_sync_reminder` is explicitly NOT touched by time (the G3-(ii) independence at the code level).

## The independence (the crux)
Setting `time` does NOT materialize a reminder — `_sync_reminder` only fires on `remindAt && remindRepeat!="off"`. A time with no reminder = a rail position, no nudge. **Live-verified:** CREATE `{time:"08:45"}` → `time='08:45', remindAt=null, remindRepeat='off'` (a time, no reminder). The FE timeline rails by `time ?? remindAt`.

## Verify (architect 4-step + live)
- **Live round-trips (architect, on the container):** CREATE time=08:45 (no reminder) persists ✓; GET board read-back carries `time` (the #117 derived-view trap cleared) ✓; PUT time=14:30 → HTTP 200, persists ✓ (the path that 500'd at mid-build); SCOPED cleanup (#72) ✓.
- **mypy:** `--no-incremental` package-scope (cache off, the #113 lesson) → "Success: no issues found". All 3 direct `Model(...)` constructor sites (`_row_to_activity`, `_derive_activity_view`, the #124 template→`ActivityInput(goal=1)`) cleared — the [call-arg] risk from adding a defaulted pydantic field handled (the new-required-schema-field lesson).
- **pytest:** 119 passed / 6 skipped / 0 errors (incl. the dedicated `test_tracing_time_field.py`).

## Gates
- Gate 1 (API): schema validator on `time`, dedicated test, existing pass, response envelope consistent, no auth (single-user). ✓
- Gate 2 (Function): unit test asserts behavior (time-field test), edge (None=unchanged on PUT; empty clears), mypy clean, no self-confirming assert. ✓
- Gate 3 (Sprint): this doc + spot-checked full functions + tester counts ≥ baseline. ✓

## Assumptions (user-review)
- **#136 G3-(ii) `time` independent of the reminder:** an activity carries a dedicated scheduled time-of-day SEPARATE from remindAt — a time can be set with NO reminder (the timeline shows it; nothing nudges). Why: the user's G3 ask was "dedicated time + frequency + channel"; coupling time to remindAt would force a reminder on every scheduled todo. How to change: if the user wants time to ALWAYS imply a reminder, drop the field and rail by remindAt (revert to pre-#136).

## Commit
- Hash: (filled at commit) — `feat(sprint-136-be-2-time): per-activity scheduled time independent of the reminder (G3-(ii))`
- Files: backend/modules/tracing/{schema,service,store}.py + this doc.
