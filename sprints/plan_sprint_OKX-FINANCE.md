# Sprint OKX-FINANCE — wire OKX per-coin balances into finance holdings (closes G2)

> User approved "tích hợp luôn" — integrate OKX balances into finance per-coin holdings (vs manual entry).
> Backend-only. The crux is the avgCost/P&L decision (OKX has no per-coin cost basis).

## Kickoff — 2026-06-15 (architect)

### Verified the data + existing wiring (the decision-shaping facts)
- **`finance_overview.holdings` is EMPTY (G2)** — can't answer "which coin am I most down on / has the most value."
- **OKX per-coin balances exist** (`exchange.OkxBalance{symbol, available, frozen, total, usdValue}`, ~10 coins live per team-lead). NO `avgCost` (OKX unified-account doesn't expose cost basis).
- **`Holding.avgCost` is REQUIRED** (schema.py:27, `ge=0`) — the phantom-field risk team-lead flagged.
- **The channel-level OKX→finance wiring ALREADY EXISTS:** `finance/service.py` imports `exchange_service`, `_okx_crypto_value()` (L345) reads OKX total, `_ensure_crypto_basis(okx_total)` (L195) snapshots the AGGREGATE crypto-channel cost on first OKX connect. So the **crypto CHANNEL value + P&L already works** (OKX total vs the aggregate snapshot basis).
- **`crypto_basis` is a SINGLE AGGREGATE** (`get_crypto_basis() -> (basis_usd, source)`), **NOT per-coin.** So there is NO per-coin cost basis anywhere.

### 🔑 THE DECISION (logic-owner call — decide-and-log) — refined Option A
team-lead's Option A assumed crypto_basis gives per-coin basis — but it's aggregate-only. So:
- **Per-coin VALUE / qty / allocation** → fully answerable from OKX (the "which coin has the most value / biggest slice" question). Build this.
- **Per-coin P&L** ("which coin is down MOST") → **honest-null** per coin. No per-coin cost basis exists; OKX doesn't provide it; the aggregate basis can't be split across coins without fabricating. Showing a `0` avgCost would fabricate a fake +∞% gain — NOT acceptable (honest-mirror).
- **The aggregate channel P&L still works** (existing wiring) — so "is my crypto channel up or down overall" IS answerable.

**Decision: OKX feeds per-coin holdings as VALUE-ONLY (qty + symbol + usdValue + allocation%); per-coin P&L = honest-null ("no per-coin cost basis").** To do this cleanly, `Holding.avgCost` becomes OPTIONAL (or a parallel value-only holding shape) so an OKX per-coin entry doesn't require a phantom cost. When a per-coin basis IS later set (future: extend crypto_basis to per-coin, or user PUT), that coin's P&L lights up. This answers G2 honestly: per-coin value/allocation now; per-coin P&L when basis exists; aggregate P&L always.

### Other decisions (logged)
- **Read-time merge, NOT sync-write** (team-lead-recommended + mine): `finance_overview` reads OKX balances LIVE each call (always fresh, no stale persisted state). The manual `holdings.md` still serves non-OKX channels (dry/etf/vn) — OKX merge is crypto-channel-only; **don't clobber manual non-crypto holdings.**
- **No double-count:** OKX crypto holdings REPLACE any manual crypto holdings (OKX is the source of truth for the crypto channel); manual etf/vn/dry holdings are untouched.
- **Fail-soft:** OKX unconfigured/down → finance falls back to manual holdings entirely (the existing `_okx_crypto_value` fail-open pattern — `get_overview()` never raises). finance_overview must NEVER break because OKX is down.

### Final task list (single backend lane)
- **OKX-FINANCE [backend]** — `finance.list_holdings`/`overview` merges OKX per-coin balances into the crypto channel (value-only, honest-null per-coin P&L), read-time, fail-soft, no-double-count, non-crypto manual intact. `Holding.avgCost` → optional (for OKX value-only entries).

## Assumptions (user-review)
- **OKX per-coin holdings = value-only** (qty/symbol/usdValue/allocation); **per-coin P&L is honest-null** because OKX has no per-coin cost basis + crypto_basis is aggregate-only. Aggregate crypto-channel P&L still works (existing snapshot). — to give per-coin P&L: extend crypto_basis to per-coin (future) or user sets it.
- Read-time merge (OKX live each call), crypto-channel only; manual non-crypto holdings (etf/vn/dry) untouched; OKX replaces manual crypto (no double-count); fail-soft when OKX down.
- `Holding.avgCost` made OPTIONAL so OKX value-only entries don't fabricate a cost.

### Deferred (logged, team-lead-confirmed PROCEED with (a), NOT (b))
- **Per-coin P&L** requires per-coin cost basis, which doesn't exist (OKX has none; crypto_basis is aggregate).
  Future task: **extend crypto_basis to PER-COIN** (a `crypto_basis.md` per-symbol map, or user PUT per coin) →
  unlocks per-coin P&L ("which coin am I down MOST"). Bigger (needs user input per coin) → deferred, not this sprint.
  Trigger: user wants per-coin P&L (not just per-coin value/allocation). Until then, per-coin P&L stays honest-null.
