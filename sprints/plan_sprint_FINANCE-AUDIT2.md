# Sprint FINANCE-AUDIT2 — pnlTotal lies about direction (the most-dangerous gap class) (Task #66)

`finance.pnlTotal` shows **+$6.99 (gain)** while the real per-coin loss sum is **−$616.91**. A TOTAL that lies about DIRECTION, leaking into life_brief (the agent's #1 surface). "không tháo phanh" violated at the totals level. Backend fix + verify all consumers.

## Kickoff — 2026-06-16 (§3.3a — gap reproduced LIVE, root pinned, all consumers grepped)

### The gap (reproduced live, Rule#0)
- `pnlTotal = {cost: 10637.49, current: 10644.48, abs: +6.99, pct: +0.07}` — a "gain".
- Sum of per-coin real `pnl.abs` (the 6 held coins) = **−616.91** (PEPE −116, ICP −20, ARB −114, S −81, TRUMP −193, IP −93).
- **$623 off, and WRONG DIRECTION (+ vs −).**

### ROOT (pinned in code — finance/service.py)
- L656: for the crypto channel, `by_channel["crypto"]["cost"] = crypto_cost` where `crypto_cost = _ensure_crypto_basis(okx_value)` = the **channel-level basis SNAPSHOT** (~$10,637, snapshotted from the OKX total VALUE on first connect → ≈ current value → +$7 rounding).
- L701: `total_cost = round(sum(c["cost"] for c in by_channel.values()), 2)` → uses that snapshot.
- L723: `pnlTotal = _pnl(total_cost, total_value)` → `_pnl(10637, 10644) = +6.99`.
- **The per-coin holdings ALREADY carry real cost** (`_okx_crypto_holdings`, L485-505): each has `avgCost = accAvgPx` and `pnl = _pnl(accAvgPx×qty, value)` (real abs/pct; null for stablecoins). pnlTotal IGNORES this and uses the channel snapshot. The snapshot basis predates the per-coin accAvgPx work and was never re-aggregated.

### The exact fix math (verified live)
- The 6 basis-known coins: **cost $850.57** (sum accAvgPx×qty), **value $233.64** → **pnl −$616.91**.
- USDT ($10,411) + ·dust = NO basis → EXCLUDED from cost/pnl (you can't claim a gain/loss on a position with no cost basis — that's the honest-null discipline at the total level).
- **Honest pnlTotal = `_pnl(sum_basis_known_cost=850.57, sum_basis_known_value=233.64) = −616.91`** — direction NEGATIVE, matches the per-coin sum. (NOT the snapshot's +7.)

### ALL pnlTotal consumers (grepped — recheck-ALL-consumers / dissolved-finding discipline)
| consumer | file | reads | render |
|---|---|---|---|
| MCP/life_brief | `read_server.py:785` (`_brief_portfolio`) | pnlTotal | the LEAK — agent's #1 surface shows phantom gain |
| Home tile | `frontend/app/page.tsx:129-133` | pnlTotal.abs/pct | colors by sign (`<0 → neg`) |
| Finance KPI | `frontend/app/finance/page.tsx:212,252` | pnlTotal.abs/pct | colors by sign |
| useFinance | `frontend/lib/useFinance.ts` | type | EMPTY default |
- All are RENDER-ONLY (color by sign). **Fix the source (service.py) → all surfaces show the honest −$617 automatically.** But VERIFY each post-fix (the recheck-all-consumers lock — don't assume).

## REVISED SCOPE / FIX (decide-and-log)
**DECISION: pnlTotal aggregates the REAL per-coin pnl (basis-known coins only); the no-basis portion is EXCLUDED from cost/pnl.** Implement in `get_overview` (finance/service.py):
- Compute `total_cost`/`total_value` for pnlTotal from the SUM of per-coin entries WHERE pnl is non-null (basis exists), NOT the channel snapshot cost. I.e. pnlTotal = `_pnl(Σ basis-known cost, Σ basis-known value)`.
- The crypto channel's snapshot `cost` STAYS for the channel-level drift framing (a different concept — channel value vs target); only pnlTotal stops using it.
- If NO coin has basis → pnlTotal honest-null (not a fabricated 0/gain).

### SCOPE-LABEL lock (team-lead, 2026-06-16 — approved + folded in)
Don't trade the +$7 lie for a −72% lie. −$617/−72% is on the basis-known cost ($850) = ~8% of the $10,644 book (98% USDT cash, no basis). "pnlTotal −72%" read as whole-portfolio = misleading the other way. **pnlTotal carries a sibling `pnlScope: {basis:"known-cost-only", coveragePct≈8, note}` on FinanceOverview** (NOT on the shared PnL type) so it can't be misread as whole-portfolio. abs/pct stay honest; the SCOPE is labeled — same discipline as basisUnknown/stablePct, applied to the total. This is hard-acceptance (6).

### LOCKS (the spine — direction honesty)
- **pnlTotal DIRECTION must match the sum-of-real-per-coin direction.** Both negative now (−$617). NEVER a phantom gain when the components are down.
- **DISTINGUISHING test:** a fixture genuinely down per-coin (real losses, + a no-basis stablecoin) → assert `pnlTotal.abs < 0` (≤ 0, NOT a rounding-gain). An aligned/happy fixture would pass against the bug — use a DIVERGENT one (losing coins + a big no-basis stable, like the live book) so a correct impl (−617) ≠ the collapsed one (+7).
- **Cross-check:** pnlTotal.abs ≈ Σ per-coin pnl.abs (within rounding). The rollup must equal its components.
- **All consumers verified:** life_brief + Home + Finance KPI all show the honest −$617 (re-curl/re-render each — recheck-all-consumers).
- **basisUnknown still honest:** the channel-level `allocations[].pnl` (basisUnknown→null) is a DIFFERENT field, unchanged. Only pnlTotal (the portfolio rollup) is corrected.

## Scope
- IN: fix pnlTotal aggregation in finance/service.py (sum basis-known per-coin cost/value); the distinguishing + cross-check + all-consumer tests; verify life_brief reflects it.
- OUT: NO change to per-coin pnl (already correct), channel `allocations[].pnl` (basisUnknown, different concept), the crypto-basis snapshot (stays for drift framing), FE code (render-only, colors by sign — fixing source fixes it; just VERIFY).
- FE: likely NO code change (consumers already color by sign + handle null) — but tester/team-lead VERIFY the 3 surfaces show −$617. If a surface hardcodes "pos" or mishandles null → a tiny FE follow-up.

## Risks / seams
- The honest pnlTotal ($-617 on a $233 basis-known book) is a LARGE % loss (−72%) — correct (these are −60–96% coins). The pct is on the basis-known cost ($850), not the whole portfolio — label it so it's not misread as "whole portfolio −72%". Consider pnlTotal carrying a note/scope ("on $850 cost-basis-known positions") so the agent/UI frames it right.
- Don't swing the bug the other way: the no-basis USDT must be EXCLUDED (not counted as a 0-cost loss) — honest-null, the same discipline as per-coin.
- This is the audit catch that matters most — a confident wrong number on the most-read surface. The fix makes the rollup honest about direction.
