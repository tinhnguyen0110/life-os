# End Sprint FINANCE-ASSISTANT Phase 2 — the decision tower core

> Status: **REVIEWED — 3 gates green, committing.** Task #54. Commit hash: see `git log`. Phase 2 of the finance-assistant arc — the heart (data → "how hard can I bet").

## What shipped (T1-T5)
- **New `modules/decision/` module** (registry auto-discovered — no core edit): `__init__.py · router.py · schema.py · service.py`.
- **T1 — `compute_q` (the ONE q-engine):** `q = freshness × coverage × agreement` (L58 canonical — NOT the L82 mean-q×penalty illustration). freshness = mean over present inputs of `exp(−age/τ)` (τ: spot 5min, macro/cycle/yield 30d, flow 1d); coverage = present/needed; agreement = 1 − dispersion (CV, single value → 1.0). PURE product, nothing hardcoded.
- **T2 — `macro_cycle`:** Investment-Clock phase (growth × inflation) from the macro axes (growth=INDPRO+UNRATE, inflation=CPI, +yield_curve); carries `qCycle = compute_q(axes)`; `mock_is_present=False` so a mock/missing axis lowers coverage honestly (never a fabricated phase). NEUTRAL (favored/defensive = the classic-clock reference map, not advice).
- **T3 — `decision_weight`:** `W = ∏ qᵢ` (q_cycle × q_macro × q_flow × s_asset) PURE PRODUCT, NO inter-layer clamp; `bindingConstraint` = argmin layer; `weight` (∏) and `confidence` (mean layer q) SEPARATE fields. A blind layer → q=0 → W=0.
- **T4 — seam wired:** `macro/service._confidence_for(value, ts, source)` now delegates to `decision.confidence_q` (single-input compute_q) — passing the real `ts` → real freshness. Confidence is now the real q, not the P1 0.9/0.2 source-stub.
- **T5 — tests** (`test_decision.py`, 10) + MCP wrappers (`macro_cycle`/`decision_weight` in read_server, count 41→43) + CATALOG.

### Verified counts (architect re-ran independently — Rule #0)
- decision + macro + p1 + mcp_read: **138 passed, 0 errors**.
- Full suite: **1575 passed, 6 skipped, 0 failed, 0 errors** (was 1565; +10 decision tests), 1 benign httpx deprecation warning.
- mypy: `modules/decision/*` + the macro seam **clean** (zero new errors).
- team-lead LIVE-verified all 5 gates on the container.

