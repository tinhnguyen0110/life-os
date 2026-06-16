# End Sprint FINANCE-AUDIT-S2 — s_asset reads held-assets technicals (Q6+Q7)

> Status: **REVIEWED — 3 gates green, committing.** Task #60. Commit hash: see `git log`. The LAST audit-fix — the q-engine is now honest (S1) AND the tower can light up from real holdings while keeping the brake (S2).

## What shipped (Q6 source + Q7 grading)
- **Q6 — `_s_asset` re-sourced to HELD assets:** `_held_symbols()` (new, service.py) reads `finance.list_holdings()` symbols, deduped, **EXCLUDING ·dust + stablecoins** (a stablecoin has no meaningful technical). For each held symbol, `_asset_signal(symbol)` computes RSI via `market.compute_indicators(symbol, ["rsi","summary"])`. `_s_asset` builds a q_from_points input per held symbol: present:true+strength when a REAL RSI series exists; present:false (honest-missing) when none. `q_from_points(..., mock_is_present=False)` → coverage = (held with real tech)/(held). **Was the permanently-empty watchlist; now the user's real book.**
- **Q7 — GRADED signal strength (not binary):** `_asset_signal` returns `min(1.0, abs(RSI − 50)/50)` — a clear overbought/oversold (RSI far from 50) reads STRONG; RSI near 50 (no edge) reads weak-but-present; no RSI series → None (absent, honest-missing). Distinguishes low-signal (present, low) from no-data (absent, 0).

### Verified counts (architect re-ran independently — Rule #0)
- test_decision: **48 passed, 0 errors**.
- Full suite: **1618 passed, 6 skipped, 0 failed, 0 errors** (was 1611; +7 S2 tests), 1 benign httpx deprecation warning.
- mypy: `decision/service.py` **clean**.
- team-lead LIVE-verified: s_asset note = "0/6 HELD assets with real technicals, q=0.0" (reads `_held_symbols`, NOT watchlist); W=0.0, binding=s_asset — the 6 held coins have no RSI-able price-history yet → honest 0.

## ⚠️ LIVE STATE — "FIX WORKS, DATA THIN" (for the user's re-verify — NOT a failed fix)
After S2, live `s_asset = 0.0` and `W = 0.0` still — BUT for the RIGHT reason: **the plumbing now reads the user's REAL holdings (`_held_symbols`), not the empty watchlist. W is 0 because the held coins (PEPE/ICP/ARB/S/TRUMP/IP are OKX value-only, lacking price-history depth) have no RSI-able series YET — honest "no real signal," NOT a hardwire to watchlist.** The GATE4 distinguishing test PROVES it CAN escape 0: a held symbol WITH a real series → s_asset > 0. So: **the fix works; the data is thin.** As the held coins accumulate price-history (or tracked assets gain depth), s_asset lights up automatically — no further code. This is the honest model, not a stuck zero.

## Code review (architect — 4-step, the divergent-distinguishing + valve + q-engine-intact hardest)
1. **git status/diff** — files STABLE (>2min; backend-2 silent-after-done → stability-checked). 4 files: decision/service (_held_symbols + _asset_signal + _s_asset re-source), test_decision (7 S2 tests), plan + end_sprint. `template/`+`data/` excluded.
2. **Read full functions:**
   - `_held_symbols()` — `list_holdings()` deduped, EXCLUDES `h.isDust`/`DUST_SYMBOL`/`STABLECOINS` (a stablecoin/dust has no technical). ✅
   - `_asset_signal(symbol)` — RSI via `compute_indicators`; `rsi is None → return None` (honest-missing, no default-fill); else `min(1.0, |RSI−50|/50)` (graded strength). ✅
   - `_s_asset` — reads `_held_symbols()`, `value=strength` (None → present:false), `q_from_points(mock_is_present=False)`. Re-source ONLY; the present-only/mock logic (the valve) untouched. ✅
