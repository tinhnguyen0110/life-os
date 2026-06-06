# End Sprint 10A — Automation / Routines (S13) [the "active" layer — app now DOES things]

> Result doc (CLAUDE.md §3.2). Sprint 10 split into 10A (Automation/S13) + 10B (Activity/S14). This is 10A: wire the rule-based routines into the existing scheduler, record every run to run_log, expose the automation API, build S13 + the live TopBar badge. The app becomes "ACTIVE" — does things on timers + on-demand, transparently logged. ARCH §9 step-7 milestone.
> Author: architect · 2026-06-06 · Commit: `feat(sprint-10A)` on `main`.

---

## 1. What shipped

### Backend — `automation` module + 4 new routines on a run-record wrapper
- **Built ON existing infra** (NOT greenfield): `core/scheduler.py` SchedulerEngine, `core/base.py` Routine, `store/db.py` run_log + record_run all pre-existed; 2 routines (market-poll/wiki-refresh) already ran.
- **`record_routine_run(routine_id, fn)` wrapper** — times start/finish, records ok/warn/error + detail to run_log, **swallows exceptions (fail-soft per-routine — one routine erroring never crashes the scheduler/others)**. ALL 6 routines refactored onto it (dedups the prior manual record_run).
- **4 new routines** (algorithms decided): `idle-hunter` (cron 22:00, projects lastDays>7 & not abandoned), `pattern-check` (cron 09:00, progress≥90 & users==0 & not abandoned — **NOT health=dead**), `journal-nudge` (event, rung-hit → nudge), `morning-pull` (cron 08:00, read projects+finance+market → summary run, NOT brief-assembly).
- **`automation` module:** `GET /routines` (merge registered set + run_log stats) + `PATCH /routines/{id}` {enabled} (toggle, **md_store-persisted** survives restart) + `POST /routines/{id}/run` (on-demand via wrapper → run_log row, 200-even-on-deps-down).

