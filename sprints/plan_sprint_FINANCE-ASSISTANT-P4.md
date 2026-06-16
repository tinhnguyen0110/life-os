# Sprint FINANCE-ASSISTANT Phase 4 — finish the foundation (nav_history reader + compute_q params)

**Task #56. Arc:** Phase 4 of the finance-assistant — additive-COMPLETION of shipped work (spec `finance/docs/build_spec_nav_history.md` §1-2). NOT new build. Backend-only.
**2 tasks:** T1 nav_history reader (the writer + table ship; expose a reader). T2 compute_q param-ization (add params, defaults = current behavior).

## Kickoff — 2026-06-16 (verified the table shape + current compute_q sig)

### T1 — nav_history reader: the writer + table EXIST → expose a reader (reuse, don't recreate)
- **`portfolio_snapshot` table EXISTS** (db.py:67): `day` (PK 'YYYY-MM-DD' UTC → UNIQUE-by-day = idempotent satisfied), `ts`, `total_value`, `by_channel`. The spec's `nav_snapshots` shape maps onto it: day=date, total_value=nav_usd. **Reuse it — do NOT create a new table** (north-star; the spec proposes a table but ours already covers it).
- **Writer ships** (`take_snapshot` finance/service.py:404, wired into morning_pull, accumulating). The spec §1.5 idempotent-by-day is satisfied by the `day` PK upsert; fail-soft-on-null should be confirmed (a null exchange_overview → no junk row).
- **Existing read fn** (db.py:363) supports `since` (a `from` filter) but NOT `to` → T1 adds the `to` bound (small extension or filter in the reader).
- **T1 = a thin reader** mapping `{day, total_value}` rows → `{series:[{date, nav}], points, range:{from,to}, warning, confidence}` with `?from&to`. confidence via compute_q (§1.7: coverage = points / points-needed-for-trend → few points = low confidence). Acceptance §1.7: empty range → `{series:[], points:0, confidence:0}` + warning, NO crash; nav matches total_value (<$0.01).

### T2 — compute_q param-ization: additive, defaults = current behavior (P2 byte-unaffected)
- Current sig (P2): `compute_q(inputs: list[QInput], *, needed=None) -> QResult`. Internal `TAU_DAYS` (days) + `age_days`; combine is hardcoded `freshness × coverage × agreement` (multiply).
- Spec §2.3 wants `params={tau, weights, combine: "multiply"|"min"|"weighted_geomean"}` + echo `params_used`. DEFAULTS must = current behavior so P2 callers (macro_cycle/decision_weight/the macro seam) are byte-unaffected (the 0.45 still falls out).
- combine enum (§2.4): multiply (f×c×a, default), min (weakest link), weighted_geomean (f^wf·c^wc·a^wa). CLOSED enum — NO free-eval. Each unit-tested.
- `params_used` echoed in QResult (§2.4 mandatory — transparency).

### ⚠️ THE ONE DECISION (for team-lead) — tau UNIT: spec=SECONDS, ours=DAYS
The spec §2.5 `tau = {price: 300, macro: 2_592_000}` is in **SECONDS**; our shipped compute_q uses `TAU_DAYS` (days) + `age_days`. Reconciliation options:
- (a) **Keep internal DAYS** (so the current defaults + the 0.45-falls-out are byte-identical), accept `params.tau` in the spec's SECONDS form, convert seconds→days inside. params_used echoes what was used (state the unit). Cleanest for not-breaking-P2.
- (b) Switch internal to SECONDS + age_seconds (matches spec literally) — but this RE-DERIVES the defaults; risk the 0.45 test shifts on rounding. More spec-faithful but more risk.
**I LEAN (a)** — additive + zero P2 risk; the param surface speaks the spec's seconds, internal stays days. Flag to team-lead — the only judgment call.

## Phase 4 scope (proposed — pending team-lead approval)
- **T1 nav_history reader:** a `/finance/nav-history` (or /decision) read + an MCP tool (count 45→46). `?from&to`. confidence via compute_q (coverage = points/points-needed). Fail-open (empty → {series:[],points:0,confidence:0}+warning). Reuse portfolio_snapshot + the existing read fn (+ the `to` bound).
- **T2 compute_q params:** add `params` (optional, defaults=current) + `params_used` echo. combine 3-enum (each tested). DEFAULTS in ONE place (a constant — §2.5 "không hardcode rải rác"). tau unit per the decision above.
- **T3 tests:** §1.7 (empty→0+warning, idempotent already, nav matches, confidence-scales-with-points) + §2.6 HARD GATES (0.45 STILL falls out on defaults; combine="min" ≠ "multiply" same input — DISTINGUISHING; params_used always present; additive — a P2 surface byte-unchanged on defaults).

## Risks / seams
- The HARD constraint: defaults = current behavior. The 0.45-falls-out (the L58 contract) MUST still pass — behavior-test a P2 surface (macro_cycle or decision_weight) is byte-identical with default params.
- combine="min" vs "multiply" DISTINGUISHING (both tested — an impl that ignores combine would give the same result; divergent modes prove it's read).
- tau unit (seconds vs days) — the one decision; (a) keeps P2 safe.
- NEUTRAL + fail-open (spec §3) — nav reader returns data+confidence, no advice; source error → low confidence + warning, no crash.
- Reuse the existing table + read fn — do NOT create nav_snapshots (portfolio_snapshot covers it).

### Locks (team-lead, 2026-06-16 — after kickoff approval)
- **tau UNIT = (a): `params.tau` accepts SECONDS** (spec §2.5 form), **converts to internal DAYS**. The engine stays days-based → current defaults + the 0.45-falls-out byte-identical (zero P2 risk). `params_used` echoes the unit explicitly (seconds-in / days-internal). §Assumptions: "compute_q params.tau accepts SECONDS (spec §2.5), converts to internal days; defaults byte-identical to P2."
- **5 HARD GATES:** (a) 0.45 STILL falls out on defaults — the existing test_decision GATE1 passes UNCHANGED; (b) combine="min" ≠ "multiply" on the SAME input (DISTINGUISHING — proves the enum switches behavior, not a no-op); (c) params_used ALWAYS in QResult; (d) a P2 surface (macro_cycle/decision_weight) byte-unchanged on default params (additive must not perturb the tower); (e) nav reader values match portfolio_snapshot rows (<$0.01).
- **REUSE portfolio_snapshot** (no new table). combine = closed 3-enum, no free-eval. DEFAULTS in ONE config constant.

### Routing / sequencing
Dispatched to **backend-2**. backend-2 done → team-lead live-verifies (nav reader series+confidence; 0.45 unchanged + min≠multiply + params_used) → architect review+commit+push. **After Phase 4 ships → team-lead runs the dogfood quality round on the complete assistant.**
