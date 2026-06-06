# Plan Sprint 3 — Market BE + ticker wiring (S8, ARCH §9 step 2)

> DRAFT (CLAUDE.md §3.3) — refresh via kickoff before dispatch. Second backend module: market price + alerts. Wires the Sprint-0 TickerTape (currently TICKER_MOCK) to real data.
> Spec: SPEC §S8 (Market & Alerts). ARCH §9 step 2. Data-fallback (operating-model §5): CoinGecko FREE for crypto, MOCK for ETF/VN — build against the schema with mock, swap real reader later. Memory: data-source-fallback.
> Author: architect · 2026-06-06 · Status: awaiting team-lead greenlight after Sprint 2 push.

## Objective
Build the `market` feature module (router/schema/service/reader) + a `market-poll` routine, persisting price points to the Sprint-0 SQLite `price_history` table. Per-asset-class reader strategy: crypto = CoinGecko free API (real), ETF/VN-Index = realistic mock (swap later). Wire TickerTape + S8 data via the API. **System LOGIC is identical whether data is real or mock — only the source swaps.**

## Tasks (4-5, ≥2 parallel)
- **T1 [backend, GATING] — market schema + per-asset-class reader + service.**
  - `schema.py`: `PricePoint {asset, price, currency, source, ts}`, `AssetQuote {asset, price, change24h, changePct, class, ts}`, `AlertRule {asset, op, threshold, ...}`.
  - `reader.py`: a SIMPLE branch on asset class — `crypto` → CoinGecko free, else → mock from `data.js`. NOT a strategy/plugin framework — `if class == "crypto": ... else: mock`. Fail-open per asset.
  - `service.py`: tracked assets (a plain dict/list in config — NOT a CRUD registry), orchestrate reader, compute `change24h`/`changePct` from `price_history` server-side.
  - Gates T2/T3.
