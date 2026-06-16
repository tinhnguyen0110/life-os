# End Sprint FINANCE-AUDIT2 — pnlTotal aggregates real per-coin pnl + scope-label (Task #66)

> Status: **REVIEWED — 3 gates green, committing.** Task #66. The audit's HEADLINE catch — a TOTAL that lied about DIRECTION (showed +$6.99 gain while the real per-coin loss was −$616.91), leaking into life_brief (the agent's #1 surface). Fixed at source + a scope-label so we don't trade the +$7 lie for a −72% lie.

## What shipped
- **The fix (`_basis_known_pnl`, finance/service.py):** pnlTotal now aggregates the per-coin entries WITH a real cost basis — `known_cost = Σ pnl.cost`, `known_value = Σ pnl.current` over entries where `pnl.abs is not None AND pnl.cost not in (None,0)` → `_pnl(known_cost, known_value)`. The no-basis (OKX value-only / stablecoin / dust) holdings are EXCLUDED (you can't claim gain/loss with no cost basis — honest-null at the total). **ROOT it fixed:** pnlTotal was `_pnl(total_cost, total_value)` where the crypto channel `cost` = `_ensure_crypto_basis` = the channel BASIS SNAPSHOT (~$10,637 ≈ current value → +$7 fake gain), ignoring the per-coin accAvgPx losses already computed. The snapshot `cost` (total_cost) STAYS for the channel drift framing — only pnlTotal stops using it.
- **Honest-null when no basis-known:** `n_known == 0` → `PnL(cost=0, current=0, abs=None, pct=None)` + a note "no holding has a cost basis yet — total P&L is unknown" — NOT a fabricated $0 gain.
- **The scope-label (`PnlScope`, new model — team-lead lock, don't trade the +$7 lie for a −72% lie):** `pnlScope = {basis:"known-cost-only", coveragePct, note}` on FinanceOverview (NOT on the shared PnL type — kept reusable). `coveragePct = known_value / totalValue × 100` (live **2.2%** — the basis-known coins are worth $234 of the $10,644 book; the rest is no-basis USDT cash). The note ("P&L on the ~2.2% of the book (6 holdings) with a cost basis; the ~98% no-basis stablecoin/value-only is excluded") makes "−72% of the basis-known 2.2%, not the whole book" legible.
- **life_brief leak fixed:** `_brief_portfolio` (read_server) now emits the honest `pnlTotal` (−$617) + `pnlScope` — the agent's #1 surface no longer reports a phantom gain.

### Verified counts (architect re-ran independently — Rule #0)
- finance + mcp_read: **158 passed, 0 errors**. Full suite: **1638 passed, 6 skipped, 0 failed, 0 errors** (was 1630; +8 #66 tests), 1 benign httpx deprecation warning. mypy: finance/service.py + schema.py **clean**.
- **LIVE cross-check on the container (architect, the headline verify):** `GET /finance .pnlTotal = {cost:850.55, current:233.52, abs:-617.03, pct:-72.54}` — DIRECTION NEGATIVE (was +$7). **Σ per-coin pnl.abs = -617.03 == pnlTotal.abs = -617.03 (EXACT match).** `pnlScope.coveragePct = 2.2` + the note. team-lead LIVE-verified life_brief.portfolio.pnlTotal = −$616.68 (the leak is fixed) + channel crypto pnl STILL null (basisUnknown untouched).

## Code review (architect — 4-step, the distinguishing + cross-check + no-basis-honest-null + PnL-unchanged hardest)
1. **git status/diff** — files STABLE (newest mtime 14:36, reviewed 14:43 — >6min, not in-flight; backend-2 silent-after-done → stability-checked). Files: finance/service (the aggregation) + schema (PnlScope model) + read_server (life_brief +pnlScope) + test_finance + test_mcp_read + plan/end_sprint. `template/*` + `data/` EXCLUDED.
2. **Read full functions** — `_basis_known_pnl` (the basis-known sum + the no-basis guard + honest-null + coverage); the `get_overview` wire-in (pnlTotal/pnlScope from it); the schema PnlScope; the read_server `_brief_portfolio` change.
3. **Verify against plan + the 6 acceptance gates** — basis-known aggregation, distinguishing, cross-check, no-basis-excluded, channel-pnl-unchanged, life_brief-honest, scope-label-legible. All have a dedicated test.
4. **Hunt additional issues — verified in code + live:**
   - **(1) DISTINGUISHING** — the test uses a DIVERGENT fixture (2 losing basis-known coins −400/−216.91 + a BIG no-basis stablecoin `_entry(0.0, 9000)` cost-0 → EXCLUDED) → asserts `pnl.abs == -616.91` AND `abs<0 and pct<0`. A snapshot-cost impl gives ~$0 here → the test fails it. The +$7 collapse can't pass. ✅
   - **(2) cross-check** — `pnlTotal.abs == Σ per-coin pnl.abs` (test + live -617.03 == -617.03). ✅
   - **(3) no-basis EXCLUDED honest-null** — all-value-only book → `pnl.abs is None` (NOT a fake $0 gain), `coveragePct is None`, note "no holding has a cost basis". The exact misread the dispatch warned against. ✅
   - **(4) channel `allocations[].pnl` (basisUnknown→null) UNCHANGED** — only the `pnlTotal=` line changed; total_cost still computed (drift); team-lead confirmed channel crypto pnl still null. ✅
   - **(5) life_brief honest** — `_brief_portfolio` emits the honest pnlTotal + pnlScope; team-lead live-verified −$616.68 (the leak gone). ✅
   - **(6) scope-label legible** — `PnlScope` (NEW model; PnL shared type UNCHANGED); coveragePct 2.2 + the note. The format handles small coverage precisely (1-decimal under 10% → "2.2%", not a misleading "0%"). ✅

## Assumptions (user-review)
- **pnlTotal aggregates ONLY basis-known per-coin pnl; no-basis EXCLUDED.** A holding with no cost basis (OKX value-only / stablecoin) is not in pnlTotal's cost/value (honest-null at the total — you can't claim a gain/loss on it). No basis-known coin → pnlTotal honest-null. **Why:** the snapshot-cost pnlTotal lied about direction (+$7 vs −$617). **How to change:** `_basis_known_pnl` (the basis filter).
- **coveragePct = known_value / totalValue × 100** (current value of basis-known holdings / total). Live 2.2% (crashed coins are a small slice of the cash-heavy book). **Why:** label the scope so −72%-of-the-basis-known isn't misread as whole-portfolio. **How to change:** `_basis_known_pnl`'s coverage formula (value-based, not cost-based — "how much of what you hold now has a known P&L").
- **The crypto basis snapshot stays for channel drift framing** — only pnlTotal stopped using it. **Why:** channel drift (value vs target) is a different concept from portfolio P&L. **How to change:** N/A.

## The 3 Quality Gates
- **Gate 1 — API:** ☑ FinanceOverview response shape additive (+pnlScope, pnlTotal now honest) · ☑ PnlScope new model, PnL shared type unchanged · ☑ no auth · ☑ NEUTRAL · ☑ fail-open (no basis → honest-null). **PASS**
- **Gate 2 — Function:** ☑ (1) DISTINGUISHING divergent fixture → pnlTotal<0 (the +$7 collapse fails) · ☑ (2) cross-check == Σ per-coin (live -617.03==-617.03) · ☑ (3) no-basis honest-null (not $0 gain) · ☑ (4) channel pnl unchanged · ☑ (5) life_brief honest · ☑ (6) scope-label legible · ☑ existing tests pass · ☑ **158 passed, 0 errors** · ☑ mypy clean. **PASS**
- **Gate 3 — Sprint:** ☑ end doc w/ verified counts + the live cross-check · ☑ architect spot-checked full functions + LIVE-verified the headline · ☑ counts ≥ baseline · ☑ team-lead LIVE-verified (pnlTotal −617 + scope-label + life_brief honest) · ☑ assumptions logged (3) · ☑ commit format. **PASS**

## Risks / follow-ups
- **The audit's headline catch is CLOSED** — pnlTotal is honest about DIRECTION (−$617, not +$7) AND scoped (−72% of the basis-known 2.2%, not whole-portfolio). The most-dangerous gap class (a confident wrong number on the most-read surface) is fixed without creating a new misread.
- **FINANCE-AUDIT3 CANDIDATE (logged, team-lead's call):** `finance_analytics.rebalance` "sell crypto $6,599" treats USDT-cash as crypto-exposure (same family — channel math) → really "deploy idle cash." Separate sprint if greenlit; has stablePct/dryPowder data for a stable-vs-risk-aware reframe (the D3a-drift analogue).
- **FE-verify (not edit):** the 3 render surfaces (Home tile, Finance KPI, useFinance) color pnlTotal by sign + handle null — they'll show −$617; verify they surface pnlScope context (tiny FE follow-up only if a surface presents −72% as whole-portfolio without the scope).
- Process: backend-2 silent-after-done (6th) — verified solid 3 ways (disk 158-green + team-lead live + my live cross-check -617.03==-617.03). Stability-check (mtime >2min) is the standing guard.