3. **Verify against plan + the 5 acceptance gates** — re-source-to-holdings, graded, valve-survives, real-data-only, distinguishing, q-engine-intact. ✅
4. **Hunt additional issues — the teeth verified:**
   - **GATE4 distinguishing = GENUINELY DIVERGENT** (team-lead's note): `HASTECH` seeded a REAL rising series (→ `_asset_signal > 0`) + `NODATA` no series (→ `_asset_signal is None`), SAME `_s_asset` call → `q > 0` AND `"1/2" in note`. NOT two identical "present" inputs. ✅
   - **GATE2 valve END-TO-END:** all-missing → `_s_asset 0` → `decision_weight()` → `s_layer.q == 0.0` AND `dw.weight == 0.0`. The full tower path, not just `_s_asset`. ✅
   - **GATE5 q-engine UNCHANGED:** GATE1 0.45 + the S1 cadence tests STILL pass alongside (48/48) — only `_s_asset`'s source changed. ✅
   - stablecoin/dust excluded (dedicated test). ✅

## Assumptions (user-review)
- **s_asset sources the user's HELD assets (not the watchlist).** `_held_symbols()` (holdings, dedup, ·dust + stablecoins excluded) → per-symbol RSI via the market path. **Why:** the watchlist was permanently empty → W stuck at 0; the §484 unblock reads real positions. **How to change:** `_s_asset`'s source.
- **Graded signal strength = `min(1.0, |RSI − 50|/50)` (RSI conviction).** A clear overbought/oversold → strong; near-50 → weak-but-present; no series → absent (0). **Why:** Q7 — signal STRENGTH, not has-RSI/no-RSI binary. **How to change:** `_asset_signal`.
- **The W=0 valve survives BY CONSTRUCTION** — re-source only; the present-only-on-real-data / `mock_is_present=False` logic is untouched. A holding with no real technical → 0; all-missing → W=0. The tower stays dark on empty signal; lights up ONLY from real per-holding technicals.
- **Live state = "fix works, data thin":** live s_asset 0 / W 0 because the held coins lack price-history depth (OKX value-only), NOT a hardwire — proven by the GATE4 distinguishing (a real-series holding → s_asset > 0). The tower lights up as the data deepens, no code change.

## The 3 Quality Gates
- **Gate 1 — API:** ☑ decision_weight/s_asset response shape unchanged (the note updates) · ☑ no auth · ☑ NEUTRAL (a technical is data, no buy/sell) · ☑ fail-open (no tech → 0, no crash). **PASS**
- **Gate 2 — Function:** ☑ (1) honest-miss not default-fill · ☑ (2) all-missing → W=0 END-TO-END (the valve) · ☑ (3) real-data-only · ☑ (4) DISTINGUISHING two-arm SAME call, divergent fixtures · ☑ (5) q-engine unchanged (GATE1 0.45 + cadence pass) · ☑ graded-not-binary · ☑ stablecoin/dust excluded · ☑ existing tests pass · ☑ **0 errors** · ☑ mypy clean. **PASS**
- **Gate 3 — Sprint:** ☑ end doc w/ verified counts + the "fix works data thin" live-state · ☑ architect spot-checked full functions · ☑ counts ≥ baseline · ☑ team-lead LIVE-verified · ☑ assumptions logged (4) · ☑ commit format. **PASS**

## Risks / follow-ups
- Live s_asset 0 / W 0 is HONEST (data thin), proven not-a-hardwire by GATE4 — it lights up as held-coin price-history deepens. (No code change needed; if the user wants W non-zero sooner, the trigger is accumulating price-history for the held coins or tracking them in the market poller.)
- **BOTH audit fixes now shipped (S1 + S2):** the q-engine's confidence is honest (cadence-aware, mock-excluded) AND the tower reads real holdings with the W=0 brake intact. team-lead pings the USER to re-verify the 6 tools end-to-end.
- Process: backend-2 silent-after-done (3rd time) — verified solid 3 ways (disk + team-lead live + this review). The op-model silent-report gotcha persists.
