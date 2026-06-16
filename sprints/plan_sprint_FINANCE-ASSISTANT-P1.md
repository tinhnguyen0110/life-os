# Sprint FINANCE-ASSISTANT Phase 1 — OKX cost-basis + macro substrate

**Task #52. Arc:** turn finance into an investment + personal-finance ASSISTANT per `finance/docs/finance_tools_spec.md` (a decision tower: q-engine → macro_cycle → decision_weight → policy/guardian). Multi-phase; Phase 1 = the data substrate, ships independently useful. Backend-only.
**Phases:** P1 (data substrate, this) → P2 (q-engine + macro_cycle + decision_weight) → P3 (allocation_target + guardian + decision_journal-finance). Each gated by team-lead.

## Kickoff — 2026-06-16 (verified each of team-lead's 4 data findings LIVE — Rule #0)

### Finding #1 — COST BASIS IS NOT A DEAD-END → **REVERSAL PROVEN LIVE** ✅
Ran the live OKX `account/balance` call (`exchange/reader.fetch_balances()`). Each `details` entry carries REAL per-coin cost-basis fields: `accAvgPx`, `openAvgPx`, `spotUpl`, `spotUplRatio`, `totalPnl`, `totalPnlRatio`. Live values: PEPE accAvgPx=0.00000702 spotUpl=-$115.84 (-57.9%); ICP -20%; ARB -76%; S -81%; TRUMP -96%; IP -93%. **So per-coin real P&L is FREE — already in the fetched response, just DISCARDED** when `exchange/reader._parse_balances` maps details→OkxBalance (keeps only symbol/qty/usdValue). The prior "cost-basis dead-end" memory tested the WRONG endpoint (orders-history, 90d retention, empty). **→ This overturns the old conclusion; the `claude-usage-token-source`-adjacent memory about cost-basis being unavailable should be corrected (note in end_sprint).** NO write tool / NO user input needed for OKX coins; older/off-OKX coins → honest-null.

### Finding #2 — Macro free-verified ✅ (+ 1 nuance)
- UNRATE / M2SL / INDPRO → FRED CSV no-key, HTTP **200** live. ✅
- **T10Y2Y (yield curve) → HTTP 000 on 3/3 attempts** — consistently failing right now (FRED no-key CSV rate-limit or transient outage). Confirms team-lead's "FLAKY, needs resilient/retry fetch" — the macro reader already fail-opens to mock, so this fits: retry + honest fail-open to last-known/mock, NEVER fabricate.
- **NUANCE (important for the dispatch):** the EXISTING macro reader (`macro/reader.py:4`) uses the FRED **JSON API requiring an api_key**, with mock fallback. But the new indicators (and the ones I verified) use the **no-key CSV path** (`fredgraph.csv?id=<series>`). The dispatch must use the no-key CSV path so it works without a key (the existing FRED-MACRO commit `61f2ad8` already added a CSV path for Fed/CPI — reuse THAT, not the keyed JSON path).

### Finding #3 — PMI = no free API → use INDPRO + jobless-claims PROXY ✅
ISM/S&P PMI is proprietary; no scrape, no fake. The q-engine's `coverage` term handles the missing growth axis honestly (coverage 3/4 → slightly lower q, not a lie). Phase 1 just adds INDPRO (+ M2/UNRATE/yield); the PROXY framing + the q math are Phase 2.

### Finding #4 — nav_history already capturing ✅ (so it's NOT in Phase 1's snapshot scope)
`portfolio_snapshot` table EXISTS (db.py:67), `take_snapshot()` EXISTS (finance/service.py:404) + REST route + (per team-lead) wired into morning_pull (D2), accumulating. **So NAV snapshot is DONE — Phase 1's T3 snapshot is the MACRO+SENTIMENT snapshot, NOT NAV.** (Expose a nav_history read tool later, not this phase.)

### F&G + BTC.d free-verified ✅
F&G=23 "Extreme Fear" (alternative.me free); BTC.d=56.48% (coingecko /global free). Both reachable live.

