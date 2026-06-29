# End Sprint TRACING-UX3 — Daily Tracing 4 UX improvements

Board task: #170. User CHỐT 2026-06-29 (/tracing).

## What shipped
4 FE-only improvements to /tracing: required time on add, remind-default = activity time, real timeline-rail with a timeless fallback bucket, and a redesigned always-visible streak + 12-week panel. No backend change.

### Changes implemented (4-step verified on disk)
- **Req 1 — required time (FE-validate)** — `onAddTodo` blocks submit on empty `todoTime` ("Chọn giờ cho việc — giờ là bắt buộc."); the time input is marked `aria-required` + a "*" cue + `.trk-req` accent border; the form is `noValidate` so our Vietnamese message shows instead of the browser's English native tooltip (which would otherwise fire first and swallow it — documented rationale in the code). `time: todoTime` always sent (no more `|| null` fallback). The 08:00 prefill stays (least friction) but is now visibly required.
- **Req 2 — remind default = giờ-việc** — `RemindControls` gets an optional `defaultTime` prop; toggling 🔔 ON seeds `remind.time = defaultTime || value.time`; the todo add-row passes `defaultTime={todoTime}`. Sync is on toggle-ON only (a later explicit remind-time edit sticks). Optional (off → activity still adds). The disjoint "07:00" no longer leaks onto a timed todo.
- **Req 3 — timeline-rail + timeless bucket** — timed rows render ascending on the rail; leftover OLD timeless rows (time=null, pre-this-sprint) drop into a labeled "Chưa đặt giờ" bucket at the bottom (shown only when `anytime.length > 0`), keeping their "đặt giờ" affordance. NO backfill (a fake time = dishonest). Old data not broken.
- **Req 4 — streak + 12w redesign** — the collapsed `<details>` → an always-visible scoped panel: prominent stat tiles 🔥 current streak (`Math.max(0, ...acts.map(a => a.streak))` — best running streak today, 0-safe on empty) + ✦ best streak (`sc.topStreak`); a clearer 12-week heatmap (`.trk-hm` bigger cells, day labels, legend kept); the per-activity streak list kept as secondary. All data already client-side (no fetch). Scoped `.trk-*` classes only — no global token.

### Verification (pass/fail)
- tsc: exit 0 ✅
- vitest (tracing scope): 65/65 (49 tracing + 16 TemplateSets), 0 errors ✅ (full suite 1117, +8 new tests per FE report)
- BE: 0 files changed ✅; tester confirmed a timeless POST is still BE-accepted (old-data path intact)
- team-lead Chrome-gate FULL PASS (6/6): (a) add w/ empty time → blocked + VN message, not added · (b) toggle remind → time auto = activity time (09:30→09:30 verified) · (c) left column real time-rail + "CHƯA ĐẶT GIỜ" bucket · (d) always-visible 🔥current/✦best tiles + labeled heatmap (pro, no collapse) · (e) old timeless in bucket + ⏰đặt-giờ pills (no backfill) · (f) console clean (no hydration/SWC) ✅

### 3 Quality Gates
- **Gate 1 (API)**: ✅ N/A — no API/router change (FE-only).
- **Gate 2 (Function)**: ✅ unit tests assert observable behavior (required-blocks-add, remind=todoTime, rail order, timeless bucket, streak/heatmap); tsc clean; vitest 100% / 0 errors; edge case `Math.max(0, ...[])`=0 (no NaN) handled.
- **Gate 3 (Sprint)**: ✅ this report w/ verified counts; architect read full diff on disk (all 4 reqs traced, tokens.css scope confirmed); tester + team-lead Chrome-gate pass; counts ≥ baseline (+8); commit format match.

## Risks / potential errors identified
- The `noValidate` choice (so the VN custom message shows) means the browser's native required-tooltip is intentionally bypassed — our JS guard is the sole gate. Correct + documented; the guard is tested. No risk.
- `currentStreak` = max across activities = the BEST running streak today (not a per-activity figure) — a reasonable "current streak" headline; documented so it's not mistaken for a sum or a single-habit value.

## Assumptions (user-review)
- **Required time = FE-validated, BE stays permissive** — *why*: it's a UX rule, not data-integrity; BE-requiring it would break old timeless activities + the template-set add + the MCP/agent channel (which legitimately posts timeless) — *how to change*: to hard-enforce at the API, make `ActivityInput.time` required in backend/modules/tracing/schema.py (but then handle old data + agent posts).
- **Old timeless activities → "Chưa đặt giờ" bucket, NOT backfilled** — *why*: inventing a time = dishonest data — *how to change*: the user can click ⏰ đặt-giờ per row to put it on the rail.
- **Current-streak headline = max(per-activity streak)** — *why*: the best running streak today is the motivating number; best = all-time topStreak — *how to change*: edit the `currentStreak` derivation in page.tsx.

## Commit
`feat(sprint-tracing-ux3): required-time + remind-default=giờ-việc + timeline-rail + streak/12w redesign (FE-only)`
Explicit-paths only (NOT template/Life Command/* or docs or app/projects/__tests__).