### Frontend — S13 Routines screen (`app/routines/page.tsx`) + live TopBar badge
- Ported `SCREENS.automation`: 4 stat cards, scheduler-status banner, trigger filter tabs, routine cards (name/trigger-pill/desc/action/toggle/Chạy/lastResult-chip/lastRun/runs), deliberate-limit note.
- **lastResult chip handles all 3 states** (ok=✓/warn=⚠/error=✗/null=no-chip) — warn renders distinctly.
- **"Routine mới" CONSTRAINED affordance** (→ "Sắp có · giới hạn ~6 routine có chủ đích · không xây marketplace" note, NOT a builder — the mock's own anti-marketplace copy).
- **Sidebar Automation nav badge = live activeCount** (the dispatch-specified element — FE self-caught having first wired the TopBar pill, then corrected to the Sidebar nav badge the `sidebar-badges-static-placeholder` backlog tracks; was hardcoded "5" → now live 6). Fail-soft → falls back to the static badge if /routines down, never blocks the sidebar. The TopBar pill is ALSO live (bonus, both wired). Only the automation badge this sprint; the other 3 stay static (the shell-task tracks them).
- FE also fixed the Sprint-0 Sidebar/shell/TopBar tests (default getRoutines mock in beforeEach so the live-badge fetch doesn't break them — no regression).

---

## 2. Verification (Rule #0) — the abandon-orthogonal trap, caught + proven closed

### The catch (the read-first-memory net firing)
Backend's first instinct reached for `health=="dead"` for idle-hunter (its Q literally asked "health==dead OR lastDays>N?"). The **abandon-orthogonal-to-health memory in its `## Read first`** + my review at the resolution closed it → idle-hunter = lastDays>7 (NOT health); pattern-check = progress≥90 & users==0 (NOT health=dead). **Proven on REAL data:** the live store has a project `active` with health=dead BUT progress=55/users=4 — pattern-check correctly does NOT flag it. If it keyed on health it WOULD have. The real data is itself the distinguishing case.

### Architect 4-step (full functions + live container)
| Check | Result |
|---|---|
| pytest | **575 passed, 0 errors** |
| vitest | **310 passed** (≥295 baseline; +15 routines/badge) |
| tsc | clean |
| Container `/routines` | 6 routines, activeCount 6, runsToday 37; idle-hunter lastResult=warn/runs=2, pattern-check ok, journal-nudge trigger=event |
| Constrained "Routine mới" (page.tsx) | note, not a builder ✓ |
| lastResult chip (page.tsx:157-162) | ok=✓/warn=⚠/error=✗/null=no-chip — all 3 distinct ✓ |
| TopBar badge (TopBar.tsx:52-82) | live activeCount, fail-soft to "—", never blocks ✓ |
| null lastRun → "chưa chạy"/"—" | ✓ |

### team-lead Rule#0 live value-diff
✅ S13 all 6 cards + toggle/Chạy + constrained button + limit footer (console 0); TopBar badge=6 (was 5); idle-hunter flagged real idle repos, market-poll polled (5 persisted), morning-pull cross-module summary ($63,422), pattern-check abandon-orthogonal PROVEN (health=dead project NOT flagged), toggle persists, wrapper-refactor no-regression on market/wiki, FE UI run round-trip (Chạy → runs++ → refetch). PASS, pre-greenlit.

### Tester T4 (PENDING API+Chrome — their lane)
pytest 575 (incl divergent pattern-check teeth) + API + Chrome value-by-value.

---

## 3. The 3 Quality Gates

### Gate 1 — API
☑ Schema (RoutineInfo frozen, Literal trigger/lastResult) · ☑ integration tests · ☑ existing pass · ☑ auto-discovered · ☑ envelope · ☑ codes (404 unknown, 200-even-on-deps-down-run, PATCH toggle) · ☑ self-describing (run_log stats merged into RoutineInfo).

### Gate 2 — Function
☑ unit tests (each routine algorithm on a fixture; **pattern-check divergent teeth — health=dead-but-not-90%-0-user IGNORED, health=act-90%-0-user FLAGGED**; fail-soft wrapper; toggle persists; manual run records) · ☑ pytest 575/0 + vitest 310/0 · ☑ edge cases (empty run_log, 0 projects, deps-down run, unknown id) · ☑ error path (fail-soft per-routine) · ☑ tsc clean · ☑ FE Chrome self-verify · ☑ scheduler tested via direct func-invoke (never a real timer).

### Gate 3 — Sprint
☑ end_sprint_10A written · ☑ architect 4-step (full functions + live container) · ☐ **tester T4 API+Chrome — PENDING** · ☑ counts ≥ baseline (pytest 544→575, vitest 295→310) · ☑ findings flagged (§5) · ☑ format `feat(sprint-10A)`.

**VERDICT: backend + FE GREEN. Gate 3 holds on tester T4 + team-lead pre-greenlit → commit on T4 report.**

---

## 4. Assumptions (user-review — decide-and-log)

- **idle-hunter = projects lastDays>7 & not-abandoned** (N=7). NOT health. To change: edit N or the rule.
- **pattern-check = progress≥90 & users==0 & not-abandoned — NOT health=dead** (the abandon-orthogonal rule — the build-to-90 detector on progress+users, not commit-age). To change: would re-introduce the health-trap; don't.
- **journal-nudge = event** (rung-hit → nudge), a catalog entry not a scheduler-timer Routine (the dataclass is interval/cron/date only — backend's sensible deviation). To change: add an event-trigger type.
- **morning-pull = pull projects+finance+market + record a SUMMARY run** this sprint, NOT brief-assembly (S11 Brief isn't built — it'll consume/extend this). To change: S11 wires the brief output.
- **Toggle persisted to md_store** `automation/toggles.md` (survives restart — the 3B mount lesson). To change: different store.
- **"Routine mới" = constrained affordance** (note, not a builder) — the mock's own "~6 routine, KHÔNG marketplace" copy backs it. To change: build a rule-builder (against the design intent).
- **TopBar badge = live activeCount** (automation only); the other 3 sidebar badges stay static (wiring all 4 = the separate shell task in `sidebar-badges-static-placeholder`).
- **Wrapper fail-soft per-routine** — a routine raising records an error run + does NOT crash the scheduler/others.

---

## 5. Risks / out-of-scope (future)

- **S10B Activity/S14** — the run_log VIEW (this sprint produces the data; S10B shows it). Next.
- **Custom routine creation** — deferred (constrained affordance); a real rule-builder needs a guarded UI (against the anti-marketplace intent).
- **journal-nudge live event wiring** — the func + direct-invoke test exist; wiring it to fire on a REAL market-poll rung-hit (vs simulated) is a small follow-up.
- **Container flap** — recurring (BE foreground exits → HTTP-000); team-lead owns keeping the stack up + a restart-policy proposal for the Sync.
- **The other 3 sidebar badges static** — the shell-task to wire all 4.

---

## 6. Retro (process learnings)

1. **abandon-orthogonal health-trap caught by the read-first-memory net (the headline) — proven on real data:** backend reached for `health=="dead"` on idle-hunter/pattern-check; the memory in its `## Read first` + my review closed it; the real store's health=dead-but-not-90%-0-user project IS the distinguishing-case proof (`verify-with-the-distinguishing-case` applied to a routine). **The read-first-memory rule is the FIRST net — and this sprint is why the user made it a per-dispatch hard gate.**
2. **Built ON existing infra** — Rule#0 at kickoff found the scheduler/Routine/run_log already existed → S10 wired routines onto it instead of rebuilding. Always Rule#0-check for existing infra before assuming greenfield.
3. **Wrapper consolidation refactor** — all 6 routines onto one `record_routine_run` (fail-soft + run_log in one path), deduping the prior per-routine manual record_run. One change-surface for the run-record contract.
4. **Split (10A/10B) held** — run_log must exist (10A) before the activity feed (10B); independently shippable; 10A ships the active engine, 10B the view.

---

## 7. Commit
- `feat(sprint-10A): automation module (S13) — 6 rule-based routines on a run-record wrapper + toggle/run + S13 screen + live TopBar badge` — automation module + 4 routines + wrapper + routines page + useRoutines + TopBar badge + plan_10 + end_10A. One commit.
- Gated on tester T4 + team-lead pre-greenlit. After: `sleep 120 && git push` → notify user → Sprint Sync → S10B.
