# Sprint FINANCE-CORRECTNESS — per-holding value/price/changePct + dust fold

**Task #49. Theme:** finance data-correctness — `FinanceOverview.holdings` carries NO per-token price/value/changePct, so consumers (the agent, the FE list) can't tell a token's worth; sub-cent dust tokens clutter the list. Backend-only payload enrichment.
**Type:** numbered sprint (single backend theme, ~3 tasks).
**Source:** dogfood consumer-agent + team-lead live Rule#0 verify (finance_overview holdings=10 but market_watchlist=0 → holdings have no price; agent mis-read "ETH $0 vs market $1842" — the holding just carries no price).

## Locked scope (team-lead decide-and-log — user notify.py'd)
1. **Add per-holding `usdValue` + `price` + `changePct`**, priced from ONE consistent market feed (market `get_quote` / `derive_change_pct` — the same path the watchlist uses), NOT OKX-rounded. **ADD fields, don't remove.**
2. **Dust fold:** holdings with `usdValue` < threshold → folded into ONE "dust" summary entry (kept counted, honest — never fabricate). Threshold decided here (see Logic).
3. **holding↔watchlist gap: enrich price+changePct ONLY.** Do NOT build full auto-sync of holdings into the watchlist engine (over-engineering for 1-user; dust tokens don't need RSI/trend). If auto-sync seems warranted → FLAG team-lead, don't expand silently.

## Kickoff — 2026-06-15

### Current code (spot-checked finance + market service)
- **The price+value ALREADY EXIST internally.** `_aggregate(holdings)` (service.py:293) computes per-holding `{holding, price, source, value, pnl}` via `_price_of` (→ `market_service.get_quote`). But `get_overview` builds `FinanceOverview.holdings` from the BARE `Holding` objects (`list_holdings()` / OKX `[Holding(**e["holding"])...]`), **dropping** the computed price+value. → The sprint is largely SURFACING already-computed data onto the holdings list, NOT a from-scratch pricing build. (Big simplification — flag this to backend so it threads the existing `_aggregate` output, doesn't re-price.)
- **`changePct` is NET-NEW per holding.** `_aggregate` computes price+value but not changePct. The market path computes it via `derive_change_pct(symbol, latest_price, feed_fallback)` (service.py:82) — the SAME fn the watchlist uses (line 501). So per-holding changePct = call `derive_change_pct` per held symbol. ONE consistent feed (the locked requirement).
- **`get_quote(symbol)` returns a raw `AssetQuote` WITHOUT changePct filled** (changePct is filled by `_apply_change_pct` only in the full `get_market()` path). So backend must derive changePct explicitly per symbol — don't expect it on the bare quote.
- **OKX path:** the crypto channel holdings come from `_okx_crypto_holdings()` (value-only, `usdValue` from OKX, `avgCost=None`, honest-null pnl). These ALREADY carry usdValue internally — surface it.
- **Schema is FROZEN + self-describing-raw:** new DERIVED fields must carry inputs / be documented (convention at top of schema.py). `usdValue`/`price`/`changePct` are derived → document their source + honest-null semantics.

### Consumers of `FinanceOverview.holdings` (MANDATORY grep — additive-safe?)
- `mcp_servers/read_server.py:705` — `_brief_portfolio` uses `len(ov.holdings)` (COUNT only) → additive fields safe. ✅
- `modules/brief/reader.py:26` — holds the FinanceOverview object (no per-field holding read) → safe. ✅
- **FE `frontend/app/portfolio/page.tsx`** (the `/portfolio` LIST) — reads `h.channel/symbol/qty/avgCost/asOf`, shows **CHANNEL-level pnl** as an explicit workaround (page.tsx:8-9 docstring: *"holdings[] carry no per-row price → show the channel pnl"*). Additive optional fields won't break it; the FE *wiring* of the new fields is OUT of scope (backend-only sprint) but the data lands so a future FE sprint can use it. ✅
- **FE `frontend/app/portfolio/[id]/page.tsx`** (DETAIL) — uses the DIFFERENT priced shape from `get_channel` (`h.holding.symbol`, `{holding, price, value, pnl}`), already priced. Untouched by the overview change. ✅
- FE `Holding` TS type (types.ts:207) — `avgCost: number` (non-null) is already slightly out of sync with backend `float | None` (pre-existing FE drift, NOT this sprint). New fields = additive optional; flag the TS type as a future FE follow-up, don't touch it here. ✅
- **Verdict: additive-only is safe across ALL consumers.** Nothing reads holdings expecting a fixed field set; the only per-field reader (FE list) ignores unknown fields.

### Drift / risk
- Don't double-price: thread `_aggregate`'s existing per-holding `value`/`price` onto the surfaced holdings rather than re-calling `_price_of`. Re-pricing would risk a DIFFERENT number than the channel value (the bug we're fixing) — the channel `value` is `sum(per-holding value)`, so the surfaced per-holding value MUST be the same numbers that sum to it (consistency invariant).
- Dust threshold is a business rule → decide-and-log (Logic below).
- Honest-null: a held symbol with NO market quote (PEPE/TRUMP may be untracked) → `usdValue`/`price`/`changePct` must be honest-NULL, not 0 (a missing price ≠ zero worth — memory honest-null). NOTE: `_aggregate` currently fail-opens to avgCost-as-price for unpriced symbols — confirm that path still yields an honest value (avgCost*qty) OR null, not a misleading 0.

### Final task list
- **T1:** surface per-holding `usdValue`/`price`/`changePct` on `FinanceOverview.holdings` (thread `_aggregate`'s computed value+price; add changePct via `derive_change_pct`; honest-null on missing quote). Additive schema fields, documented self-describing. Consistency invariant: per-holding usdValue sums to channel value.
- **T2:** dust fold — holdings with `usdValue < THRESHOLD` collapse into ONE `{symbol:"dust", count, usdValue}` summary entry; real tokens stay individual. Counted + honest.
- **T3:** tests — distinguishing-case (real PEPE → real usdValue+changePct; dust ETH 1e-7 → folds, not a $0 line; missing-quote symbol → honest-null not 0) + the consistency invariant + all existing finance/overview tests + the read_server `len(holdings)` consumer unchanged.

### Locks (team-lead, 2026-06-15 — after approval)
1. **Consistency-invariant test = TOLERANCE, not exact `==`.** Each per-holding value is `round(price*qty, 2)`; summing N rounded values ≠ the channel's own rounded sum → exact `==` flakes. Assert `abs(sum(per-holding usdValue, incl dust) - channel value) < 0.01 * holding_count`. Keep the invariant, make it rounding-safe.
2. **Dust summary entry must be a VALID Holding.** Confirm `qty=0` passes `qty: Field(ge=0)` (0 OK), `symbol="·dust"` passes `min_length=1` (OK), no real token is ever literally "·dust" (· prefix = collision-proof, assert it). On the dust entry, `price` + `changePct` are NULL (a sum-of-many has no single price) — only `usdValue` + `count` meaningful.

### Decide-and-log (team-lead approved → notify.py user)
- Dust threshold `DUST_USD_THRESHOLD = 1.00`. usdValue < $1 → folded (null usdValue NOT folded — unknown ≠ small).
- Dust fold = display grouping; folded value still counts toward channel + total (totalValue unchanged).

### Routing
Dispatched to **backend-2** (the active backend instance; a stale `backend` from a prior session is idle/stood-down). team-lead verifies live (invariant + distinguishing case on the real container) on backend done, BEFORE architect review+commit.
