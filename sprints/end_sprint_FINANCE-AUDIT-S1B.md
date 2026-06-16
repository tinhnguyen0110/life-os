# End Sprint FINANCE-AUDIT-S1B — macro_cycle cadence consistency (close the half-fix)

> Status: **REVIEWED — 3 gates green, committing.** Task #61. Reactive sprint (same theme as S1). Commit hash: see `git log`. Closes the cadence half-fix the user's re-verify caught.

## What shipped (the surgical fix)
S1 made freshness cadence-aware via `confidence_q` (macro_overview), but macro_cycle's `_axis` passed the AXIS LABEL ("growth"/"inflation") as the QInput.name → freshness looked up cadence by the label → not in CADENCE_LAG_DAYS → absolute-age. So the SAME CPI had freshness 0.58 (overview) vs 0.21 (cycle). The fix:
- `_axis_q_input` += `indicator_name: str | None = None` → `QInput(name=(indicator_name or name))` — keys the cadence lookup on the INDICATOR (cpi/industrial_production/unemployment/yield_curve_10y2y), not the axis label.
- `_axis(name, indicator, ...)` passes its `indicator` through (`_axis_q_input(..., indicator_name=indicator)`).
- **CLEAN SEPARATION:** `CycleAxis.axis` STAYS the axis label (growth/inflation — display unchanged); only the internal QInput.name (cadence key) → indicator. REUSE CADENCE_LAG_DAYS (no new map). `macro_cycle.paramsUsed.tauSeconds` → per-indicator.

### Verified counts (architect re-ran independently — Rule #0)
- test_decision + macro: **72 passed, 0 errors**.
- Full suite: **1623 passed, 6 skipped, 0 failed, 0 errors** (was 1618; +5 S1B tests), 1 benign httpx deprecation warning.
- mypy: `decision/service.py` **clean**.
- team-lead LIVE-verified: macro_overview CPI freshness 0.5826 == macro_cycle cpi-axis freshness 0.5826 (was 0.58 vs 0.21) — IDENTICAL; q_cycle 0.143→0.5144 (measure-fixed); GATE1 0.45 byte-identical.

## ⚠️ q_cycle ROSE — because the MEASURE was fixed (flag for the user, inverse of S1's q-drop)
q_cycle went 0.143 → ~0.514 — NOT because of new data, but because CPI (and the other monthly axes) are no longer punished as stale in macro_cycle (cadence now applies there too, matching macro_overview). The cross-tool inconsistency the user caught is closed. This is the fix working — the same "q moves because the MEASURE was fixed" the user wanted, here raising q_cycle (S1 lowered q_macro by excluding mock; S1B raises q_cycle by fixing the cadence half-miss). Both are honest measure-corrections.

## Code review (architect — 4-step, the cross-tool match + brake + macro_overview-unchanged hardest)
1. **git status/diff** — files STABLE (>2min; backend-2 silent-after-done → stability-checked). 4 files: decision/service (the threading), test_decision (6 S1B tests), plan + end_sprint. `template/`+`data/` excluded.
2. **Read full functions:**
   - `_axis_q_input(..., indicator_name=None)` → `QInput(name=(indicator_name or name))`. The cadence lookup keys on the indicator when given. ✅
   - `_axis` passes `indicator_name=indicator` (it already had `indicator`). ✅
   - **`CycleAxis(axis=name)` UNCHANGED** — the display label stays growth/inflation; only the internal QInput.name changed (the clean separation — display ≠ cadence key). ✅
3. **Verify against plan + the 4 acceptance gates** — cross-tool match, q_cycle-rose-flag, brake-in-cycle, macro_overview-unchanged + GATE1. ✅
4. **Hunt additional issues — the teeth verified:**
   - **GATE1 cross-tool match (the user's spine):** `assert abs(overview_cpi − cycle_cpi) < 0.02` AND `cycle_cpi > 0.5`. Asserts the two tools AGREE on the same CPI's freshness — NOT just "cycle rose." ✅
   - **GATE3 brake in macro_cycle:** a CPI 90d overdue → `cpi_fresh < 0.2` in macro_cycle's breakdown. The "không tháo phanh" survives the cycle path. ✅
   - **GATE4 macro_overview unchanged + GATE1 0.45 byte-identical:** confidence_q untouched (S1 result identical); GATE1 `test_GATE1_q_cycle_045` passes alongside (72/72). Only the `_axis` path changed (additive). ✅
   - paramsUsed per-indicator (dedicated test). ✅

## Assumptions (user-review)
- **macro_cycle freshness is now cadence-aware via indicator-name threading.** `_axis` threads the indicator (cpi/industrial_production/etc) into the QInput so the cadence lookup keys on the indicator, not the axis label. REUSES CADENCE_LAG_DAYS (no duplicate map). `CycleAxis.axis` display label unchanged. **Why:** S1 left macro_cycle on absolute-age (the half-fix); the two tools must agree on the same indicator's freshness. **How to change:** the `_axis_q_input` cadence-key / CADENCE_LAG_DAYS.
- **q_cycle rose because the MEASURE was fixed** (cadence now applies in macro_cycle), NOT new data — 0.143→~0.514. The cross-tool inconsistency is closed.

## Note for the user (s_asset "0/6" — a SEPARATE data-capture gap, NOT this sprint)
The user asked why s_asset is "0/6 held assets with real technicals." Answer: the held coins (PEPE/ICP/ARB/S/TRUMP/IP) are OKX value-only positions that **lack price-HISTORY depth (no OHLC series in the market store yet)** — so there's no RSI-able series to compute a technical from. This is a downstream **data-capture gap (OHLC-history-for-holdings)**, NOT a bug: S2's plumbing is correct (it reads the real holdings; the GATE4 distinguishing test proves a held symbol WITH a real series → s_asset > 0). The tower lights up as the held-coins' price-history accumulates — no code change. **A future sprint candidate** (capture/backfill OHLC history for held symbols) if the user wants s_asset non-zero sooner — flagged, not folded into S1B.

## The 3 Quality Gates
- **Gate 1 — API:** ☑ macro_cycle/macro_overview response shapes unchanged (freshness values now consistent) · ☑ no auth · ☑ NEUTRAL · ☑ fail-open. **PASS**
- **Gate 2 — Function:** ☑ CROSS-TOOL match (overview CPI ≈ cycle CPI freshness, the spine) · ☑ brake in macro_cycle (90d overdue → <0.2) · ☑ macro_overview S1 unchanged · ☑ GATE1 0.45 byte-identical · ☑ paramsUsed per-indicator · ☑ existing tests pass · ☑ **0 errors** · ☑ mypy clean. **PASS**
- **Gate 3 — Sprint:** ☑ end doc w/ verified counts + the q_cycle-rose flag + the user s_asset note · ☑ architect spot-checked full functions · ☑ counts ≥ baseline · ☑ team-lead LIVE-verified · ☑ assumptions logged (2) · ☑ commit format. **PASS**

## Risks / follow-ups
- **The cadence work is now COMPLETE + consistent:** both macro_overview AND macro_cycle are cadence-aware, agree on the same indicator's freshness, exclude mock, and keep the overdue-real brake. The user's cross-tool inconsistency is closed.
- **s_asset "0/6"** = the OHLC-history-for-holdings data-capture gap (above) — a separate future candidate, not a bug.
- Process: backend-2 silent-after-done (4th time) — verified solid 3 ways. The op-model silent-report gotcha is now a persistent pattern worth a process note.
