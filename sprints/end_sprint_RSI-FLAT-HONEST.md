# end_sprint_RSI-FLAT-HONEST — RSI on a flat series = 50 neutral, not 100 (Cairn #62)

> Result. honest-mirror fix: a flat price series no longer yields RSI=100 ("extreme overbought") — it reads 50 (neutral, zero momentum). Commit `<hash>` `fix(sprint-RSI-FLAT-HONEST)`. Status: ✅ all gates pass. backend-w3 EDITED (ta.py + test); architect 4-step + committed (§3).

## The bug (Rule#0-grounded — team-lead's analysis confirmed on disk)
`ta.py:285` `_rsi_from`: `if l == 0: return 100.0`. A FLAT series (all prices equal — common from a mock-flat feed) → every delta 0 → avg_gain=0 AND avg_loss=0 → `l==0` → returns 100.0. RSI=100 = "extreme overbought", but a flat series has ZERO momentum (the opposite). Amplified by `summarize()` (RSI≥70 → `rsi_signal="overbought"`) → life_brief surfaced a fake "overbought" on flat/mock data = honest-mirror breach.

## What shipped
| File | Change |
|---|---|
| `modules/market/ta.py` | `_rsi_from`: `if l == 0: return 50.0 if g == 0 else 100.0` — disambiguate the avg_loss==0 branch by the gain. flat (g==0 AND l==0) → 50.0 neutral; all-real-gains (l==0, g>0) → 100.0 (unchanged); all-losses → 0.0 (already correct via the rs=0 formula, NOT the l==0 branch). EXACT `==0` (no float epsilon — a tiny-but-real move is handled by the rs formula; epsilon would over-engineer). Covers both call-sites (seed line 291 + RMA loop 296). + reconciled the stale rsi() docstring. |
| `tests/test_market_ta.py` | +3 tests: `test_rsi_flat_series_is_50_not_100` (THE distinguishing — flat [100]*20 → RSI 50, every point 50; a folded impl FAILS), `test_summarize_flat_series_rsi_is_neutral_not_overbought` (consumer end-to-end: summarize-flat → rsi_signal "neutral" not "overbought"), `test_rsi_all_up_still_100_after_flat_fix` (regression guard). |

## Design (LOCKED — decide-and-log, team-lead-approved)
- **RSI on a flat series (avg_gain==avg_loss==0) = 50.0 neutral** (was 100.0). A flat series has no momentum → neutral is the honest read; 100 ("overbought") is a garbage signal. all-gains still 100, all-losses still 0, canonical Wilder (rs>0 path) untouched.
- **EXACT `==0`, no float epsilon** — near-flat-but-real moves are handled by the rs formula; an epsilon would over-engineer + risk mis-flattening a tiny-but-real move.
- **#56 mock-suppress SPLIT** — a data-provenance policy (should TA run on mock-flat history at all?) at the service/consumer layer, NOT the RSI math. Separate slice (no existing mock-suppression in ta.py — genuinely different layers).

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step:** read full `_rsi_from` on disk (`return 50.0 if g == 0 else 100.0` exact; rs>0 path untouched); the 3 tests genuinely distinguish (flat→50 explicit-fail-on-100; summarize-flat→neutral consumer proof; all-up regression guard); scope clean (2 files, +34/-2, no other indicator/path touched); confirmed all-down→0 + canonical preserved via the untouched formula.
- **backend-w3 evidence:** FULL pytest 1958/0 (baseline 1955 + 3) + mypy clean; all 67 ta tests pass; LIVE :8686 — flat[100]*20 → RSI 50.0, summarize-flat → "neutral", all-up → 100, all-down → 0.

## 3 Gates — ALL PASS
- **Gate 1 (API):** N/A (no router change — pure indicator math; surfaces through existing market_indicators/summarize). ✅
- **Gate 2 (Function):** the flat-series distinguishing (RSI==50 not 100) + the consumer end-to-end (summarize→neutral) + regression guards (all-up 100/all-down 0/canonical); exact ==0; 0 errors; mypy clean. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step + backend live evidence; commit format; git-status clean; RSI-FLAT-only stage (2 files + 2 docs). ✅

## Assumptions (user-review)
- **RSI on a flat series (avg_gain==avg_loss==0) = 50.0 neutral** (was 100.0); all-gains still 100, all-losses still 0. **Why:** zero momentum → neutral is honest; 100 "overbought" is a garbage signal life_brief surfaced. **How to change:** the `l==0` branch in ta.py `_rsi_from`.
- **EXACT-zero check (no float epsilon)** — near-flat-real moves handled by the formula. **How to change:** add a tolerance in `_rsi_from` if a real near-flat case ever misreads.
- **#56 mock-suppression SPLIT** to its own slice (provenance policy ≠ math fix).

## Notes
- Closes Cairn #62. backend-w3 EDITS; architect commits (§3). The honest-mirror pillar: a degenerate input must yield an HONEST reading (neutral), never a confident-but-meaningless signal (overbought). Backlog next: #56-mock-suppress, #14 (write-route 404s), #46-P3, #43, #37-40, #15 (life_brief-F&G dogfood).
