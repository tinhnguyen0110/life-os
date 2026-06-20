# end_sprint_REMINDERS-1 — reminders storage module + UTC-normalize fix (Cairn #27, +1A)

> Result. GAP-4 storage GATE (unblocks #28-31). Includes the REMINDERS-1A reactive fix (Gate-2 bug caught in architect review). Commit `<hash>` `feat(sprint-REMINDERS-1)`. Status: ✅ all 3 gates pass.

## Objective (met)
GAP-4 (dogfood-R4): no reminders/agenda. Built `modules/reminders/` (registry-discovered) — single-user alarm model: title + due_at + repeat/re-notify policy fields + done-tick. CRUD + idempotent tick + UTC-normalized due/done filters. The storage GATE for #28(MCP)/#29(notify)/#30(brief)/#31(FE).

## What shipped
| File | Change |
|---|---|
| `modules/reminders/{router,service,reader,schema,store}.py + __init__` | the module: `MODULE = BaseModule(name="reminders", router=router)` (no routines — notify is #29); registry auto-discovered. |
| `store.py` | module-local SQLite `reminders` table (init-on-first-use, not in core db.py); CRUD + idempotent tick + the due/done filter query. |
| `schema.py` | the FROZEN `Reminder` contract (#28/#31 mirror) + the ReminderInput validators (title-not-blank, due_at-parseable + **UTC-normalize, 1A**). |
| `tests/test_reminders.py` | 29 tests (CRUD + tick-idempotent + due/done filters + defensive + the 4 1A distinguishing). |

## The frozen schema (#28/#31 mirror)
`id, title(1-200,stripped), note(≤2000|None), due_at(ISO, UTC-normalized), repeat(once|daily|weekly), re_notify_every(≥1|None, #29), max_times(≥1|None, #29), notified_count(≥0, #29), done_at(ISO|None), created(ISO UTC)`.

## Logic
- **tick:** sets done_at=now (UTC) on the FIRST tick; IDEMPOTENT (re-tick = no-op, done_at unchanged, returns the row, not an error).
- **filters (UTC, `<=` inclusive):** today = due_at ≤ end-of-today-UTC AND not done; week = ≤ now+7d AND not done; undone = not done; all/unknown = everything (lenient), newest-due first. The today/week filter respects BOTH due-window AND done-status (the distinguishing).

## REMINDERS-1A (the Gate-2 fix — caught in architect 4-step review)
**Bug:** `list_reminders` does a LEXICOGRAPHIC string compare assuming "all stored UTC", but the validator stored due_at RAW (not normalized). A non-UTC-offset due_at mis-filtered — repro: `due_at="2026-06-21T02:00:00+07:00"` (= 2026-06-20T19:00Z = today-in-UTC) → lexicographic compare → wrongly EXCLUDED from filter=today. Missed by backend's 25 tests AND team-lead's first live-verify (both used UTC/Z fixtures — the verify-with-the-distinguishing-case trap). Caught by architect 4-step (read the validator-vs-store seam) + team-lead's independent repro.
**Fix:** `schema.py _due_parseable` normalizes due_at → UTC: offset-aware (Z/±HH:MM) → `astimezone(UTC)`; **naive (no tz) → `replace(tzinfo=UTC)` (assume UTC — attach, do NOT astimezone a naive dt → that would use the ambiguous system-local tz)**. Now all stored due_at are UTC → the store's lexicographic compare is correct (its "all-UTC" assumption is now TRUE). + 4 distinguishing tests.

## Verification (Rule #0 — 3-way + container)
- **architect:** read the full store (table/CRUD/tick/filter) + schema (validators) — found the Gate-2 UTC bug, repro'd it; confirmed the 1A fix on disk (offset→astimezone, naive→replace-tzinfo); ran the FULL suite myself → **1741 passed, 6 skipped, 0 failed** (the true post-1A count; tester's 1737 was the pre-1A figure). reminders subset 25→29 (+4 1A tests).
- **team-lead independent container Rule#0:** /health discovers reminders; CRUD round-trip (ids 4/5/6); tick→done_at + re-tick idempotent; the today-filter distinguishing (includes today-undone, excludes today-DONE + next-week — respects BOTH due AND done); cleanup clean. Re-verified 1A: the +07:00 repro NOW PASSES (stored normalized "2026-06-20T19:00:00+00:00", IN filter=today); naive assumed-UTC.
- **tester:** the 6-case API round-trip + the 4 1A distinguishing (29/29), all on the container.

## 3 Gates — ALL PASS
- **Gate 1 (API):** REST POST/GET/GET{id}/PUT-tick/DELETE, envelope {success,data,warning?}, 400/404/422; module auto-discovered (NOT a core/main.py edit). ✅
- **Gate 2 (Function):** 29 tests incl. tick-idempotent + the due/done distinguishing + the 1A non-UTC distinguishing; 0 errors; mypy clean; the validator-vs-store UTC seam fixed. ✅
- **Gate 3 (Sprint):** end-doc w/ the TRUE 1741 count; full-function spot-check; architect + team-lead container + tester; commit format. ✅

## Assumptions (user-review)
- **reminders = SQLite (module-local store), single-user alarm model.** **How to change:** the schema in modules/reminders/.
- **naive due_at → assumed UTC** (1A; single-user simplest honest rule — attach tzinfo=UTC, not local-convert). **How to change:** the _due_parseable validator.
- **due/done filter boundaries:** today = ≤ EOD-UTC & undone; week = ≤ +7d & undone; undone = done null; `<=` inclusive, UTC. **How to change:** list_reminders.
- **tick idempotent** (re-tick = no-op); repeat-roll-forward deferred to #29.
- **DELETE returns 200 + {success, data:{deleted}}** (not bare 204 — keeps the app-wide {success,data} envelope; backend's decide-and-log, team-lead-accepted).
- **unknown filter → lenient `all`**.

## Notes
- The storage GATE — schema FROZEN + announced → #28(MCP)/#29(notify)/#30(brief)/#31(FE) now mirror + fan out.
- The 1A bug → memory `reminders-tz-filter-bug-2026-06-21` (generalize: normalize ISO timestamps to UTC at the WRITE boundary if you string-compare them).
- Committed as ONE (#27+1A) — no buggy-then-amend.
