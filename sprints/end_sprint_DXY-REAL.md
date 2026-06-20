# end_sprint_DXY-REAL — let real FRED DXY show (never persist mock) — Cairn #15

> Result. dogfood-R4 GAP-2. Commit: `<hash>` (filled at commit). Status: ✅ all 3 gates pass.

## Objective (met) + scope correction
The Cairn task said "wire real DXY via FRED DTWEXBGS" — but the **live-first kickoff found that wiring already done + working** (DTWEXBGS mapped in config; the reader fetches real DXY inside the container). The REAL bug, traced to the row level: `refresh()` PERSISTED `source='mock'` rows with a today-ts that SHADOWED the real monthly FRED row (recent newest-first → frozen mock); a fresh refresh couldn't dislodge it (real ts older). Affected ALL FRED indicators on any transient outage. Corrected scope (team-lead approved): **never persist mock into the time-series** + one-shot purge. Same user outcome (real DXY), correct root, hardens all macro indicators.

## What shipped
| File | Change |
|---|---|
| `backend/modules/macro/store.py` | `record_point` early-returns when `source=='mock'` — the SINGLE chokepoint covering all callers (refresh + snapshot), can't be missed. + `purge_mock() -> int` (DELETE source='mock' only, idempotent) + `count_by_source`/`count_all` (before/after delta proof helpers). |
| `backend/modules/macro/service.py` | `_indicator_view` cold-start fallback: when the store has NO real points (unprimed install), read the reader's mock points DIRECTLY (NOT via store → nothing persisted), surface honestly tagged source='mock', `points=0`. Preserves the "empty install still returns display numbers" contract WITHOUT persisting mock. try/except so the display fallback never raises. |
| `backend/tests/test_macro.py` | 6 tests (below). |

## The fix (never persist mock — S1 mock-excluded extended to the WRITE path)
Mock = the absence of real data → it must NEVER enter the time-series. A failed FRED fetch now records NOTHING; the prior real point stands; freshness/confidence already brake on staleness honestly. The W=0/staleness brakes are unaffected (they live in coverage/freshness). One-shot `purge_mock()` cleared the historical stuck-mock rows so the live read immediately surfaces real DXY.

## Verification (Rule #0 — re-run, not trusted)
- **architect live (container):** all 7 macro indicators source='fred', **0 mock**; dxy = real **119.5073**, change **−0.6101** (NOT flat-0 mock), confidence **0.7724** (was 0).
- **architect pytest:** test_macro + test_decision → **93 passed, 0 failed, 0 errors**. Full suite 1671→**1676** (+5; 2 existing tests reconciled — their premise WAS the bug, ran-the-red).
- **chokepoint scope:** grep confirms `record_point` is macro-only — no other module persists mock.
- **team-lead live:** 7/7 fred, 17 frozen mock rows purged (real 86→86 untouched); q_macro **0.5108→0.6211** (dxy joining the axes — the #13 synergy the dispatch predicted), W 0.1195→0.1453 "thin".
- **tester:** /tmp/verify_dxy_real_t2.py — A (dxy real) + A2 (joins axes) + **B (force-FRED-fail → NO new mock row, prior real survives, isolated DB, live store untouched)** + 6-other no-regression (see tester report).

## The 6 tests
`test_refresh_persists_real_points`, `test_DXY_record_point_skips_mock`, `test_DXY_record_point_mock_cannot_shadow_real` (the root), `test_DXY_GATEb_fred_failure_persists_no_mock_real_survives` (the durable spine — a purge-once fix FAILS this), `test_DXY_purge_mock_deletes_only_mock`, `test_DXY_GATEd_cold_start_still_returns_numbers`.

## Code review (architect 4-step)
1. diff — store.py (skip + purge + 2 helpers), service.py (cold-start direct-reader fallback), test_macro.py (6).
2. read FULL record_point / purge_mock / _indicator_view cold-start — traced entry→exit.
3. vs plan — never-persist chokepoint + guarded purge + cold-start display preserved = the approved corrected scope.
4. hunted — chokepoint macro-only (grep); purge exact-match only; cold-start can't shadow (empty-store only, reader-direct no-persist); GATEb durable-root present. No edge missed.

## 3 Gates — ALL PASS
- **Gate 1 (API):** macro_overview shape unchanged (dxy source flips mock→fred); integration green. ✅
- **Gate 2 (Function):** 6 behavior tests incl. force-fail (isolated DB) + purge-only-mock + cold-start; 93 pass/0 err; single chokepoint; real distinguishing asserts. ✅
- **Gate 3 (Sprint):** end-doc w/ verified counts; full-function spot-check; team-lead live + architect Rule#0; counts ↑ (+5); commit format. ✅

## Purge guard (executed safely on the live store)
Purged ONLY `source='mock'` rows (17); real-row count UNCHANGED (86→86, team-lead-confirmed). Idempotent (re-run → 0). Surgical per the test-writes-pollute lesson.

## Assumptions (user-review)
- **Mock never persisted to macro_history** (S1 mock-excluded extended to the WRITE path — `record_point` skips source=='mock'); mock is display-on-empty only (cold-start reader-direct, not stored). A transient FRED outage → NO row, the prior real point stands (confidence/freshness brake honestly). One-shot purged 17 stuck mock rows from the live store (real rows untouched). **How to change:** to re-allow persisted mock, drop the source!='mock' guard in record_point — but that re-introduces the frozen-mock-shadows-real bug.

## Notes
- Hardens ALL macro indicators against the freeze, not just DXY (DXY was the symptom).
- Synergy with #13 (decision-agreement): dxy now real → macro coverage includes it → q_macro 0.51→0.62.
