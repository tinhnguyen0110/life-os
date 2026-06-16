# Sprint FINANCE-AUDIT-S2 — s_asset reads held-assets technicals (Q6+Q7, the last audit-fix)

**Task #60.** From the dogfood audit (`AUDIT_finance_q1-q8.md` Q6/Q7): `s_asset` reads the WATCHLIST (empty live → 0 → W=∏q=0, the tower can never light up). Point it at the user's HELD assets' technicals (the §484 unblock) so the tower lights up from REAL holdings — WITHOUT removing the W=0 valve. Backend-only, NEUTRAL.
**User spine:** the W=0 valve MUST survive — "không tháo phanh" for the tower (no path lights it from nothing).

## Kickoff — 2026-06-16 (read current _s_asset + the held-asset technical path)

### Current state (the bug)
- `_s_asset` (decision/service.py) reads `mkt.watchlist_data()`. The watchlist is EMPTY live (0 items) → 0 points → coverage 0 → q=0 → **W = q_cycle×q_macro×q_flow×s_asset = 0** (permanently — the watchlist never fills).
- It ALREADY grades on `has_tech` (rsi present + trend not flat) + uses `q_from_points(..., mock_is_present=False)` (real-data-only). So the GRADING + the real-data discipline exist; the SOURCE (watchlist) is wrong.

### The fix's pieces (all exist — compose them)
- **Held symbols:** `finance.list_holdings()` → `.symbol` (the user's actual book).
- **Per-symbol technicals:** `market.compute_indicators(symbol, ["rsi", "summary"])` / `ta.summarize()` (ta.py `rsi` L264, `summarize` L469) — RSI + trend per symbol, over the price series. A held asset WITH a real series → real RSI/trend; with NO market data (e.g. an untracked/illiquid coin, or a stablecoin like USDT with no meaningful technicals) → honest-missing (contributes 0).
- So `_s_asset` = for each HELD symbol, compute its technicals → present:true with the RSI value when real, present:false when no real data → `q_from_points(..., mock_is_present=False)`. coverage = (held assets with real technicals) / (held assets). The grading is the RSI/trend signal strength.

### The W=0 valve survives NATURALLY (the spine)
- A held asset with NO real RSI/trend → present:false → contributes 0 (honest-missing, NOT a default-fill).
- ALL held assets missing real technicals → coverage 0 → s_asset q=0 → W=0. The tower stays DARK on empty signal — no path lights it from nothing. (The existing `mock_is_present=False` + present-only-on-real-data already enforce this; we just change the SOURCE from watchlist to holdings.)

## Scope (Q6 source + Q7 grading)
- **Q6 — source from holdings:** `_s_asset` reads `list_holdings()` symbols (not the watchlist), computes per-symbol technicals via the existing market path. Real technical → contributes; no data → 0. NO watchlist auto-sync (scoped out — over-engineering).
- **Q7 — GRADED, not binary:** s_asset reflects signal STRENGTH (the RSI/trend quality), not just has-RSI/no-RSI. A weak/ambiguous technical → low-but-nonzero; a strong one → high. (The current code already extracts the RSI value; ensure the grading is a real strength signal, e.g. via `summarize()`'s trend signal, not a 0/1 flag.)
- Dedup/sanity: a held symbol that appears once (don't double-count); stablecoins/dust with no real technicals → honest-miss (0), not a fabricated neutral.

## HARD ACCEPTANCE (USER-PINNED — the W=0 valve survives)
- (1) a holding with NO real RSI/trend → that holding's contribution = 0 (honest-missing, NOT a default-fill).
- (2) ALL holdings missing real technicals → s_asset = 0 → W = ∏q = 0 (the tower stays dark; no path lights it from nothing).
- (3) s_asset reflects REAL technical data only — a holding with no market-history → 0, never a fabricated signal.
- (4) DISTINGUISHING: a holding WITH real RSI/trend → s_asset > 0 (tower can escape 0 LEGITIMATELY) AND a holding WITHOUT → still 0 in the SAME call (proves per-holding real-data read, not a blanket lift).
- (5) compute_q L58 + the S1 cadence fix + the 0.45 default ALL stay intact (additive — only _s_asset's source changes).

## Risks / seams
- The W=0 valve is the spine — the fix must NOT introduce a default-fill that lights the tower on empty signal. Test (2) (all-missing → 0) + (4)'s second arm (a no-data holding still 0 in a mixed call) are the teeth.
- DISTINGUISHING (4) is the proof it reads real per-holding data: a mixed book (one real-tech + one no-tech) → s_asset >0 BUT driven only by the real one (coverage reflects the split). A blanket-lift impl would give the no-tech holding a signal too — must NOT.
- Q7 grading: don't regress to binary; the strength must vary with the technical (a strong trend > a weak/flat one). But a FLAT/ambiguous technical is still "present" data (low signal) vs NO data (absent) — distinguish low-signal (present, low) from no-data (absent, 0).
- Additive: only `_s_asset`'s SOURCE changes (watchlist → holdings); compute_q/cadence/0.45 untouched (behavior-test a tower surface unaffected on the q-engine side).
- After S2: team-lead pings the USER to re-verify the 6 tools (q_macro moved for the right reason from S1; W escapes 0 when holdings have real technicals; still 0 when they don't).

### Locks (team-lead, 2026-06-16 — approved as drafted)
- Re-source, DON'T rebuild the valve (the present-only-on-real / mock_is_present logic stays; only the SOURCE changes watchlist→holdings). The W=0 valve survives BY CONSTRUCTION.
- **DISTINGUISHING (gate 4) on GENUINELY DIVERGENT fixtures:** one held symbol with a REAL price-series (→ s_asset>0) + one with NONE (→ 0), asserted in the SAME call. NOT two identical "present" inputs.
- **REPORT THE LIVE s_asset VALUE + WHY** (in backend's report + end_sprint): do the held coins (PEPE/ICP/ARB/S/TRUMP/IP) actually have price-history depth for RSI right now? If thin → s_asset may STILL be ~0 live (W=0) — CORRECT (honest no-signal), NOT a failed fix. Distinguishes "fix works, data thin" from "fix didn't take." (team-lead will tell the user this.)
- 5 hard acceptance gates: (1) honest-miss not default-fill; (2) all-missing→W=0; (3) real-data-only; (4) two-arm distinguishing; (5) compute_q/cadence/0.45 intact.

### Routing / sequencing
Dispatched to **backend-2**. backend-2 done (+ reports the live s_asset value) → team-lead live-verifies (s_asset reads holdings; W escapes 0 if real tech, stays 0 if not — reports which) → architect review+commit+push → **then team-lead PINGS THE USER to re-verify the 6 tools end-to-end.** This is the LAST audit-fix sprint.
