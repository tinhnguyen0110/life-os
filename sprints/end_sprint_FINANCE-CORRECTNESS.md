# End Sprint FINANCE-CORRECTNESS — per-holding value/price/changePct + dust fold

> Status: **REVIEWED — 3 gates green, committing.** Task #49. Commit hash: see `git log` (this is the sprint-FINANCE-CORRECTNESS commit).

## Objective (recap)
`FinanceOverview.holdings` carried NO per-token price/value/changePct → the agent + FE couldn't tell a token's worth; sub-cent dust tokens cluttered the list. Backend-only payload enrichment: surface usdValue/price/changePct (from the numbers `_aggregate` already computes — NOT re-priced) + fold sub-$1 holdings into one per-channel `·dust` summary.

## What shipped
- **`modules/finance/schema.py`** — 5 additive nullable fields on `Holding`: `price`, `usdValue` (= price×qty, the same number that sums to channel value), `changePct` (via `derive_change_pct`), `isDust`, `count`. All documented self-describing per the FROZEN convention; price+changePct stated NULL on a dust entry.
- **`modules/finance/service.py`** —
  - `_holding_from_entry()` surfaces price/usdValue/changePct from the aggregate entry (never re-prices). UNPRICEABLE (OKX no-value, OR cost-fallback with no real basis → price 0) → null price+usdValue → stays VISIBLE.
  - `_is_dust()` — priced AND known usdValue AND strict `< DUST_USD_THRESHOLD ($1.00)`. Null-price/null-usdValue → NOT dust.
  - `_fold_dust()` — per channel, collapse priced-sub-$1 into ONE `·dust` Holding (isDust, count, usdValue=sum). Display-only; totals unchanged.
  - `_enriched_holdings(by_channel)` — builds the flat list from `by_channel` (post-OKX-override) → consistency invariant holds BY CONSTRUCTION.
  - `get_overview` now sets `holdings=_enriched_holdings(by_channel)`; the old G2 flat-rebuild (`[Holding(**e["holding"])...]` that DROPPED price) is removed — that was the bug source.
  - `_change_pct_of()` — per-holding 24h % via the watchlist's `derive_change_pct`; the re-`get_quote` is served from the 30s CoinGecko TTL cache (no double network hit — verified).
- **`tests/test_finance_enrichment.py`** (NEW, 14 tests) — behavior-tested (seed → get_overview → assert), divergent fixtures.

