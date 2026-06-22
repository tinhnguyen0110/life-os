# end_sprint_125-NOTE-ONESHOT — note one-shot future-date remind (Cairn #125, TRACING-UX2 T4)

> Result. Note remind gains a ONE-SHOT future-date kind: a note can remind on a specific FUTURE date+time, ONCE (repeat="once"), distinct from the #121 recurring kind; activity remind stays daily-recurring (unchanged). Past-date → 422. Commit `<hash>` `fix(sprint-125-note-oneshot)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT live: future→repeat=once+UTC-due, past→422, reads-back-once, delete→no-orphan). Cairn #125 TRACING-UX2 T4 — be-only, CLOSES on this commit → completes the TRACING-UX2 BE arc (#121/#124/#125). Disjoint from #126 (FE, parallel).

## What shipped
| File | Change |
|---|---|
| `tracing/schema.py` | Note +`remindDate: str \| None` (future YYYY-MM-DD; None = no one-shot) — FROZEN. The full note shape is now {id,text,remindAt?,remindDate?,remindRepeat,remindChannel,created}. |
| `tracing/store.py` | remind_date column + idempotent ALTER-guard migration. |
| `tracing/service.py` (`_sync_note_reminder`) | TWO kinds: `remindDate + remindAt` set → a `repeat="once"` reminder at remindDate@remindAt (VN→UTC); else `remindRepeat≠off` → the #121 today@remindAt recurring. Clear (remindRepeat='off' / nulls remind_date) → sync deletes (no orphan). + `note_remind_in_past` helper. |
| `tracing/router.py` | 🔴 past-date validation (note_remind_in_past on the MERGED values) → 422 (note_remind_in_past) at the agent-facing boundary. |
| `tests/test_tracing_note_oneshot.py` (NEW, 11) | oneshot→once+future-due / 🔴 reads-back-once / past→422 / update-to-past→422 / #121-recurring-still-works / clear→deleted+nulled / delete→no-orphan / both-kinds-coexist / bad-date→422. |

## Design (LOCKED — two note-remind kinds, closed-set repeat reads RAW)
- **two note-remind KINDS:** (1) ONE-SHOT — remindDate(future)+remindAt → `repeat="once"` at that future instant (fires once); (2) RECURRING (#121) — remindRepeat≠off, no remindDate → today@remindAt daily/weekdays. Activity remind UNCHANGED (always daily — does NOT get the one-shot).
- **🔴 past-date → 422** at the router (validates the merged remindDate+remindAt vs VN-now) — honest agent-error, no row stored.
- **🔴 the closed-set-coercion check (the #121 lesson applied):** repeat is a closed set {once,daily,weekly}; the reminders reader reads `repeat` RAW (NO coercion — unlike the `source` field which #121 had to fix). So 'once' reads back correctly. VERIFIED on the read-back surface (the pinned test reads the full list → repeat=='once') — the right distinguishing surface (not just persistence).
- clear/delete lifecycle (#121) holds: clear remind → reminder deleted + remind_date nulled; delete note → reminder gone (no orphan).

## Verification (Rule#0 — architect INDEPENDENT, live on the real surface)
- **architect 4-step (read FULL):** `_sync_note_reminder` two-branch (remindDate→once vs #121 recurring); `note_remind_in_past` + the router 422; remind_date column + migration. Staged #125 BE-only (the 3 #126 FE files left dirty — disjoint parallel). ✅
- **🔴 INDEPENDENT LIVE (the distinguishing cases):** future note (remindDate=2026-07-15 @ 09:00 VN) → linked reminder **repeat reads back "once"**, source="tracing-note", channel="discord", due_at=2026-07-15T02:00Z (09:00 VN→UTC ✓); **PAST date → 422** (no row); **delete note → 0 orphan reminders** (scoped #72 cleanup). ✅
- **the read-back surface verified (the #121 closed-set lesson):** repeat reads back "once" — not coerced/downgraded. ✅
- **mypy --no-incremental clean; 29 passed** (oneshot + notes, independent); backend FORWARD 2411/0 == REVERSE; activity-remind-still-daily + both-kinds-coexist tested. ✅

## 3 Gates
- **Gate 1 (API):** /tracing/notes +remindDate; past→422+hint (agent-readable); one-shot repeat=once; reads-back honest. ✅
- **Gate 2 (Function):** the 11 tests (oneshot→once / reads-back-once / past→422 / clear→deleted / delete→no-orphan / activity-daily / both-coexist) + live + mypy. NOT self-confirming (the read-back + the live tick the right surfaces). ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent live; staged EXACTLY #125 BE (NO #126 FE / data leak); commit format; migration idempotent on a migrated db. ✅

## Assumptions (user-review)
- **note remind = two kinds:** one-shot (remindDate+remindAt → once) OR recurring (remindRepeat≠off → daily/weekdays). **How to change:** the _sync_note_reminder branch.
- **activity remind stays daily** (no one-shot for activities). **How to change:** mirror the remindDate path onto the activity sync (NOT done — user wanted it note-only).
- **past remind → 422.** **How to change:** the note_remind_in_past router check.

## Notes
- Cairn #125 TRACING-UX2 T4 — user-CHỐT (the 2-kinds-of-remind ask). backend-w3 built; architect committed (§3 sole-committer). 🔴 **The closed-set-coercion lesson (#121) APPLIED PROACTIVELY:** #125 adds a new `repeat` value path ('once') to a closed-set field — the exact shape that bit #121 (source coerced to a closed set → downgraded on read-back). I flagged it in the dispatch; backend verified the reminders reader reads `repeat` RAW (no coercion, unlike source) → 'once' reads back; the pinned test + my live verify confirmed it on the read-back surface. The lesson prevented the recurrence. **Parallel-lane staging (9th clean):** committed BE-only while #126 FE in flight (3 files left dirty, leak-check clean). **Completes the TRACING-UX2 BE arc** (#121 day-notes + #124 template-add + #125 one-shot). **#129-BE unblocks** (serial BE, after this commit). #126-FE carries on parallel. REST-only, no restart.
