# End Sprint PERF — finance get_quote memoize + batch (no Redis) (Task #68)

> Status: **REVIEWED — 3 gates green, committing.** Task #68. Finance tabs were slow (0.73–15s) — `get_quote()` did a fresh single-asset CoinGecko fetch per coin, no cache. Fixed in-process (request-scoped memo + batch-prefetch) → N CG calls → 1. The hard guard (identical payload pre/post) held: a pipe-speed fix, NOT a logic change. NO Redis, NO new dep.

## What shipped
- **Request-scoped quote memo (`market/service.py`, ContextVar):** `_quote_memo: ContextVar[dict[str,AssetQuote]|None]` (default None = no batch → today's behavior unchanged for all other callers). `begin_quote_batch()` sets `{}` + returns the token; `end_quote_batch(token)` resets it (ALWAYS in a `finally` → never leaks across requests — a leaked memo = stale prices, worse than slow). `prefetch_quotes(symbols)` dedups + ONE `reader.read_quotes(all)` → populates the memo with the reader's OWN AssetQuote objects (so `_feed_change_pct` rides along → identical quote). `get_quote(sym)`: memo HIT → return the memoized quote (no network); MISS with an active memo → single read + STORE (so the 2nd same-symbol call this request — `_price_of` then `_change_pct_of` — is also a hit, dedup even for an ad-hoc symbol). `_asset_for()` extracted so a memoized quote is built byte-identically to a fresh one.
- **`get_overview` (`finance/service.py`) is now a thin wrapper:** `begin_quote_batch()` → try `prefetch_quotes(_overview_priced_symbols(holdings))` + `_get_overview_impl(holdings)` → `finally end_quote_batch(token)`. The entire original body is unchanged in `_get_overview_impl` — the numbers can't change. `_overview_priced_symbols` extracts symbol STRINGS only (manual + OKX held); fail-soft (OKX read error → just manual symbols; the batch is an optimization, never a correctness dependency).
- **The lying docstring fixed:** `_change_pct_of`'s false "the feed is TTL-cached, served from cache within the request" → the TRUE "get_overview opens a request-scoped quote memo, so this re-fetch is served from the memo."
- **(3) TTL/cachetools DEFERRED** (team-lead) — not needed: the memo+batch already dropped /finance to ~10ms warm. No new dep, no `--build`.

### Verified counts (architect re-ran independently — Rule #0)
- finance + market suites: **151 passed, 0 errors**. Full suite: **1649 passed, 6 skipped, 0 failed, 0 errors** (was 1638; +11 #68 tests). mypy: market/service.py + finance/service.py **clean**.
- **LIVE timing (architect, the headline measure):** /finance **0.35s / 0.009s / 0.011s** (3 runs) — warm calls ~**10ms** vs the **0.73–2.71s** baseline (up to 15s under CG rate-limit). The first run is the single batched CoinGecko fetch; subsequent runs hit the OKX-cached snapshot floor. **~70–250× faster warm.**
- **LIVE canary (the #66 invariant still holds post-perf):** /finance pnlTotal.abs −615.74 == Σ per-coin −615.74 (exact), pnlScope.coveragePct 2.2. (The −615.74 vs the earlier −617.03 is REAL market movement — coins ticked — NOT a regression; the model_dump-equality test is the deterministic proof the LOGIC is unchanged.)

## Code review (architect — 4-step, the identical-payload guard + seam-A + memo-no-leak hardest)
1. **git status/diff** — files STABLE (newest mtime 15:11, reviewed 15:27 — >16min, not in-flight). Files: market/service (the memo) + finance/service (the wrapper) + test_finance + test_finance_okx + test_market + plan/end_sprint. `template/*` + `data/` EXCLUDED.
2. **Read full functions** — the ContextVar memo + begin/end/prefetch + `_asset_for` + the new get_quote (hit/miss-store); the `get_overview` wrapper + `_overview_priced_symbols` + `_get_overview_impl` (body unchanged); the docstring fix.
3. **Verify against plan + the 5 acceptance gates** — identical-payload, call-count, request-scoped, fail-open, docstring-true + the 2 seams (snapshot consistency, store-on-miss). All have a dedicated test.
4. **Hunt additional issues — verified in code + LIVE:**
   - **(1) IDENTICAL PAYLOAD (the spine)** — `test_perf68_identical_payload_memo_vs_no_memo`: runs get_overview WITH the memo (asserts 1 CG fetch) AND WITHOUT (begin/end/prefetch monkeypatched to no-op → asserts >1 fetch, a real control) → `ov_memo.model_dump() == ov_plain.model_dump()`. Same feed, memo on vs off, byte-identical. The control (c2>1) proves the test catches divergence. The #66 −617/2.2 canary live + every decision-tower/honest-null/distinguishing test still green. ✅
   - **(2) CALL-COUNT 6→1** — `test_perf68_overview_batches_to_one_coingecko_fetch` (assert 1) + the live ~10ms. ✅
   - **(3) REQUEST-SCOPED (no leak)** — `_quote_memo.get() is None` after get_overview returns; `test_perf68_two_sequential_calls_each_fetch_fresh` (no stale sharing); `test_end_quote_batch_resets_memo_to_none`. The finally-reset is the guard. ✅
   - **(4) fail-open** — `test_perf68_fail_open_intact_when_coingecko_down` (CG down → batched prefetch fail-opens to last-known/mock, just once). ✅
   - **(5) docstring true** — the false cache claim replaced with the memo truth. ✅
   - **SEAM A (snapshot consistency — the one number-change risk I flagged):** `test_perf68_okx_discovery_read_does_not_drift_value` — two DIFFERENT snapshots (60k/61k) → `crypto.value == 61000` (the holdings-building read, NOT the discovery 60k) + `calls>=2` (discovery pre-read happened). PROVEN structurally safe: `_overview_priced_symbols` yields only symbol STRINGS (can't corrupt a value); values come from `_okx_crypto_holdings`' own read. ✅
   - **SEAM B (store-on-miss):** `test_store_on_miss_dedups_adhoc_symbol` — an ad-hoc symbol not pre-fetched, 2× in a batch → `_fetch_coingecko` once. Proves the dedup, not just the prefetch. ✅

## Assumptions (user-review)
- **Request-scoped quote memo (ContextVar, reset in finally) + batch-prefetch in get_overview.** N single-asset CoinGecko fetches → 1 batched. The memo is per-request — set on enter, reset on exit; a 2nd request re-fetches (no process-global staleness). **Why:** /finance was 0.7–15s from N sequential single-asset CG calls; the batch + dedup makes it ~10ms warm. **How to change:** the memo lifecycle (begin/end) / the prefetch symbol set in `_overview_priced_symbols`.
- **(3) TTL cache (cachetools 30–60s) DEFERRED** — the memo+batch alone got /finance to ~10ms warm, so a process-TTL isn't needed (would add a dep + `--build` for no measured benefit). **Why:** no-overengineering — measure before adding infra. **How to change:** revisit only if a real measured need appears (e.g. CG rate-limit on the single batched call).
- **The fix is PURE plumbing — zero derived-number change** (the identical-payload model_dump test). The same quotes, fetched once. **Why:** a perf fix must not move a number (the #66 pnlTotal/pnlScope/W=0 valve are the canary). **How to change:** N/A — the derivation is untouched.

## The 3 Quality Gates
- **Gate 1 — API:** ☑ /finance response shape + every value UNCHANGED (identical-payload) · ☑ no schema change · ☑ no auth · ☑ NEUTRAL · ☑ fail-open intact (one batched attempt). **PASS**
- **Gate 2 — Function:** ☑ (1) identical-payload (model_dump ==, the spine) · ☑ (2) call-count 6→1 · ☑ (3) request-scoped/no-leak · ☑ (4) fail-open · ☑ (5) docstring true · ☑ seam-A drift-safe · ☑ seam-B store-on-miss · ☑ existing tests pass (incl all #66) · ☑ **0 errors** · ☑ mypy clean. **PASS**
- **Gate 3 — Sprint:** ☑ end doc w/ verified counts + the before/after timing + the live canary · ☑ architect spot-checked full functions + LIVE-measured · ☑ counts ≥ baseline (+11) · ☑ team-lead to live-verify the speedup · ☑ assumptions logged (3) · ☑ commit format `fix(sprint-PERF)`. **PASS**

## Risks / follow-ups
- **/finance ~10ms warm (was 0.7–15s)** — the N×CoinGecko bottleneck is gone (N→1 batched), with ZERO number change (the identical-payload spine). The user's slow-tabs complaint is resolved.
- **(3) TTL is a logged follow-up, not needed now** — only revisit if the single batched CG call itself hits a rate-limit under heavy tab-refresh; the 60s-stale tradeoff would then buy 0-network refreshes.
- The architect-flagged seams (A snapshot-drift, B store-on-miss) were both nailed with tests at the design stage — the value of reviewing the mechanism before the build, not just the diff after.
- Process: backend-2 silent-after-done (7th) — verified solid 3 ways (disk 151+1649-green + my live timing/canary + this review). Stability-check (mtime >2min) is the standing guard.
