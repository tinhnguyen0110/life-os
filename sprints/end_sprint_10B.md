# End Sprint 10B — Activity Feed / Run Log (S14) [the VIEW — app now ACTIVE + TRANSPARENT]

> Result doc (CLAUDE.md §3.2). Sprint 10 split into 10A (Automation/S13) + 10B (Activity/S14). This is 10B: the transparency view of the run_log S10A produces. `activity` module reads run_log, `GET /activity` (feed + stats + per-run detail), S14 screen + Home Activity widget swap. Completes the Automation pair: S10A the app DOES things, S10B the user SEES them. "Chống hộp đen."
> Author: architect · 2026-06-06 · Commit: `feat(sprint-10B)` on `main`.

---

## 1. What shipped

### Backend — `activity` module (reader over run_log, mostly-READ sprint)
- **`activity` module** (registry auto-discovered): `GET /activity?routine=&status=&range=today|week|all` (feed + stats) + `GET /activity/{run_id}` (per-run detail, 404 unknown). A NEW all-routines run_log query (the existing `recent_runs` was per-routine).
- **ActivityFeed** `{runs, count, runsToday, okCount, warnCount, errorCount, successRate|null, avgDurationMs|null, byRoutine[]}` + **ActivityRun** `{id, routineId, routineName, status, detail, startedAt, finishedAt|null, durationMs|null}`.
- **successRate = okCount/count×100 (PERCENTAGE)** — consistent with winRate/pct/avgPeak app-wide (the units saga, §2). warn+error both count against. Cap: newest-100 in `runs`, `count` = filtered total (no silent truncation). Lenient filters (garbage ?status → return all). detail = the human summary (mock's desc + output both from it).

### Frontend — S14 Activity screen (`app/activity/page.tsx`) + Home Activity widget
- Ported `SCREENS.activity`: 3 stat cards (run-today / success+**breakdown** / avg-dur), filter tabs (server-side re-fetch so cap/count stay correct), today/week segment, feed rows (status chip ✓/⚠/✗ + name + detail + time/ago/dur), click-row→fuller-detail.
- **successRate renders as PERCENTAGE** (e.g. 81.1%), null→"—" (NOT "0%"); the ok/warn/error **breakdown** shown (a warn-heavy 80% reads differently than error-heavy).
- **Cap visible** ("hiển thị {N} gần nhất / tổng {count}") — no silent truncation.
- **Home Activity widget swap** (`page.tsx:204`): ComingSoonStub → `<HomeActivityTile />` (recent runs, **per-tile fail-open** — /activity down → this tile errors, rest of Home renders). Only Brief remains a Home stub (S11).

---

## 2. Verification (Rule #0) — the run-the-red-first saga

### The headline (a 3-round Rule#0 untangling) → memory `run-the-red-before-naming-its-cause`
The freeze surfaced a successRate units conflict (dispatch said percentage; the tester scaffold said fraction). Three rounds of stale-read cause-claims flew both ways: backend froze claiming "green / it's the tester's DB bug"; team-lead's re-check reported "7 fails: units + get_feed TypeError." **One disk-run settled it:** `pytest tests/test_activity.py` → 1 failed (not 7); the failure was the tester scaffold's DB-isolation bug (Fixture B's `close_db()` doesn't delete rows → count piled to 10) — exactly backend's ORIGINAL diagnosis. RULING: percentage wins (app-wide convention + dispatch); the scaffold is the outlier → tester realigns its OWN scaffold + fixes the DB reset (`DELETE FROM run_log`); backend's code stands untouched. team-lead independently re-ran + owned the reversal. **Lessons: run the red + read the traceback before naming a cause; a spec conflict's authority = dispatch + app-convention, not whichever artifact read first; escalating a genuine conflict (vs thrashing) is correct.**

### Architect 4-step (full functions + live container)
| Check | Result |
|---|---|
| pytest | **597 passed, 0 errors** (activity 22, all green) |
| vitest | **329 passed** (≥310 baseline; +19 activity/Home) |
| tsc | clean |
| Container `/activity` (rebuilt) | count 52, **successRate 80.8 (PERCENTAGE)**, ok/warn/err 42/10/0, byRoutine desc, avgMs 284 — real S10A data |
| successRate-as-% + null→"—" (page.tsx:111-112) | ✓ (not 0%, not fraction) |
| breakdown (113) | ok·warn·lỗi composition ✓ |
| cap visible (107,129) | "N gần nhất / tổng M" ✓ |
| Home widget per-tile fail-open (HomeActivityTile) | self-fetch, own error, rest of Home unaffected ✓ |

### team-lead Rule#0 live value-diff (rebuilt container + Chrome — the cure applied)
✅ S14 3 stat cards (81.1% + 43ok·10warn·0lỗi breakdown, 288ms), feed rows, value-by-value vs /activity, console 0; Home Activity widget swapped live (recent runs, replacing the S5 stub); successRate percentage; honest-empty (Lỗi filter → "—" not "0%"). PASS, pre-greenlit.

### Tester T4 (PENDING API+Chrome — their lane; scaffold green 22/0)
API (/activity vs real run_log + filters + /activity/{id} 200/404) + Chrome.

---

## 3. The 3 Quality Gates

### Gate 1 — API
☑ Schema (ActivityFeed/ActivityRun frozen, Literal status) · ☑ integration tests · ☑ existing pass · ☑ auto-discovered · ☑ envelope · ☑ codes (404 unknown run, lenient garbage filter → all) · ☑ self-describing (successRate carries {ok,total}, breakdown counts).

### Gate 2 — Function
☑ unit tests (feed shape, stats successRate=ok/total×100 + avgDuration + byRoutine; **the DISTINGUISHING test — warn-heavy vs error-heavy at same successRate, different breakdown**; cap newest-100/count=total; filters; empty→null-stats) · ☑ pytest 597/0 + vitest 329/0 · ☑ edge cases (empty, null finished_at→durationMs null, 0 runs→null stats, garbage filter) · ☑ tsc clean · ☑ FE Chrome self-verify (rebuilt container) · ☑ per-tile fail-open (Home widget).

### Gate 3 — Sprint
☑ end_sprint_10B written · ☑ architect 4-step (full functions + live container) · ☐ **tester T4 API+Chrome — PENDING** · ☑ counts ≥ baseline (pytest 575→597, vitest 310→329) · ☑ findings flagged (§5) · ☑ format `feat(sprint-10B)`.

**VERDICT: backend + FE GREEN. Gate 3 holds on tester T4 + team-lead pre-greenlit → commit on T4 report.**

---

## 4. Assumptions (user-review — decide-and-log)

- **successRate = okCount/count × 100 (PERCENTAGE 0-100)** — warn+error both count against (a warn "ran but flagged" isn't a clean success). Consistent with winRate/pct/avgPeak app-wide (the units ruling). FE carries the ok/warn/error breakdown so the composition is visible. To change: would break app-wide rate consistency.
- **Run-log cap = newest 100 + range filter**; `count` = filtered total (NOT capped). FE shows "N gần nhất / tổng M" (no silent truncation). To change: paginate.
- **`detail` = both desc + output** (one run_log column); click-detail shows it fuller. A separate rich-output column is a later enhancement. To change: add an output column to run_log.
- **Lenient filters** — garbage ?status/?range → return all (no 422 for a bad read filter). To change: strict-validate filter params.
- **Home Activity widget = recent N runs, per-tile fail-open** (self-fetch, independent error). Only Brief remains a Home stub (S11).
- **range: today = started_at ≥ today-00:00 UTC; week = ≥7d; all = no filter.**

---

## 5. Risks / out-of-scope (future)

- **Live-streaming feed** (the mock's "tail -f" pill) — fetch-on-load + manual refresh this build (no SSE/websocket — north-star). Pill is cosmetic.
- **Rich per-run output** — detail is one column (desc+output both from it); a verbose-output column is a later enhancement.
- **Run-log pagination UI** — newest-100 + range; infinite-scroll deferred (cap is visible).
- **Container flap** — recurring (team-lead owns keeping the stack up + a restart-policy proposal for the Sync).

---

## 6. Retro (process learnings)

1. **The run-the-red-first saga (the headline) → memory `run-the-red-before-naming-its-cause`:** a successRate units conflict spawned 3 rounds of stale-read cause-claims (backend "green"; team-lead "7 fails/units/TypeError") that ONE disk-run settled (1 fail = the tester scaffold's DB-isolation, backend's original diagnosis). Lessons: RUN the red + read the traceback before naming a cause; spec-conflict authority = dispatch + app-convention not the first artifact read; escalating a genuine conflict is correct. **team-lead adopted the cure on itself** (re-ran the suite + rebuilt container before greenlighting, not off the report).
2. **The Automation pair completes the active+transparent app** — S10A the app DOES things (routines run+log), S10B the user SEES them (S14 feed + Home widget). ARCH §9 step-7 fully landed.
3. **App-wide consistency as a ruling axis** — when a field's units are contested, the established app convention (every rate = percentage) is the tiebreaker; a lone outlier is the bug.

---

## 7. Commit
- `feat(sprint-10B): activity module (S14) — run_log feed reader + stats + S14 screen + Home Activity widget` — activity module + activity page + useActivity + HomeActivityTile + Home swap + plan_10B + end_10B. One commit.
- Gated on tester T4 + team-lead pre-greenlit. After: `sleep 120 && git push` → notify user → Sprint Sync → next (S11 Brief / S12 Settings → completes 14 screens).
