# end_sprint_117-REMINDCHANNEL-READBACK — GET /tracing read-back surfaces the stored remindChannel (Cairn #117)

> Result. GET /tracing read-back returned `remindChannel: in_app` ALWAYS, even when `discord` was stored (POST-echo + the linked reminder were correct — only the list read-back lied). Root cause: `_derive_activity_view` (the ActivityView projection for the overview/GET path) DROPPED `remindChannel` — it carried #75's remindAt/remindRepeat but missed #111's channel when the view was extended. 1-line fix + a teeth-proven read-back test. Commit `<hash>` `fix(sprint-117-remindchannel-readback): GET /tracing read-back surfaces stored remindChannel`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT teeth-check). Cairn #117 — be-only, CLOSES on this commit. Reactive fix off the #111 lane.

## The bug (two read paths, #111 threaded only one)
- **POST /tracing/activities echo** → `_row_to_activity` → raw `Activity` → HAS remindChannel ✓ (the surface that was correct).
- **GET /tracing (overview) read-back** → `service.overview()` → `_row_to_activity` (Activity, has it) → **`_derive_activity_view(act)` → ActivityView (DROPPED it)** ❌ → the schema default `in_app` masked the stored channel.
- Why remindAt/remindRepeat read fine but remindChannel didn't: the view carried the #75 fields, the #111 field was missed when ActivityView was extended. The store/migration/`_row_to_activity` were all correct since #111 — only the downstream VIEW projection dropped it.

## What shipped
| File | Change |
|---|---|
| `modules/tracing/service.py` (`_derive_activity_view`) | **+1 line:** `remindChannel=act.remindChannel` (mirrors the remindAt/remindRepeat carry; the ActivityView now surfaces the stored channel). No schema/store/migration change (the column + `_row_to_activity` read were already correct from #111). |
| `tests/test_tracing_reminders.py` (+32) | `test_117_overview_readback_surfaces_stored_channel` — **parametrized over all 3 channels**, EXERCISES the read-back surface (`overview()` → `views[0].remindChannel`), asserts == the stored channel (the GET-read-back path, NOT the POST-echo). + `test_117_get_activity_readback_surfaces_channel` pins the single-activity Activity path. |

## Verification (Rule#0 — architect INDEPENDENT, teeth-proven)
- **architect 4-step (read FULL):** the fix is exactly the dropped field in `_derive_activity_view` (read the function; the 2 read paths confirmed — Activity has it, ActivityView dropped it). No stray staged change (the staged service.py diff is the ONE +1 line). ✅
- **🔴 TEETH-CHECK (the requirement, INDEPENDENTLY proven):** removed the fix line, re-ran the #117 tests → `[email]` + `[discord]` **FAIL** with the exact bug signature (`- discord / + in_app` — the view-serializer drop); `[in_app]` + get_activity PASS (default coincides). Restored the fix → all 4 pass. So the test EXERCISES the broken surface and would have caught the bug — NOT a self-confirming POST-echo false-green (the POST-echo passed WHILE the bug was live, which is exactly why a POST-echo test would have been false-green). ✅
- **🔴 LIVE (the surface all 3 repros — frontend + team-lead + me — found broken):** create `{remindChannel:discord, goal:1}` → GET /tracing read-back `remindChannel = discord` (was in_app); confirmed across a forced BE restart (so it's the fix, not stale-container). Scoped-cleaned the probe by-id (#72). ✅
- **Suite:** tracing surface **74 passed / 0 failed** (incl the +32); mypy clean on tracing/service.py (the yaml-stub warnings are pre-existing in other modules, not this change). ✅

## 3 Gates
- **Gate 1 (API/agent):** GET /tracing read-back now honest (surfaces the stored channel; honest-mirror — the record no longer lies about the user's choice). ✅
- **Gate 2 (Function):** the teeth-proven read-back test (parametrized 3 channels, fails-without-fix on email+discord) + the get_activity pin + 74/0 + mypy clean. NOT self-confirming (proven by the remove-fix check). ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent teeth + live; staged EXACTLY #117 (service.py +1 + test, NO #113/projects/read_server/data/template leak); commit format. ✅

## Assumptions (user-review)
- **the GET /tracing read-back now surfaces the stored remindChannel** (the ActivityView carries it). **How to change:** the `_derive_activity_view` field list.
- n/a otherwise — this is a pure honest-mirror correction (the record was lying about the stored channel; now it tells the truth).

## Notes
- Cairn #117 — be-only reactive fix off the #111 reminder-channel lane. backend-w3 built (fix + teeth test); architect committed (§3 sole-committer). 🔴 **The cross-check that saved it:** I initially called frontend-w3-2's flag a "false alarm" after testing the POST-echo (correct) — the WRONG surface. frontend-w3-2 re-flagged with a numeric-goal repro + team-lead independently reproduced; all three converged on the GET-read-back. The honest correction → #117 stayed open → real gap fixed. Lesson recorded (`verify-the-reported-surface-not-an-adjacent-one`): a passing adjacent path (POST-echo) does NOT clear the reported path (GET read-back); when a field flows through >1 serializer (Activity vs ActivityView), grep all map sites. The teeth requirement (test the broken surface, not the false-green echo) is exactly why a POST-echo test would have masked this. Disjoint from #113 (tracing vs projects); committed #117-first per the locked ordering. No restart needed (modules/ hot-reloads). After push → team-lead live-verifies GET read-back=discord.
