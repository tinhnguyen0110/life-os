# Sprint DECISION-AGREEMENT — fix the structurally-dead q_cycle (Cairn #13, dogfood R4 #1)

> Created 2026-06-21 by architect. HIGH — the decision tower's headline verdict (life_brief.decision.verdict) is permanently "blind". Touches LOCKED finance-arc contracts — team-lead sanity-checked + APPROVED the semantic (option B, cycle-only).

## The bug (confirmed at code + live)
`life_brief.decision.verdict` = "blind" in EVERY mixed Investment-Clock phase. Live (overheat): W=0.0, q_cycle=0.0 (freshness 0.7575 × coverage 1.0 × **agreement 0.0**), other 3 layers healthy (q_macro .51, q_flow .58, s_asset .53), bindingConstraint=q_cycle.

**ROOT (decision/service.py:314-331, 385):** `_axis_q_input` passes a SIGNED DIRECTION CODE as the `compute_q` `value` (`{up:+1, down:−1, flat:0}`). `compute_q` then computes `agreement = 1 − dispersion(present values)` (coefficient of variation). In overheat the cycle values are `{+1(growth↑), +1(inflation↑), −1(yield_curve↓)}` → max dispersion → agreement≈0 → q_cycle = freshness×coverage×0 = 0 → W=∏q = 0 "blind". 

**The category error:** for the cycle, `agreement`-as-sign-dispersion asks *"do the phase axes point the same direction?"* — but **axes diverging in direction is what DEFINES an Investment-Clock phase** (4 phases exist precisely because growth & inflation diverge). So sign-dispersion is structurally ~0 in every non-trivial phase → q_cycle dead-on-arrival. Direction codes `{+1,+1,−1}` are categorical signals, not comparable magnitudes you take CoV over; the divergence is SIGNAL, not data-disagreement.

## The fix (DECIDED — option B, team-lead approved)
For the CYCLE's `compute_q` call ONLY, agreement reflects **data consistency** (each present axis is its own internally-consistent real reading → agreement=1.0 when present), NOT sign-agreement of the phase axes. The cycle's trustworthiness comes ENTIRELY from **freshness × coverage** (which already correctly handle stale→freshness↓, missing/mock→coverage↓).
- **Implementation = option B:** pass `params={"agreement":"neutral"}` (or the equivalent existing param flag) to the cycle's `compute_q([indpro_qi, cpi_qi, yc_qi], needed=3, params={...})` so agreement is forced to 1.0, computed from freshness×coverage only. B over A (drop the dir-code value) because B keeps the direction-code VISIBLE in the QResult breakdown (transparency) + uses the locked `params` plumbing (self-documenting, no contract break).
- **SCOPE: the cycle compute_q call ONLY.** Do NOT touch compute_q's global agreement formula — `q_macro` (q_from_points) + the macro-confidence seam (confidence_q) use value-dispersion across SAME-KIND readings where dispersion IS real disagreement. Review must confirm no other compute_q caller's agreement changes.
- The param flag must be a CLOSED enum addition to `_resolve_params` (like the existing `combine` enum) — never a free-eval. Default unchanged = byte-identical to today for every existing caller.

## Valve preserved (the spine — "không tháo phanh")
The W=0 brake now lives ENTIRELY in coverage (mock/missing axis → coverage<1 → 0 if all gone) + freshness (genuinely stale → ↓). agreement was never the right brake for the cycle. A fix that just floored/clamped W would remove the valve — this does NOT; it removes a spurious penalty and lets the real brakes (coverage/freshness) do their job.

## Tasks
- **T1 (backend, gating):** add the `agreement:"neutral"` mode to `_resolve_params`/`_combine`-or-`compute_q` (closed enum, default unchanged) + pass it from the cycle's `compute_q` call in `macro_cycle()`. Write the 3-case distinguishing test (below). `docker compose restart backend` (decision/service.py IS hot-reloaded — but main.py isn't; restart to be safe for the live curl). Backend writes the pytest.
- **T2 (tester):** verify the 3 cases LIVE on the container — real overheat phase → W>0 verdict NOT "blind" (re-GET /decision/weight); force mock/missing cycle → W=0 "blind" still; partial → honest-reduced. Confirm weight≠confidence still distinct + NEUTRAL (no advice verb) intact.
- **T3 (architect):** 4-step review + commit. (No docs change — internal q semantic.)

## HARD GATE (the 3-case distinguishing test — both directions, in the test file)
- **A (bug fixed):** overheat (or any phase) + full + fresh cycle axes → q_cycle ≈ freshness×coverage (e.g. ~0.7575) → W > 0 → verdict NOT "blind".
- **B (valve preserved):** cycle axes ALL mock/missing → coverage 0 → q_cycle 0 → W=0 "blind" STILL fires. ← a lazy "always W>0" fix FAILS this.
- **C (partial honest):** 1/3 cycle axes present → coverage 0.333 → q_cycle honest-reduced (not 0, not full).
Plus: weight≠confidence still two distinct numbers; NEUTRAL gate (no should/buy/sell/deploy verb) intact; existing decision-tower + the LOCKED q-engine distinguishing tests (L58 stale-data, W=∏q-no-clamp) still green.

## Baseline
pytest 1662 passed / 6 skipped / 0 failed (post-#1; #2 MCP-URL runs parallel in different files). Keep 0-failed; expect +3 (the 3 cases).

## Assumptions (user-review)
- **cycle q agreement = data-consistency (neutral 1.0 when present), NOT phase-axis-direction-agreement** — divergence DEFINES the phase (signal, not noise); the valve lives in coverage/freshness. Scoped to the cycle compute_q call; q_macro / confidence_q dispersion UNTOUCHED. **How to change:** drop the `agreement:"neutral"` param from the cycle call → reverts to sign-dispersion (the bug returns). The flag is a closed enum in _resolve_params; default = today's behavior for all other callers.

## Notes
- LOCKED contracts intact: q = freshness×coverage×agreement (just agreement≠sign-dispersion for the cycle); W=∏q no-clamp; weight≠confidence; NEUTRAL.
- Separate theme from #2 MCP-URL (decision/service.py vs main.py/MCP) — no file conflict, both run.
