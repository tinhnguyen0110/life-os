# End Sprint FINANCE-ASSISTANT Phase 4 — finish the foundation (nav_history reader + compute_q params)

> Status: **REVIEWED — 3 gates green, committing.** Task #56. Commit hash: see `git log`. The final foundation piece — the finance-assistant is now fully complete + calibration-ready.

## What shipped (T1-T3)
- **T1 — nav_history reader:** a `/decision/nav-history` (+ MCP tool, count 45→46) reader over the EXISTING `portfolio_snapshot` table (NO new table — the spec's `nav_snapshots` maps onto it: day=date, total_value=nav). Returns `{series:[{date, nav}], points, range:{from,to}, warning, confidence}` with `?from&to`. confidence via the shared compute_q (coverage = points / `NAV_POINTS_FOR_TREND`). Fail-open: empty → `{series:[], points:0, confidence:0}` + warning, no crash. NEUTRAL.
- **T2 — compute_q param-ization:** `compute_q(inputs, *, needed, params=None) -> QResult` += `params={tau (SECONDS), weights, combine}` + `paramsUsed` echo. `DEFAULT_Q_PARAMS` in ONE place. `params.tau` accepts the spec's SECONDS, converts to internal DAYS (the engine stays days-based → byte-identical to P2). combine = CLOSED 3-enum (multiply default / min / weighted_geomean), an unknown → multiply (never free-eval). `_resolve_params(None)` → exactly the defaults.
- **T3 — tests:** the 5 hard gates + tau-conversion + combine-modes + nav-empty/scales/range/neutral.

### Verified counts (architect re-ran independently — Rule #0)
- test_decision + finance + mcp_read: **176 passed, 0 errors**.
- Full suite: **1596 passed, 6 skipped, 0 failed, 0 errors** (was 1585; +11 decision/nav tests), 1 benign httpx deprecation warning.
- mypy: `modules/decision/*` **clean**.
- team-lead LIVE-verified: 0.45 byte-identical (test_decision GATE1 unchanged), min≠multiply (live multiply 0.45 vs min 0.5), nav_history 1 real point ($10652.31, confidence 0.0321 honest-low + short-series warning), paramsUsed present.

## Code review (architect — 4-step, hardest on the additive-must-not-perturb constraint)
1. **git diff** — 9 files: decision (service/schema/router/MCP), read_server/CATALOG, test_decision + 3 count-bumps, 2 sprint docs. `template/`+`data/` excluded.
2. **Read full functions — the #1 check (default = old path, byte-identical):**
   - `DEFAULT_Q_PARAMS["tau"]` = `TAU_DAYS × 86400` (seconds); `_resolve_params` converts back `tau_sec / 86400` → exactly `TAU_DAYS`. A `None`/`{}` params → the defaults → byte-identical. ✅
   - `_freshness(age_days, data_type, tau_days=None)` — `None → TAU_DAYS` (the exact old path). ✅
   - `_combine` multiply fall-through (last line) = `return freshness * coverage * agreement` — the byte-identical default; `min` → `min(f,c,a)`; `weighted_geomean` → normalized weighted geomean (0-component → 0). CLOSED enum (the `_resolve_params` guard forces combine ∈ the 3; unknown → multiply, never free-eval). ✅
   - **The P2 call-sites (macro_cycle/decision_weight) are UNCHANGED in the diff** → they call compute_q with default params → byte-identical. The only NEW call-site is the nav reader's own (`compute_q(qinputs, needed=NAV_POINTS_FOR_TREND)`). ✅
   - nav reader REUSES `portfolio_snapshot` (no new table); nav = total_value. ✅
3. **Verify against plan** — tau=(a) seconds-in/days-internal, combine-closed-enum, params_used always, reuse-table, defaults=current, 5 hard gates. ✅
4. **Hunt additional issues — all 5 hard gates have DEDICATED tests:** `test_P4_GATEa_default_params_byte_identical`, `test_P4_GATEb_min_differs_from_multiply` (distinguishing), `test_P4_GATEc_params_used_always_present`, `test_P4_GATEd_macro_cycle_unchanged_on_default_params` (the P2-surface byte-unchanged — the additive-must-not-perturb proof), `test_P4_GATEe_nav_matches_snapshot_rows`. Plus tau-conversion, combine-each-mode, nav-empty/scales/range/neutral. Comprehensive; no gaps.

## Assumptions (user-review)
- **compute_q `params.tau` accepts SECONDS (spec §2.5), converts to internal DAYS; defaults byte-identical to P2.** The engine stays days-based; `DEFAULT_Q_PARAMS.tau` = `TAU_DAYS × 86400` so the default round-trips exactly. `paramsUsed.tauUnit = "seconds-in/days-internal"` (transparency). **Why:** zero P2 risk (the 0.45 L58 contract stays byte-identical) while the param surface speaks the spec's seconds. **How to change:** to go internally-seconds, re-derive `TAU_DAYS` (would risk the 0.45 rounding — not done).
- **`NAV_POINTS_FOR_TREND = 30`** — the coverage denominator for nav confidence (a ~monthly series is "enough" for a trend). Few points → low confidence. **Why:** a short NAV series can't support a trend claim; 30 ≈ a month of daily points. **How to change:** the constant.
- **combine = CLOSED 3-enum (multiply default / min / weighted_geomean), unknown → multiply fallback, NO free-eval.** **Why:** safety — never eval an arbitrary formula passed from outside; the 3 modes are each unit-tested. **How to change:** add a mode to `_COMBINE_MODES` + `_combine` + a test.
- **MCP tool count 45→46** (nav_history).

## The 3 Quality Gates
- **Gate 1 — API:** ☑ /decision/nav-history + the MCP tool response-shaped · ☑ no auth · ☑ NEUTRAL (data + confidence) · ☑ fail-open (empty → 0+warning, no crash) · ☑ capability gate auto-holds. **PASS**
- **Gate 2 — Function:** ☑ 0.45 byte-identical on defaults (GATEa — the L58 contract holds) · ☑ min≠multiply DISTINGUISHING (GATEb) · ☑ params_used always (GATEc) · ☑ P2 surface byte-unchanged on defaults (GATEd — additive doesn't perturb the tower) · ☑ nav matches snapshot (GATEe) · ☑ existing tests pass (full suite) · ☑ **0 errors** · ☑ mypy clean · ☑ combine closed-enum (no free-eval). **PASS**
- **Gate 3 — Sprint:** ☑ end doc w/ verified counts · ☑ architect spot-checked full functions (the default=old-path + the P2-unchanged) · ☑ counts ≥ baseline · ☑ team-lead LIVE-verified · ☑ assumptions logged (4) · ☑ commit format. **PASS**

## Risks / follow-ups
- **🏁 The finance-assistant FOUNDATION is COMPLETE:** data (P1) → state + weight (P2) → policy + reward + proactive (P3) → nav reader + tunable compute_q (P4). nav_history's time-asymmetric accumulation runs daily (CAGR/drawdown/volatility become computable as the series fills); compute_q is calibration-ready (params tunable once a NAV series + backtest exist).
- **NEXT (team-lead): a dogfood quality round** over the complete assistant — a blank-context consumer over allocation/guardian/decision_weight/macro_cycle/nav_history/per-coin-pnl, tracing weak answers to missing data (the north-star "what's missing" trick).
- Process note: the arc memory `finance-assistant-arc-2026-06-16` lives in the user auto-memory dir (`~/.claude/projects/.../memory/`, written by team-lead) — the correct shared location. The architect-local `backend/.claude/agent-memory/` path from the playbook did not persist; the shared dir is authoritative.
