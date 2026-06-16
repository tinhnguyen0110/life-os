# End Sprint FINANCE-ASSISTANT Phase 3 (FINAL) — policy + proactive + reward

> Status: **REVIEWED — 3 gates green, committing.** Task #55. Commit hash: see `git log`. The FINAL phase — the assistant is now structurally complete (data → state → weight → policy → reward + proactive).

## What shipped (T1-T4)
- **T1 — `allocation_target`** (in `modules/decision/`): {phase (defaults to live macro_cycle), capital, monthlyAdd, horizonYears} → reference channel weights + per-channel `rationale` + `vsStaticGoldenPath` delta + `confidence` (compute_q). The classic Investment-Clock phase tilt (§157) + a USER-CONFIGURABLE capital-size tilt. NEUTRAL — a REFERENCE weighting with the model reason shown, never an order.
- **T2 — `finance_guardian`** (in `modules/decision/`): a scanner set over EXISTING reads → `{alerts:[{severity, msg, evidence, sources}], confidence}`. Rules: high-stablecoin-while-fearful (stablePct + F&G), meme/concentration (correlation), dust-cleanup. Mirrors the `insights()` pattern (fail-soft, evidence-grounded, real-data-only). Each alert NEUTRAL — an observation framed as a QUESTION ("…is standing in cash here an intentional bet?").
- **T3 — decision_journal-finance wiring** (WIRE, not rebuild): `DecisionEntry`/Input/Update += `expectedEv`/`worstCase`/`decisionWeight` (additive optional). `domain="investment"` convention. The propose→accept→land loop (WRITE-LOOP-E2E) lands finance decisions.
- **T4 — MCP wrappers + tests:** allocation_target + finance_guardian as MCP read tools (count 43→45 + CATALOG). settings `AppConfig`/`AppConfigPatch` += `riskCapitalSmallUsd`(50000)/`riskCapitalLargeUsd`(500000), user-editable via PATCH /settings.

### Verified counts (architect re-ran independently — Rule #0)
- decision + decision_journal + settings + mcp_read: **164 passed, 0 errors**.
- Full suite: **1585 passed, 6 skipped, 0 failed, 0 errors** (was 1575; +10 decision tests), 1 benign httpx deprecation warning.
- mypy: the P3 changed files **clean** (no new errors).
- team-lead LIVE-verified all gates: no-advice-verb on BOTH live payloads (zero), capital-tilt distinct ($10k crypto41/dry19 vs $1M crypto31/dry29), 2 real-data NEUTRAL guardian alerts.

