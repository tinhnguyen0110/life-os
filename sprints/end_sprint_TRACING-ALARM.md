# End Sprint TRACING-ALARM — custom-weekday reminders + seed 3 daily check-ins

Board task: #172. User CHỐT: alarm-style custom-weekday reminders + seed 3 daily check-in activities using the new feature.

## What shipped
A real weekday-mask in the reminders engine (Mon0..Sun6, VN-tz) + a "custom" repeat mode with per-day selection; fixed the long-standing "weekdays fires daily" lie as a bonus; seeded 3 VN-named daily check-in activities. BE schema/store/scheduler + FE custom-day UI + seed.

### Changes implemented (4-step verified on disk + live curl + independent test re-run)
- **BE T1 — weekday mask (the core)** — `reminders/service.py`: `_parse_days` (CSV→set, fail-soft, NULL=no-mask), `_vn_weekday` (VN-tz weekday, the reminders-tz lesson), and the mask check at the TOP of `_should_fire` (days set AND VN-weekday ∉ mask → skip; additive, cap/re-notify/escalate untouched, pre-migration tolerant). `reminders/store.py`: nullable `days` column (idempotent ALTER) + carried through create/update. `tracing/schema.py`: RemindRepeat +"custom" + remindDays list[int]|None (validated 0-6, non-empty for custom). `tracing/service.py`: `_sync_reminder` maps repeat→days CSV (daily→None, weekdays→"0,1,2,3,4" FIXING the lie, custom→remindDays) + reads remindDays back in ActivityView (the #117 thread-through). `tracing/store.py`: remind_days column.
- **BE T2 — seed** — idempotent helper seeds 3 activities (skip if id exists): Check-in sáng 07:00 custom [0,1,2,3,4], Check-in trưa 12:00 custom [0,1,2,3,4], Báo cáo tối 21:00 daily. VN names, remind ON in_app, goal=1. Run live → total 10 activities, 7 old untouched.
- **FE T3 — custom-day UI** — RemindControls: repeat select +"Tùy chọn (chọn thứ)"; when custom, 7 day-toggles (T2…CN → ints 0..6, Mon0..Sun6); types +"custom"/remindDays; chip renders the days compactly ("T2-T6" contiguous-collapse); scoped `.trk-day-*` CSS (no global token). Old daily/weekdays unchanged.

### Day convention (the off-by-one risk — locked + tested)
Python `date.weekday()` Mon0..Sun6 end-to-end (schema · store · scheduler · FE). The day-mask test asserts the **distinguishing case**: a Mon-Fri mask does NOT fire Sat(5)/Sun(6), DOES fire Mon(0); a custom [1,3] fires Tue/Thu only; no-mask fires every day; AND the **VN-tz-not-UTC** case (an instant Monday-in-VN/Sunday-in-UTC fires the Mon-Fri mask — masking on the UTC day would be wrong).

### Verification (pass/fail)
- Live curl GET /tracing (Rule#0): 10 activities; 3 new correct (Check-in sáng 07:00 custom [0,1,2,3,4], Check-in trưa 12:00 custom [0,1,2,3,4], Báo cáo tối 21:00 daily, VN names, remindDays round-trips); 7 old untouched. ✅
- BE pytest (architect re-ran independently): 18 pass incl. the day-mask distinguishing-case + VN-tz case + seed idempotency. Backend reported 285 pytest +12, mypy clean. ✅
- FE tsc exit 0; vitest tracing 71/71 (full 1123 per FE report); 0 errors. ✅
- team-lead Chrome-gate FULL PASS: 3 seed activities on rail (VN names) · chips ("🔔 07:00 · T2-T6 · In-app", "🔔 21:00 · hằng ngày") · RemindControls custom + 7 toggles Mon0..Sun6 (DOM-verified no off-by-one) · old activities intact · console clean. ✅

### 3 Quality Gates
- **Gate 1 (API)**: ✅ schema validation (remindDays 0-6, custom-needs-days 422); additive `days` column; no manual core edit; response envelope intact.
- **Gate 2 (Function)**: ✅ unit tests assert observable behavior incl. the distinguishing-case + VN-tz; mypy clean; tsc clean; 0 errors; mask is additive + fail-soft + pre-migration tolerant; old reminders (days=NULL) fire every day unchanged.
- **Gate 3 (Sprint)**: ✅ this report w/ verified counts; architect read the day-mask + weekdays-fix diffs in full, curl-verified the live data, re-ran the BE tests; team-lead Chrome-gate pass; one sprint commit.

## Risks / potential errors identified
- The weekday mask computes in VN tz (not UTC) — critical for near-midnight reminders. Tested explicitly (test_mask_vn_weekday_not_utc). No risk.
- A masked-skip does NOT roll due_at (the daily roll only happens on a real fire) → due_at stays today, the scan re-checks each tick (harmless, still skipped) and the day passes naturally. Verified the next allowed day fires.
- Data mutation (3 seeds) on the runtime store is gitignored — the seed helper + tests are committed, so a fresh DB reproduces it.

## Assumptions (user-review)
- **Day convention = Mon0..Sun6 (Python weekday)** — FE shows T2=0…CN=6. *how to change*: it's the locked convention; changing it means editing every layer + tests.
- **"weekdays" now genuinely fires Mon-Fri (was a lie that fired daily)** — *why*: the engine never had a day-mask; #172 adds one and corrects weekdays. **Impact: ZERO existing activities used "weekdays"** (verified via curl — all 7 old were reminder-off), so no current user behavior changes; it's a pure forward fix. *how to change*: n/a (it's a bug fix).
- **Seed 3: check-ins T2-T6 (skip weekend), báo cáo daily** — *why*: check-ins are work-rhythm (weekday), a daily report is every-day; sensible defaults — *how to change*: edit each on /tracing (repeat + days + time fully user-editable), or re-run the seed helper after deleting.

## Commit
`feat(sprint-tracing-alarm): custom-weekday reminder mask (Mon0..Sun6, VN-tz) + weekdays-lie fix + seed 3 daily check-ins`
Explicit-paths only (5 BE code + 2 BE test + 3 FE + 2 sprint docs; NOT template/Life Command/* or docs or projects-tests or the gitignored runtime DB).
