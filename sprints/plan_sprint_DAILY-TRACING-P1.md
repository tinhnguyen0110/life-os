# Sprint DAILY-TRACING-P1 — BE store + service + API + derivations (Cairn #65 Phase 1)

> Created 2026-06-21 by architect (kickoff ∥ while backend does #68). #65 Phase 1 of 4 (P1 BE → P2 MCP → P3 FE → P4 brief). The G-HABIT module — manual habit/activity logging. BUILD directly (user-decided direction, no scope-gate). HOLD dispatch until #68 commits (1 implementer, sequential). backend EDITS; architect commits (§3).

## Context
Net-new `modules/tracing/` — track day-to-day habits (run/code/study/work): user LOGS sessions → derived streak/pct/week/12w-heatmap/score. Ported from `template/Life Command` DB.tracing (data.js:109) + S14. DISTINCT from reminders (alarms) + journal (decisions). Raw-data-first: store the raw sessions, DERIVE all metrics server-side.

## Storage (DECIDED — no-overengineering, mirror the reminders module pattern)
Two module-owned SQLite tables on the shared connection (like reminders' `init_reminders_tables`), NOT md:
- **`tracing_activities`** (defs): `id TEXT PK, name, emoji, icon, unit, goal REAL, color, created, archived INT DEFAULT 0`.
- **`tracing_logs`** (sessions, time-series): `id INTEGER PK, activity_id TEXT, date TEXT (YYYY-MM-DD, VN-day), ts TEXT (ISO), val REAL, dur_min INT|NULL, note TEXT`. Index (activity_id, date).
(SQLite for both: defs are structured + logs are time-series/derive-heavy — md is for git-versioned prose. Single-user, simplest.)

## API (router.py)
- `GET /tracing` → TracingOverview {date, activities:[ActivityView], heatmap12w:[int×84], score} (the S14 payload).
- `POST /tracing/{activity_id}/log` → log a session {val, dur_min?, note?} (date defaults today-VN; multiple/day accumulate).
- `POST /tracing/activities` / `PUT /tracing/activities/{id}` / `DELETE` (archive) — activity-def CRUD.
- Errors → agent_error (the #46 helper — reuse, it's the standard now).

## 🔑 DERIVATIONS (the architect deliverable — server-side, raw-data-first). All dates = VN-day (UTC+7).
Let `today` = the VN current date. For an activity with goal G:
- **today** {done, val, dur, note, pct}: `val` = Σ(today's sessions' val); `dur` = Σ(dur_min) formatted; `pct` = round(min(100, val/G*100)) (G>0; G==0 → pct 0); `done` = val ≥ G; `note` = the latest session's note today.
- **streak** (consecutive goal-met days ending at the most recent met day): walk backwards from `today`; a day "met" if Σ(that day's val) ≥ G. **Decision (decide-and-log):** today-incomplete does NOT break the streak — count the streak through yesterday; if today is already met, include it. (So a streak shows "N days" even mid-today before you've logged — today is "at risk", not a break.) Formally: streak = count of consecutive met-days going back from `today` if today-met, else from `yesterday`. A gap (an unmet day) stops the count.
- **week[7]** (Mon→Sun of the current week): per-day Σ(val) for this Mon-Sun (0 for no-session days).
- **history12w[84]** (oldest→newest, 84 days = 12 weeks Mon-Sun ending this Sun): per-day Σ(val) (or 0). (For binary-ish habits the val is the raw sum; FE renders intensity.)
- **heatmap12w[84]** (combined, oldest→newest): per-day SCORE 0-4 = COUNT of activities that MET their goal that day (Σ(val per activity that day) ≥ that activity's G). Caps at the activity count (≤4 in the mock but generalize to N).
- **score** {total, done, pct, timeActive, topStreak}: `total` = active (non-archived) activity count; `done` = how many met goal today; `pct` = round(done/total*100); `timeActive` = Σ(today's all sessions' dur_min) formatted "Hh Mm"; `topStreak` = max(streak across activities).
- **ActivityView** = the def + today + week[7] + history12w[84] + streak (the S14 card payload).

## Defensive / honest-mirror
- No sessions yet for an activity → today {done:false, val:0, pct:0}, streak 0, week/history all 0 — HONEST empty, NOT fabricated. New install (no activities) → activities:[], score all 0, heatmap all 0 (+ honest empty, count 0).
- goal==0 → pct 0 (no divide-by-zero), done=false.
- A log with val<0 → reject (agent_error INVALID_INPUT). Unknown activity_id on log → 404 NOT_FOUND.
- timezone: ALL dates are VN-day (UTC+7) — a session's `date` is derived from its ts in VN tz (a 23:30-VN session = today-VN, not tomorrow-UTC).

## Registry
New `modules/tracing/` folder → auto-discovered (BaseModule, NO core/main.py edit).

## HARD GATE (distinguishing)
- Log 2 sessions same day → today.val = SUM (accumulate, not overwrite); pct updates.
- streak: log goal-met 3 consecutive days → streak 3; SKIP a day (no log) → streak resets (a divergent case: 3-met-then-gap → streak counts only the post-gap run).
- heatmap day-score = COUNT of activities met that day (seed 2 activities, 1 met → score 1; both met → 2 — the distinguishing that it's a count, not a boolean).
- VN-tz: a 23:30-VN session → counts on the VN day, not UTC-tomorrow.
- honest-empty: a fresh activity → all-zero derived, no fabricated streak.
- pytest 0-failed, mypy clean.

## Baseline
pytest = post-#68 count. Keep 0-failed.

## Test ownership split
backend: the derivation tests (2-session accumulate; streak-3-then-gap-resets the DIVERGENT case; heatmap-count-not-boolean; VN-tz-day; honest-empty; goal==0 no-divide). tester: live curl POST log → GET /tracing reflects.

## Assumptions (user-review)
- **store = 2 SQLite tables** (tracing_activities defs + tracing_logs sessions), module-owned on the shared connection (mirror reminders) — NOT md. **Why:** structured + time-series + derive-heavy; single-user simplest. **How to change:** the store schema.
- **streak** = consecutive goal-met VN-days; today-incomplete does NOT break it (today = at-risk, counted-if-met). **How to change:** the streak walk in service.
- **heatmap score** = COUNT of activities meeting goal that day (0-N). **all derived server-side** (raw-data-first); FE renders only.
- VN-day (UTC+7) for all date bucketing.

## Notes
- #65 Phase 1 (BE foundation). P2 MCP (tracing_overview + tracing_log) / P3 FE (/tracing S14) / P4 brief — after P1. backend EDITS modules/tracing/; architect commits fix(sprint-DAILY-TRACING-P1). HOLD until #68 commits. The derivations above are the core spec — implementer codes them, doesn't improvise.
