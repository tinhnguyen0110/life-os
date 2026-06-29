# Sprint TRACING-ALARM — custom-weekday reminders + seed 3 daily activities

Board task: #172. User CHỐT 2 things together:
1. Custom-weekday reminder mode (like an alarm: pick which days T2-CN, e.g. skip weekend).
2. Seed 3 daily activities using the new feature: 7h check-in, 12h check-in, 21h report.

## Kickoff — 2026-06-29

### Architecture findings (multi-layer sprint)
- **The reminders engine has NO weekday-mask today.** `RemindRepeat = Literal["daily","weekdays","off"]` (tracing schema L47); `_REPEAT_MAP = {"daily":"daily","weekdays":"daily"}` (tracing service L250) → **"weekdays" currently FIRES DAILY** — a documented honest lie (service L247-249). The reminders engine `Repeat = ["once","daily","weekly"]` (reminders schema L16) has no day-of-week concept.
- **Fire decision lives in `_should_fire(row, now_iso, now)`** (reminders service L212) — called per-reminder in `notify_scan` (L264, the 1-min routine). The daily roll `_roll_due_at` (L194) advances due_at +1 day past now on each fire.
- **Reminder store table** (store.py L26) has `repeat` + needs an additive `days` column (idempotent ALTER pattern already established L69-78).
- **tracing→reminder sync** `_sync_reminder` (service L253) one-way upserts the linked reminder via `reminders.upsert_for_activity`.
- **FE** RemindControls (page.tsx L77) has a daily/weekdays `<select>`; types `RemindRepeat = "daily"|"weekdays"|"off"` (types/tracing.ts L50).
- **Seed path** = POST /tracing/activities (idempotent by id, like #171's backfill).

### 🔒 DAY CONVENTION (LOCKED — the off-by-one risk)
**Python `date.weekday()`: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6 — end-to-end (BE schema · scheduler · FE).** Matches the existing `vn_today().weekday()` ("Mon = weekday 0", service L102-104). FE labels: T2=0, T3=1, T4=2, T5=3, T6=4, T7=5, CN=6. NO CN=0/7 ambiguity. Every layer stores/compares the same int set. Tests assert the mapping explicitly (a T2-T6 mask = [0,1,2,3,4] must NOT fire on Sat(5)/Sun(6)).

### Decisions (architect)
- **(a) Schema:** add `"custom"` to `RemindRepeat` (additive — daily/weekdays/off unchanged). Add `remindDays: list[int] | None` to ActivityInput/Update/ActivityView (Mon0..Sun6; None unless repeat="custom"). Validate: ints 0-6, deduped, non-empty when repeat="custom" (else 422). The reminders engine gets a nullable `days` column (CSV of ints) + a `Repeat` value — keep engine `repeat="daily"` for both weekdays+custom, the DAY-MASK does the skipping (engine fires daily, mask gates the day).
- **(b) Scheduler:** add a day-mask check at the TOP of `_should_fire`: if `row["days"]` is set AND `vn_now().weekday() ∉ days` → return False (skip today; the daily roll already moved due_at to tomorrow so it re-checks next day). Additive — cap/re-notify/escalate logic untouched. **Also FIX the old "weekdays" lie**: map weekdays → days=[0,1,2,3,4] so it now genuinely skips Sat/Sun (an honest improvement, logged). VN weekday = compute from the VN-tz now (consistent with vn_today).
- **(c) Seed 3 activities** via idempotent POST /tracing/activities (skip if id exists, like #171):
  - `checkin-sang` "Check-in sáng" 07:00, repeat=custom days=[0,1,2,3,4] (T2-T6, skip weekend)
  - `checkin-trua` "Check-in trưa" 12:00, repeat=custom days=[0,1,2,3,4]
  - `report-toi` "Report tối" 21:00, repeat=daily (every day — a daily report)
  - All with remind on (channel default in_app). Logged to Assumptions (user can change days/channel).

### BE/FE split
- **BE (main):** RemindRepeat+"custom" & remindDays in tracing schema; reminders store `days` column (idempotent ALTER) + create/update/upsert_for_activity carry it; `_should_fire` day-mask check + weekdays→[0-4] fix; `_sync_reminder` passes days; a seed helper (idempotent) run on live store. Tests: day-mask skip (T2-T6 not fire Sat/Sun), weekdays-now-honest, custom round-trip, seed idempotent, old daily/weekdays/off not broken.
- **FE:** RemindControls — add a "Tùy chọn (chọn thứ)" segment option; when custom, show 7 day toggles (T2…CN → 0..6); send remindRepeat="custom" + remindDays. types add "custom" + remindDays. Render a custom reminder's days on the chip ("🔔 07:00 · T2-T6"). Old daily/weekdays still work.

### Final task list
- T1 (BE): schema + store `days` column + service day-mask in `_should_fire` + weekdays-fix + `_sync_reminder` + tests.
- T2 (BE): seed 3 activities (idempotent helper, run live) — depends on T1's custom support landing.
- T3 (FE): RemindControls custom-day UI + types + chip render + tests.
- T1 ∥ T3 (BE service/schema vs FE — disjoint files); T2 after T1 (needs custom).

### Dispatch plan
- backend ← T1 (gating: the custom support) → then T2 (seed) after T1 lands.
- frontend ← T3 (parallel with T1, disjoint files; the wire-contract = RemindRepeat+custom + remindDays list[int] Mon0..Sun6).
- tester: scheduler day-mask test (the off-by-one guard) + FE custom UI + seed verify.
- team-lead Chrome-gate before push.

## Assumptions (user-review) — filled in end_sprint
