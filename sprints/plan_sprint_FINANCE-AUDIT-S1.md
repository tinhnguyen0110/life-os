# Sprint FINANCE-AUDIT-S1 — q-engine cadence-aware freshness (Q1+Q2+Q3, one theme)

**Task #59.** A REAL-BUG fix from the dogfood audit (`AUDIT_finance_q1-q8.md`): freshness rewards a "stamped-today" mock 4.6× over real FRED data that's naturally lagged by its publication cadence. Corrupts the q-engine premise (every tower layer ∏s q). Backend-only, NEUTRAL.
**User framing (the spine):** "sửa đường ống, không tháo phanh" — FIX THE PIPE, DON'T REMOVE THE BRAKES. Penalize real LATENESS, don't blanket-reward real data.

## Kickoff — 2026-06-16 (verified the freshness flow + the 2 entry points + the mock inconsistency)

### The bug, root-pinned (reproduced live)
- `_freshness(age_days, data_type, tau_days)` (decision/service.py L62) = `exp(-max(0,age)/τ)` — measures ABSOLUTE age, keyed on `data_type` ("macro"), NOT the specific indicator.
- The mock generator (`macro/reader.py:_mock_points` L70) stamps its latest point at `_today()` → age ~0 → freshness ~1.0.
- Real FRED carries the TRUE observation date; a monthly indicator (CPI) is inherently ~46d old at publication → freshness `exp(-46/30) ≈ 0.21`.
- LIVE: real CPI confidence 0.2148 vs mock DXY 0.9952 = **4.6× inversion**.

### The two entry points cadence must reach (both call compute_q → _freshness)
- **`confidence_q`** (L246 — the macro_overview seam): single-input compute_q per indicator. `mock_is_present` is HARDCODED present (a mock gets a real freshness q) → **macro_overview COUNTS mock high (~0.99)**.
- **`q_from_points`** (L223 — the macro_cycle path): HAS `mock_is_present` param; macro_cycle passes `False` → **mock EXCLUDED (present:false)**.
- → **Q3 inconsistency root:** `confidence_q` lacks `mock_is_present`; `q_from_points` has it. Same mock, opposite handling.

### The fix's seam (where cadence enters — minimal threading)
- `QInput` ALREADY has a `name` field (L50). So thread the **indicator name** → a cadence lookup in `_freshness`: `age_effective = max(0, age_days − cadence_lag[name])` where `cadence_lag` is a per-indicator config map (CPI ~30d, M2 ~45d [FRED ~6wk lag], fed ~30d, yield ~1d, INDPRO ~45d, UNRATE ~30d). A monthly indicator observed within its cadence → age_effective ~0 → freshness ~1.0 (ON-TIME, not punished). Lateness BEYOND the cadence still penalizes (the brakes stay).
- Q2 (per-indicator τ/cadence): the cadence map IS the per-indicator config — bundle it. Unregistered indicators (synthetic test inputs) → no cadence → `exp(-age/τ)` unchanged → **GATE1 0.45 byte-identical** (it uses inputs named "x", not real indicators).
- Q3 (mock consistency): add `mock_is_present` to `confidence_q` (default matching the chosen rule) so macro_overview + macro_cycle handle mock the SAME way. **Decide ONE rule:** mock EXCLUDED everywhere (present:false in both — the honest "mock isn't real data" stance, matches macro_cycle) OR mock forced-low. **Lean EXCLUDED** (consistent with the spec's honest-missing; a mock shouldn't inflate confidence anywhere) — flag to team-lead as the one decision.

## Scope (3 parts, ONE fix)
- **Part 1 — cadence-aware freshness:** `_freshness` (or a wrapper) subtracts the indicator's expected cadence-lag before the exp decay. A per-indicator `CADENCE_LAG_DAYS` config map (Q2's per-indicator τ, bundled). On-time → ~1.0; overdue-beyond-cadence → drops.
- **Part 2 — thread the indicator name** from the macro seam (`_confidence_for` → `confidence_q` → QInput.name) so freshness can look up the cadence. (q_from_points already carries name.)
- **Part 3 — mock consistency:** `confidence_q` gains `mock_is_present` (or the equivalent) so macro_overview ↔ macro_cycle treat mock identically (EXCLUDED, pending team-lead's pick).

## ACCEPTANCE (USER-PINNED hard gates)
- (a) **real CPI on-time → freshness ~1.0** (a monthly indicator ~30-46d old, within cadence, no longer punished like stale).
- (b) **mock NEVER > a real on-time indicator** — assert `mock_conf < real_ontime_conf` (the 4.6× inversion GONE).
- **DISTINGUISHING (don't tháo phanh):** a real indicator GENUINELY overdue (CPI 90d when cadence 30d) → freshness DOES drop. Test BOTH: on-time→high, overdue→low. The fix penalizes real LATENESS, not hands real a free pass.
- **DON'T BREAK P2:** GATE1 `test_GATE1_q_cycle_045` (freshness×coverage×agreement, 0.45-falls-out on defaults) STILL passes UNCHANGED — the generic compute_q default behavior is byte-identical (cadence applies only to registered indicators; synthetic inputs unaffected). Behavior-test it.

## Risks / seams
- The byte-identical guard: cadence keys on the indicator NAME via a config map; an input with no registered cadence → no subtraction → `exp(-age/τ)` exactly as today. GATE1 uses "x" (unregistered) → unchanged. This is the load-bearing don't-break-P2 lock.
- The DISTINGUISHING is the user's spine — overdue real MUST still drop. A fix that blanket-floors real freshness at 1.0 would pass (a)+(b) but FAIL the distinguishing (tháo phanh). Test the overdue case.
- Mock-consistency rule is the one decision (EXCLUDED vs forced-low) — flag to team-lead.
- Q2 per-indicator cadence is REQUIRED here (a shared τ can't express CPI-30d vs M2-45d) — bundled into the cadence map.

### Locks (team-lead, 2026-06-16 — approved)
- **MOCK = (A) EXCLUDED everywhere** (present:false in both confidence_q + q_from_points). A mock is the ABSENCE of real data; never raises confidence. Matches macro_cycle's honest-missing.
- **CONSEQUENCE (locked + tested): excluding mock DROPS coverage → q_macro/q_cycle go HONESTLY DOWN where mock inflated them. INTENDED (the fix), via COVERAGE not a hidden floor.** end_sprint must FLAG: "q_macro dropped because mock no longer inflates it — intended, not a regression." Test: 2-real+2-mock → coverage 2/4 (assert the coverage number).
- **The DISTINGUISHING ("không tháo phanh") must be TEETH-Y:** a 90d-overdue real CPI (cadence 30 → 60d over) → freshness materially < 1.0 (assert < ~0.2). An on-time→high + overdue→low PAIR. A blanket-floor impl passes (a)+(b) but FAILS this.
- **all-mock → honest-empty (q low + warning), NOT a crash** (test the all-mock case).
- **Byte-identical guard:** GATE1 0.45 unchanged (synthetic "x" → no cadence → exp(-age/τ) as today).
- Cadence map = per-indicator (Q2 bundled), ONE config place.

### Routing / sequencing
Dispatched to **backend-2**. backend-2 done → team-lead live-verifies (CPI high, mock<real, q_macro honestly lower via coverage-not-floor, 0.45 byte-identical) → architect review+commit+push → **Sprint 2 (s_asset reads held assets, Q6+Q7) with its own hard acceptance (the W=0 valve MUST survive — no path lights the tower on empty signal).**