## Code review (architect — 4-step, NEUTRAL gate hardest)
1. **git diff** — 13 files: decision (service/schema/router/MCP), decision_journal (schema + service's 4 sites), settings/schema, read_server/CATALOG, test_decision + 3 count-bumps + the settings-shape test, 2 sprint docs. `template/`+`data/` excluded.
2. **Read full functions — the NEUTRAL gate (the load-bearing check) beyond the verb-regex:**
   - allocation_target rationale = `"reference {x}% — classic clock ({phase}) tilt {±n}pp, {tier}-capital tilt {±m}pp vs golden-path {z}%"` — pure DATA framing, the MODEL reason, NO imperative.
   - guardian alerts ALL framed as QUESTIONS: "…is standing in cash here an intentional bet?", "…is this diversification or one concentrated bet?", "…worth a cleanup?" — observations, not directives. (Checked for soft-advice the verb-regex misses — consider/time-to/need-to/better — NONE present; "worth a cleanup?" is a question, acceptable.)
   - **capital-tilt READS from settings (L450-452):** `cfg = settings_svc.get_config()` → `riskCapitalSmallUsd`/`riskCapitalLargeUsd` (getattr defaults) — NOT hardcoded. ✅
   - **decision_journal additive across ALL 4 sites (the built-but-not-wired trap):** `_render` (md WRITE, L87) + `_parse` (md READ, L125) + `create_entry` (L166) + `update_entry` (`_merge`, L204) ALL carry expectedEv/worstCase/decisionWeight. So a field round-trips (persists + reads back), not schema-only-vanishes. ✅
   - **calibration/Brier UNTOUCHED** — not in the decision_journal diff; the additive fields don't alter it.
3. **Verify against plan** — allocation NEUTRAL-reference, guardian real-data-questions, decision_journal WIRE, capital-tilt user-configurable, count 43→45, no-advice-verb gate. ✅
4. **Hunt additional issues** — none. The no-advice-verb test is the hard gate (passes); the capital-size distinguishing proves the tilt is real (not ignored); guardian real-data-only prevents fabricated concern; decision_journal round-trips across all 4 sites; calibration intact.

## Assumptions (user-review)
- **Capital-tilt thresholds USER-CONFIGURABLE (default $50k small / $500k large).** `riskCapitalSmallUsd`/`riskCapitalLargeUsd` on AppConfig, editable via PATCH /settings. capital < small → tilt aggressive (+5pp crypto/−5pp dry); ≥ large → conservative (−5pp crypto/+5pp dry). **Why:** single-user app — the user's risk appetite is theirs, not ours to hardcode; we default, they override. **How to change:** PATCH /settings, or the defaults in settings/schema.py.
- **allocation_target = REFERENCE, NOT advice.** A reference weighting (classic-clock + capital-size) with the model reason shown — not an order. NEUTRAL (no advice verb — the load-bearing gate). **Why:** highest advice-risk tool; the tool surfaces what the data implies, the human/agent decides.
- **finance_guardian = OBSERVATIONS framed as QUESTIONS** ("…intentional bet?"), real-data-only (a mock/empty source → no alert). **Why:** a guardian firing on mock data fabricates concern; questions surface unknown-unknowns without directing.
- **decision_journal = WIRED (additive), domain="investment".** expectedEv/worstCase/decisionWeight added across all 4 round-trip sites; falsificationCondition already = "invalidation"; the propose→accept→land loop (WRITE-LOOP-E2E) lands it. calibration/Brier untouched. **Why:** the spec said wire, not rebuild — the module was ~90% there.
- **MCP tool count 43→45** (allocation_target + finance_guardian).

## The 3 Quality Gates
- **Gate 1 — API:** ☑ /decision/allocation + /decision/guardian + the 2 MCP tools response-shaped · ☑ no auth · ☑ NEUTRAL (no advice verb — the load-bearing gate, asserted on BOTH) · ☑ settings PATCH validates the new fields · ☑ capability gate auto-holds. **PASS**
- **Gate 2 — Function:** ☑ no-advice-verb HARD gate (verb-regex + soft-advice string-read) · ☑ capital-size DISTINGUISHING ($10k≠$1M tilt; threshold from settings — patch test) · ☑ guardian real-data-only (mock → no fire) · ☑ decision_journal additive round-trips all 4 sites + calibration intact · ☑ existing tests pass (full suite) · ☑ **0 errors** · ☑ mypy clean. **PASS**
- **Gate 3 — Sprint:** ☑ end doc w/ verified counts · ☑ architect spot-checked full functions (NEUTRAL strings + the 4 round-trip sites) · ☑ counts ≥ baseline · ☑ team-lead LIVE-verified all gates · ☑ assumptions logged (5) · ☑ commit format. **PASS**

## Risks / follow-ups
- **🏁 The finance-assistant is STRUCTURALLY COMPLETE:** data (P1: real cost-basis + 7 macro axes + daily accumulation) → state + weight (P2: q-engine + macro_cycle + decision_weight, provably L58) → policy + reward + proactive (P3: allocation_target + decision_journal + finance_guardian). A full RL-framed decision system (state → policy → weight → reward), all NEUTRAL (the agent/human decides).
- **Natural next step (user's to trigger):** a dogfood consumer-agent round (the north-star "what's missing" trick) over the now-complete assistant — connect a real agent via MCP, ask real investment questions, find the gaps the complete system still has.
- position_size (fractional-Kelly) + rebalance_plan + market_regime remain as future candidates (out of this arc's scope).
