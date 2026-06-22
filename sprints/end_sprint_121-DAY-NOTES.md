# end_sprint_121-DAY-NOTES — day-note store + CRUD + note→reminder link (Cairn #121, TRACING-UX2 T1)

> Result. The /daily-tracing redesign (corrected spec — hard-code templates REJECTED) needs a day-note store: a note = text + optional remind. Added tracing_note + CRUD + a note→reminder link reusing the #75 pattern + #111 channels. Caught + fixed a RECURRING #117-class source-coercion bug (reminder persisted source='tracing-note' but read back 'manual'). Commit `<hash>` `fix(sprint-121-day-notes)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT live read-back + delete-lifecycle + mypy). Cairn #121 TRACING-UX2 T1 — be-only, CLOSES on this commit. FREEZE done → #122 (FE) dispatched. Disjoint from #122.

## What shipped (tracing + reminders + test)
| File | Change |
|---|---|
| `tracing/{store,schema,service,router}.py` | tracing_note table + CRUD (GET/POST/PUT/DELETE /tracing/notes); Note shape FROZEN {id,text,remindAt?,remindRepeat,remindChannel,created} (+ NoteInput/NoteUpdate); 422 blank-text/bad-HHMM; 404; honest-empty []. `_sync_note_reminder` (mirrors #75 `_sync_reminder`): note WITH remind → UPSERT linked reminder; PUT-clear/off → delete; delete-note → unlink first (no orphan). DROP hard-code templates (#109 CRUD stays UNUSED, flagged). |
| `reminders/service.py` | the note-link forge-guard (source="tracing-note", reuse the `activity_id` column as the linked-id — NO migration) + `delete_for_note`. |
| `reminders/schema.py` | `Reminder.source` Literal WIDENED → `manual | tracing | tracing-note` (#121). |
| 🔴 `reminders/reader.py` | `row_to_reminder` source-coercion FIXED — it coerced to a closed set {manual,tracing} → silently downgraded 'tracing-note' to 'manual' (so _note_reminders found 0). Now passes tracing-note through. |
| `tests/test_tracing_notes.py` (NEW, 18) | note+remind→linked+channel + 🔴 source READS BACK 'tracing-note' + PUT-clear→deleted + 🔴 delete→reminder-gone-no-orphan + 🔴 activity-remind regression + both-sources-coexist + honest-empty + 422/404. |

## Design (LOCKED — reuse #75 link, the activity_id column as generic linked-id, forge-guard)
- **note→reminder = the #75 `_sync_reminder` pattern** (one-way tracing→reminder, fail-soft) — `_sync_note_reminder`: remindAt + remindRepeat≠off → UPSERT (source="tracing-note", channel=note.remindChannel, due=today-VN@remindAt→UTC); else → delete. Reuse the #29 reminders engine, no new one.
- **link key = the reminders `activity_id` column as a generic "linked-entity id"** (note id stored there, scoped by source="tracing-note") — NO reminders migration (decide-and-log: lean, single-user; backend agreed, didn't add a separate note_id).
- **🔴 the #117-recurring fix:** a reminder's source flows through `row_to_reminder` which coerced to a CLOSED set — adding a new source ('tracing-note') without widening that coercion silently downgrades it on READ-BACK (persists right, reads wrong — the exact #117 two-serializer trap). Fixed the Literal + the coercion in BOTH schema + reader.
- DROP hard-code templates (#109 template CRUD UNUSED, flagged not deleted).

## Verification (Rule#0 — architect INDEPENDENT)
- **architect 4-step (read FULL):** the _sync_note_reminder (mirrors #75); the forge-guard + delete_for_note; **the #117-recurring fix in reader.py** (coercion now passes tracing-note). Staged #121-only (no FE/#122 leak). ✅
- **🔴 INDEPENDENT live read-back (the recurring-bug surface — Rule#0):** created a note WITH remind=discord → the linked reminder READS BACK source='tracing-note', channel='discord' (was the bug: read back 'manual'). The test ASSERTS the read-back (`r.source == "tracing-note"`, line 60), not just persistence — the #117 distinguishing-case discipline. ✅
- **🔴 live delete-lifecycle:** delete note → 0 orphan reminders + the note gone (scoped cleanup, #72). ✅
- **mypy --no-incremental** (cache off, #113 lesson) tracing + reminders clean; **57 passed** (tracing-notes + reminders, independent); backend FORWARD 2386/0 == REVERSE; 18 new tests (incl activity-remind regression + both-sources-coexist). ✅

## 3 Gates
- **Gate 1 (API):** /tracing/notes CRUD (422 blank/bad-HHMM, 404, honest-empty); note→reminder link agent-readable; source reads back correctly. ✅
- **Gate 2 (Function):** the 18 tests (the distinguishing cases incl source-read-back + delete-no-orphan + activity-remind-regression) + live read-back + delete-lifecycle + mypy clean + FWD==REVERSE. NOT self-confirming. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent live; staged EXACTLY #121 (tracing + reminders + test, NO FE #122 / data leak); commit format. ✅

## Assumptions (user-review)
- **note→reminder link key = reuse the reminders `activity_id` column** (note id, source="tracing-note") — NO migration. **How to change:** add a `note_id` column (rejected as over-engineering for single-user). 
- **note WITH remind emits a linked reminder; delete note → reminder gone** (mirrors activity-remind). **How to change:** _sync_note_reminder / delete_for_note.
- **hard-code templates DROPPED** (#109 CRUD unused, flagged). **How to change:** wire it back (the user rejected it).

## Notes
- Cairn #121 TRACING-UX2 T1 — user-CHỐT (the rewritten /daily-tracing redesign: text+tick+remind + text+remind notes, NO hard-code). backend-w3 built; architect committed (§3 sole-committer). 🔴 **The #117 recurrence is the standout:** adding a new `source` value to reminders re-triggered the #117 read-back-coercion bug (a field flowing through a serializer that coerces to a CLOSED set → a new value silently downgrades on read-back, persists-right-reads-wrong). Caught by the 4-step's #117-focus + the test asserting the READ-BACK (not persistence) + my live read-back verify. Lesson reinforced: when you ADD a value to a closed-set field, grep every coercion/serializer that maps that field + assert the new value READS BACK (the `verify-the-reported-surface` / closed-set-coercion family). **FREEZE done → #122 (FE 2-col) dispatched to frontend-w3-2** (parallel, disjoint FE vs BE). REST-only, no restart, no count-assert.
