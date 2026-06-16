# Sprint FINANCE-AUDIT-S3 — OHLC history for held coins (light up s_asset)

**Task #62.** The "fix works data thin → now data deepens" follow-on the S1B end_sprint flagged. S2 made s_asset read held coins, but the held coins have NO price-history → s_asset stuck 0/6 → W=0. Capture real OHLC for held coins so RSI computes → s_asset > 0 → the tower can escape W=0. Backend-only, NEUTRAL.

## Kickoff — 2026-06-16 (source VERIFIED live by team-lead; capture path read)

### The gap (root, confirmed)
- `compute_indicators(asset)` reads `history(asset)` → `price_history` rows by `asset`. A held coin with NO rows → RSI None → s_asset present:false → 0.
- `price_history` currently has ONLY the watchlist (BTC/ETH/SOL/XAU/VNINDEX/FUEVFVND) — NOT the held coins (PEPE/ICP/ARB/S/TRUMP/IP). The existing `backfill_history` only works for `tracked_assets()` with a cgId — held coins aren't tracked → skipped.

### Source VERIFIED (team-lead live-checked BEFORE dispatch — the verify-source-before-build / OKX-orders-dead-end lesson):
- OKX `/api/v5/market/candles?instId=<SYM>-USDT&bar=1D` (PUBLIC, no-auth) → real candles for PEPE/ICP/ARB/TRUMP ✅ — the PRIMARY source.
- CoinGecko `/coins/<id>/market_chart?days=30` → real series (721 pts for pepe) ✅ — the FALLBACK.
- So real OHLC IS available per held coin (NOT a dead-end). A coin on NEITHER → honest-null (don't fabricate).

### The capture path to REUSE (don't build a parallel one)
- **`db.record_price(asset, price, ts, source)`** (store/db.py:141) — the single write point into `price_history`. The capture writes HERE.
- **`history()`/`compute_indicators`** (read path) — UNCHANGED; they already read price_history by asset. Once held-coin rows land, RSI + s_asset light up automatically.
- **`_held_symbols()`** (decision/service.py, S2) — the dust+stablecoin-excluded held set. Capture iterates THIS.
- **`fetch_market_chart(cg_id, days)`** (market/reader.py:148) — the existing CoinGecko historical fetch (the fallback; cgId = symbol.lower() best-effort, like get_quote does).
- **NEW: an OKX public candles fetch** — OKX `/market/candles` is PUBLIC, but exchange/reader's `_get` SIGNS every request. So add a small UNSIGNED public GET for market/candles (no auth needed — public endpoint; held coins are tradeable regardless of the user's account). This is the only genuinely-new piece.

## Scope (3 parts)
- **Part 1 — held-coin price-history capture:** a fn that reads `_held_symbols()` → per coin, fetch a daily candle series (OKX public market/candles PRIMARY → CoinGecko market_chart FALLBACK → honest-skip if neither) → `record_price(symbol, price, ts, source="okx-candles"/"coingecko-hist")`. Fail-soft per coin (one fails → others capture). Honest source tag.
- **Part 2 — routine + one-time backfill:** wire to a daily scheduler routine (mirror macro-snapshot) so it accumulates; + a ONE-TIME backfill (~30d) so RSI (needs ~14+ points) works NOW, not in 2 weeks. Idempotent (don't dup a day's row — dedup by asset+ts day, like the snapshot pattern).
- **Part 3 — s_asset lights up:** NO code change to s_asset/compute_indicators — once the held coins have ~14+ price_history rows, `compute_indicators(PEPE)` → real RSI → s_asset > 0 → W can escape 0. (The plumbing from S2 is correct; S3 just feeds it data.)

## Locks (team-lead, 2026-06-16 — approved as drafted + 2 added)
- **LOCK #1 — idempotent dedup covers BOTH backfill AND daily overlap:** `record_price` dedup by (asset, UTC DAY) — re-running the backfill, OR the daily routine twice same-day, OR backfill-then-daily-same-day → NO duplicate rows (ONE row per asset per day, latest wins; same discipline as nav/macro-snapshot's day-PK upsert). Test: run backfill TWICE → row count STABLE.
- **LOCK #2 — OKX candle parse (a real-but-WRONG-RSI trap):** OKX candle = `[ts, open, high, low, close, vol, ...]` — use `close` (index 4), NOT open. OKX returns NEWEST-FIRST → store ASCENDING by ts (oldest→newest, as history()+RSI expect). SANITY ASSERT: stored series' LATEST price ≈ the live quote (±sane band, e.g. ±10%) — catches an open-vs-close or reversed-order bug. Test it.

## ACCEPTANCE (hard)
- (1) **held coins get REAL price_history rows** (OKX candles, honest source) — verify PER-COIN the source actually returns data (a held coin not on OKX → CoinGecko → honest-null/skip if neither; NEVER fabricate a series).
- (2) **after backfill: `market_indicators(PEPE)` returns a REAL RSI (not None)**; s_asset live goes 0/6 → >0/6.
- (3) **W can be > 0** when all 4 layers nonzero — BUT the **W=0 VALVE STILL HOLDS** for a coin genuinely without history (honest-missing, NOT backfilled-fake). DISTINGUISHING: a held coin WITH fetched history → contributes; one with NO source → still 0, SAME call. NO fake data forces the tower on.
- (4) **idempotent (LOCK #1)** — run backfill TWICE → row count STABLE (one row per asset per day); covers backfill+daily overlap.
- (5) **OKX parse correct (LOCK #2)** — stored series uses CLOSE, ascending; latest stored price ≈ live quote (±sane band) — proves not open/reversed.
- (6) fail-soft per coin (one fetch fails → others capture); NEUTRAL.

## Risks / seams
- The DISTINGUISHING (3) is the spine: real-history-coin lights s_asset, no-source-coin stays 0 — proves the data is REAL per coin, not a blanket backfill that fakes everyone. Test a coin with a (mocked) real series + one with none.
- OKX public candles = an UNSIGNED GET (don't reuse the signed `_get`). Fail-open to CoinGecko, then honest-skip.
- Idempotent: dedup by asset+day (the snapshot pattern) — re-running the routine/backfill doesn't duplicate rows.
- REUSE record_price + the read path — don't build a parallel store. Only the CAPTURE source-list (held vs tracked) + the OKX-candles fetch are new.
- Don't fabricate: a coin on neither source → honest-null, no synthetic series (the audit's whole spine — real data only).
- After S3: s_asset is no longer structurally stuck at 0 — it reflects the held coins' real technicals as data accumulates daily.
