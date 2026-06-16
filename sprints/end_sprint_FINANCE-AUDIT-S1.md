# End Sprint FINANCE-AUDIT-S1 — q-engine cadence-aware freshness (Q1+Q2+Q3)

> Status: **REVIEWED — 3 gates green, committing.** Task #59. Commit hash: see `git log`. A REAL-BUG fix from the dogfood audit: freshness rewarded a stamped-today mock 4.6× over real lagged FRED data.

## What shipped (one fix, 3 parts)
- **Part 1 — cadence-aware freshness:** `CADENCE_LAG_DAYS` config map (one place, per-indicator: cpi/fed/unemployment 30d, m2/INDPRO 45d [FRED ~6wk lag], yield/dxy/F&G/btc.d 1d). `_freshness` subtracts the indicator's cadence: `age_effective = max(0, age − cadence_lag.get(name, 0))` → `exp(-age_effective/τ)`. An on-time indicator (within cadence) → freshness ~1.0; overdue-beyond-cadence → still drops (the brakes). An UNREGISTERED name → cadence 0 → `exp(-age/τ)` exactly as before (the byte-identical guard). [Q2 per-indicator τ bundled here.]
- **Part 2 — thread the indicator NAME:** `confidence_q(..., indicator_name=None)` → QInput.name → `_freshness` cadence lookup. `macro/service._confidence_for(..., indicator=None)` passes the indicator key (additive, defaulted).
- **Part 3 — mock EXCLUDED everywhere (team-lead LOCKED=A):** `confidence_q`'s `present = (value is not None) and (source != "mock")` — a mock counts as NOT covered (present:false) → coverage 0 → q 0, SAME as q_from_points. Fixes the Q3 two-tool inconsistency (macro_overview ↔ macro_cycle now agree). A mock is the ABSENCE of real data; never raises confidence.

### Verified counts (architect re-ran independently — Rule #0)
- test_decision + macro + p1: **76 passed, 0 errors**.
- Full suite: **1611 passed, 6 skipped, 0 failed, 0 errors** (was 1604; +7 S1 tests).
- mypy: `decision/service.py` + `macro/service.py` **clean**.
- team-lead LIVE-verified: CPI conf 0.5834 (was 0.21), DXY mock conf 0.0 (was 0.99), M2 conf 0.3539 (was 0.079) — inversion GONE. `_freshness` direct: cpi on-time 30d→1.0, cpi overdue 90d→0.135, synthetic cadence-free→0.90 (GATE1).

## ⚠️ INTENDED CONSEQUENCE (flag for the user's re-verify — NOT a regression)
**q_macro / q_cycle are LOWER now** than before S1, because mock indicators (DXY + yield-curve were fail-open mock) no longer inflate them — excluding mock DROPPED COVERAGE (from 4/4 toward real-only), so q honestly reflects only the real axes. **This is the fix working — "q moves because the MEASURE was fixed," exactly what the user wanted.** It is via the COVERAGE number, NOT a hidden floor (tested: 2-real+2-mock → coverage exactly 0.5, presentInputs 2). The tower was over-confident on mock; it now reports honest confidence.

## Code review (architect — 4-step, against the adjusted GATE1 contract)
1. **git status/diff** — files STABLE (>2min; backend-2 silent-after-done → stability-checked first). 4 files: decision/service (cadence + mock-exclude), macro/service (the seam passes indicator + excludes mock), test_decision (GATE1 rename + 7 S1 tests), test_finance_assistant_p1 (the mock-conf assertion TIGHTENED to ==0.0). `template/`+`data/` excluded.
2. **Read full functions:**
   - **GATE1 byte-identical (the adjusted contract):** GATE1 inputs renamed to cadence-FREE `axis_a/b/c/d` (NOT in CADENCE_LAG_DAYS), with a comment "do NOT rename to cpi/yield_curve". The 0.45 assert is the SAME absolute-age math (`exp(-3.16/30)=0.90 × 0.5 × 1.0`). The rename is cosmetic-to-the-computation — contract PRESERVED, not weakened. ✅
   - **The cadence teeth-test has BOTH arms (the "không tháo phanh" spine):** GATEa on-time cpi 30d → conf >0.95; GATEc overdue cpi 90d → `overdue < 0.2` (0.135) AND `overdue < on_time`. A blanket-floor would pass on-time but FAIL overdue. TEETH-Y. ✅
   - **Mock excluded in BOTH tools (Q3):** confidence_q `present = ... and source != "mock"` (overview) == q_from_points' rule (cycle). Both exclude mock now. ✅
   - **Coverage-not-floor:** GATEe asserts `coverage == 0.5` + `presentInputs == 2` (the NUMBER, not just "q lower"). ✅ GATEf all-mock → coverage 0, q 0, no crash. ✅
