# Sprint RSI-FLAT-HONEST — RSI on a flat series = 50 neutral, not 100 (Cairn #62)

> Created 2026-06-21 by architect (NEVER-FREE design lane while backend implements WIKI-RECONCILE). HIGH — honest-mirror: a FLAT price series yields RSI=100 ("extreme overbought") = a garbage signal life_brief surfaces (esp. on mock-flat VN-Index/ETF). DESIGN-only; HOLD dispatch until WIKI-RECONCILE commits (1 backend, sequential tree).

## The bug (Rule#0-grounded — team-lead's analysis confirmed on disk)
`backend/modules/market/ta.py:284` `_rsi_from`:
```python
def _rsi_from(g: float, l: float) -> float:
    if l == 0:
        return 100.0          # ← flat series (g==0 AND l==0) ALSO hits this → RSI=100
    rs = g / l
    return 100.0 - (100.0 / (1.0 + rs))
```
A FLAT series (all prices equal — common from a mock-flat feed) → every delta 0 → avg_gain=0 AND avg_loss=0 → `l==0` → returns 100.0. RSI=100 means "extreme overbought" — but a flat series has ZERO momentum, the opposite of overbought. **Amplified by `summarize()`** (ta.py:469): RSI≥70 → `rsi_signal="overbought"` → life_brief surfaces a fake "overbought" on flat/mock data = honest-mirror breach.

## The fix (DECIDED — decide-and-log, honest-mirror)
Disambiguate the `l==0` (zero average-loss) branch by the gain:
```python
def _rsi_from(g: float, l: float) -> float:
    if l == 0:
        return 50.0 if g == 0 else 100.0   # flat (no movement) → neutral; all-gains → 100
    rs = g / l
    return 100.0 - (100.0 / (1.0 + rs))
```
- **`avg_gain==0 AND avg_loss==0`** (flat, no movement) → **50.0 neutral** (no momentum → neither overbought nor oversold). THE fix.
- **`avg_loss==0 AND avg_gain>0`** (all real gains) → **100.0** (correct, unchanged).
- **`avg_gain==0 AND avg_loss>0`** (all losses) → **0.0** (already correct via rs=0 in the formula; not in the l==0 branch).

### Edge / NOT-over-engineer note
`_rsi_from` is called for the seed (line 291) AND the RMA smoothing loop (296). The EXACT-flat case is avg_gain==avg_loss==0 (a fully flat window). After a flat RUN inside a moving series, RMA values decay toward 0 but rarely hit exactly 0.0 (float) — those are handled naturally by the formula. So the fix targets EXACT 0==0 (no float tolerance — adding an epsilon would be over-engineering + could mis-handle a genuinely tiny-but-real move). Keep `== 0`.

## #56 relationship — SPLIT (my kickoff decision)
#56 also mentions "suppress signal when source=mock" (e.g. dxy empty history). That is a SEPARATE layer — a data-PROVENANCE policy (should we run/trust TA on mock-flat history at all?) decided in service/consumer, NOT the RSI math. #62 = the pure RSI-degenerate MATH fix (ta.py-local, testable in isolation). Folding a provenance policy into a math fix mixes concerns. **#62 stays tight = the _rsi_from fix; #56's mock-suppression = its own slice later.** (Grep confirmed: NO existing source=mock suppression in ta.py — they're genuinely different layers.)

## HARD GATE (distinguishing)
- **flat series** `[100]*20` → RSI == **50.0** (NOT 100). The distinguishing test — an impl that folds flat into 100 FAILS this. (No flat-series RSI test exists today — that gap hid the bug.)
- **all-up** `range(1,20)` → RSI == 100 (existing test_rsi_all_up_is_100 still passes — the g>0 path).
- **all-down** `range(20,1,-1)` → RSI == 0 (existing test_rsi_all_down_is_0 still passes).
- **canonical Wilder reference** unchanged (existing test_rsi_canonical_wilder_reference — the fix doesn't touch the rs>0 path).
- **summarize() end-to-end:** a flat series → `rsi_signal=="neutral"` (NOT "overbought") — proves the consumer-facing fix.
- pytest 0-failed (baseline = post-WIKI-RECONCILE count), mypy clean.

## Baseline
pytest = post-WIKI-RECONCILE count (confirm at dispatch). Keep 0-failed. +2 tests (flat→50, summarize-flat→neutral).

## Assumptions (user-review)
- **RSI on a flat series (avg_gain==avg_loss==0) = 50.0 neutral** (was 100.0); all-gains still 100, all-losses still 0. **Why:** a flat series has no momentum → neutral is the honest reading; 100 ("overbought") is a garbage signal. **How to change:** the `l==0` branch in ta.py `_rsi_from`.
- EXACT-zero check (no float epsilon) — near-flat-but-real moves are handled by the formula; an epsilon would be over-engineering. **How to change:** add a tolerance in `_rsi_from` if a real near-flat case ever misreads.
- #56 mock-suppression SPLIT to its own slice (provenance policy ≠ math fix).

## Notes
- HOLD dispatch until WIKI-RECONCILE commits (sequential, 1 backend, 1 tree). backend EDITS ta.py + test_market_ta.py → architect 4-step + commits `fix(sprint-RSI-FLAT-HONEST)`. Tiny sprint (~3-line fix + 2 tests).
- honest-mirror pillar: a degenerate input must yield an HONEST reading (neutral), never a confident-but-meaningless signal (overbought).
