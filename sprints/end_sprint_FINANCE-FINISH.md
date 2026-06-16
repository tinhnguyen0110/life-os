# End Sprint FINANCE-FINISH — wire the decision tower into life_brief + allocation_target optional capital

> Status: **REVIEWED — 3 gates green, committing.** Task #57. Commit hash: see `git log`. The finish piece — the finance-assistant is now fully wired end-to-end (one life_brief call = data + tower + policy + proactive).

## Source
The dogfood quality round over the complete finance-assistant (team-lead, 2026-06-16) — graded well, surfaced 2 real gaps. Both backend-only, additive, pure wiring.

## What shipped (G1 + G2)
- **G1 — life_brief folds the decision tower (the 9th section):** `_brief_decision()` composes the ALREADY-IMPORTED tower fns read-only → `{weight, verdict, bindingConstraint, phase, topGuardianAlert}` (weight/verdict/bindingConstraint ← decision_weight; phase ← macro_cycle; topGuardianAlert ← the highest-severity guardian alert's msg, or None — honest-empty). Added `"decision": _section("decision", _brief_decision)` to life_brief (the 9th, per-section fail-soft via the existing helper). Docstring updated. NEUTRAL (verdict band / state label / question — no advice).
- **G2 — allocation_target optional capital:** `allocation_target(capital: float | None = None, ...)` — when None, defaults to the live portfolio value (`fin.get_overview().totalValue`); an explicit capital overrides (a what-if). Fail-open if the portfolio is unreadable.

### Verified counts (architect re-ran independently — Rule #0)
- mcp_read + decision + mcp_e2e: **137 passed, 0 errors**.
- Full suite: **1604 passed, 6 skipped, 0 failed, 0 errors** (was 1596; +8 G1/G2 tests).
- mypy: `read_server.py` + `decision/service.py` + `decision/router.py` **clean**.
- team-lead LIVE-verified: life_brief 9 sections incl. `decision` {weight:0.0, verdict:"blind", bindingConstraint:"s_asset", phase:"overheat", topGuardianAlert:"crypto 98% stablecoin while F&G 23 — intentional?"}; no-advice-verb on the WHOLE brief = none; allocation_target() no-arg → totalValue ($10.6k → tier small, crypto 41%/dry 19%).

## Code review (architect — 4-step, the NEUTRAL re-check + additive-doesn't-perturb hardest)
1. **git status/diff** — files STABLE (>2min old, not in-flight — verify-after-write-settles). 6 files: read_server (the section + the allocation wrapper), decision/service (the capital default), decision/router, test_decision + test_mcp_read + test_mcp_e2e (the section-set consumer), 2 sprint docs. `template/`+`data/` excluded.
2. **Read full functions:**
   - `_brief_decision()` composes `_decision_weight()`/`_decision_macro_cycle()`/`_decision_guardian()` READ-ONLY; `top_alert = alerts[0].msg if alerts else None` (severity-ranked, honest-empty). Returns the 5 fields. NEUTRAL.
   - `"decision": _section("decision", _brief_decision)` — the 9th, wrapped in the existing fail-soft `_section` (a tower fn raising → that section `{error}`, the OTHER 8 assemble).
   - G2 service: `if capital is None: overview,_ = fin.get_overview(); capital = float(overview.totalValue)` — the live default; explicit overrides; fail-open.
3. **Verify against plan** — 9th section, fail-soft per-section, NEUTRAL, additive, G2 default-to-totalValue + override. ✅
4. **Hunt additional issues — all 5 hard gates have DEDICATED tests:** `test_G1_life_brief_has_decision_section`, `test_G1_decision_section_failsoft_keeps_other_8` (per-section fail-soft), `test_G1_neutral_recheck_with_decision_section` (the load-bearing re-check — no-advice-verb passes WITH the section), `test_G1_additive_does_not_perturb_portfolio_section` (the 8 unchanged), `test_G2_no_capital_uses_finance_totalvalue` + `test_G2_distinguishing_two_capitals_diverge` (the distinguishing — proves the default isn't ignored) + a `test_G2_no_capital_fail_open_when_portfolio_unreadable` bonus. test_mcp_e2e's expected section SET updated to include "decision" (a real consumer). No gaps.

## Assumptions (user-review)
- **life_brief gains a 9th `decision` section** — the decision tower (W/verdict/bindingConstraint/phase/topGuardianAlert) surfaced on the 1-call agent surface, fail-soft + honest-empty + NEUTRAL. **Why:** the tower was built (P2-P3) but not wired into the synthesis surface the agent reads most (built-but-not-wired-into-synthesis). **How to change:** the `_brief_decision` builder / the life_brief composer.
- **allocation_target capital defaults to finance totalValue** when omitted (was required positional). **Why:** an agent asking "what allocation suits me?" shouldn't need to know its own capital — the live book is the natural default; explicit still overrides for a what-if. **How to change:** the `if capital is None` branch.

## The 3 Quality Gates
- **Gate 1 — API:** ☑ life_brief 9-section shape · ☑ allocation no-arg works · ☑ no auth · ☑ NEUTRAL (no advice verb — re-checked WITH the new section) · ☑ fail-soft per-section. **PASS**
- **Gate 2 — Function:** ☑ 9th section present + correct fields · ☑ fail-soft per-section (other 8 intact) · ☑ the no-advice-verb re-check passes · ☑ 8 existing sections byte-unchanged (additive-doesn't-perturb) · ☑ G2 default-capital DISTINGUISHING + fail-open · ☑ existing tests pass (1604) · ☑ **0 errors** · ☑ mypy clean. **PASS**
- **Gate 3 — Sprint:** ☑ end doc w/ verified counts · ☑ architect spot-checked full functions · ☑ counts ≥ baseline · ☑ team-lead LIVE-verified · ☑ assumptions logged (2) · ☑ commit format. **PASS**

## Risks / follow-ups
- **🏁 The finance-assistant is FULLY WIRED end-to-end:** one `life_brief` call now surfaces data + tower (W/phase) + policy (via the standalone allocation tool) + proactive (top guardian alert). The dogfood-found synthesis gap is closed.
- Process note: backend-2 finished the work but did NOT send a SendMessage report this turn (silent-after-done). The disk state + team-lead's Rule#0 live verify + this independent review confirm it's complete and correct — but the missing report is the silent-stall pattern (op-model §) worth noting. No work lost.
- Stale agents (the prior-config architect/backend/frontend/tester) were USER-ordered terminated this turn; only architect-2 / backend-2 / team-lead remain. Task #57 reassigned to backend-2 cleanly; frontend's GLOBAL-GRAPH T2 already committed (db8cf2f), nothing lost.
