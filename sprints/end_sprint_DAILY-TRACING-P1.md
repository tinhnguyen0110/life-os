# end_sprint_DAILY-TRACING-P1 — BE store + service + API + derivations (Cairn #65 Phase 1)

> Result. Net-new `modules/tracing/` (G-HABIT) — the BE foundation: raw sessions stored, all metrics DERIVED server-side (VN-day). Commit `333054a` `fix(sprint-DAILY-TRACING-P1)`. Status: ✅ all gates pass. backend-w3 BUILT (6 module files + test); architect 4-step + committed (§3). Phase 1 of 4 (P1 BE → P2 MCP → P3 FE → P4 brief).

## What shipped (6 new module files + test, 952 lines)
| File | Change |
|---|---|
| `schema.py` (181) | Input/Entity split (ActivityInput/ActivityUpdate/LogInput + Activity/TodayStat/ActivityView/TracingScore/TracingOverview), field_validators, VN-day helpers (VN_TZ=UTC+7, vn_today/vn_now_iso/vn_day_of — naive ts assumed-VN, offset-aware converted to VN). |
| `store.py` (173) | 2 SQLite tables (tracing_activities defs + tracing_logs sessions, index(activity_id,date)) on the shared conn, init-on-first-use (mirrors reminders). CRUD + windowed log reads. |
| `service.py` (262) | ALL derivations: today (Σ val, pct=round(min(100,val/goal*100)) goal>0 else 0, done=val≥goal, latest note, dur "Hh Mm"); streak (consec goal-met VN-days, today-incomplete=at-risk-not-break, gap stops, goal<=0→0); week[7] Mon→Sun; history12w[84]; heatmap12w[84]=COUNT activities-met/day; score. |
| `reader.py` (31) | thin read surface (delegates to service — no dup). |
| `router.py` (85) | GET /tracing · POST /tracing/{id}/log · POST/PUT/DELETE /tracing/activities. errors → agent_error (404 unknown act, 409 dup, 422 val<0/blank). MODULE=BaseModule(name="tracing"). |
| `tests/test_tracing.py` (213, 12) | the divergent distinguishing set. |

## Design (LOCKED — raw-data-first, derive server-side)
- store raw sessions; DERIVE all metrics (no precomputed/cached derived state). 2 SQLite tables (defs + logs), module-owned (mirror reminders) — NOT md (structured + time-series + derive-heavy, single-user simplest).
- VN-day (UTC+7) all bucketing. streak = at-risk-not-break. heatmap = COUNT (0-N) not boolean.

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step:** read the crux derivations on disk — streak (today-met→cursor today else yesterday; walk-while-met; gap stops; goal<=0→0) ✅; heatmap (per-day COUNT of activities met, not boolean) ✅; VN-tz (vn_day_of: naive→assumed-VN, offset→astimezone-VN) ✅; scope = only modules/tracing/ + test (NO core/main.py — registry contract held).
- **backend-w3 evidence:** FULL pytest 1994/0 (baseline 1982 + 12); mypy clean; registry auto-discovered LIVE (/health 23 modules, ZERO core edit); LIVE curl — POST log val=4 then val=7 SAME DAY → today.val 11 (ACCUMULATED not 7), pct 100, done True, dur "1h 10m", heatmap[-1]=1 (count met today), score correct; honest-empty envelope (0 activities → all-0); throwaway purged (no prod pollution).
- **Divergent distinguishing (all green):** accumulate (2-same-day→SUM), streak-3-then-gap→1 (gap severs older run), today-incomplete-doesn't-break, today-met-includes-today, heatmap-COUNT (1met→1/both→2), VN-tz (23:30+07:00→same day, 23:30Z→next VN day, naive→assumed-VN), honest-empty, goal==0 no-divide, archive-keeps-logs.

## 3 Gates — ALL PASS
- **Gate 1 (API):** GET /tracing + log + activity CRUD; agent_error errors; registry auto-discovered (no core edit); honest-empty envelope. ✅
- **Gate 2 (Function):** the divergent distinguishing set (accumulate/streak-gap/heatmap-count/VN-tz/honest-empty/goal==0); mypy clean; 0 errors. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step (crux derivations on disk) + backend live POST→GET; commit format; git-status clean; tracing-only stage. ✅

## Assumptions (user-review)
- **store = 2 SQLite tables** (tracing_activities defs + tracing_logs sessions), module-owned on the shared conn (not md) — structured + time-series + derive-heavy, single-user simplest. **How to change:** the store schema.
- **streak** = consec goal-met VN-days; today-incomplete = at-risk, NOT a break (walk from yesterday if today unmet); gap stops; goal<=0→0. **How to change:** _derive_streak.
- **heatmap day-score** = COUNT of activities meeting goal (0-N, not boolean). All derived server-side (raw-data-first). **How to change:** _derive_heatmap.
- **VN-day (UTC+7)** all bucketing; naive ts assumed-VN, offset-aware converted. **DELETE = archive** (soft, logs survive); **goal==0** → pct 0, never done, never heatmaps.

## Notes
- #65 Phase 1 of 4 (the BE foundation). backend-w3 BUILTS; architect commits (§3). Next (auto-run): P2 MCP (tracing_overview + tracing_log, REST≡MCP) → P3 FE (/tracing S14, FE-verified→ship per the UI-async rule) → P4 brief-wire. Then #63 → #64. The G-HABIT module is underway — raw-data-first, all derived, honest-empty.
