# Sprint FINANCE-AUDIT-S1B — macro_cycle cadence consistency (close the S1 half-fix)

**Task #61. Reactive sprint, same theme as S1.** The user's re-verify caught a REAL gap: S1's cadence fix reached `confidence_q` (macro_overview) but NOT macro_cycle's path — so the SAME indicator has DIFFERENT freshness in the two tools (internally inconsistent). A legit miss on S1's scope (the recurring `dissolved-finding-recheck-all-consumers` lesson: I fixed one q-engine entry point, not both). Backend-only, NEUTRAL.

## Kickoff — 2026-06-16 (root pinned)

### The gap (team-lead confirmed live; I confirmed the code root)
- Same CPI (asOf 05-01, 46d): macro_overview freshness **0.58** (cadence-aware ✓) BUT macro_cycle freshness **0.2144 = exp(-46/30)** OLD absolute-age ❌. Two tools, same data, different freshness.
- q_cycle stuck artificially low (~0.143) — the EXACT Q1 bug, fixed in only one of the two tools.

### ROOT (pinned in code)
- `_axis_q_input(name, value, ts, source, direction)` (decision/service.py L314) builds `QInput(name=name)` where `name` is the AXIS LABEL ("growth"/"inflation"/"yield_curve") — NOT the indicator name. → freshness looks up cadence by the axis label → NOT in CADENCE_LAG_DAYS → no subtraction → absolute-age (the bug).
- `_axis(name, indicator, ...)` (L337, inside macro_cycle) ALREADY HAS the `indicator` (cpi / industrial_production / unemployment / yield_curve_10y2y) — it's the 2nd arg — but calls `_axis_q_input(name, ...)` (L349) passing the axis LABEL, dropping the indicator.
- **CADENCE_LAG_DAYS already has all the axis indicators** (cpi 30, industrial_production 45, unemployment 30, yield_curve_10y2y 1) — so NO new map; the fix is to use the indicator name the helper already holds.

### The fix (minimal, surgical — thread the indicator name)
- `_axis_q_input` gains an `indicator_name` param → `QInput(name=indicator_name or name)`. `_axis` passes its `indicator` through. So the QInput's cadence lookup keys on the INDICATOR (cpi/industrial_production), not the axis label.
- **Clean separation:** `CycleAxis.axis` STAYS the axis label (growth/inflation — the user-facing phase label); only the internal `QInput.name` (the cadence-lookup key) becomes the indicator. Display unchanged; cadence correct.
- `macro_cycle.paramsUsed.tauSeconds` → per-indicator (like macro_overview), same root — once QInput keys on the indicator, the params echo the per-indicator cadence.
- REUSE the SAME `CADENCE_LAG_DAYS` (don't duplicate the map).

## ACCEPTANCE (USER-PINNED hard gates)
- (1) **SAME-CPI-SAME-FRESHNESS (the internal-consistency the user demands):** macro_overview CPI freshness ≈ macro_cycle inflation-axis freshness (both cadence-aware ~0.58). **Assert they MATCH** (the same indicator, same cadence, same freshness across the two tools).
- (2) **q_cycle RISES for the right reason** — the MEASURE was fixed (cadence now applies in macro_cycle too), NOT new data. Flag in end_sprint (like the S1 q-drop flag, inverse direction).
- (3) **"không tháo phanh" survives in macro_cycle too:** a genuinely-overdue axis (e.g. a CPI 90d old) STILL drops in macro_cycle's freshness (the brake works in BOTH tools now). Test overdue→low.
- (4) **macro_overview behavior from S1 UNCHANGED + compute_q 0.45 byte-identical** (additive — only macro_cycle's freshness path changes; the confidence_q seam + GATE1 untouched). Behavior-test.

## Scope
- IN: thread the indicator name through `_axis` → `_axis_q_input` so macro_cycle's freshness is cadence-aware; per-indicator paramsUsed; tests.
- OUT: NO change to confidence_q (S1, macro_overview — already correct). NO new cadence map (reuse CADENCE_LAG_DAYS). NO change to the axis DISPLAY labels (CycleAxis.axis stays growth/inflation). NO compute_q / 0.45 change. NO s_asset / nav (S2 done; separate).

## Risks / seams
- The separation: axis LABEL (display) vs indicator NAME (cadence key) — don't conflate. CycleAxis.axis = label; QInput.name = indicator. The fix changes only the QInput's cadence-lookup key.
- The SAME-CPI-SAME-FRESHNESS assertion (1) is the user's spine — it proves the two tools are now consistent (the half-fix closed). Make it a direct cross-tool comparison.
- "không tháo phanh" (3) must survive in macro_cycle — same as S1's macro_overview teeth, now for the cycle path.
- Byte-identical (4): the confidence_q seam + compute_q default + GATE1 0.45 unchanged (only the _axis_q_input/_axis indicator-threading changes). Behavior-test macro_overview's S1 result + GATE1 unchanged.

### Locks (team-lead, 2026-06-16 — approved as drafted)
- **SAME-CPI-SAME-FRESHNESS = CROSS-TOOL MATCH** (the user's spine): the test asserts macro_overview CPI freshness ≈ macro_cycle inflation-axis freshness (~0.58), proving the TWO TOOLS AGREE on the same indicator — NOT just "macro_cycle rose."
- q_cycle RISES because the MEASURE was fixed (flag in end_sprint, inverse of S1's q-drop).
- "không tháo phanh" in macro_cycle too — a 90d-overdue axis STILL drops (< ~0.2).
- macro_overview S1 behavior UNCHANGED + GATE1 0.45 byte-identical (additive — only the _axis path; behavior-test).
- Surgical: thread indicator_name; REUSE CADENCE_LAG_DAYS (no new map); CycleAxis.axis stays the display label.

### Routing / sequencing
Dispatched to **backend-2**. backend-2 done → team-lead live-verifies (macro_cycle CPI/inflation freshness ≈ macro_overview ~0.58 MATCHING; q_cycle risen; brake survives; overview unchanged) → architect review+commit+push → **team-lead pings the user the cross-tool consistency is fixed.** The s_asset "0/6" note (OHLC-history-for-holdings) is a SEPARATE future candidate, relayed to the user — NOT folded here.

## Note for the user (NOT this sprint — a separate data-capture gap)
The user asked why s_asset is "0/6". Answer: the held coins lack price-HISTORY depth for RSI (OKX value-only coins have no OHLC series in the market store yet) — a downstream data-capture question (OHLC history for held coins), NOT this sprint. S2's plumbing is correct (reads holdings); it lights up as the data deepens. (Relay to the user separately or note here.)
