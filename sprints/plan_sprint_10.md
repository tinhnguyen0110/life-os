# Plan Sprint 10 — Automation + Activity (S13 + S14) [the "active" backbone] — SPLIT PROPOSED

> Author: architect · 2026-06-06 · Status: kickoff DONE · **proposing a SPLIT (S10A + S10B)** · awaiting team-lead mock-diff + greenlight.
> Spec: SPEC §S13 (Routines) + §S14 (Activity Feed). Mock: `template/Life Command/app/screens-active.js` `SCREENS.automation` + `SCREENS.activity` + `DB.routines`/`DB.activity` (`data.js`) — HAS mocks → PORT. ARCH §3 (scheduler) §7 (`GET /routines · PATCH /routines/{id} · POST /routines/{id}/run` · `GET /activity`) §10 (the 6 routines table). The ARCH §9 step-7 "app active" milestone.
> Memory: `schema-freeze-gate`, `unhandled-errors-not-green`, `mock-diff-catches-dropped-feature`, `dev-server-ports`, `test-where-the-reader-greps`, `verify-with-the-distinguishing-case`, `abandon-orthogonal-to-health` (pattern-check operates on abandoned+progress, NOT health=dead), `single-dev-no-overengineering`.

## What ALREADY exists (Rule#0 at kickoff — this is NOT greenfield)
- **`core/scheduler.py`** — `SchedulerEngine` (register/register_many/start/shutdown, interval/cron/date triggers, `enabled` flag for test/CI no-op mode). Built.
- **`core/base.py:44` `Routine` dataclass** — `{id, func, trigger, trigger_args, name, enabled}` + validation. Built.
- **`run_log` SQLite table** (db.py:43) + `record_run(routine_id,status,detail,...)` + read helpers + ok/warn/error validation. Built.
- **2 routines registered:** `wiki-refresh` (projects/router.py:133), `market-poll` (market/router.py:105). So the registry→scheduler wiring works.
→ Sprint 10 ADDS the remaining ~4 routines + the automation/activity API modules + run_log-recording-on-execution + the 2 screens. The hard infra (scheduler engine, Routine contract, run_log) is DONE.

## Why SPLIT (team-lead flagged >6 tasks → split)
Counting the units: 4 new routine algorithms + automation module (3 endpoints) + activity module (1 endpoint + reader) + run_log-recording wrapper + S13 screen + S14 screen + 2 Home swaps = **8+ units across 2 modules + 2 screens.** That's a full-sprint-and-a-half. Independently shippable boundary: **routines + run-log must EXIST before the activity feed has anything to show.** So:

### → S10A — Automation / S13 (the routines + scheduler + run-log recording)
The "active" engine: register the ~6 routines, wrap execution to record run_log, expose `GET /routines` + `PATCH /routines/{id}` (toggle) + `POST /routines/{id}/run` (on-demand), build the S13 Routines screen + the sidebar "routine active" badge. After S10A the app DOES things + LOGS them.