- **T2 [backend] — market router + persist to price_history.**
  - `GET /market` (quotes + trigger table + alert history), `GET /market/history/{asset}`, **alert-rule set/delete** (so the user CAN configure thresholds per SPEC §S8 "Cấu hình ngưỡng alert per-asset" — that's a real feature, keep it; just implement it as simple md_store/SQLite writes, not a heavy CRUD framework). Poll writes via `db.record_price`. Envelope + error codes. `MODULE` auto-discovered.
  - Macro signals (Brent/CPI/Fed — SPEC §S8): return a SIMPLE stub/mock block this sprint (the feature appears on screen; real macro feeds swap in later per data-fallback). Don't omit it — the user's S8 shows it.
- **T3 [backend] — market-poll routine.**
  - `Routine(market-poll, interval 5min)`: fetch tracked assets, persist, evaluate alert rules, RECORD fired alerts to run_log (the user sees alert history per SPEC §S8). Fail-open per asset. Detection + record this sprint; push DELIVERY (desktop/Discord) is a later sprint — but the alert HISTORY the user views IS in scope.
- **T4 [frontend] — TickerTape + S8 Market screen (full feature).**
  - TickerTape → real `GET /market` quotes (replace TICKER_MOCK), green/red from changePct.
  - **S8 screen (`app/market/page.tsx`) — BUILD IT** (the user needs the screen, SPEC §S8): real-time prices, trigger table ("đã chạm / còn cách bao xa"), macro-signal block, alert history, per-asset threshold config UI. Port the mock. Render-only for derived data. (This is the user-facing feature — keep it; implement simply with the shared components from Sprint 2.)
- **T5 [tester] — verify.**
  - pytest: reader (CoinGecko mocked + mock-class deterministic), changePct math, alert-trigger eval, price_history + alert-history row-exists (Sprint-13 lesson), fail-open feed-down. Chrome live (:3010→:8001): ticker real prices + colors, S8 screen renders prices/triggers/macro/history, threshold config works. Cover real behavior.

## Logic/Algorithm (architect decides — decide-and-log; market is non-CRUD)
> Decide these at kickoff + log to §Assumptions:
- **Per-class price source:** crypto=CoinGecko free `/simple/price?ids=...&vs_currencies=usd&include_24hr_change=true`; etf/vn=mock (seeded realistic). Fail-open: feed down → last `price_history` value + a warning, never crash.
- **change24h / changePct:** derived server-side from `price_history` (the point ≥24h ago vs now), NOT from the feed's own field where possible (raw-data-first — we own the series). If <24h of history, use the feed's `include_24hr_change` as fallback.
- **Alert trigger (SIMPLE):** a hardcoded list of `{asset, op: above|below, threshold}` in config. State = hit / near (within a fixed % — pick one, e.g. 5%) / far. "Còn cách bao xa" = `(threshold - price)/price`. No rule-CRUD, no per-state config knobs — 1 dev, a few thresholds in a file.
- **market-poll cadence:** 5min interval, hardcoded (don't make it configurable until needed).
- **Tracked assets:** a plain list seeded from mock `data.js` (BTC/ETH + a couple ETF/VN). Edit the list in config if it changes — no asset-management API.

## Defensive (MANDATORY)
- CoinGecko down/ratelimited/timeout → fail-open to last-known price + warning; the poll + endpoint never crash.
- Empty price_history (first run) → changePct null/0, no divide-by-zero.
- Unknown asset class → skip with warning.
- Network reader has a timeout (don't hang the routine).

## Dispatch standards (every task)
- Runtime: BE `uvicorn main:app` :8000 (CORS now works) · FE `npm run dev` :3010.
- Baseline: pytest 221, vitest 170.
- Ownership: failing test → report, don't edit; tester reports never fixes; re-read cross-file at current mtime before reporting (team rule).
- FE (T4): mock file = mock `data.js` ticker shape; "render-only — backend computes changePct/triggers."

## Dispatch ordering
1. T1 GATING (schema + reader + service) alone.
2. T2 + T3 fan out after T1.
3. T4 (FE ticker) after T2 (needs the /market endpoint). T5 pre-scaffolds from T1.

## Kickoff — 2026-06-06
### Verified live (data-fallback §5 bước 3 — xem payload thật trước khi code)
- **CoinGecko free SỐNG:** `GET /api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true` → `{"bitcoin":{"usd":60818,"usd_24h_change":-3.14},"ethereum":{...}}`. No API key, fast. Shape locked: `{<id>:{usd:float, usd_24h_change:float}}`.
- **price_history table có sẵn** (Sprint 0): `record_price(asset, price, ts, currency="USD", source=None)`. Cột asset/price/currency/source/ts(ISO). Reader chỉ cần gọi nó.
- **Mock shape** (data.js): `{sym, price, chg}` để seed ETF/VN.
- Không drift. Reader = `if class=="crypto": coingecko else: mock` — đúng kim chỉ nam (đơn giản kỹ thuật).
### Feature scope (sau khi user làm rõ "tính năng đầy đủ")
- S8 screen + alert config + macro block + alert history ĐỀU LÀM (SPEC §S8). Chỉ alert push-delivery (desktop/Discord) defer.

## Open items at kickoff
- CoinGecko: verify the free endpoint + rate limits at kickoff (operating-model §5 step 3 — inspect the real payload before coding); if unusable → all-mock this sprint, swap later.
- "near" alert threshold % (decide).
- S8 screen LANDS this sprint (user needs the full feature — clarified by user "tính năng vẫn đầy đủ"). Only alert push-DELIVERY (desktop/Discord) defers — that's infra, not a screen.

## Logic decisions (chốt khi backend hỏi — decide-and-log → §Assumptions)
- Assets: config list BTC/ETH/SOL (crypto→CoinGecko cgId) + VNINDEX(1283.5)/FUEVFVND(24.8) (mock). `LIFEOS_MARKET_ASSETS` override.
- CoinGecko: batch `/simple/price?ids=...&vs_currencies=usd&include_24hr_change=true`, no key, timeout 8s, fail-open→last-known else mock.
- changePct = (latest - price_at_or_before(now-24h))/that*100; thiếu history → feed usd_24h_change; không có gì → None.
- AlertRule {id,symbol,op:above|below,threshold,enabled} in md_store `market/alerts.md`. op CHỈ above/below (bỏ pct — đủ dùng, kim chỉ nam). State hit/near(≤5%)/far, distance=(threshold-price)/price*100. Edge-trigger record→run_log.
- alertHistory = run_log query (routine_id=market-poll, status=warn, latest 20). MacroSignal = mock list (Fear&Greed/BTC-Dom/Brent). 
- Endpoints: GET /market (quotes+triggers+macro+history), GET /market/history/{sym}?hours=24, POST/DELETE /market/alerts.
- Mock deterministic (seed hash(symbol+date), KHÔNG random thuần — test ổn định).
