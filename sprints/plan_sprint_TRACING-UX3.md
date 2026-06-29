# Sprint TRACING-UX3 — Daily Tracing 4 UX improvements

Board task: #170. User CHỐT 2026-06-29 (/tracing).

4 requirements:
1. Add việc BẮT BUỘC giờ (currently optional, default 08:00).
2. Nhắc nhở optional, default = giờ-việc (currently disjoint EMPTY_REMIND.time="07:00").
3. Cột trái = timeline-rail thật (every activity now has a time).
4. Redesign streak + lịch sử 12 tuần (currently a small collapsed `<details>`).

## Kickoff — 2026-06-29

### Decisions (architect)
- **(a) Required time = FE-validate only, NO BE change.** BE `ActivityInput.time: str | None` (schema L90) already validates HH:MM format. Making it BE-required would break (1) old timeless activities, (2) the template-set add path, (3) the MCP/agent channel posting timeless. It's a UX requirement, not a data-integrity one. FE blocks "Thêm" when time empty + surfaces clearly. BE stays permissive (honest: old data + agent can still post timeless). → **BE untouched.**
- **(b) Old timeless activities = KEEP fallback bucket, NO backfill.** Old activities have `time=null`. Backfilling a fake time = dishonest. The existing `timelineOrder()` already splits `timed` (railTime set, ascending) vs `anytime` (timeless). Keep that split: timeline rail shows timed rows on the time-axis; remaining timeless (old data ONLY — new adds now require time) render in a small "Chưa đặt giờ / Cả ngày" bucket at the bottom with the clickable "đặt giờ" still working. No migration, no data touch. → guardrail "việc cũ không vỡ" satisfied.
- **(c) Remind-default-sync = in the add-form state.** When the user toggles remind ON in the add row, default `remind.time = todoTime` (the activity's time), NOT the disjoint "07:00". Implement: when toggling remind on (RemindControls or the todo add-row), seed `time` from the current `todoTime`. User can still change/disable. EMPTY_REMIND.time stays as a fallback for the notes add-row (which has no activity-time) OR also syncs to a sensible default — for the TODO row specifically, sync to todoTime. Keep optional (off → activity still adds).
- **(d) Streak + heatmap redesign = pure presentation, NO BE change.** All data already client-side: `a.streak` (per-activity current streak), `sc.topStreak` (all-time best), `data.heatmap12w` (84 cells, count-per-day). "Current streak" headline = max(a.streak across activities) = the best running streak today; "best" = sc.topStreak. Redesign: un-collapse the `<details>` into a proper panel; prominent current/best streak stat (🔥 current, ✦ best); a clearer 12-week heatmap (bigger cells, week columns, month/day labels, legend). Scoped `.tlx-*`/`.hm-*` classes, NO global token. → **BE untouched.**

### BE/FE split
- **FE = ALL 4 requirements.** page.tsx (add-form required-time validate + remind-default-sync + timeline-rail bucket + streak/heatmap redesign) + tokens.css (scoped streak/heatmap styles). Possibly a tiny helper in the file.
- **BE = NONE.** No schema/endpoint change. (If tester finds the FE-only required-time is somehow insufficient, escalate — but the analysis says FE-validate is correct + sufficient.)

### Final task list
- **T1 (FE, only task):**
  1. Required time: block onAddTodo when `todoTime` empty (`if (!todoTime) { setAddErr("Chọn giờ cho việc — giờ là bắt buộc."); return; }`), mark the time input required (visual + aria-required), keep the 08:00 prefill but the user must see/confirm it. Remove the silent `time: todoTime || null` fallback-to-null (now always a real time).
  2. Remind-default-sync: toggling todo-remind ON seeds `remind.time = todoTime`; keep editable/optional.
  3. Timeline-rail: keep timed-first; render any leftover timeless (old data) in a small "Chưa đặt giờ" bucket (clickable đặt-giờ preserved). Make the timed list a real vertical time-rail (hour label left · dot · row), if not already.
  4. Streak+heatmap redesign: replace the collapsed `<details>` with an always-visible scoped panel — current-streak (max a.streak, 🔥) + best-streak (sc.topStreak, ✦) prominent + a clearer 12w heatmap. Scoped classes only.
  - Tests: required-time-blocks-add, remind-default=todoTime, timeline-rail renders timed, timeless-bucket for old data, streak/heatmap render. tsc clean, vitest 100%.

### Dispatch plan
- frontend ← T1 (all 4). No BE task. tester verifies (vitest+tsc, +API curl confirming a timeless POST still accepted at BE = old-data-not-broken). team-lead Chrome-gate 6 checks.

## Assumptions (user-review) — filled in end_sprint
