# end_sprint_DECISION-AGREEMENT — fix the structurally-dead q_cycle (Cairn #13)

> Result. Dogfood-R4 #1 blocker: the decision tower's headline verdict was permanently "blind". Commit: `<hash>` (filled at commit). Status: ✅ all 3 gates pass.

## Objective (met)
`life_brief.decision.verdict` = "blind" in EVERY mixed Investment-Clock phase — the agent's single "how hard can I bet" verdict was dead-on-arrival. Fixed: q_cycle now lights up (W>0, verdict actionable) WITHOUT removing the genuine-no-data W=0 valve.

## Root cause (confirmed at code + live)
`_axis_q_input` passed a SIGNED DIRECTION CODE as the `compute_q` `value` ({up:+1, down:−1, flat:0}); `compute_q` computed `agreement = 1 − dispersion(present values)`. In overheat (growth↑+1 / inflation↑+1 / yield_curve↓−1) the values diverge → max dispersion → agreement≈0 → q_cycle = freshness×coverage×0 = 0 → W=∏q=0 "blind". **Category error:** sign-divergence of the phase axes is what DEFINES an Investment-Clock phase (4 phases exist BECAUSE growth & inflation diverge) — it's SIGNAL, not data-disagreement. So sign-dispersion is structurally ~0 in every non-trivial phase.

## Fix (option B — closed-enum agreement mode, cycle-only scope)
For the CYCLE's `compute_q` call ONLY, agreement = data-consistency (1.0 when present), NOT sign-agreement; the cycle's trust rests on freshness × coverage (which still brake). Implementation:
- `DEFAULT_Q_PARAMS["agreement"] = "dispersion"` (default = today's behavior) + `_AGREEMENT_MODES = ("dispersion", "neutral")`.
- `_resolve_params` resolves `agreement_mode` (closed enum; unknown → dispersion; echoed in `params_used`) → 5-tuple.
- `compute_q`: `if agreement_mode == "neutral": agreement = 1.0` else the original 1−dispersion path UNCHANGED.
- `macro_cycle()` (L429) — the ONLY call passing `params={"agreement":"neutral"}`.
- B over A (drop the dir-code value): keeps the direction-code VISIBLE in the breakdown (transparency) + uses the locked `params` plumbing (no contract break).

## Valve preserved (the spine — "không tháo phanh")
The W=0 brake now lives ENTIRELY in coverage (mock/missing axis → coverage<1, 0 if all gone) + freshness (genuinely stale → ↓). agreement was never the right brake for the cycle. A clamp/floor would have removed the valve; this removes only the spurious sign-penalty.

## Verification (Rule #0 — re-run, not trusted)
- **architect direct trace (venv):** A FIX overheat → qCycle.q **0.7572** (was 0.0), agreement 1.0, coverage 1.0, paramsUsed.agreement=neutral; W **0.1196**, verdict **"thin"** (not blind), binding=q_macro (genuinely dimmest), weight≠confidence True. B VALVE neutral+all-missing → q **0.0** (brake via coverage survives neutral). C SCOPE default dispersion caller, divergent {+1,−1} → agreement **0.0** (dispersion intact for non-cycle). D ENUM unknown mode → dispersion fallback, no crash.
- **architect pytest:** test_decision.py + test_macro.py → **88 passed, 0 failed, 0 errors**. Full suite 1662→**1671** (+9, backend-reported, team-lead-confirmed).
- **scope grep:** ONLY `macro_cycle`'s cycle call (L429) passes `agreement:"neutral"`; the other 6 q-engine call-sites (q_from_points ×3, confidence_q, nav compute_q ×2) pass no agreement param → default dispersion, byte-identical.
- **team-lead live (Rule#0):** /decision/weight → weight 0.1197 verdict "thin" not "blind", binding q_macro, qCycle.q 0.7573 agreement 1.0 paramsUsed.agreement="neutral", weight 0.12 ≠ confidence 0.60; compute_q([],needed=3,neutral) → 0.0 valve.
- **tester:** 3-case script (A/B/C + weight≠confidence + no-advice-verb + divergent-default-dispersion scope) — green (see tester report).

## Code review (architect 4-step)
1. diff — 68+/24− in decision/service.py + test_decision.py.
2. read FULL compute_q agreement block + _resolve_params closed-enum + macro_cycle L429 + QResult echo — traced entry→exit.
3. vs plan — option B exactly, cycle-only, valve via coverage/freshness, weight≠confidence + NEUTRAL intact.
4. hunted — scope grep confirms cycle-only; enum-fallback safe (unknown→dispersion, no eval); valve survives neutral (coverage brake); GATE5 single-source AST stays green (the L429 comment dodges the banned-words trap); no edge missed.

## 3 Gates — ALL PASS
- **Gate 1 (API):** /decision shape unchanged (paramsUsed +additive agreement key); integration tests green. ✅
- **Gate 2 (Function):** 3-case distinguishing test both directions + scope + enum-fallback; 88 pass/0 err; valve edge proven; closed-enum no free-eval; real divergent-case asserts. ✅
- **Gate 3 (Sprint):** end-doc w/ verified counts; full-function spot-check; team-lead + architect Rule#0 both directions; counts ↑ (+9); commit format. ✅

## Assumptions (user-review)
- **cycle q agreement = data-consistency (neutral 1.0 when present), NOT phase-axis-direction-agreement** — divergence DEFINES the phase (signal, not noise); the valve lives in coverage/freshness. Scoped to the cycle compute_q call; q_macro / confidence_q dispersion UNTOUCHED. **How to change:** drop the `agreement:"neutral"` param from the cycle call → reverts to sign-dispersion (the bug returns). The flag is a closed enum in _resolve_params; default = today's behavior for all other callers.

## Locked contracts intact
q = freshness×coverage×agreement (just agreement≠sign-dispersion for the cycle); W=∏q no-clamp; weight≠confidence; NEUTRAL gate; compute_q single-source (AST/grep green).
