# Sprint FINANCE-ASSISTANT Phase 2 — the decision tower core (q-engine → macro_cycle → decision_weight)

**Task #54. Arc:** Phase 2 of the finance-assistant (spec `finance/docs/finance_tools_spec.md`). The HEART: turn the P1 data substrate into "how hard can I bet right now." Backend-only.
**Build order (spec §439-456):** q-engine (`compute_q`) FIRST = the shared contract → macro_cycle (the RL state) → decision_weight (W = ∏q, the combiner). decision_weight is the TOP of the tower but built LAST (it's a pure product of the others — spec §423).

## Kickoff — 2026-06-16 (re-read the precise spec sections; verified P1 data feeds q)

### Spec sections nailed down (follow EXACTLY — spec §45 "2 people can't implement it differently")
- **q-engine (§51-87):** `q = freshness × coverage × agreement`, each ∈ [0,1]. ONE `compute_q()`; no tool rolls its own.
  - `freshness = exp(−age / τ)` — τ per data type: spot ~5min, macro ~30d, cycle/yield ~30d.
  - `coverage = (#inputs with data) / (#inputs needed)`.
  - `agreement = 1 − dispersion`. 1 source → =1 (no dispersion); multiple sources disagreeing → <1.
- **decision_weight (§26-49):** `W = q_cycle × q_macro × q_flow × s_asset` — **pure product, NO inter-layer clamp** (§40-44: the hierarchy "lower light ≤ upper light" is enforced BY the multiply, NOT by `min(qᵢ, q_{i-1})`). A layer at 0 → W=0 automatically. `binding_constraint` = the dimmest layer (names where to add data). An absolute-prohibition policy is SEPARATE, not in the W math (§48).
- **weight vs confidence (§116-132):** TWO separate numbers, agent must NOT conflate. `weight` = how hard to bet (signal strength). `confidence` = how much I trust the weight measurement. Dangerous quadrant = high-weight + low-confidence (signal lures a big bet but the measurement is unreliable). Rule: when confidence < threshold, downgrade ALL weight to "observe."
- **macro_cycle (§134-164):** Investment Clock, 4 phases (Growth × Inflation): recovery(↑,↓) / overheat(↑,↑) / stagflation(↓,↑) / slowdown(↓,↓). Axes from the macro data; carries `q_cycle` from compute_q. PMI/unemployment missing → coverage handles it honestly (don't fabricate a phase).

### P1 data is READY to feed q (verified live)
- **freshness:** `macro_history` stores `ts` per point (ISO obs date) → `age = now − ts` computable per indicator. ✅
- **coverage:** macro_cycle's 4 axes — growth(INDPRO proxy, +UNRATE), inflation(CPI) + yield_curve. P1 shipped all 4 macro axes; PMI proxied by INDPRO (the decided assumption). When an axis is mock (FRED-down) → it counts as NOT-covered (lowers coverage honestly).
- **agreement:** each macro indicator is single-source (FRED) → agreement=1 per indicator; macro_cycle's agreement = do the axes point to the SAME phase (e.g. yield steepening + CPI cooling both → recovery → high agreement; conflicting → <1).
- **The confidence seam is ready:** `macro/service._confidence_for(source)` is the swap point (the comment says "call-site `_indicator_view` unchanged; only this fn's body swaps for the real q"). compute_q replaces it.
- **No q-engine exists yet** (grep-confirmed) → genuinely new, not a rebuild.

### Where compute_q lives (registry/architecture call)
compute_q is CROSS-MODULE (macro_cycle, decision_weight, later flow/asset all call it). Options: (a) a shared `core/` or `modules/finance/q_engine.py` pure helper, (b) a new `modules/decision/` module housing macro_cycle + decision_weight + compute_q. **Lean (b) a `decision` module** (macro_cycle + decision_weight + compute_q together) — it's a feature area with its own router + MCP tools, fits the module/registry pattern; compute_q as a pure fn within it that others import. Flag to team-lead — this is the one architecture decision Phase 2 needs.

## Phase 2 scope (proposed — pending team-lead approval)
- **T1 — q-engine (`compute_q`) FIRST (the shared contract):** the pure `compute_q(inputs) → {q, freshness, coverage, agreement, breakdown}` per spec §57-87. τ table, the 3-component product. Unit-tested against the spec's worked example (§75-83: 2/4 axes → q_cycle ≈ 0.45 must FALL OUT of the formula, not be typed). The decay/coverage/agreement each tested in isolation + composed.
- **T2 — macro_cycle (the RL state):** Investment Clock phase from the macro axes (growth=INDPRO+UNRATE trend, inflation=CPI trend, +yield_curve regime), carrying `q_cycle = compute_q(...)`. Honest on missing axes (coverage<1 → lower q + warning, never a fabricated phase). NEUTRAL (data + q, no advice).
- **T3 — decision_weight (the combiner, built last):** `W = ∏ qᵢ` pure product, no clamp; `binding_constraint`; the weight-vs-confidence two-number legend (§116). Phase-2 layers available: q_cycle (macro_cycle), q_macro (macro_overview confidence — now real via compute_q), q_flow (a minimal flow — F&G/BTC.d from P1 sentiment snapshot), s_asset (per-asset signal — market RSI/trend, exists). A layer with no data → q=0 → W=0 (honest "blind = don't bet").
- **T4 — wire confidence seam → compute_q:** replace `macro/service._confidence_for` body with compute_q (the call-site stays — the seam P1 left). So macro_overview's confidence becomes the REAL q, not the source-stub.
- **T5 — tests:** compute_q worked-example (§75-83 0.45 falls out); macro_cycle 4 phases + honest-missing-axis; decision_weight pure-product (a 0 layer → W=0) + binding_constraint + weight≠confidence; the dangerous-quadrant (high weight + low confidence) surfaced distinctly.

## Risks / seams
- This is P0 + the spec is precise — implement the formulas EXACTLY (§45). The worked example (§75-83) is the acceptance test: 0.45 must emerge from the math.
- **No clamp** (§40-44) — the #1 spec subtlety. decision_weight is a pure product; the hierarchy is enforced by the multiply. A `min(qᵢ, q_{i-1})` clamp is explicitly WRONG (erases lower-layer info). Test that a dim upper layer still preserves the lower layer's contribution (0.3 × 0.9 keeps the 0.9's effect).
- weight vs confidence MUST be two separate fields the agent can't conflate (§116) — test they're distinct + the legend is in the payload.
- q_flow + s_asset are MINIMAL in Phase 2 (a real flow/asset signal layer is later) — use what P1+existing market gives (F&G/BTC.d, RSI/trend); a layer with thin data → low q honestly, don't over-build.

### Locks (team-lead, 2026-06-16 — after kickoff approval)
- **ARCHITECTURE = (b) new `modules/decision/` module** (router/schema/service, registry auto-discovered). `compute_q` = a PURE importable fn there (the "one compute_q" contract); macro_cycle + decision_weight as the tower's tools (+ MCP read wrappers). NOT scattered helpers.
- **SCOPE = minimal q_flow/s_asset, NO market_regime** (the gom tool is Phase 3). q_flow from P1's F&G/BTC.d; s_asset from existing market RSI/trend. A thin flow → low q_flow → honest low W (correct, not a gap — north-star).
- **5 HARD GATES:** (1) THE acceptance test §75-83 — q_cycle ≈0.45 FALLS OUT of compute_q by computation, NOT typed (the phase-defining test; 0.45 hardcoded anywhere = fake q-engine). (2) decision_weight pure-product NO-clamp, DISTINGUISHING: dim-upper(0.3)+bright-lower(0.9) → W=0.27 (∏ not min-clamp) AND a zero layer → W=0 (an all-equal fixture would pass a broken clamp). (3) weight vs confidence distinct fields + dangerous quadrant. (4) macro_cycle honest-missing (coverage<1 → lower q + warning, never a fabricated phase) + NEUTRAL (no advice verb). (5) compute_q SINGLE source — grep macro_cycle/decision_weight/_confidence_for all call it, none reimplements.
- Build order T1 compute_q → T2 macro_cycle → T3 decision_weight → T4 wire seam → T5 tests.

### Routing / sequencing
Dispatched to **backend-2**. backend-2 done → team-lead live-verifies (0.45 falls out, W=∏q distinguishing, macro_cycle phase from real axes) → architect review+commit+push → **Phase 3 (allocation_target + guardian + decision_journal-finance) next**.
