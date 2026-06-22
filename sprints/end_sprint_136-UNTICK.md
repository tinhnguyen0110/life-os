# end_sprint_136-UNTICK — un-tick endpoint (the tick-toggle un-complete) (Cairn #136 BE half)

> Result. #136's tick-toggle needs an un-complete path (the user's "tick rồi không hoàn được") — there was none (POST /log accumulates; val ge=0). Added `DELETE /tracing/{id}/sessions?date=<today-VN>` → clears that activity's today logs → today.done=false (SCOPED #72). Commit `<hash>` `feat(sprint-136-untick)`. Status: ✅ verified (backend-w3; architect 4-step + INDEPENDENT live toggle round-trip). Cairn #136 BE half — be-only, commits independently. DISJOINT from #136-FE (FE owns the tick-toggle wiring + the 5 asks). The FE half closes #136.

## What shipped
| File | Change |
|---|---|
| `tracing/store.py` (`delete_sessions_for_day`) | `DELETE FROM tracing_logs WHERE activity_id=? AND date=?` — SCOPED to one activity + one day (#72). Returns the deleted count. |
| `tracing/router.py` | `DELETE /tracing/{activity_id}/sessions?date=<YYYY-MM-DD>` (default today-VN) → returns `{activityId, date, deletedSessions, view}` (the freshly-derived view so the FE renders un-done immediately). 404 unknown. |
| `tracing/service.py` | wires the clear + re-derives the view. |
| `tests/test_tracing_untick.py` (NEW, 8) | toggle round-trip (log→done, clear→un-done) + SCOPED (clear A-today doesn't touch A-yesterday nor B-today) + 404 + honest deletedSessions:0. |

## Design (LOCKED — un-complete = delete today's sessions, SCOPED, honest)
- the tick-toggle (FE-driven): tick a NOT-done row → POST /log {val:1} (existing); tick a DONE row → DELETE /tracing/{id}/sessions?date=today (this) → done=val≥goal with val=0 → false. Clean (no negative-val hack).
- **SCOPED (#72):** the delete is keyed on (activity_id, date) ONLY — never blanket, never other activities/days. Proven (the SCOPED test + my live).
- the response carries the derived `view` (the FE renders un-done without a re-fetch).

## Verification (Rule#0 — architect INDEPENDENT, live)
- **architect 4-step (read FULL):** `delete_sessions_for_day` SCOPED (activity_id AND date); the DELETE endpoint + derived-view response + 404. Staged #136-BE tracing-only (the #136-FE files left dirty — disjoint, frontend's lane; clean whole-stage, no hunk-split — BE *.py vs FE). ✅
- **🔴 INDEPENDENT LIVE toggle round-trip (the distinguishing case):** seed goal=1 todo → POST log val=1 → done=True, val=1.0; **DELETE today's sessions → deletedSessions=1, view.done=False; GET /tracing → done=False, val=0.0** (the un-tick — the user's complaint fixed). scoped cleanup. ✅
- **mypy --no-incremental clean; 8 passed** (independent); backend FORWARD 2466/0 == REVERSE; SCOPED proven (A-today clear leaves A-yesterday + B-today). ✅

## 3 Gates
- **Gate 1 (API):** DELETE /tracing/{id}/sessions (agent-readable {activityId,date,deletedSessions,view}); 404; honest 0; SCOPED. ✅
- **Gate 2 (Function):** the 8 tests (toggle round-trip + SCOPED + 404 + honest-empty) + live + mypy. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent live; staged EXACTLY #136-BE tracing (NO #136-FE/wiki/template leak); commit format. ✅

## Assumptions (user-review)
- **un-complete a todo = DELETE today's sessions for it** (val→0 → done=false). **Why:** "tick rồi không hoàn được" = can't un-check; tick should toggle. **How to change:** the clear endpoint / the FE tick-toggle's un-complete branch.

## Notes
- Cairn #136 BE half — the un-tick endpoint (frontend flagged it had NO BE path: POST /log accumulates, val=-1→422; verified). backend-w3 built (claimed-at-start — no board-claim gap); architect committed (§3 sole-committer). The decided tick-toggle (decide-and-log, user async-notified) needed this small SCOPED clear-log endpoint. **Parallel-lane:** #136-BE (tracing BE) ∥ #136-FE (app/tracing + lib/*) — disjoint (BE *.py vs FE), so #136-BE is a clean whole-stage (no hunk-split, unlike the W3A/#136-FE shared-lib tangle). team-lead Chrome-verifies the FULL toggle in the UI when #136-FE lands (FE taps a DONE row → this DELETE → un-done). The FE half (the 5 asks + the tick-toggle wiring) closes #136. REST-only, no restart.
