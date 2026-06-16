# Sprint FINANCE-ASSISTANT Phase 3 (FINAL) — policy + proactive + reward

**Task #55. Arc:** the LAST phase of the finance-assistant (spec `finance/docs/finance_tools_spec.md`). After this the assistant is structurally complete: **data (P1) → state + weight (P2) → policy + reward + proactive (P3).** Backend-only.
**3 tools:** allocation_target (policy), finance_guardian (proactive), decision_journal-finance (RL reward).

## Kickoff — 2026-06-16 (re-read §206-380; verified what's already built — much is)

### decision_journal — ALREADY ~90% built → WIRE, don't rebuild (spec §335 says so)
`modules/decision_journal/` has: `thesis`, `falsificationCondition` (= the spec's "invalidation"), `confidence`/`predicted` (the probability claim → Brier/calibration), `domain` (bias-cluster key), `outcome` (right/wrong on resolve → the anti-resulting reward), open→resolved lifecycle. The propose→accept→land loop is SHIPPED (WRITE-LOOP-E2E `74b9025`). **GAP = only the §339 `expected_ev` + `worst_case` fields (additive optional) + a finance-decision convention** (domain="investment" + optionally a finance-context link). NOT a rebuild — add 2 fields + wire finance to use the existing module + propose_decision.

### allocation_target — composes EXISTING pieces (phase + capital + golden-path engine)
golden_path (static targets in `golden_path.md`) + simulate's HHI/drift engine + (now from P2) macro_cycle's phase all exist. allocation_target (§208) = `policy(state)`: phase + capital + horizon → a REFERENCE weight set with per-channel rationale + `vs_static_goldenpath` delta. New logic = the phase→weights reference map + the capital-size adjustment (§212: small capital + steady income → can tilt aggressive; large capital = survival constraint → fractional-Kelly conservatism). Carries confidence from compute_q.

### finance_guardian — pure compose over EXISTING reads (all alert data exists)
The §358 example alerts all run on data we have: `stablePct` (the 98%-cash alert — finance already computes it), F&G (P1 fetchers), market `correlation` (the meme-correlation "tưởng đa dạng nhưng không" alert), cost-basis null (now mostly fixed by P1). So guardian = a set of rule-based SCANNERS over the existing read paths, each emitting a NEUTRAL observation + evidence + severity. New = the scan rules + the framing.

### THE HARD RISK (team-lead flagged): these are the HIGHEST advice-risk tools
allocation_target ("recommended weights") + guardian ("alerts") are inherently "what to do"-shaped. NEUTRAL must be enforced HARD:
- allocation_target = a REFERENCE allocation + rationale + the delta-vs-golden-path. It is DATA (here's what the classic-clock + your capital implies), NOT an order. No "you should/buy/sell/move."
- guardian = OBSERVATIONS with evidence ("98% cash while F&G recovering — is this an intentional bet?"), NOT directives. Framed as questions/observations, never "do X."
- decision_journal = the user's OWN logged reasoning — neutral by nature.
- TEST IT: assert no advice verb (should/buy/sell/rebalance/move/deploy/recommend/must) in any allocation_target or guardian payload (the same NEUTRAL gate the insights/macro tools already pass).

## Phase 3 scope (proposed — pending team-lead approval)
- **T1 — allocation_target:** in `modules/decision/` (the tower module). Input {phase (from macro_cycle), capital, monthly_add, horizon_years}. Output: target weights + per-channel rationale + vs_static_goldenpath delta + confidence (compute_q). The phase→weights reference map (classic-clock) + capital-size tilt. NEUTRAL (reference, not order).
- **T2 — finance_guardian:** in `modules/decision/` (or finance). A scanner set over existing reads → `{alerts:[{severity, msg, evidence, sources}], confidence}`. Each alert NEUTRAL + evidence-grounded (the insights-tool pattern). Rules over REAL data only (a rule whose source is mock/empty doesn't fire — same discipline as insights).
- **T3 — decision_journal-finance wiring:** add §339 `expectedEv` + `worstCase` (additive optional) to DecisionEntry; a finance-decision convention (domain="investment") + the propose_decision path already lands it (WRITE-LOOP-E2E). Optionally a `decision_weight`-snapshot link (log the W at decision time → later learn). Minimal — reuse, don't rebuild.
- **T4 — MCP wrappers + tests:** allocation_target/finance_guardian as MCP read tools (count 43→45); decision_journal already exposed. Tests: NEUTRAL (no-advice-verb HARD on allocation+guardian), allocation capital-size-changes-weights (distinguishing: $10k vs $1M → different tilt), guardian fires-on-real-data-only (a mock source → no alert), decision_journal §339 fields land + the finance domain convention + calibration still works.

## Risks / seams
- HIGHEST advice-risk phase — the NEUTRAL no-advice-verb test is the load-bearing gate (assert on allocation_target + guardian payloads).
- allocation_target capital-size logic (§212) is a business rule → decide-and-log the tilt thresholds (small vs large capital boundary).
- guardian rules over REAL data only (mock/empty source → no fire — the insights discipline); don't fabricate an alert from a stub.
- decision_journal = wire not rebuild; the §339 fields are additive; don't disturb the existing calibration/Brier.
- After P3: the assistant is structurally complete. A dogfood consumer-agent round (the north-star trick) is the natural next "what's missing" generator.

### Locks (team-lead, 2026-06-16 — after kickoff approval)
- **Capital-size tilt MUST be USER-CONFIGURABLE, not hardcoded.** Add `riskCapitalSmallUsd`(default 50000) + `riskCapitalLargeUsd`(default 500000) to `AppConfig`/`AppConfigPatch` (user-editable via PATCH /settings); allocation_target READS them. Rationale: single-user app — the user's risk appetite is theirs, not ours to hardcode. We default, they override. (Precedent: `wikiAgentAutonomous` user-ordered toggle.)
- **NO-ADVICE-VERB = THE load-bearing gate.** allocation_target + finance_guardian payloads must contain NO advice verb (should/buy/sell/rebalance/move/deploy/recommend/must/ought) — same NEUTRAL gate insights/macro pass. A leak = BLOCKER. allocation = reference+rationale+delta (data); guardian = observations+evidence framed as questions, never imperatives. The capital-tilt is presented as "classic-clock + your capital-size implies this REFERENCE weighting," NOT "you should be aggressive."
- **4 distinguishing/reuse locks:** (1) capital-size DISTINGUISHING test ($10k vs $1M → genuinely different tilt; threshold from settings). (2) guardian fires on REAL data only (mock/empty → no alert — the insights discipline; a guardian firing on mock fabricates concern). (3) decision_journal WIRE not rebuild — additive expectedEv/worstCase/decisionWeight + domain="investment"; do NOT disturb calibration/Brier (assert it still computes). (4) count 43→45.
- Scope OUT: position_size/rebalance_plan (later), finance_set_basis (P1's accAvgPx already solved cost-basis — redundant).

### Routing / sequencing
Dispatched to **backend-2**. backend-2 done → team-lead live-verifies (no-advice-verb on both, capital-tilt distinguishing, guardian-real-data-only, decision_journal calibration intact) → architect review+commit+push. **After P3 the assistant is STRUCTURALLY COMPLETE (data→state→weight→policy→reward+proactive)** — a dogfood consumer-agent round is the natural next step.