3. **Verify against plan + adjusted checklist** — cadence map per-indicator, mock=A excluded, byte-identical via cadence-free rename, teeth-y distinguishing, coverage-not-floor. ✅
4. **Hunt additional issues** — none. The p1 assertion change TIGHTENS (mock conf `== 0.0`, was the loose `0 < q ≤ 1` I'd flagged in the P2 review) — this audit fix actually closes that looseness. `_confidence_for`'s new `indicator` param is defaulted (additive, callers safe).

## Assumptions (user-review)
- **Cadence-aware freshness (`CADENCE_LAG_DAYS` map)** — freshness measures lag vs the indicator's publication cadence, not absolute age. On-time real → high; overdue real → still drops. **Why:** a monthly indicator is naturally ~30-46d old at publication; absolute-age punished it like stale data (the bug). **How to change:** the cadence map.
- **Mock EXCLUDED everywhere (A)** — a mock indicator → present:false → coverage 0 → q 0, in BOTH macro_overview + macro_cycle. **Why:** a mock is the absence of real data; it must never raise confidence (the 4.6× inversion). **How to change:** the `source != "mock"` guard.
- **GATE1 inputs renamed to cadence-free names — the 0.45 contract is PRESERVED** (same absolute-age math; the "cpi" name was a coincidence). **Consequence:** q_macro/q_cycle are honestly lower (mock no longer inflates) — INTENDED, not a regression.

## The 3 Quality Gates
- **Gate 1 — API:** ☑ macro confidence response unchanged in shape (values honestly change) · ☑ no auth · ☑ NEUTRAL · ☑ fail-open (all-mock → honest-empty, no crash). **PASS**
- **Gate 2 — Function:** ☑ (a) CPI on-time → ~1.0 · ☑ (b) mock < real, mock==0 · ☑ (c) DISTINGUISHING overdue-90d → 0.135 < 0.2 (the teeth-y spine) · ☑ (d) GATE1 0.45 byte-identical (cadence-free rename) · ☑ (e) coverage-not-floor (coverage 0.5 asserted) · ☑ (f) all-mock honest-empty · ☑ existing tests pass (1611) · ☑ **0 errors** · ☑ mypy clean. **PASS**
- **Gate 3 — Sprint:** ☑ end doc w/ verified counts + the intended-q-drop flag · ☑ architect spot-checked full functions vs the adjusted contract · ☑ counts ≥ baseline · ☑ team-lead LIVE-verified · ☑ assumptions logged (3) · ☑ commit format. **PASS**

## Risks / follow-ups
- q_macro/q_cycle lower post-S1 is INTENDED (mock-deflation via coverage) — flagged above for the user's re-verify.
- **Next: Sprint 2 (s_asset reads held assets, Q6+Q7)** — point s_asset at the user's held assets' technicals so the tower can light up, WITH the hard acceptance that the W=0 valve survives (a holding with no real RSI → s_asset contributes 0; ALL missing → W still 0; no path lights the tower on empty signal).
- Process: backend-2 finished but did not SendMessage a report (silent-after-done, 2nd time) — verified solid 3 ways (disk + team-lead live + this review). The op-model silent-report gotcha.