## Code review (architect — 4-step, against the L58 contract team-lead locked)
1. **git diff** — 4 new decision files + test_decision.py + read_server/CATALOG (MCP wrappers + count 41→43) + macro/service.py (the seam) + 2 changed P1 test assertions + 3 mcp count-bumps. `template/`+`data/` excluded.
2. **Read full functions:**
   - **compute_q = L58, NOT L82 (the #1 review check):** body is `q = freshness * coverage * agreement` (3-component product). `_freshness` = `exp(-age/τ)` (real, from age). NO `mean(axis_q) × penalty` anywhere. ✅ The 0.45 falls out: 0.9 × 0.5 × 1.0.
   - **The stale-data L58 proof is rigorous (test_decision.py L34-44 + L60-63):** an EXACT-freshness test (`age = -30·ln(0.9)` → asserts freshness ≈0.90 by computation) + the fresh(1.0)-vs-stale(exp(-1)≈0.37) divergence — proving freshness is genuinely IN the product (an L82 impostor that ignores freshness would FAIL these). This is the airtight distinguishing case.
   - **decision_weight ∏ no-clamp:** pure product, bindingConstraint=argmin, weight≠confidence. No `min(qᵢ,q_{i-1})` clamp. ✅
   - **T4 seam:** receives value+ts+source → real freshness via compute_q; signature stable; call-site passes `latest_row["ts"]`. ✅
   - **GATE 5 single-source:** macro_cycle + decision_weight bodies have ZERO freshness/coverage/agreement reimplementation (awk-confirmed empty) — they CALL compute_q; an AST test (`test_GATE5_compute_q_is_the_single_source`) proves it. ✅
3. **Verify against plan** — L58 (not L82), no-clamp, weight≠confidence, honest-missing, single-source, minimal q_flow/s_asset, module (b). ✅
4. **Hunt additional issues — the 2 changed P1 assertions (team-lead's flagged item):** `yc.confidence == 0.9/0.2` → `0.0 < yc.confidence <= 1.0`. **VERDICT: loose-but-NOT-a-regression-mask, and justified.** The change is CORRECT (confidence is now real-q; a fresh-but-mock value genuinely has a real freshness q — honesty is carried by the `source` tag + the warning, both still asserted, NOT by a magic 0.2). The loose range is acceptable BECAUSE the q-MATH is rigorously proven in test_decision.py (exact-freshness + stale-divergence) — these P1 tests only confirm the seam DELEGATES (they still assert source-tag + present + the mock warning). NOTE for the record: a tighter P1 assertion (seed a known-age point → assert confidence ≈ exp(-age/τ)) was possible but redundant given test_decision's teeth; the loose range does not hide a regression because the distinguishing proof lives where the math is.

## Assumptions (user-review)
- **q-engine = L58 canonical (`freshness × coverage × agreement`), NOT the L82 worked-example phrasing** (`mean-axis-q × coverage_penalty`). The spec had both; team-lead locked L58. They coincide at ~0.45 only on the example's numbers — the stale-data test proves the impl is L58. **How to change:** the `compute_q` body (but L58 is the right RL model — freshness must be in the product).
- **Seam semantic change: macro confidence is now real-q (freshness from ts), so `source='mock'` no longer auto-means low confidence.** A fresh-but-mock value gets a real freshness q; honesty is carried by the `source` tag + warning, not the number. **Why sound:** the q-engine is the right model — a fresh mock is genuinely more trustworthy than a stale mock, and the source tag still flags it's mock. (2 P1 tests updated to assert real-q-in-range + the preserved source/warning honesty signals — verified not a regression-mask.) **How to change:** to re-floor mock confidence, gate it in `confidence_q`.
- **Minimal q_flow / s_asset (no market_regime).** q_flow from P1's F&G/BTC.d; s_asset from existing market RSI/trend. A thin flow → low q → honest low W (correct, not a gap). market_regime (gom relative_strength + correlation + dominance) is a Phase-3 candidate. **How to change:** build market_regime when the flow layer needs more fidelity.
- **MCP tool count 41→43** (macro_cycle + decision_weight added).

## The 3 Quality Gates
- **Gate 1 — API:** ☑ /decision/* + macro_cycle/decision_weight MCP tools response-shaped · ☑ no auth · ☑ NEUTRAL (no advice verb — asserted) · ☑ capability gate auto-holds (pure read). **PASS**
- **Gate 2 — Function:** ☑ the §75-83 0.45 FALLS OUT by computation + the stale-data L58 divergence (exact freshness) · ☑ decision_weight ∏ no-clamp DISTINGUISHING (dim-upper×bright-lower < min; zero→0) · ☑ weight≠confidence distinct + dangerous quadrant · ☑ macro_cycle honest-missing · ☑ GATE-5 single-source (AST) · ☑ existing tests pass (full suite) · ☑ **0 errors** · ☑ mypy clean · ☑ the 2 P1 changes verified not regression-masks. **PASS**
- **Gate 3 — Sprint:** ☑ end doc w/ verified counts · ☑ architect spot-checked full functions against the L58 contract · ☑ counts ≥ baseline · ☑ team-lead LIVE-verified all 5 gates · ☑ assumptions logged (4) · ☑ commit format. **PASS**

## Risks / follow-ups
- s_asset is BLIND live (watchlist empty) → W=0 currently — which is the spec's thesis working: weak data = don't bet. When the watchlist fills (or market_regime lands in P3), s_asset lights up and W rises honestly.
- **Phase 3 next:** allocation_target (policy(state)) + finance_guardian (proactive alerts) + decision_journal-finance (the RL reward, wiring the existing decision_entries to finance). The tower (state → weight) now exists; P3 adds policy + the learning loop.
