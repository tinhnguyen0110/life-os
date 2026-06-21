# end_sprint_74-TEST-ACTIVITY-TESTCLIENT — kill the test_activity flake at the root (Cairn #74)

> Result. The 15 test_activity API tests that hit a LIVE `:8686` server via `requests` (skip-guarded + flaky → #58 marked them `slow` → they vanished from the DEFAULT suite, MASKING the flake) are converted to in-process `TestClient(app)`: fast, deterministic, no live server, running in the DEFAULT suite again. The 2 value-by-value tests that asserted REAL S10A run_log rows now SEED their own rows + assert against the seed (a TestClient app starts with an EMPTY db — a naive convert would make them vacuous). Commit `<hash>` `fix(test): test_activity requests→TestClient (kill flake at root, seed-preserve distinguishing power)`. Status: ✅ verified (backend-w3 built; architect 4-step + independent teeth + suite re-run). The ROOT fix #58's slow-marker only masked — un-holds the suite from a live-server dependency.

## What shipped (1 test file — test-only, NO prod code)
| File | Change |
|---|---|
| `backend/tests/test_activity.py` (+126/−124) | Section B: 15 `@pytest.mark.slow` API tests `requests.get/post(f"{BASE}/...")` → `app_client.get/post("/...")` (in-process `TestClient`). The module-scoped `server` skip-fixture + `_server_up()` + `BASE` + the lazy `requests` importorskip → REMOVED, replaced by a function-scoped `app_client` fixture (canonical `test_automation_api.py` pattern). All 15 slow markers dropped. +1 NEW distinguishing test (`test_api_successrate_all_ok_is_100`). Section A service units + Section C Chrome stubs UNTOUCHED. |

## Design (LOCKED — seed-then-assert, one shared db, distinguishing power preserved)
- **`app_client` fixture** = `create_app()` + monkeypatch `settings.data_dir`/`db_path`(tmp)/`scheduler_enabled=False`/`project_repos={}` + `db.DB_PATH=None` + `db.close_db()`, wrapped in `with TestClient(app) as c`. Scheduler OFF (routines register but never fire); empty project_repos (no real repo scan).
- **The db-sharing correctness (THE risk):** `app_client` sets `settings.db_path`; `db.DB_PATH=None` so `_db_path()` honors `settings.db_path`; Section A's `_seed` → `db.record_run` writes to that SAME isolated db once the app is up. App reads + seed writes resolve to ONE db file → seeded rows appear in `GET /activity`. (The trap a naive convert hits: app and seed on different dbs → empty feed → vacuous pass. Avoided.)
- **Seed-then-assert (the 2 real-data tests, value-by-value NOT vacuous):**
  - `test_api_get_activity_real_s10a_rows` — seeds a market-poll OK + an idle-hunter WARN; asserts `len(runs)==2` (exact), `routine_ids=={"market-poll","idle-hunter"}` (exact set), full ActivityRun shape, AND newest-first (idle-hunter @+10s → `runs[0]`).
  - `test_api_idle_hunter_warn_has_detail` — seeds 1 idle-hunter WARN with an exact detail string; asserts `len==1` + exact detail round-trip.
- **Non-vacuous everywhere:** filter/byRoutine/get-by-id tests SEED rows + assert `runs`/`by` non-empty before the `all(...)`/field checks (the old `if runs:` guards that could pass on an empty feed are gone). `successrate_is_percentage` now seeds 4 ok + 1 warn → asserts exactly 80.0 (distinguishing vs a fraction 0.8).

## Verification (Rule#0 — architect independent, not just backend's report)
- **architect 4-step (read FULL functions):** read the `app_client` fixture + all 16 API tests + `_iso`/`_seed` helpers. db-sharing CORRECT (settings.db_path honored, single db) ✅; the 2 teeth tests SEED + assert exactly (not `>=0`) ✅; no remaining `requests.*` (grep 0) ✅; 0 real `@pytest.mark.slow` (anchored `grep -nE '^@pytest\.mark\.slow'` = 0) ✅; Section A/C untouched ✅.
- **architect independent teeth-proof:** patched out the 2 seeds → `real_s10a_rows` + `idle_hunter_warn_has_detail` BOTH went RED (2 failed); restored → 2 passed. Real distinguishing power, NOT vacuous. (Did NOT trust backend's teeth report — re-ran it.)
- **architect independent suite re-run:** `test_activity.py` alone = 44 passed / 6 skipped (Chrome stubs) / 0 failed, in-process, NO `:8686` needed. DEFAULT suite (`-m 'not slow'`) FORWARD = **2095 passed / 6 skipped / 3 deselected / 0 failed** (the 15 now IN default). REVERSE-order (`ls tests/test_*.py | tac`) = **2095 passed / 6 skipped / 3 deselected / 0 failed** (identical to forward → no isolation leak, coheres #73/#79). INCLUSIVE (`-m ""`) = 2098 (per backend; the +3 are pre-existing non-activity slow tests).

## 3 Gates
- **Gate 2 (Function):** unit tests assert observable behavior (seeded rows round-trip through the real router); edge cases (404/422/garbage-lenient) kept; teeth-proven (seed-revert→RED); 0 errors/0 unhandled in the suite tail; DEFAULT 2095/0 forward+reverse. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent teeth + independent suite re-run; counts ≥ baseline (2079→2095 default, the 15 moved in + 1 new); commit-hygiene (staged set = EXACTLY test_activity.py, `git diff --cached --name-only` checked); commit format `fix(test):`. ✅

## Assumptions (user-review)
- test_activity API tests run in-process via TestClient against an isolated tmp db (no live `:8686`), seeding run_log rows where they assert real data. **How to change:** the `app_client` fixture / the per-test `_seed` calls.
- Seeded timestamps use small POSITIVE offsets (`now + Ns`) for ordering — harmless (relative ordering only; `range=today` spans the day). **How to change:** the `started_offset`/`finished_offset` args.

## Notes
- Cairn #74 — the ROOT fix for the test_activity flake that #58's `@pytest.mark.slow` only MASKED. backend-w3 built; architect 4-step + committed (§3 sole-committer). The 15 live-server tests are now fast in-process default tests with their distinguishing power PRESERVED (seed-then-assert, teeth-proven). Un-holds #78 consideration (the suite no longer carries a live-server dependency for these). Next: #35/#36 batch (team-lead queues).
