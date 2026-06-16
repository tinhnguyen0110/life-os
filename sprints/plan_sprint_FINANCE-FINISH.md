# Sprint FINANCE-FINISH — wire the decision tower into life_brief + allocation_target optional capital

**Task #57. Source:** the dogfood quality round over the complete finance-assistant (team-lead, 2026-06-16) — graded well (per-coin pnl A, guardian A, tower A−, nav A) but surfaced 2 real gaps. Backend-only, additive.

## Kickoff — 2026-06-16 (verified the _section pattern + the tower tools + neutrality)

### G1 (HIGH VALUE) — life_brief omits the decision tower → wire it in (built-but-not-wired-into-SYNTHESIS)
- `life_brief` (read_server.py:891 — the 1-call surface the agent reads MOST) composes 8 sections via `_section("source", _brief_<x>)` (fail-soft helper at L764: builds, tags `source`, on exception → `{source, error}`, the brief still assembles). The 8: portfolio/market/projects/claude/decisions/macro/news/wiki.
- The decision tower (P2-P3) — decision_weight, macro_cycle, finance_guardian — is NOT in it. **Built but not wired into the synthesis surface** (the SAME class as the round-2 SYNTH gap that added macro/news/wiki). An agent calling life_brief doesn't see W/verdict/phase/top-alert.
- **The tower tools are ALREADY imported into read_server** (`_decision_weight`/`_decision_macro_cycle`/`_decision_guardian`, L86-91) + exposed as standalone MCP tools. So G1 = compose them into a 9th `_section` — the fns are right there.
- **NEUTRAL — verified zero risk:** decision_weight's `verdict` is `_verdict(weight)` = a single descriptive word `"strong"/"moderate"/"thin"/"blind"` (NO advice verb; the existing P3 `test_GATE4_decision_weight_neutral_no_advice_verb` already gates it). phase (macro_cycle) + the guardian top alert (questions) are already NEUTRAL. So the new section carries no advice-verb risk; the no-advice-verb test on life_brief still passes.

### G2 (small UX) — allocation_target forces `capital` positional
- `allocation_target(capital: float, *, phase=None, monthly_add=0.0, horizon_years=3.0)` (service.py:515) — `capital` is REQUIRED. An agent asking "what allocation suits me?" can't call it without knowing capital.
- FIX: `capital: float | None = None` → when None, default to `finance_overview.totalValue` (data already there — `get_overview().totalValue`). An explicit capital still overrides.

## Phase scope (proposed — pending team-lead approval)
- **G1:** add a `_brief_decision()` builder composing `{weight, verdict, bindingConstraint, phase, topGuardianAlert}` from `_decision_weight()`/`_decision_macro_cycle()`/`_decision_guardian()`; add `"decision": _section("decision", _brief_decision)` to life_brief (the 9th section). Fail-soft (one tower tool down → {error}, brief still assembles); honest-empty (no data → null/empty fields, no fabrication). Update the life_brief docstring (add the 9th section line). NEUTRAL (no advice verb — the bands/phase/alert are already neutral).
- **G2:** `allocation_target` capital → optional, default to finance_overview.totalValue; explicit overrides. + the MCP wrapper `_decision_allocation` mirrors (no-arg → totalValue).
- **Tests:** G1 — life_brief has the 9th `decision` section (weight/verdict/bindingConstraint/phase/topGuardianAlert); fail-soft (tower down → {error}, other 8 intact); NEUTRAL (no-advice-verb on the whole brief STILL passes); the 8 existing sections byte-unchanged (additive doesn't perturb). G2 — no-capital → uses totalValue; explicit capital → overrides (DISTINGUISHING: two different capitals → different tilt, proving the default isn't ignored).

## Risks / seams
- NEUTRAL on the new decision section — the load-bearing gate (verified the source data is already neutral, but the life_brief no-advice-verb test must still pass with the section added).
- Don't perturb the 8 existing sections (behavior-test one unchanged) or the tower (the decision tools are READ-only here, composed not modified).
- G2 default-capital DISTINGUISHING: no-arg uses totalValue, explicit overrides → two capitals give different tilts (proves the default is real, not ignored).
- Fail-soft: a tower tool erroring must not break life_brief (the `_section` pattern already handles it — the new builder just needs to be wrapped in `_section`).
- After this: an agent gets the FULL assistant (data + tower + policy + proactive) in ONE life_brief call.

### Locks (team-lead, 2026-06-16 — approved as drafted, no tweaks)
- G1: 9th `decision` section via the existing `_section` fail-soft pattern → {weight, verdict, bindingConstraint, phase, topGuardianAlert}. tower down → that section {error} + the OTHER 8 intact (per-section fail-soft, NOT whole-brief). **The life_brief no-advice-verb test STILL passes WITH the section added (load-bearing re-check).** The 8 existing sections byte-unchanged (additive-doesn't-perturb behavior test). NEUTRAL (verdict=descriptive band, not advice — verified safe at source).
- G2: capital optional → defaults to finance_overview.totalValue; DISTINGUISHING test (no-arg uses totalValue; explicit different-capital → different tilt, proving the default isn't silently ignored/hardcoded).
- Both pure wiring, no decide-and-log.

### Routing / sequencing
Dispatched to **backend-2**. backend-2 done → team-lead live-verifies (life_brief decision section with real W/phase/top-guardian; allocation no-arg works) → architect review+commit+push. **After this the assistant is fully wired end-to-end — one life_brief call = data + tower + policy + proactive.**
