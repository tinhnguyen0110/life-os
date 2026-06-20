# end_sprint_DUST-FOLD — fold sub-$1 dust in exchange_overview (Cairn #17)

> Result. dogfood-R4 GAP-5. Commit: `<hash>` (filled at commit). Status: ✅ all 3 gates pass.

## Objective (met)
`exchange` (GET /exchange) listed sub-$1 dust as full balance rows (ETH 3.95e-7, LINK, DOGE 6.6e-7). `finance_overview` already folds dust; the raw exchange read didn't. Applied the SAME fold philosophy to the exchange balance list — one `·dust` summary, value preserved, total unchanged.

## What shipped
| File | Change |
|---|---|
| `backend/modules/exchange/schema.py` | OkxBalance + `isDust: bool=False` + `count: int|None=None` (additive/nullable, mirrors finance Holding). |
| `backend/modules/exchange/service.py` | `_is_dust_balance` (usdValue not None AND < $1; no price clause — OkxBalance has none; null-usdValue stays visible) + `_fold_dust_balances` (flat fold → one ·dust summary, usdValue=Σ, count, total=0) + applied in `sync()` AFTER total_usd computed. `DUST_USD_THRESHOLD`/`DUST_SYMBOL` mirrored from finance (circular-import-safe, commented). |
| `backend/tests/test_exchange.py` | +6 tests. |

## Reuse + adaptation (not a blind import)
finance's `_fold_dust`/`_is_dust` operate on `Holding` (price + usdValue + channel). OkxBalance has `usdValue: float|None`, NO price, NO channel. So: predicate = `usdValue is not None AND usdValue < $1` (drop the price clause); flat fold (no channel grouping); null-usdValue stays VISIBLE (unknown ≠ small — the finance lock). Threshold MIRRORED not imported (finance.service imports exchange.service → a back-import is circular; mirror documented as the conceptual single-source).

## Verification (Rule #0)
- **team-lead live (/exchange):** 1 ·dust row (count=3, the 3 sub-$1 coins), 8 total rows; no sub-$1 non-dust leak; totalUsdValue preserved (10624.90, display-only); CROSS-MODULE finance totalValue unaffected (10624.9) — finance uses pre-fold total, not the list sum.
- **architect Rule#0:** cross-module no-leak confirmed — `finance/service.py:482 if b.total <= 0: continue` skips the ·dust row (total=0) → no leak into held-balances/holdings/q_macro. test_exchange + test_finance → **86 passed, 0 failed**. Full suite 1682 (+6).
- **distinguishing:** sub-$1 priced dust → folded; ≥$1 + $1.00-boundary → individual; null-usdValue → stays VISIBLE; total identical pre/post.

## Code review (architect 4-step)
1. diff — schema (isDust/count) + service (_is_dust_balance/_fold_dust_balances + sync apply-after-total + mirrored threshold) + test (6).
2. read FULL — predicate (usdValue-only, null stays visible), fold (flat, total=0 summary, Σ preserved), sync (fold after total) — traced entry→exit.
3. vs plan — reuse finance philosophy on OkxBalance, flat fold, null-visible lock, total preserved = exactly the approved scope.
4. hunted — cross-module ·dust no-leak (finance total>0 filter, confirmed); threshold-mirror circular-import-safe; type:ignore is the known no-pydantic-mypy-plugin gotcha (scoped + commented), not a real type bug. No edge missed.

## 3 Gates — ALL PASS
- **Gate 1 (API):** /exchange shape additive (OkxBalance +isDust/count); integration green. ✅
- **Gate 2 (Function):** 6 behavior tests (fold / ≥$1 + boundary / null-visible distinguishing / total-preserved); 86 pass/0 err; null-usdValue lock; real distinguishing asserts. ✅
- **Gate 3 (Sprint):** end-doc w/ verified counts; full-function spot-check; team-lead live + architect Rule#0; counts ↑ (+6); commit format. ✅

## Assumptions (user-review)
- **exchange folds sub-$1 priced dust into one `·dust` summary** (usdValue=Σ, count), same $1 threshold + philosophy as finance (null-usdValue stays visible = unknown≠small). DISPLAY-only, total unchanged. **How to change:** edit DUST_USD_THRESHOLD in exchange.service (mirror of finance's) or _is_dust_balance.
- **Threshold mirrored, not imported** (circular-import-safe). **How to change:** keep the two DUST_USD_THRESHOLD in sync if finance's ever changes (commented at both sites).

## Notes
- Single-user no-overengineering: reused finance's proven philosophy.
- Independent of #15/#14 (different module). Committed serially after #15.
