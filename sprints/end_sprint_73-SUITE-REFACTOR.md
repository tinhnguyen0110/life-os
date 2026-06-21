# end_sprint_73-SUITE-REFACTOR — suite −34% via env-gated MCP-skip (Cairn #73)

> Result. DEFAULT suite 211→139s (−34%, ~−47% from the original 262s) via a test-only env-gated skip of the 80ms MCP-mount build (64% of create_app) — WITHOUT a session-scope app, so every test still gets a FRESH isolated app (ZERO new leak risk). Commit `<hash>` `fix(sprint-73-suite-refactor)`. Status: ✅ all gates pass. backend-w3 BUILT (a lower-risk approach than the dispatch suggested); architect 4-step + committed (§3). <60s not reached (139s) → #78 (session-scope, risky) follow-up. The reorder gate surfaced a PRE-EXISTING bug → #79.

## What shipped (4 files — test-infra only, ~2-line prod guard)
| File | Change |
|---|---|
| `main.py` | +`import os` + a 2-line guard in `_build_mcp_servers`: `if os.environ.get("LIFEOS_SKIP_MCP_MOUNTS")=="1": skip` (test-only fast path — "never set in prod"). Skips the 80ms MCP-mount build (64% of create_app) → 125→39ms/app. |
| `tests/conftest.py` | +`os.environ.setdefault("LIFEOS_SKIP_MCP_MOUNTS","1")` suite-wide (the REST app-tests don't need the MCP HTTP mounts). |
| `tests/test_mcp_http.py` | the client fixture `monkeypatch.delenv("LIFEOS_SKIP_MCP_MOUNTS")` → its mount tests build the REAL MCP servers (so MCP coverage is unaffected). |
| `tests/test_suite_isolation.py` (NEW) | the isolation distinguishing proof (alpha/beta write-own-marker + fresh-store-empty — symmetric, reorder-safe). |

## Design (LOCKED — cheaper-fresh-app, NOT shared-app; the lower-risk choice)
- backend PROFILED (create_app=125ms/test, _build_mcp_servers=80ms=64%, only test_mcp_http exercises the mounts) → skip the MCP build for the REST app-tests via an env flag. **This is "a cheaper fresh app", NOT "a shared session-scope app"** — every test STILL builds a fresh isolated app (isolated_paths untouched) → ZERO new leak risk. Deliberately chose this over the dispatch's session-scope suggestion (which carried the leak risk the coverage-guard was meant to police). The implementer improving the spec with profiling evidence — the right call (safe win over the risky number).
- prod NEVER sets the flag → prod always builds the full MCP mounts (no behavior change).

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step (read full):** the MCP-skip guard (main.py, prod-never-set) ✅; conftest setdefault + test_mcp_http delenv (MCP coverage preserved) ✅; fresh-app-per-test preserved (no session-scope → no new leak) ✅; the isolation test is real (symmetric write-marker, reorder-safe) ✅; 4-file surface, no cross-lane leak ✅.
- **backend-w3 evidence:** DEFAULT 211→139s (−34%); DEFAULT 2046 passed / 6 skipped / 0 failed (INCLUSIVE 2046+); the isolation distinguishing test green in-order AND reversed; mypy unaffected.
- **team-lead independent verify:** the 3-file change env-gated test-only; not session-scope (fresh app per test); the isolation test reorder-safe; the pre-existing-bug attribution confirmed (#73 touches NO backend finance/basis — the "finance" in the diff was the static template, not the module).

## ⚠️ The reorder gate surfaced a PRE-EXISTING bug (→ #79, NOT #73's)
The dispatch's REORDERED-green gate found: `test_finance::test_overview_with_okx_uses_basis_as_cost` fails under full-suite REVERSE order (a crypto_basis leak from a preceding cross-file test). PROVEN pre-existing (identical fail with the flag OFF; #73 touches no finance state; default fixed-order suite 0-failed). The gate did exactly its job — found a real latent cross-file isolation bug, NOT a #73 regression. → **#79** (the crypto_basis per-test reset fix, test-only, latent).

## Honest gaps (ship-safe-with-honest-gap, per the dispatch)
1. **<60s NOT reached (139s)** — the MCP-skip got the biggest SAFE chunk; the rest (per-test registry mount_all ~39ms × hundreds) needs a session-scope app (the risky path #73 deliberately avoided). → **#78** (session-scope for <60s; depends on #79's isolation fix first). 139s may be good-enough; #78 only if <60s is truly required.
2. The pre-existing reorder-isolation bug → **#79** (above).

## 3 Gates — ALL PASS
- **Gate 2 (Function):** DEFAULT 2046/0 (coverage-guard: same pass count, faster); the isolation distinguishing test (in-order + reversed); the MCP coverage preserved (test_mcp_http builds the real servers). ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + backend profiling-evidence + team-lead verify; the reorder-bug attributed pre-existing (#79) + the <60s gap honest (#78); 4-file surgical stage; commit format. ✅

## Assumptions (user-review)
- DEFAULT `pytest` skips the MCP-mount build (env-gated, test-only — prod always builds them) → 139s. The full MCP servers are still tested (test_mcp_http un-sets the flag). <60s deferred to #78 (session-scope, risky). **How to change:** the flag / #78.

## Notes
- Cairn #73. backend BUILT (lower-risk env-gate, not the risky session-scope); architect committed (§3). 3rd Rule#0 catch this stretch (migration-order #75-BE, #77-premise, now the reorder-attribution) — the isolation gate found a real pre-existing bug + backend attributed it not-#73 WITH proof. Follow-ups: #78 (session-scope <60s, after #79) + #79 (crypto_basis reorder-isolation). Next: #64 (per-repo memory — dispatching to backend now). nav-IA held for user.
