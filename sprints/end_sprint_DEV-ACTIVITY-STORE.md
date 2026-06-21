# end_sprint_DEV-ACTIVITY-STORE — lastScanned freshness + no-scan-yet + regression-pin (Cairn #77)

> Result. The dev_activity GET already store-reads (~5ms, NOT a 24s re-scan — the dispatch premise was wrong, backend Rule#0-flagged + architect verified). #77 delivers the REAL gaps the intent covered: honest `lastScanned` freshness + a "no scan yet" warning + a regression-pin that LOCKS the fast store-read. Commit `<hash>` `fix(sprint-DEV-ACTIVITY-STORE)`. Status: ✅ all gates pass. backend-w3 BUILT; architect 4-step + committed (§3). Refined-scope (no no-op).

## The premise correction (Rule#0, implementer-corrects-architect)
The dispatch said "GET /dev_activity re-scans 24s on every call → make it store-read." Backend FLAGGED (with evidence) that get_overview ALREADY reads `store.rows_since` (NOT scan()); GET = ~5ms; the 24s is the cold SCAN (POST /scan + the daily routine, the write path) — correct. architect verified independently (get_overview docstring "does NOT scan"; scan() only in POST/routine; GET route = store-read). So the headline change was ALREADY shipped (#63-P1). #77 was refined to the genuine gaps — NOT a no-op.

## What shipped (the refined scope — 5 files)
| File | Change |
|---|---|
| `store.py` | +`get_last_scanned()` + a scan_meta row (record the most-recent scan ts on each scan()). |
| `service.py` | scan() stamps last_scanned (the write path records freshness). |
| `schema.py` | +`lastScanned: str \| None` on DevActivityOverview (additive — re-announced; honest None when never-scanned). |
| `reader.py` | get_overview surfaces lastScanned + the `never_scanned` detection (last_scanned None AND row_count 0) → a "no scan yet — POST /dev_activity/scan or wait for the daily routine" warning when roots ARE configured (distinct from the "roots not set" case). Still NO scan-on-read. fail-soft. |
| `tests/test_dev_activity.py` | +the freshness/honesty/regression tests. |

## Design (LOCKED — honest freshness, lock the fast-read)
- **lastScanned** = honest freshness so the agent/UI knows how stale the board is (None when never-scanned).
- **"no scan yet" vs "roots not set"** — two DISTINCT honest-empty causes (never-scanned-but-configured → "scan now"; not-configured → "set roots"). So honest-empty isn't misread as "no activity".
- **the regression-pin** — `test_never_scanned_honest_empty_warning` + `test_scanned_empty_is_not_never_scanned` (the distinguishing: scanned-empty SETS lastScanned + NO "no scan yet"; never-scanned → None + the warning) + `test_mcp_dev_activity_includes_lastScanned` (MCP≡REST). These LOCK the already-correct fast store-read (no auto-scan-on-read) against silent regression.

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step (read full settled files):** the premise-correction verified (GET store-reads, no scan() in the read path) ✅; lastScanned from store.get_last_scanned ✅; never_scanned = last_scanned None AND row_count 0 ✅; the no-scan-yet warning distinct from roots-not-set ✅; fail-soft (store error → honest-empty + warning) ✅; the regression-pin tests are real teeth (scanned-empty ≠ never-scanned the distinguishing) ✅; dev_activity-only surface (no cross-lane leak — #75-TWEAK tracing files separate).
- **backend-w3 evidence:** the freshness/no-scan-yet/regression tests; mypy clean; DEFAULT suite 0-failed (architect's full-suite run corroborates). LIVE: POST /scan stamps lastScanned → GET fast (store-read) + carries lastScanned; empty store → "no scan yet" warning.

## 3 Gates — ALL PASS
- **Gate 1 (API/MCP):** lastScanned additive (re-announced); honest-empty distinguishes never-scanned vs not-configured; MCP≡REST carries lastScanned (#24). ✅
- **Gate 2 (Function):** the freshness + the regression-pin (scanned-empty ≠ never-scanned, no-scan-on-read locked); DEFAULT 0-failed; mypy clean. ✅
- **Gate 3 (Sprint):** plan(via dispatch)+end docs; architect 4-step + backend evidence + live; dev_activity-only surgical stage; commit format; the premise-correction reconciled (refined-not-no-op). ✅

## Assumptions (user-review)
- GET /dev_activity (REST + MCP) serves FROM the store (~5ms) — already true since #63-P1; #77 adds honest `lastScanned` + the never-scanned-vs-not-configured warning distinction + the regression-pin. The 24s only happens on the WRITE path (POST /scan + the daily routine). **How to change:** the reader / the scan_meta.

## Notes
- Cairn #77. The dispatch premise ("GET re-scans 24s") was WRONG — backend's Rule#0 flag (the implementer-corrects-architect direction) + architect's independent verify caught it; refined to the real gaps (lastScanned + no-scan-yet + the regression-pin) instead of a no-op. backend BUILT; architect committed (§3). dev_activity-only (separate from the #75-TWEAK tracing-camel + #75-FE, committed after, arrival-order). The agent-first win: the MCP consumer reads the board fast + KNOWS its freshness. Next: [#75-TWEAK + #75-FE joint] → #73 → #64.
