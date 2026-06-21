# Sprint SUITE-SPEED — faster default test run + flake-kill (Cairn #58)

> Reactive NEVER-FREE fill-lane (team-lead-raised). Backend test-infra only — ZERO prod change. Mark the slowest live-network tests `@pytest.mark.slow` (opt-in via `-m slow`), default-deselect them, and remove redundant `importlib.reload(main)` from app fixtures. backend-w3 BUILT; architect commits (§3). Disjoint from #65-P4 + #72 + a11y.

## Context
The default `pytest` run was 262s, with a recurring flake (test_activity's 15 live-:8686 API tests, 7-failed intermittently). Root: ~16 fixture files redundantly `importlib.reload(main)` (~600× create_app setup) + a handful of live-network tests (life_brief pulls macro/news/CoinGecko ~8s, ego_graph perf).

## Scope
IN: `backend/pyproject.toml` (markers + addopts) + 18 `@pytest.mark.slow` marks (test_activity, test_wiki, test_brief_reminders) + reload-removal from 15 app-fixture files (+ their unused `import importlib`). LEFT test_mcp_http.py's reload (it tests main itself — intentional).
OUT: the <60s target (real fix = fixture-scope refactor → #73; test_activity → TestClient → #74). NO prod code, NO frontend.

## Logic (test-config only, reversible)
- `[tool.pytest.ini_options]`: `markers = [slow: ...]` + `addopts = -m 'not slow'` → default deselects the slow set; the gate runs inclusive via `-m ""`.
- mark the 18 slowest/flakiest tests `@pytest.mark.slow`.
- remove redundant `importlib.reload(main)` (the app fixture already builds a fresh app per test via create_app — the reload was double-work).

## Verification (architect 4-step + backend evidence)
- **backend-w3:** DEFAULT 262→211s (−19.5%); flake ELIMINATED (test_activity 7-failed→0 in default, now slow-marked opt-in); INCLUSIVE (`-m ""`) 2008 passed / 6 skipped / 0 failed — ZERO coverage lost (the coverage-guard); marker registers (no unknown-marker warning); all 16 touched fixture files green after reload-removal; test_mcp_http.py reload intentionally KEPT.
- **architect:** content-diff each #58 file (ONLY slow-marks + reload-removal + pyproject — NO brief/tracing/P4 content leaked in); the INCLUSIVE gate green WITH P4 coexisting (my own run: 2018/0/0 = 2008 + 10 P4); the <60s honest gap accepted + tracked (#73/#74).
- **<60s NOT met** (211s = distributed ~600× create_app setup, not an outlier) — honest gap, team-lead accepted + opened #73 (fixture-scope) + #74 (test_activity→TestClient). NOT in this commit.

## 3 Gates — PASS
- **Gate 2 (Function):** INCLUSIVE 2008/0/0 (zero coverage lost); flake killed; coverage-guard (default-deselect + inclusive-gate both proven); marker registers. ✅
- **Gate 3 (Sprint):** docs; backend evidence + architect content-diff (no cross-lane leak from the intermixed tree); commit format; reversible test-config only. ✅

## Assumptions (user-review)
- **default `pytest` = `-m 'not slow'`** (fast dev loop); the CI/gate runs INCLUSIVE (`-m ""`) — full coverage preserved, slow tests opt-in. 18 tests slow-marked (live-network + perf). **How to change:** the addopts / the marks.
- **<60s deferred** to #73 (fixture-scope refactor) + #74 (test_activity→TestClient) — 211s is the honest current state, not the target. **How to change:** those follow-ups.

## Notes
- Cairn #58. Reactive NEVER-FREE fill-lane. backend-w3 BUILT; architect commits fix(sprint-suite-speed). Committed from an INTERMIXED tree (P4/#72/a11y also done) — surgically staged #58-only (content-diff vs the others). Follow-ups #73/#74 for the real <60s.
