# End Sprint 3 — Market BE + ticker + S8 screen

> Result doc (CLAUDE.md §3.2). 2nd backend module (market price + alerts), real CoinGecko crypto + mock ETF/VN, wired TickerTape + built the S8 Market screen. Full feature set (per user "tính năng đầy đủ"), simple implementation (per north-star).
> Author: architect · 2026-06-06 · Commit: `feat(sprint-3)` on `main`.

---

## 1. What shipped

### Backend — `modules/market/` (2nd registry-discovered module, zero core edit)
- **schema.py** (FROZEN): `AssetQuote{symbol,name,assetClass,price,changePct:float|None,currency,ts,source}`, `AlertRule{id,symbol,op,threshold,enabled}` + `AlertRuleInput` (no id, POST body), `AlertTrigger{...,state:hit|near|far,distancePct}`, `AlertEvent`, `MacroSignal{name,value:str,status,note}`, `PricePoint`.
- **reader.py**: `read_quote` — `if assetClass=="crypto"` → CoinGecko free batch `/simple/price` (httpx, timeout, no key), else → deterministic mock (seed by symbol+date, stable for tests). **Fail-open**: feed down/timeout/429 → last-known from price_history else mock + warning, never crashes. `if/else` branch, NOT a plugin framework (north-star).
- **service.py**: tracked assets = flat config list (BTC/ETH/SOL crypto + VNINDEX/FUEVFVND mock). `get_market()` → quotes+triggers+macro+alertHistory. **changePct derived server-side from price_history** (≥24h-ago vs latest; fallback feed's usd_24h_change; None if no series — raw-data-first). `add_rule` = **UPSERT by (symbol,op)** (one threshold per symbol+op, no duplicates). `history(symbol,hours)`. Alert eval: hit/near(≤5%)/far + distancePct.
- **router.py**: `GET /market`, `GET /market/history/{symbol}` (empty series → 200+[]; unknown symbol → 404 — distinguishes empty-vs-unknown), `GET/POST /market/alerts` (POST takes AlertRuleInput, server-assigns id), `DELETE /market/alerts/{rule_id}`. Envelope + codes. `MODULE` auto-discovered.
- **market-poll routine** (interval 5min): fetch → persist to price_history → eval alerts → edge-trigger record fired alerts to run_log (alert history). Fail-open per asset. Detection+record; push-delivery (desktop/Discord) deferred.
- **db.py** helpers: `prices_for`/`latest_price`/`recent_runs` (price + alert-history queries).

### Frontend — TickerTape (real) + S8 Market screen
- `lib/types.ts` mirrors the frozen market schema verbatim.
- TickerTape → real `GET /market` quotes (replaced TICKER_MOCK), green/red from changePct.
- **S8 screen `app/market/page.tsx`**: live prices (5 assets, source tag), trigger table, macro block, alert history, threshold config form (set/delete via POST/DELETE). Render-only (changePct/distancePct/state from backend, FE formats; null→"—"). Reuses Sprint-2 shared components. useSafeRouter.

---

## 2. Verification (Rule #0 + behavior-test — architect + team-lead + tester)

| Check | Result |
|---|---|
| backend pytest default | **309 passed** |
| backend pytest `-n auto` | 309 passed (stable both orders) |
| CoinGecko fail-open (mocked 500/timeout) | last-known/mock + warning, no crash |
| Upsert (behavior-test) | POST {ETH,above,4000}+{4500} → **1 rule, threshold 4500** (no dup) |
| history empty-vs-unknown (behavior-test) | BTC (valid, empty series) → **200+[]** · ZZZ (untracked) → **404** |
| DELETE by id | 200; unknown id → 404 |
| data-fallback transparency | source tag: coingecko (real BTC/ETH/SOL) / mock (VNINDEX/FUEVFVND) |
| registry auto-discovery | /health modules=[market,projects] routines=[market-poll,wiki-refresh] — 0 core edit (2nd module) |
| frontend vitest + tsc | 186 passed + clean |
| Live Chrome /market (tester + team-lead, independent) | 5 assets render (BTC 60273 -3.6% / ETH 1545 -8.0% / SOL 61.7 -7.3% coingecko + VNINDEX 1277 / FUEVFVND 24.7 mock), ticker live + colors, macro (Fear&Greed/BTC-Dom/Brent), threshold form upsert-in-UI (set BTC/above 2× → 1 rule), fail-open during session (CoinGecko 429 → last-known, no crash), API pill "live" |

CoinGecko HTTP is MOCKED in all tests (never hit real API in CI — flaky/ratelimit). Verify-proportional (per team-lead rebalance): mock + fail-open test + one `-n auto` + teeth on new logic + live-Chrome — NOT the full Sprint-1 ritual.

---

## 3. The 3 Quality Gates

### Gate 1 — API (market router)
☑ Schema constraints · ☑ integration tests per endpoint (E/F active) · ☑ existing pass (309) · ☑ module auto-discovered (0 core edit) · ☑ envelope · ☑ codes 400/404 (empty-vs-unknown distinguished) · ☑ no auth (localhost).

### Gate 2 — Function
☑ Observable-behavior asserts (reader branch + fail-open, upsert, changePct, alert eval, history) · ☑ existing pass (309 + 186) · ☑ edge cases (empty series, unknown symbol, feed down, dup alert, null changePct) · ☑ error path explicit (fail-open reader; 404 unknown / 200 empty) · ☑ types (mypy + tsc clean) · ☑ no self-confirming asserts · ☑ FE Chrome self-verify.

### Gate 3 — Sprint
☑ end_sprint_3 + counts re-confirmed · ☑ architect proportional 4-step (reader/router/service/S8) · ☑ tester realigned + full green + Chrome · ☑ team-lead behavior-test re-verify · ☑ counts ≥ baseline (pytest 221→309, vitest 170→186) · ☑ findings flagged · ☑ format `feat(sprint-3)`.

**VERDICT: ✅ All 3 gates GREEN** (Chrome live confirmed by tester + team-lead independently; behavior-test upsert/history/fail-open PASS; 309 pytest + 186 vitest + tsc clean).

---

## 4. Assumptions (user-review — decide-and-log)

- **CoinGecko free** `/simple/price` for crypto (BTC/ETH/SOL), no key, timeout, batch one call. ETF/VN = deterministic mock. **System logic identical real-vs-mock — only the reader source swaps** (data-fallback §5). To change: add a real ETF/VN feed reader.
- **changePct = (latest - price ≥24h-ago)/that × 100** from OUR price_history (raw-data-first); fallback feed's usd_24h_change; None if no series. To change: edit the lookback window.
- **Alert = UPSERT by (symbol, op)** — one threshold per symbol+op (re-setting updates, never duplicates). op = above/below only (no pct — simple, add if needed). Persisted in md_store `market/alerts.md`. DELETE by server-assigned id. To change: allow multiple thresholds per pair (+ a richer alert model).
- **Alert state**: hit (crossed) / near (≤5% of threshold) / far. distancePct = (threshold-price)/price × 100.
- **history empty series → 200+[]** (valid asset, no data yet — raw-data-first, like /projects empty=[]); **unknown symbol → 404**. To change: n/a, this is the correct distinction.
- **MacroSignal = mock** (Fear&Greed/BTC-Dom/Brent, value as display string). Real macro feeds swap later (data-fallback). On-screen now per SPEC §S8.
- **market-poll = 5min interval, hardcoded**; detection+record only, push-delivery (desktop/Discord) deferred to a later sprint (infra, not a screen).
- **Tracked assets = flat config list** (`LIFEOS_MARKET_ASSETS` override), no asset-management API (1 dev edits the list).

---

## 5. Risks / out-of-scope (future)

- **Alert push-delivery** (desktop/Discord) deferred — detection + history work; delivery is the next market sprint.
- **Real ETF/VN feed** — mock now; swap a real reader later (logic unchanged).
- **CoinGecko rate-limit** — free tier ~10-30 req/min; the 5min poll + on-demand /market is well under, but if assets grow a lot, add caching/backoff. Not needed at 3 crypto.
- **Macro signals are mock** — clearly tagged; real feeds later.

---

## 6. Sprint Sync — Retro (process learnings)

1. **Schema-freeze-gate (THE lesson — memory `schema-freeze-gate`):** the market schema moved ≥4× while FE/tester were mirroring (distance↔distancePct, value float↔str, AlertRule no-id↔id, DELETE symbol/op↔id) → a cascade of stale-discrepancy rounds (FE's "3 bugs", tester's 14-fail ×2 were ALL pre-realign snapshots — zero real bugs among them). Fix isn't more verification (Rule #0 caught every drift) — it's **not opening the mirror handoff until the schema is frozen + announced.** New dispatch gate for contract sprints: backend freezes once + says "frozen — these fields", THEN FE/tester mirror.
2. **Behavior-test beats field-read (memory `behavior-test-not-field-read`):** the 2 REAL bugs this sprint (alert upsert-vs-append, history empty-vs-unknown) were invisible to static schema/field reads — they only surfaced by EXERCISING the behavior (POST twice; GET on empty DATA_DIR). For logic/state bugs, run the sequence + inspect the result, don't read the model.
3. **Verify-proportional rebalance (team-lead):** full Sprint-1 ritual (5 orders + xdist ×3 + teeth-all) reserved for Tier-S/suspect-order tests; normal sprint = default + one `-n auto` + teeth on NEW logic + live-Chrome. Kept verification sharp where it matters, lighter on routine work — proportional to a 1-dev app.
4. **North-star applied (memory `single-dev-no-overengineering`):** simple HOW (if/else reader not plugin, config-list assets not CRUD, alerts in md_store not new table), full WHAT (S8 screen + alert config + macro + history all shipped). Trimmed FE's spark/change7d (no SPEC payoff), op-pct (not needed) — cut technical complexity, not user value.
5. **Data-fallback proven:** CoinGecko real + mock ETF/VN, `source` tag makes it transparent. Real external network call #1 — fail-open held (never crashed on a down feed).

---

## 7. Commit
- `feat(sprint-3): Market BE + ticker + S8` — market module + FE ticker/S8 + plan/end docs. One commit.
- After: `sleep 120 && git push` → notify.py → team-lead Sprint Sync report → **Sprint 3B (Docker)** dispatch → then Sprint 4.
