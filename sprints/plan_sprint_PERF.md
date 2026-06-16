# Sprint PERF — kill finance N×2 CoinGecko fetches (in-process, NO Redis) (Task #68)

Finance tabs slow (0.7–15s); root = `get_quote()` does a fresh single-asset CoinGecko fetch every call, called per-coin with no cache. Fix in-process (memoize + batch) — NO Redis/infra (single-user, north-star). A perf fix must NOT change any derived number (valves intact).

## Kickoff — 2026-06-16 (§3.3a — root confirmed live + in code, baseline measured)

### Baseline (LIVE, container :8686)
- `/finance`: **0.73s / 0.77s / 2.71s** across 3 runs (varies with CoinGecko latency; memory saw up to ~15s under rate-limit).
- `/exchange`: **0.005s** (OKX one-shot — NOT the culprit; the control).
- The whole point is a MEASURABLE before/after — record `time_total` before + after.

### Root (confirmed in code — memory `finance-perf-no-cache-2026-06-16`)
- `read_quotes(assets: list[dict])` (market/reader.py:200) is **ALREADY batched** — ONE `_fetch_coingecko(cg_ids)` for all crypto. The waste is calling it ONE ASSET AT A TIME via `get_quote`.
- `get_quote(symbol)` (market/service.py:61) → `read_quotes([asset])` = one single-asset CoinGecko fetch, NO cache.
- finance `get_overview` per held coin: `_price_of` (L249, manual holdings only) → get_quote AND `_change_pct_of` (L268/L497, OKX coins) → get_quote. For the live OKX book each held coin → `_change_pct_of` → get_quote → 1 single-asset CG fetch (~6 priceable: PEPE/ICP/ARB/S/TRUMP/IP; USDT/dust don't need CG). Manual holdings would add the 2× (`_price_of` too) but are empty live.
- ⚠️ **The LYING docstring** (`_change_pct_of`, service.py:255-257): "the quote re-fetch here is served from cache within the request (no double network hit)" — FALSE, no request-cache exists. `get_quote` calls SOLELY supply `feed_fallback = quote.changePct` (the 24h-change fallback). The fix must make the docstring TRUE or delete the claim.
- get_quote callers: ONLY 3 (finance _price_of + _change_pct_of, market service.py:486) — small blast radius, a memo is clean.
- `cachetools` NOT installed → the optional TTL (3) needs a requirements.txt add (deps change → `--build`). So do (1)+(2) first (no new dep), measure, add TTL only if still needed.

## FIX (decide-and-log — in-process, NO Redis)
1. **Request-scoped batch + memoize get_quote** — at the top of `get_overview`, pre-fetch `read_quotes(<all held priceable symbols>)` in ONE batched call, populate a request-scoped quote map; `_price_of`/`_change_pct_of` (and get_quote) read from that map instead of each doing `read_quotes([one])`. Net: N single-asset CG calls → 1 batched call. Makes the lying docstring TRUE.
   - Mechanism (backend's choice, simplest correct): a `contextvars.ContextVar` request-memo set/reset around get_overview, OR thread a `quotes: dict[str, AssetQuote]` through `_price_of`/`_change_pct_of`. ContextVar is cleanest (no signature churn; get_quote checks the memo first). Whatever's chosen: the memo is REQUEST-SCOPED (set + RESET per get_overview call — no cross-request staleness).
2. **(already half-done by 1)** the batch IS `read_quotes(all)` — (1) folds batch + memoize together: one pre-fetch populates the memo.
3. **TTL cache 30–60s (OPTIONAL — DECIDE AFTER measuring 1):** only if (1) doesn't get it fast enough. Needs cachetools (requirements.txt add + `--build`). 60s-stale crypto is fine for a personal dashboard. **Do NOT add speculatively** — measure (1) first; if /finance is already <300ms, skip (3) (no-overengineering).

### HARD ACCEPTANCE
- **MEASURABLE speedup:** /finance time_total AFTER < baseline (target: the N CG calls → 1, so a warm call should drop toward the OKX-bound floor, well under 1s). Report before/after numbers.
- **CALL COUNT:** the CoinGecko fetch count per /finance drops from N (≈6) to 1 (assert/log the `_fetch_coingecko` call count — a test that counts calls, or a logged counter).
- **ZERO derived-number change (the valves — the whole risk of a perf fix):** pnlTotal (−617, #66), pnlScope (coveragePct 2.2), per-coin pnl, changePct, allocations, W=0 valve, honest-null — ALL byte-identical before/after. The fix is PURE plumbing (same quotes, fetched once). A behavior-test: /finance response body (minus timing) is identical pre/post.
- **request-scoped (no staleness):** the memo is set + RESET per get_overview — a 2nd request re-fetches (test: two calls, the memo doesn't leak; or a price change between calls is seen). NOT a process-global cache (that's (3), gated separately).
- **fail-open intact:** CoinGecko down → the batched call fail-opens to last-known/mock (read_quotes already does this) — same as before, just once.
- **the lying docstring fixed:** made true (memo exists) or the false claim deleted.
- existing finance + market tests + the #66 distinguishing/pnlScope tests ALL still pass (0 derived change).

## Decision (team-lead, 2026-06-16): do (1)+(2), MEASURE, DEFER (3)
team-lead approved (1) request-memoize + (2) batch this sprint; (3) TTL cachetools = LOGGED follow-up (ship 1+2, measure /finance time_total, decide (3) only if still needed). NO new dep this sprint. The HARD constraint: identical /finance payload pre/post (pipe-speed fix, not a logic change) — pnlTotal −617/pnlScope/W=0 valve/honest-null/distinguishing all unchanged.

## Scope
- IN: the request-memoize + batch-prefetch in get_overview (+ get_quote reads the memo); fix the docstring; the call-count + identical-body + speedup tests. (3) TTL DEFERRED (logged follow-up).
- OUT: NO Redis/queue/infra · NO change to any derived number (pnl/changePct/allocations/W) · NO change to read_quotes' batching (already correct) · NO new dep UNLESS (3) is justified by measurement · FE (none — pure backend perf).

## Risks / seams
- The ONLY risk of a perf fix = silently changing a number. Guard it HARD: assert the /finance body is IDENTICAL pre/post (the perf fix is plumbing). The #66 pnlTotal/pnlScope + the distinguishing tests are the canary — they must stay green.
- ContextVar memo MUST reset per request (a leaked memo = stale prices across requests — worse than slow). Test two sequential calls don't share stale state.
- Don't over-fix: if (1)+(2) gets /finance under ~300ms, STOP — skip the TTL + the cachetools dep (north-star). Measure, then decide (3).
- The OKX held-coin PRICE comes from OKX usdValue (free), not CoinGecko — only changePct-fallback hits get_quote. So the CG batch is for the changePct fallbacks; confirm the batch covers exactly the symbols that hit get_quote.
