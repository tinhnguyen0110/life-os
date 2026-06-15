# End Sprint FINANCE-MCP-SHAPE — finance_analytics over MCP + warnings DRY refactor

> Status: **REVIEWED — 3 gates green, committing.** Task #50. Commit hash: see `git log` (this is the sprint-FINANCE-MCP-SHAPE commit).

## Objective (recap)
The REST `/finance/analytics` (rebalance + risk/HHI + returns) wasn't an MCP read tool → the agent couldn't read it. And the `gp_warnings + price_warnings` assembly was duplicated verbatim across `get_overview` + `get_channel`. Backend-only: add the MCP wrapper + DRY the warnings source (output byte-identical).

## Scope decisions (architect kickoff + team-lead rulings)
- **CLAIM 1 (finance_analytics MCP) — BUILT.**
- **CLAIM 2 (warnings) — (b) shared-helper refactor**, NOT a strip. The kickoff consumer grep found `brief/reader.py:49` reads `overview.warnings` → stripping would break the brief synthesis surface. So DRY the SOURCE; every tool keeps emitting its full self-contained list; output BYTE-IDENTICAL.
- **CLAIM 3 (finance_summary) — SKIPPED** (overview already returns totalValue/change/pnlTotal/dryPowder; a 4th overlapping read = over-engineering, north-star).

## What shipped
- **`mcp_servers/read_server.py`** — `finance_analytics()` MCP read tool (mirrors `finance_simulate`: aliased-private `_fin_analytics` import → no-write capability gate auto-holds; wraps `_with_warnings(_fin_analytics(), "analytics")`; neutral docstring). Registered in TOOLS (40→41).
- **`modules/finance/service.py`** — `_finance_warnings(holdings)` helper returns `(targets, ladder_cfg, by_channel, gp_warnings + price_warnings)` — the shared prefix. `get_overview` (L601) + `get_channel` (L704) rewired to call it. `simulate` + `get_analytics` UNTOUCHED (divergent — confirmed not in diff). Output byte-identical.
- **`tests/test_finance_mcp_shape.py`** (NEW) — analytics callable + envelope + neutral + capability-gate-no-write-leak + count-41 + the BYTE-IDENTICAL warnings behavior test on a RICH fixture (gp-absent + 2 cost-fallback + 4 drift warnings → asserts `list ==` against the captured pre-refactor baseline `_BASE_OVERVIEW`, for overview/analytics/channel/simulate).
- **count-bump consumers** (all real, tied to finance_analytics): `tests/test_mcp_read.py` (2 asserts 40→41), `tests/test_mcp_http.py` (stdio count 40→41), `mcp_servers/CATALOG.md` (totals 50→51 + the new row), `docs/MCP-CONFIG.md` (totals 40/50 → 41/51 — team-lead's edit, included per their instruction).

### Verified counts (architect re-ran independently — Rule #0)
- MCP-shape + finance trio (`test_finance_mcp_shape` + `test_mcp_read` + `test_finance` + `test_finance_enrichment`): **171 passed, 0 errors**.
- Full suite: **1540 passed, 6 skipped, 0 failed, 0 errors** (1528 baseline + 12 new = 1540), 1 benign httpx deprecation warning.
- mypy: `read_server.py` + `finance/service.py` **clean**.
- team-lead LIVE-verified: TOOLS=41, finance_analytics present + envelope `{analytics, warnings}` w/ analytics={totalValue,rebalance,risk,returns,asOf}; capability gate green (test_mcp_read 93 passed, no write leak); byte-identical warnings test present. The pre-existing okx-isolation flake fails identically pre-refactor → NOT a regression.

## Assumptions (user-review)
- (none new — this sprint adds no business rule. The CLAIM 2 design decision (DRY-source not strip, because the brief consumes overview.warnings) + CLAIM 3 skip are scope calls, logged here for the record, not algorithm assumptions.)

## Code review (architect — 4-step, full functions)
1. **git diff** — read_server +17 (import + wrapper + TOOLS entry), service +27/-15 (helper + 2 rewired sites), 4 count-bump consumers, new test file. `template/`+`data/` excluded.
2. **Read full functions** — `finance_analytics` is a faithful mirror of `finance_simulate` (gate-safe). `_finance_warnings` returns exactly `gp_warnings + price_warnings`; the 2 call-sites substitute it inline. `get_channel` now calls `list_holdings()` ONCE (was twice) + reuses `holdings` — deterministic, so output identical (minor efficiency win). simulate + get_analytics confirmed UNTOUCHED in the diff.
3. **Verify against plan** — CLAIM 1 built, CLAIM 2=(b) byte-identical, CLAIM 3 skipped, count 40→41, gate auto-holds. ✅
4. **Hunt additional issues** — none. The byte-identical test uses a RICH multi-warning fixture (not empty/aligned — would pass against a broken refactor otherwise). Count-bump consumers all legit. No consumer breakage (brief warnings flow unchanged — the refactor changes the SOURCE path, not the output).

## The 3 Quality Gates
- **Gate 1 — API:** ☑ finance_analytics wraps an existing read path, response `{analytics, warnings}` · ☑ no auth · ☑ capability gate (no-write AST/namespace) green unchanged · ☑ no module mutation. **PASS**
- **Gate 2 — Function:** ☑ analytics tests assert observable behavior + envelope · ☑ byte-identical warnings BEHAVIOR test (rich fixture, list ==) · ☑ existing tests pass (full suite) · ☑ **0 errors** (full tail read) · ☑ edge: empty portfolio → zeroed/None · ☑ mypy clean · ☑ no self-confirming asserts. **PASS**
- **Gate 3 — Sprint:** ☑ end doc w/ verified counts · ☑ architect spot-checked full functions · ☑ counts ≥ baseline · ☑ team-lead LIVE-verified (final gate, no separate tester for no-UI sprint) · ☑ out-of-scope flagged (count-bump consumers documented) · ☑ commit format. **PASS**

## Risks / follow-ups
- The MOUNTED `/mcp/read/mcp` HTTP server needs `docker compose restart backend` to LIST finance_analytics (read_server isn't hot-reloaded under the HTTP mount) — the REST + harness + tests already confirm the code; the restart is only for the live HTTP tool-list. Noted, not a blocker.
- Next sprint: WRITE-LOOP-E2E (the propose→accept→land agent loop, never exercised end-to-end).