## Phase 1 scope (backend-only, ships independently)
- **T1 — OKX cost-basis → real pnl:** extend `OkxBalance` (additive) with `accAvgPx`/`spotUpl`/`spotUplRatio`; parse them in `exchange/reader._parse_balances`; in `finance/_okx_crypto_holdings` set `Holding.avgCost = accAvgPx` when present (→ the FINANCE-CORRECTNESS `_pnl(cost,value)` lights up automatically) OR surface spotUpl as the per-coin pnl directly. honest-null for coins w/o accAvgPx. Builds DIRECTLY on the shipped per-holding enrichment (usdValue/price already there).
- **T2 — extend macro:** add `yield_curve_10y2y` (T10Y2Y, RESILIENT fetch — retry + fail-open), `unemployment` (UNRATE), `m2_liquidity` (M2SL), `industrial_production` (INDPRO) to the macro INDICATORS map + get_overview/get_history. Use the NO-KEY CSV path (reuse the FRED-MACRO CSV reader, not the keyed JSON).
- **T3 — daily macro+sentiment snapshot routine:** a scheduler routine snapshots the daily-changing signals (F&G, yield-curve, BTC.d) → macro_history; monthly macro fields dedupe (don't re-store unchanged).
- **confidence seam:** each new output carries a SIMPLE source-based confidence (live=high, mock/fail-open=low) — the full `compute_q()` (freshness×coverage×agreement) is Phase 2; flag the seam in code (a `# Phase-2: replace with compute_q()` marker) so it's a clean upgrade, not a rewrite.

## Final task list (proposed — pending team-lead approval)
- T1 OKX cost-basis wire (exchange schema+reader, finance holdings).
- T2 macro extension (4 indicators, no-key CSV, resilient yield-curve).
- T3 daily macro+sentiment snapshot routine.
- T4 tests: cost-basis lands real pnl (divergent: PEPE -58% not null) + honest-null for no-accAvgPx + macro 4 new indicators (mock-honest when FRED down) + snapshot dedupe + confidence field present.

## Risks / seams
- The OKX accAvgPx covers buys since the account's OKX history; a coin held off-OKX or pre-history → no accAvgPx → honest-null (don't fabricate). Test the honest-null path with a no-accAvgPx fixture.
- Yield-curve T10Y2Y is live-failing NOW — the resilient fetch + mock-honest path is load-bearing; test it returns honest-mock (not a crash, not a fabricated number) when the fetch 000s.
- confidence is a Phase-1 STUB (source-based), not the real q — must be clearly seamed so Phase 2 swaps in compute_q() without touching call-sites.
- The prior cost-basis "dead-end" memory is now WRONG — correct/annotate it (end_sprint note). [DONE: `verify-source-has-real-data-before-building` memory already updated to note the OKX-basis HOLD was OVERTURNED.]

### Locks (team-lead, 2026-06-16 — after kickoff approval; both data findings disk-confirmed)
- **Q1 = avgCost = accAvgPx** (reuse the shipped `_pnl` path — single source of truth). PLUS carry `spotUpl`/`spotUplRatio` in the parsed balance as a CROSS-CHECK (not a 2nd displayed pnl). T4 SANITY test: `abs(our_pnl_pct − okx_spotUplRatio*100) < ~5pp` on a real coin (PEPE) — a large divergence = a price-feed bug to surface, not silently accept.
- **Q2 = T3 snapshot is MACRO+SENTIMENT only** (NAV already captured via portfolio_snapshot/take_snapshot/morning_pull — do NOT re-snapshot; nav_history read tool is a later phase).
- **Macro = NO-KEY CSV** (reuse `_fetch_fred_csv` from FRED-MACRO `61f2ad8`, NOT the keyed JSON `reader.py:4` path). yield-curve resilient retry+fail-open; others straight.
- **MANDATORY defensive (team-lead HARD): FRED 000/504 → fail-open to mock + low confidence + warning, NEVER 500.** Test the path (mock FRED 000 → indicator present, source=mock, no exception). T10Y2Y is HTTP-000 live right now.
- **Additive-only** on OkxBalance/Holding (grep-confirmed: all consumers `model_dump()`, FE reads specific fields → safe).
- **confidence = Phase-1 source-based STUB + `# Phase-2: compute_q()` seam marker** (clean seam, swap real q in P2 without touching call-sites).

### T5 (folded into P1 after team-lead's live-verify, 2026-06-16) — surface per-holding pnl on finance_overview
**Interaction caught at live-verify:** the keystone (real per-coin pnl) landed on `exchange_overview` but `finance_overview` (the main agent surface) still read NULL — the channel-level `basisUnknown` rule nulls the aggregate because USDT (98% by value, no basis) dominates, MASKING PEPE's real -58%. Architect verified the cause on disk: `_aggregate` (~L342) ALREADY computes per-holding pnl; `_holding_from_entry` (the FINANCE-CORRECTNESS surfacer) just DROPS it (carries usdValue/price/changePct but not pnl) — classic built-but-not-wired. Fix = surface the already-computed per-holding pnl (the 4th derived field, same pattern). team-lead approved folding into P1.
- `Holding` += `pnl: PnL | None` (additive); `_holding_from_entry` threads `entry["pnl"]` (NOT recomputed — single source of truth). basis-less → null, real-basis → real. Dust entry → pnl None.
- **basisUnknown channel logic UNTOUCHED** (correct — USDT-dominated channel aggregate is honestly null; per-holding is the right granularity).
- DISTINGUISHING test (team-lead HARD): a no-basis (USDT) AND a real-basis (PEPE) coin in the SAME channel/response → USDT.pnl null, PEPE.pnl.pct ~-58% (proves per-holding, not channel-masked). + spotUpl sanity <5pp. + additive-consumer grep.

### Routing / sequencing
T1-T4 dispatched + backend-done + team-lead live-verified PASS (7 macro indicators, real cost-basis, 1560 pytest). T5 dispatched to **backend-2** (the keystone-landing fold). backend-2 T5 done → architect reviews the WHOLE P1 (T1-T5) together + 3 gates + commit + foreground push → **Phase 2 (q-engine + macro_cycle + decision_weight) next**.