### Verified counts (architect re-ran independently — Rule #0)
- Finance trio (`test_finance_enrichment` + `test_finance` + `test_mcp_read`): **159 passed, 0 errors**.
- Full suite: **1528 passed, 6 skipped, 0 failed, 0 errors** (1514 baseline + 14 new = 1528, matches backend's report). 1 benign httpx deprecation warning.
- mypy: `finance/service.py` + `finance/schema.py` **clean**.
- team-lead's LIVE-container verify (the final gate): 8 holdings (ETH/LINK/DOGE folded into one ·dust count=3), 7 real tokens individual w/ usdValue+price, invariant EXACT (sum crypto = 10651.27 == channel 10651.27), changePct None (live CoinGecko 429 → honest-null fail-open, NOT a code bug; test L80 proves it populates with a series).

## Assumptions (user-review)
- **Dust threshold = $1.00** (`DUST_USD_THRESHOLD`) — holdings with 0<usdValue<$1 fold into one per-channel `·dust` summary. **Why:** the real dust (ETH/LINK/DOGE ~1e-7 qty) is ~$0; $1 folds genuinely-negligible positions while keeping anything a user might track. **How to change:** the one constant in `finance/service.py`.
- **Dust fold = DISPLAY grouping, value PRESERVED** — folded dust's usdValue still counts toward channel value + totalValue (the fold is on the surfaced list only, AFTER values are computed). totalValue is UNCHANGED by folding. **Why:** honest — never hide value, only de-clutter the display. **How to change:** remove the `_fold_dust` call in `_enriched_holdings`.
- **Sub-cent-priced (usdValue rounds to 0.0) WITH a real price DOES fold** (team-lead ruling on the spec gap). **Why:** a coin OKX prices at sub-cent (1e-7 qty) IS ~$0 worth — folding it removes the exact `$0.00` clutter the consumer-agent complained about. A `0 < usdValue` predicate would have left it an ugly $0.00 line; the rule is `usdValue < threshold` including 0.0-with-price. **How to change:** the `_is_dust` predicate.
- **avgCost=0 / no-quote → UNPRICEABLE, stays visible (NOT folded)** (backend's extra-edge, team-lead + architect ratified). **Why:** a cost-fallback price of 0.0 from a zero basis is the ABSENCE of a price, NOT a real $0 valuation — folding it would hide an unknown-worth holding. So a 0-price-from-no-basis → null price+usdValue → visible (the agent sees "I don't know this token's worth", honest). A cost-fallback WITH a real avgCost keeps usdValue=avgCost×qty (honest estimate). **How to change:** the `unpriceable` clause in `_holding_from_entry`.

## Code review (architect — 4-step, full functions)
1. **git diff** — schema +41 (5 fields), service +148 (5 new fns + get_overview rewire + G2-block removal), new test file. `template/`+`data/` are pre-existing/runtime — excluded.
2. **Read full functions** — traced `get_overview` → `_enriched_holdings` → `_holding_from_entry`/`_is_dust`/`_fold_dust` entry→exit. Invariant holds by construction (flat list built from the same `by_channel` entries that produce channel value). Removed G2 rebuild is the precise bug fix. `_change_pct_of` TTL-cache claim verified against reader.py (COINGECKO_TTL_S=30).
3. **Verify against plan** — every locked item present: surface-not-reprice, $1 strict threshold, dust-valid-Holding, null≠dust, honest-null, invariant-with-tolerance, no FE/no auto-sync.
4. **Hunt additional issues** — none. The BUG-KILLER test uses a 0.0-usdValue-WITH-price fixture (TINY 1e-9), not a happy $0.50 — exercises the real boundary. avgCost=0 edge correctly handled. No double network hit (TTL cache). No consumer breakage (read_server len() test asserts folded count).

## The 3 Quality Gates
- **Gate 1 — API:** ☑ /finance response shape additive (FinanceOverview unchanged structurally; Holding gains nullable fields) · ☑ no auth · ☑ integration covered (get_overview behavior tests) · ☑ no module-mutation introduced. **PASS**
- **Gate 2 — Function:** ☑ 14 unit/behavior tests assert observable behavior (seed→get_overview→assert), DIVERGENT fixtures · ☑ existing tests pass (full suite 1528) · ☑ **0 errors / 0 unhandled rejections** (full tail read) · ☑ edge cases: dust 0.0-with-price, strict $1 boundary, null≠dust, missing-quote estimate, no-dust · ☑ honest-null explicit · ☑ mypy clean · ☑ no self-confirming asserts (re-validates Holding(**dust.model_dump())). **PASS**
- **Gate 3 — Sprint:** ☑ end doc written w/ verified counts · ☑ architect spot-checked full functions · ☑ counts ≥ baseline (1528 ≥ 1514) · ☑ team-lead LIVE-verified (invariant + distinguishing case on real container) — final gate, no separate tester for no-UI sprint · ☑ assumptions logged (4 items) · ☑ commit format. **PASS**

## Risks / follow-ups
- FE `Holding` TS type (types.ts:207) is out of sync (`avgCost: number` non-null vs backend `float | None`, and lacks the 5 new fields) — PRE-EXISTING + the new fields are a future FE sprint (wiring per-holding usdValue into the /portfolio list, which currently shows channel-level pnl as a workaround). Flagged, NOT this backend-only sprint.
- changePct shows None live right now due to a CoinGecko 429 (external, fail-open) — correct behavior; it populates when the feed recovers / a series exists.
