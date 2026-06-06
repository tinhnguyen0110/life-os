# Plan Sprint 10B — Activity Feed / Run Log (S14) [the VIEW of what the routines did]

> Author: architect · 2026-06-06 · Status: kickoff DONE · awaiting team-lead mock-diff + `## Read first` gate + greenlight.
> Spec: SPEC §S14 (Activity Feed — chống hộp đen / anti-black-box). Mock: `template/Life Command/app/screens-active.js` `SCREENS.activity` + `DB.activity` (`data.js:116-ish`) — HAS a mock → PORT. ARCH §6 (run_log table — the SOURCE, ALREADY has S10A data) / §7 (`GET /activity`). The completion of the Automation pair: S10A produced the data, S10B shows it.
> Memory: `unhandled-errors-not-green`, `schema-freeze-gate`, the run_log/db existing code (`store/db.py` recent_runs/record_run), `dev-server-ports`, `mock-diff-catches-dropped-feature`, `verify-live-app-not-just-suite`, `behavior-test-not-field-read`, `verify-with-the-distinguishing-case`.

## Objective
Replace the Activity EmptyScreen with the real S14 "Activity Feed" — the transparency view of the run_log. A mostly-READ sprint: the `activity` module reads run_log (the table S10A's wrapper has been recording to), exposes `GET /activity` (feed + stats + per-run detail), builds S14 + swaps the Home Activity Feed stub → live. "Minh bạch — automation vừa làm gì. Chống hộp đen." Full feature per SPEC §S14, simplest impl.

## Data source — REAL run_log data ALREADY exists (Rule#0 at kickoff)
The run_log SQLite table (`backend/store/life_os.db`) ALREADY has S10A's real entries:
```
market-poll  ok | polled: persisted=5 fired=0
pattern-check ok | Không có dự án build-to-90 (≥90% & 0 user).
journal-nudge ok | Chưa có cảnh báo giá mới để nhắc journal.
idle-hunter  warn | <4 idle projects>  (etc.)
```
Columns: `id, routine_id, status(ok/warn/error), detail, started_at, finished_at`. So S10B has REAL data to value-diff IMMEDIATELY (no seeding). `recent_runs(routine_id, limit)` exists but is PER-routine — S14 needs an ALL-routines feed query (new in the activity reader). **`detail` is the human summary** — the mock's `desc` (short) AND `output` (full) both derive from it (this build: desc=detail truncated, output=detail full; a separate richer output field is a later enhancement).

## Honest-mirror — every SCREENS.activity panel (none dropped)
| Mock panel | Data | Sprint 10B |
|---|---|---|
| Title + tabs (Tất cả/Thành công/Lỗi) + Hôm nay/Tuần segment | filter + range | **LIVE** |
| 4 stat cards (Run hôm nay / Thành công / Lỗi / Thời gian TB) | derived from run_log | **LIVE** |
| Run-log feed (✓/✗ + name + desc + time + ago + dur + status + output) | run_log rows | **LIVE** |
| Click row → full log + output detail | run_log row by id | **LIVE** (GET /activity/{id} or the row carries output) |
| Home Activity widget (recent N) | run_log recent | **LIVE swap** (the S5 Home stub → live) |

## ActivityRun + ActivityFeed SHAPE (full field list — T1 gating dispatch msg #1)
```
GET /activity?routine=&status=&range=today|week|all → ActivityFeed {
  runs:        list[ActivityRun]
  count:       int
  runsToday:   int
  okCount:     int
  warnCount:   int
  errorCount:  int
  successRate: float | None      # okCount / count × 100; None if 0 runs; carries {ok, total}
  avgDurationMs: int | None      # mean (finished-started) over runs with a finished_at; None if 0
  byRoutine:   list[{routine, count}]   # runs grouped by routine
}
ActivityRun {
  id:         int                # run_log row id (for detail/click)
  routineId:  str                # "market-poll"
  routineName: str               # display "Market Poll" (from a routine-name map; fallback = routineId)
  status:     "ok"|"warn"|"error"
  detail:     str                # the human summary (the mock's desc AND output both from this)
  startedAt:  str                # ISO-8601
  finishedAt: str | None
  durationMs: int | None         # finished-started in ms; None if no finished_at
}
GET /activity/{run_id} → the single ActivityRun (full detail). 404 unknown.
```
Envelope + codes. Mock's `ago` (relative "7 phút trước") + `time` (HH:MM) + `dur` ("3.1s") = FE-formatted from startedAt/durationMs (not stored — FE derives, like other screens).

## Tasks (3-4: BE gating → FE → tester)
- **T1 [backend, GATING] — activity module (reader over run_log).**
  - NEW `backend/modules/activity/` (schema + service + router). `GET /activity` (feed + filters + stats) + `GET /activity/{id}`. A NEW all-routines run_log query (recent_runs is per-routine — add `all_runs(limit, since)` or similar to db.py or the activity reader). Routine-name map (routineId → display name; reuse the automation module's names if shared). FREEZE field-by-field + curl (shows the REAL S10A runs).
  - Gates T2/T3.
- **T2 [backend] — activity stats + filters** (may fold into T1). successRate/avgDuration/byRoutine derivations + ?routine=/?status=/?range= filters.
- **T3 [frontend] — S14 Activity screen + Home widget swap.**
  - `app/activity/page.tsx` (replace EmptyScreen) — port SCREENS.activity: 4 stat cards, filter tabs (all/ok/err), today/week segment, feed rows (status chip ✓/⚠/✗ + name + desc + time/ago/dur + output), click-row→detail (expand or modal). + **swap Home `page.tsx:203` ComingSoonStub → live Activity widget** (recent N runs). Blocked by T1 frozen + serving.
- **T4 [tester] — verify activity.**
  - pytest (activity reader over run_log: feed shape, stats math successRate/avgDuration/byRoutine on a fixture, filters by routine/status/range, empty-runlog→empty stats, per-run detail by id). API curl (`GET /activity` vs the REAL run_log rows + filters + /activity/{id} 200/404). Chrome `docker compose up -d`: S14 renders the REAL S10A runs, value-by-value vs `GET /activity`, click-row→output, filter tabs, Home widget live (was stub), console 0, 0 unhandled. Pre-scaffold from T1.

## Logic/Algorithm (architect-decided — decide-and-log)
- **feed:** all run_log rows (across routines) newest-first, filtered by ?routine/?status/?range. range: today = started_at ≥ today-00:00; week = ≥ 7d ago; all = no filter.
- **routineName:** map routineId → display ("market-poll"→"Market Poll"). Reuse the automation routine-name source; fallback = routineId title-cased.
- **durationMs:** `(finished_at - started_at)` in ms; None if finished_at null. (Many S10A runs are instant — same start/finish second → 0ms, valid.)
- **successRate:** `okCount / count × 100` (1dp). None if 0 runs. carries {ok, total}. (warn counts as NOT-ok for success rate? DECIDE: successRate = ok / total; warn + error both count against it — a warn is "ran but flagged something", not a clean success. Log it.)
- **avgDurationMs:** mean durationMs over runs with finished_at; None if none.
- **byRoutine:** group runs by routineId, count, desc.
- **stats respect the active filter** (the 4 cards reflect the current range/filter — or always show today? DECIDE: the cards show the CURRENT range's stats; "Run hôm nay" is always today regardless. Log it.)

## Defensive (MANDATORY)
- Empty run_log → `{runs:[], count:0, runsToday:0, okCount:0, ..., successRate:null, avgDurationMs:null, byRoutine:[]}`, 200 not 500. (Unlikely — S10A populated it — but the test fixture uses a fresh db.)
- A run_log row with null finished_at → durationMs null (in-progress or crashed mid-run); FE shows "—" for dur. Don't crash.
- Malformed/legacy row (missing detail) → detail="" , don't skip the row (it still ran).
- 0 runs → successRate/avgDuration null (not 0 — honest "no data").
- ?status= invalid value → 422 or ignore-and-return-all (DECIDE: ignore unknown filter value, return all + no error — lenient read).
- GET /activity/{id} unknown → 404.
- Very large run_log (market-poll runs every 10m → hundreds of rows) → the feed paginates or caps (DECIDE: default limit 100 newest, ?range scopes it; log the cap so it's not silent truncation — `count` reflects the filtered total, `runs` the capped page).

## Dispatch standards
- Runtime: `docker compose up -d` (DETACHED). Baseline: pytest 575, vitest 310 (post-10A).
- **`## Read first` per role (HARD GATE — team-lead checks first):** BE → `unhandled-errors-not-green`, `schema-freeze-gate`, the run_log/db existing code (store/db.py), `dev-server-ports`; FE → `mock-diff-catches-dropped-feature`, `unhandled-errors-not-green`, `dev-server-ports`; tester → `verify-live-app-not-just-suite`, `behavior-test-not-field-read`, `verify-with-the-distinguishing-case`.
- Full field list msg #1 + freeze field-by-field + test-ownership-split + container-up-detached.
- FE: mock = SCREENS.activity, mirror frozen shape render-only; derive time/ago/dur from startedAt/durationMs.

## Dispatch ordering
1. T1 GATING (activity module + run_log reader) alone → freeze (curl the REAL S10A runs).
2. T2 (stats/filters) after/with T1.
3. T3 (FE + Home swap) after frozen + serving. T4 pre-scaffolds from T1.

## Out of scope (north-star)
- **Separate rich `output` field** — this build derives both desc + output from run_log's `detail` (one field). A distinct verbose-output column is a later enhancement if runs produce long logs.
- **Live-streaming/tail -f feed** — the mock shows a "live · tail -f" pill; this build is fetch-on-load + manual refresh (no websocket/SSE — north-star). The pill can be cosmetic or a refresh button.
- **Run_log pagination UI** — default newest-100 + range filter; infinite-scroll/paging deferred (log the cap).
- **Per-run re-run from the feed** — the feed VIEWS runs; re-running is S13's POST /run (don't duplicate).