### → S10B — Activity / S14 (the view of the run-log)
The transparency layer: `activity` module `GET /activity` (run_log reader + today-count/success-rate stats + per-run detail), the S14 Activity Feed screen + the Home Activity widget swap. After S10B the user SEES what the routines did. (S10B needs S10A's run_log data to be meaningful.)

---

# ============ S10A — Automation / S13 ============

## Objective (S10A)
Wire the ~6 rule-based routines into the existing scheduler, record every execution to run_log, expose the automation API, build S13. The app becomes "active" (does things on a timer + on-demand, transparently logged). NO AI (CLAUDE.md hard rule — pure rules).

## The 6 routines (ARCH §10 — algorithms DECIDED, decide-and-log)
| id | trigger | algorithm (decided) | exists? |
|---|---|---|---|
| `market-poll` | interval 10m | fetch prices → check ladder rungs → emit alert (market module) | ✅ exists |
| `wiki-refresh` | event/interval | new commit → reader re-reads status/metadata (projects) | ✅ exists |
| `idle-hunter` | cron 22:00 | scan projects, flag any with `lastDays > N` (N=**7**, ARCH §10 ">N days") + not abandoned → warn | NEW |
| `pattern-check` | cron 09:00 | scan projects: `progress >= 90 AND users == 0` → build-to-90 warn. **Operates on progress+users, NOT health=dead** (memory abandon-orthogonal). Excludes already-abandoned. | NEW |
| `journal-nudge` | event (price hits rung) | when market-poll detects a ladder rung hit → remind to log a journal entry | NEW |
| `morning-pull` | cron 08:00 | pull all modules → assemble the brief data (the S11 Brief precursor — this sprint just records the run + a summary; full Brief is S11) | NEW |

**Thresholds (decide-and-log):** idle-hunter N=7 days · pattern-check ≥90% & 0 users · all cron times per the mock (22:00/09:00/08:00). Log to §Assumptions.

## RunLog recording (the key new wiring)
Wrap each routine's `func` so execution records to run_log: `started_at`, `status` (ok/warn/error), `detail` (a human summary + output), `finished_at`. A routine that raises → status=error + the traceback summary (fail-SOFT: one routine erroring doesn't crash the scheduler). This is what S14 reads. **Scheduler-test approach (team-lead's ask): routines must be testable WITHOUT real timers** — call the wrapped func DIRECTLY (the `enabled=False` engine mode already supports register-without-running; tests invoke `routine.func()` + assert the run_log row).

## Routine + RoutineStatus SHAPE (S10A — full field list, T1 msg #1)
```
RoutineInfo (GET /routines → list) {
  id:        str
  name:      str
  trigger:   "interval"|"cron"|"date"|"event"   # display (event = market-driven)
  triggerLabel: str         # "mỗi 10 phút" / "22:00 mỗi tối" / "commit mới"
  desc:      str            # what it does
  action:    str            # the action summary
  enabled:   bool           # on/off (PATCH toggles)
  lastRun:   str | None     # ISO-8601 of last run (from run_log), else None
  lastResult: "ok"|"warn"|"error"|None   # last run status
  runs:      int            # total run count (run_log count for this id)
}
GET /routines → {routines: [RoutineInfo], activeCount, total, runsToday, lastRunAt}
PATCH /routines/{id} body {enabled: bool} → toggle, returns RoutineInfo. 404 unknown.
POST /routines/{id}/run → run on-demand NOW, record run_log, return {id, status, detail, startedAt, finishedAt}. 404 unknown.
```

## Tasks (S10A — 4: BE gating → FE → tester)
- **T1 [backend, GATING] — automation module + the 4 new routines + run_log recording.**
  - 4 new `Routine`s (idle-hunter/pattern-check/journal-nudge/morning-pull) with the decided algorithms, supplied via their owning modules' `routines()` (idle-hunter+pattern-check → projects; journal-nudge → journal/market; morning-pull → a new automation or brief-precursor). Run-record wrapper.
  - `automation` module: `GET /routines` (merge registered routines + run_log stats) + `PATCH /routines/{id}` + `POST /routines/{id}/run`. Reads the scheduler's registered set + run_log. FREEZE + curl.
  - Gates T2/T3.
- **T2 [backend] — routine execution → run_log wiring + scheduler integration test** (may fold into T1). Each routine records on run; manual run works; toggle persists.
- **T3 [frontend] — S13 Routines screen** (`app/automation/page.tsx` or `routines/`, replace EmptyScreen) — port SCREENS.automation: 4 stat cards, scheduler-status banner, routine cards (toggle/run/last-run/runs), trigger filter. + sidebar "routine active" badge.
- **T4 [tester] — verify** — pytest (each routine's algorithm on a fixture: idle-hunter flags >7d, pattern-check flags 90%-0-user NOT health=dead, run records to run_log; toggle persists; manual run records; scheduler register without real-timer). API curl (GET/PATCH/POST). Chrome: toggle a routine, run on-demand → run_log row, value-by-value. **Scheduler tested WITHOUT waiting for timers** (invoke func directly).

## Logic/Algorithm (S10A — decided)
- **idle-hunter:** `[p for p in projects if p.lastDays is not None and p.lastDays > 7 and not p.abandoned]`. Emits a warn run_log + (later) an alert. N=7.
- **pattern-check:** `[p for p in projects if (p.progress or 0) >= 90 and p.users == 0 and not p.abandoned]` → build-to-90 warning. **NOT health-based** (abandon-orthogonal memory). Excludes abandoned.
- **journal-nudge:** triggered by market-poll detecting a ladder-rung hit → record a nudge run ("giá chạm rung X, ghi journal?"). Event-driven (no own timer).
- **morning-pull (LOCKED):** cron 08:00 → read projects.list + finance.overview + market summary (existing readers) + record a run_log `ok` row with `detail="pulled N projects · finance $X · M quotes"`. **NO brief output, NO new store, NO Brief dependency** (S11 Brief isn't built — it'll consume/extend this later). A "warm-the-data + log-it-ran" routine. Testable: run → assert a run_log row with the summary. OWNED by the automation module (cross-module). §Assumptions: "morning-pull = pull+summarize+log this sprint, NOT brief-assembly (S11 extends)."
- **run_log recording:** wrap func → on call: insert started_at; run; on success status=ok (or warn if the rule found something to flag); on exception status=error + detail=summary; finished_at. Never let a routine exception crash the scheduler (fail-soft per-routine).
- **runsToday:** count run_log rows with started_at today. **lastResult/lastRun:** newest run_log row for the id.

## Defensive (S10A — MANDATORY)
- A routine `func` raises → status=error in run_log, scheduler keeps running (fail-soft per-routine, NOT fail-the-whole-scheduler).
- `POST /run` on a routine whose deps are down (e.g. market feed) → records error run, returns the error detail, 200 (the RUN happened, it just failed — that's a logged outcome, not a 500).
- Empty run_log (no runs yet) → routines show lastRun=None/lastResult=None/runs=0, 200.
- PATCH/POST unknown routine id → 404.
- Scheduler disabled (test/CI mode) → routines register but don't fire on timer; manual run + func-invoke still work + record.
- pattern-check/idle-hunter with 0 projects → empty result, ok run (not error).

---

# ============ S10B — Activity / S14 (separate dispatch after S10A lands) ============

## Objective (S10B)
The transparency view of the run_log S10A produces. `activity` module `GET /activity` (run_log reader + stats + per-run detail) + S14 Activity Feed screen + Home Activity widget swap.

## ActivityFeed SHAPE (S10B — sketched, finalized at S10B kickoff)
```
GET /activity?routine=&status=&range=today|week → {
  runs: [{id, routineId, routineName, status(ok/warn/error), desc, startedAt, finishedAt, durationMs, output}],
  count, runsToday, okCount, errorCount, successRate, avgDurationMs, byRoutine:[{routine, count}]
}
GET /activity/{run_id} → full run detail + output.
```
Reads run_log (db.py helpers). S14 screen: feed rows (✓/✗ + name + desc + time + dur + status), 4 stat cards (run-today/success/error/avg-dur), filter tabs (all/ok/err), today/week segment, click-row→detail. + Home Activity widget (recent N runs) swapping the Home stub.

## S10B tasks (sketch — 3): T1 activity module (GET /activity + reader + stats) · T2 FE S14 screen + Home widget swap · T3 tester. (Detailed at S10B kickoff after S10A.)

---

## Dispatch standards (both)
- Runtime: `docker compose up -d` (DETACHED). Baseline: pytest 544, vitest 295 (post-S9).
- **`## Read first` per role** (BE → scheduler/Routine/run_log existing code + abandon-orthogonal + schema-freeze + test-where-reader-greps; FE → mock-diff + unhandled-errors + dev-ports; tester → verify-live-app + behavior-test + workaround-then-ask).
- **Full field list msg #1** + freeze field-by-field + test-ownership-split + container-up-detached.
- **Scheduler-test rule:** routines tested by INVOKING func directly + asserting the run_log row — NEVER by waiting for a real timer. The `enabled=False` engine mode + direct func-call is the test path.

## Out of scope (north-star)
- **NO AI routines** (CLAUDE.md hard rule — all 6 are pure rules; AI-generated routines deferred to the Claude-Code-MCP build).
- **NO routine marketplace / skill-library** (SPEC §S13 explicit "~6 có mục đích, KHÔNG skill-library").
- **Create/edit-routine form — DEFERRED (resolved at mock-diff, the MOCK ITSELF backs it).** The mock has a "Routine mới" button BUT `screens-active.js:53` literally says "Giới hạn có chủ đích: ~6 routine có mục đích rõ... KHÔNG xây marketplace 54 skill" + ARCH §10 "~6 routine, KHÔNG skill-library." A full rule-builder would CONTRADICT the mock's own stated design. **Resolution: RENDER the "Routine mới" button (it's a mock element — honest-mirror, don't omit) BUT as a CONSTRAINED affordance** — click → a "sắp có · theo chủ đích giới hạn ~6 routine" note (the deliberate-limit copy explains the constraint). NOT a full builder. Logged to §Assumptions.
- **Full Brief assembly** (morning-pull just records the pull; the Brief screen is S11).
- **GCP 24/7 scheduler** — local APScheduler only (ARCH: "sau chuyển GCP nếu cần").
