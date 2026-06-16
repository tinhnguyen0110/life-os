# End Sprint FINANCE-ASSISTANT Phase 1 — OKX cost-basis + macro substrate

> Status: **REVIEWED — 3 gates green, committing.** Task #52. Commit hash: see `git log` (this is the sprint-FINANCE-ASSISTANT-P1 commit). Phase 1 of the finance-assistant arc.

## Objective (recap)
Lay the data substrate for the finance-assistant decision tower (spec `finance/docs/finance_tools_spec.md`): unlock per-coin P&L (the spec's "pnl null everywhere" dead field), extend the macro layer, start daily macro+sentiment accumulation, and seam in a confidence field (the q-engine principle; full compute_q is Phase 2).

## What shipped (T1-T5)
- **T1 — OKX cost-basis → real pnl.** `OkxBalance` += `accAvgPx`/`spotUpl`/`spotUplRatio` (additive nullable). `exchange/service._parse_balances` parses them via `_opt_float` ('' → None, honest-null, never a fabricated 0). `finance/_okx_crypto_holdings` sets `Holding.avgCost = accAvgPx` when present → the shipped `_pnl(cost, value)` lights up; carries `okxSpotUplRatio` in the entry for the cross-check. **avgCost=accAvgPx is the single source of truth; spotUpl is cross-check only, not a 2nd pnl.**
- **T2 — macro +4 indicators.** `yield_curve_10y2y`(T10Y2Y) / `unemployment`(UNRATE) / `m2_liquidity`(M2SL) / `industrial_production`(INDPRO), fetched via the NO-KEY CSV (`_fetch_fred_csv`, reuse of FRED-MACRO `61f2ad8`). RESILIENT: retry the CSV (FRED_CSV_RETRIES) before fail-open to mock (T10Y2Y is HTTP-000 live). Each indicator source-tagged.
- **T3 — daily macro+sentiment snapshot routine.** `macro-snapshot` cron (07:30 daily) via the automation registry (`_external_func` resolves `macro_sentiment_snapshot` on demand — respects the module contract). Snaps F&G (alternative.me) / BTC.d (coingecko /global) / yield-curve daily; monthly FRED fields self-dedupe via month-ts upsert; fail-soft per signal.
- **T5 (folded in after live-verify) — per-holding pnl on finance_overview.** `Holding` += `pnl: PnL | None`. `_holding_from_entry` threads the EXISTING `entry["pnl"]` (NOT recomputed — same number `_aggregate` made). Surfaces per-holding granularity so a basis-less coin's null (USDT) doesn't MASK a real-basis coin's pnl (PEPE -58%) — the channel-level `basisUnknown` aggregate stays honestly null + UNTOUCHED. Dust entry → pnl None.
- **confidence seam (Phase-1 stub):** source-based (`fred`/`live` → 0.9; `mock` → 0.2) with `# Phase-2: replace with compute_q()` markers in macro/schema.py + macro/service.py — a clean seam, Phase 2 swaps real q in without touching call-sites.

### Verified counts (architect re-ran independently — Rule #0)
- P1 trio (finance_assistant_p1 + finance + finance_enrichment + macro + exchange + automation + mcp_read): **236 passed, 0 errors**.
- Full suite: **1565 passed, 6 skipped, 0 failed, 0 errors** (was 1549; T1-T4 → 1560, T5 → 1565), 1 benign httpx deprecation warning.
- mypy: the 2 errors in `exchange/service.py` (L50 float Any-None, L100 ExchangeOverview syncedAt) are **PRE-EXISTING** — confirmed by stashing P1 → same 2 errors on the pre-P1 version (at L36/L81). P1 introduced ZERO new mypy error.
- team-lead LIVE-verified incl. the DISTINGUISHING proof: finance_overview per-holding pnl PEPE -58.02% / ICP -20.4% / ARB -75.87% / S -81.15% / TRUMP -96.4% / IP -93.11% (REAL); USDT.pnl null + dust.pnl null (honest) — USDT-null AND PEPE-real IN THE SAME response proves per-holding granularity, not channel-masked. 7 macro indicators (3 fred-real + yield/dxy honest-mock on FRED-000). spotUpl cross-check held (<0.1pp).

## Assumptions (user-review)
- **Cost-basis reversal — OKX accAvgPx is FREE + real (the prior "dead-end" was WRONG).** OKX `account/balance` already returns per-coin `accAvgPx`/`spotUpl`/`spotUplRatio`; the old "no cost basis" conclusion tested orders-history (90d retention, empty) — the WRONG endpoint. So per-coin P&L needs NO write tool / NO user input for OKX coins. **How to change:** the memory `verify-source-has-real-data-before-building` is already corrected.
- **avgCost = accAvgPx (single source of truth for pnl).** Reuses the shipped `_pnl` path; spotUpl is OKX's own calc, carried only as a cross-check (sanity <5pp). **How to change:** `_okx_crypto_holdings` `avg_cost` line.
- **PMI = INDPRO proxy (no scrape, no fake).** ISM/S&P PMI is proprietary/no-free-API; INDPRO + (later) jobless-claims is the growth proxy; the missing axis is handled honestly by the Phase-2 q `coverage` term (3/4 → lower q, not a lie). **How to change:** add a PMI source if a free one appears.
- **Dust threshold inherited** from FINANCE-CORRECTNESS ($1.00) — unchanged this sprint.
- **confidence = Phase-1 source-based STUB (fred 0.9 / mock 0.2), seamed for Phase-2 compute_q().** NOT the real q yet — the freshness×coverage×agreement compute is Phase 2. **How to change:** swap `_confidence_for(source)` for `compute_q()` at the seam markers (call-sites unchanged).
- **Daily snapshot = daily-changers only (F&G / BTC.d / yield-curve).** Monthly FRED fields self-dedupe (re-storing an unchanged monthly value daily = noise). NAV is NOT re-snapshotted (portfolio_snapshot/take_snapshot already capture it via morning_pull). **How to change:** the `macro_sentiment_snapshot` signal list.

## Code review (architect — 4-step, full functions)
1. **git diff** — 10 code files (~298 ins) + 1 new test + 3 test count-bumps. `template/`+`data/` excluded.
2. **Read full functions** — `_opt_float` (honest-null ''→None); `_okx_crypto_holdings` (avg_cost=accAvgPx → _pnl, okxSpotUplRatio carried); `_holding_from_entry` (threads entry["pnl"], not recomputed); macro `fetch_latest` retry-then-mock + `fetch_fear_greed`/`fetch_btc_dominance` fail-soft; `macro_sentiment_snapshot` (daily-changers, monthly dedupe, fail-soft per signal); the automation registry `_external_func` resolution. `from __future__ annotations` present → `pnl: PnL` forward-ref OK.
3. **Verify against plan** — T1-T5 + all locks present: avgCost=accAvgPx single-source, no-key CSV, FRED-000 fail-open, additive-only, basisUnknown untouched, confidence seam, macro-only snapshot. ✅
4. **Hunt additional issues** — none. The 2 OKX pnl paths (`_okx_crypto_holdings` direct + `_aggregate` for manual) both use `_pnl` → consistent. The distinguishing test (USDT null + PEPE real same response) can't false-pass. 2 mypy errors verified pre-existing. The snapshot routine respects the module/registry contract (no hard automation→macro coupling).

## The 3 Quality Gates
- **Gate 1 — API:** ☑ /finance + /macro + /exchange responses additive (nullable fields) · ☑ no auth · ☑ FRED-000 → fail-open mock, NEVER 500 (tested) · ☑ snapshot routine fail-soft per signal. **PASS**
- **Gate 2 — Function:** ☑ tests assert observable behavior (real pnl lands, mock-honest on FRED-down, dedupe) · ☑ DIVERGENT fixtures (PEPE -58% real + USDT null same response; spotUpl sanity) · ☑ existing tests pass (full suite) · ☑ **0 errors** · ☑ honest-null explicit (''→None) · ☑ no NEW mypy error (2 pre-existing) · ☑ Phase-2 seam marked. **PASS**
- **Gate 3 — Sprint:** ☑ end doc w/ verified counts · ☑ architect spot-checked full functions · ☑ counts ≥ baseline · ☑ team-lead LIVE-verified incl. the distinguishing proof · ☑ assumptions logged (6) · ☑ commit format. **PASS**

## Risks / follow-ups
- T10Y2Y is HTTP-000 live (FRED no-key CSV transient/rate-limit) → currently honest-mock + low confidence; recovers when the feed does (resilient retry built).
- The confidence field is a Phase-1 STUB — Phase 2 replaces it with the real `compute_q()` (freshness×coverage×agreement) at the seam markers.
- **Phase 2 next:** q-engine (`compute_q`) → macro_cycle (the RL state, Investment Clock) → decision_weight (W = ∏q). The substrate this phase laid (real pnl, 4 macro axes, daily accumulation) feeds those.
