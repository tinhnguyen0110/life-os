# Sprint DXY-REAL — let real FRED DXY show (never persist mock) — Cairn #15, dogfood-R4 GAP-2

> Created 2026-06-21 by architect. Live-first kickoff CORRECTED the scope (the DTWEXBGS probe found the wiring already works). Awaiting team-lead "yes corrected" before dispatch.

## Scope correction (live-traced — the key kickoff finding)
The Cairn task says "wire real DXY via FRED DTWEXBGS." **That wiring is ALREADY done + working** — verified live INSIDE the container: `core/config.py` maps `dxy→DTWEXBGS`; `reader.fetch_latest('dxy')` → 12 pts, source='fred', 119.5073, no warning; DTWEXBGS CSV is real (5336 rows) + shape matches the existing FRED reader. Building "wire DTWEXBGS" would re-build the already-built thing.

## The REAL bug (row-level trace)
`/macro/overview` shows **dxy source='mock', asOf 2026-06-16, change 0, confidence 0** because `get_overview` reads `store.recent('dxy', limit=2)` newest-first, and the stored rows are:
`[(121.7552, mock, 06-16), (121.7552, mock, 06-15), (119.5073, fred, 06-12)]`
→ the two NEWEST are MOCK → it reports mock. Those mock rows were PERSISTED by `refresh()` with a today-ts on days FRED was transiently unreachable from the container. The real monthly FRED row (06-12) is OLDER, so it sits below and can never surface — **a fresh `refresh()` does NOT fix it** (verified on the container: 84 pts written, 0 warnings, DXY rows unchanged; the real point dedups at its monthly ts 06-12 < the frozen mock 06-16).

**Bug class:** `refresh()`/`record_point` persists mock into the time-series with a today-ts that shadows real data — violating the LOCKED "mock = absence of real data, never counts" philosophy (S1 mock-excluded). Affects ANY FRED indicator on a transient outage, not just DXY.

## The fix (DECIDED — decide-and-log; team-lead sanity-check requested)
**Mock must NEVER be persisted into the time-series.**
1. In `macro/service.refresh()` (and any other `record_point` call-site that can receive a mock-sourced point — grep them), SKIP `store.record_point` when `source == 'mock'`. A failed fetch records NOTHING; the prior real point stands; confidence/freshness already brake on staleness honestly. (Matches S1 mock-excluded: a mock is the ABSENCE of data — it must not enter the series.)
2. **One-shot purge** of the existing stuck mock rows: delete `source='mock'` rows from macro_history (a `store` helper or a guarded one-shot) so the live container immediately surfaces the real FRED DXY. Idempotent / safe (only removes mock rows; real rows untouched).
3. The `_mock_points` reader fallback STAYS for the cold-start/never-fetched display case (get_overview's auto-refresh on empty), but it must not be PERSISTED — mock is for display-on-empty only, never stored as an observation.

## Tasks
- **T1 (backend, gating):** skip-persist-mock in refresh() + the snapshot routine (grep all record_point sites; only persist source!='mock') + the one-shot mock purge + tests. `docker compose restart backend` then run the purge (or wire it as a guarded startup/one-shot). Backend writes the pytest.
- **T2 (tester):** live — `/macro/overview` dxy → source='fred', real value (~119.5), change≠0, confidence>0; macro_cycle/q_macro coverage now INCLUDES dxy (was excluded as mock); the DISTINGUISHING negative: force a FRED-fail (e.g. bad series id / network) → NO new mock row persisted, the prior real point remains (not a frozen mock).
- **T3 (architect):** 4-step review + commit.

## HARD GATE (distinguishing — both directions)
- **A (fix):** dxy live → source='fred', confidence>0, change≠0 (NOT the flat-0 mock); it joins the macro axes (coverage includes it → q_macro honestly stronger, synergy with #13).
- **B (no-regression / the spine):** a FRED fetch FAILURE → the series keeps its last REAL point, NO mock row persisted (a test that mocks a fetch failure + asserts the stored series has no new source='mock' row). ← proves we fixed the root (don't-persist-mock), not just purged once.
- mock-on-cold-start display still works (empty series → get_overview still returns numbers, tagged mock, but doesn't persist).

## Baseline
pytest 1671 passed / 6 skipped / 0 failed (post-#13). Keep 0-failed; expect +2-3.

## Purge guard (team-lead lock — touches the LIVE runtime store backend/data)
- Purge ONLY rows where `source == 'mock'` (EXACT match) — never touch source='fred'/real rows.
- Count rows BEFORE + AFTER; assert ONLY mock rows deleted, real-row count UNCHANGED; REPORT the delta (N purged).
- Idempotent / re-runnable (no-op once clean). Surgical — Rule#0 + test-writes-pollute lesson (it's the user's live macro_history).

## Assumptions (user-review)
- **Mock never persisted to macro_history** (S1 mock-excluded extended to the WRITE path — skip record_point when source=='mock'); mock is display-on-empty only. A transient FRED outage → NO row, the prior real point stands (confidence/freshness brake honestly). One-shot purged N stuck source='mock' rows from the live store (real rows untouched, delta reported). **How to change:** to re-allow persisted mock, drop the source!='mock' guard in record_point/refresh — but that re-introduces the frozen-mock-shadows-real bug.

## Notes
- This hardens ALL macro indicators against the freeze, not just DXY (DXY is the symptom).
- LOCKED S1 mock-excluded philosophy reinforced (mock = absence of data) — consistent, not a new contract.
- Same module as scoped (macro/service.py + store.py); no scope creep beyond the root fix.
