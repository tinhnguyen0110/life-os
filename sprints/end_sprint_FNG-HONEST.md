# end_sprint_FNG-HONEST — one honest Fear&Greed source (Cairn #44 + #54)

> Result. honest-mirror fix: market_overview no longer contradicts decision/guardian/life_brief on F&G — all surfaces now read the ONE macro store. Commit `ee96074` `fix(sprint-FNG-HONEST)`. Status: ✅ all gates pass. backend-w3 EDITED (market service+schema+test); architect 4-step + committed (§3). team-lead live-verified 3-surface + the band lock.

## The bug (Rule#0-grounded)
TWO F&G sources used inconsistently: the REAL macro `fear_greed` store (alternative.me, ~23 live — what decision/guardian/life_brief cite) vs a HARDCODED `MacroSignal(value="38")` in market/service.py:599. So market_overview showed mock-38-as-real while every other surface cited the real ~23 = the honest-mirror breach (an agent reading 38 in one tool + 23 in another can't trust either). #54 was the same bug's market_overview=38 half.

## What shipped
| File | Change |
|---|---|
| `modules/market/schema.py` | `MacroSignal` +`source: str = "mock"` +`asOf: str \| None = None` (additive, defaulted → existing consumers + the market_overview twin unaffected). Docstring: value="n/a" when source has no data (honest, never fabricated); source marks live\|mock; asOf = freshness ts. |
| `modules/market/service.py` | `macro_signals()` now reads `macro.store.latest("fear_greed")` + `latest("btc_dominance")` (the SAME points decision reads — single source of truth) instead of hardcoded strings. Store-None → value="n/a"/source="mock"/asOf=None (honest, NEVER a number). Brent (no feed) → value="$72" but source="mock". New `_fng_status()` = the 3-band {fear,neutral,greed}. Lazy `from modules.macro import store` (circular-import guard). **Fail-soft `_latest()` helper** — a store-read error / uninitialized macro_history → None → honest n/a, never a 500 (better than spec). |
| `tests/test_market_fng_honest.py` (NEW) | 8 tests: F&G reads-store-value+source (distinguishing vs hardcode-38); F&G == macro store latest (EQUAL single-source, divergent fixture 61); BTC.d reads store; F&G/BTC.d None→honest n/a (NOT a number); Brent mock-marked; band cut-offs (10 parametrized boundaries); `_fng_status` only-3-values; source-reflects-store-truth (exploits never-persist-mock: a mock point isn't stored → market keeps the last REAL point). |

## Design (LOCKED — fork (a), team-lead-confirmed)
- **ONE source of truth = the real macro `fear_greed`/`btc_dominance` store** (alternative.me + coingecko, free, what decision/guardian/life_brief already trust). market reads THAT directly via `store.latest()` (leaner than macro_overview — no FRED cold-start; sentiment indicators have no FRED series).
- **honest-mirror:** store-None / read-error → "n/a" + source="mock", NEVER a fabricated number (the DXY-HONEST precedent). The never-persist-mock invariant (record_point early-returns on source='mock') means a stored point is ALWAYS real → market can only show a mock NUMBER via the empty-store n/a case, which it doesn't (it shows "n/a").
- **BTC.d → real too** (team-lead scope-expand; the coingecko feed exists + is stored daily). **Brent → source="mock"** (no free feed).
- **REST≡MCP:** market_overview is NOT in the wiki #24 parity gate, but REST /market + the MCP market_overview both call the same `macro_signals()` → identical by construction.

## Verification (Rule#0 — architect 4-step + team-lead live + backend evidence)
- **architect 4-step:** read full `macro_signals`/`_fng_status`/schema/all-8-tests; traced the distinguishing (seed store=N → market value==N, not 38); diff scope clean (schema +2 additive fields; service = import + the macro_signals/_fng_status region only, no unrelated fn); grep confirmed NO stray `value="38"` (only "extreme" in a docstring explanation, not a code path); the `Any` import is used (the `_latest` annotation); tests use DIVERGENT fixtures (23, 61, 40, 99) so a collapsed/hardcoded impl fails them.
- **team-lead live (in-container):** market F&G = 23/live/2026-06-20 == macro store latest fear_greed → single-source PASS. BTC.d market == store. The old "38" is GONE.
- **backend-w3 evidence:** cross-surface live (value/source/asOf all agree byte-identical); store-None → honest n/a (+ fail-soft covers uninitialized macro_history); Brent source="mock"; mypy CLEAN (service+schema); stage surface = exactly the 3 files. pytest = **1940 passed / 6 skipped / 0 failed** (full venv suite, exit 0, 249s; baseline 1922 + 18 FNG tests) · 212/0 targeted-subset.

## 3 Gates — ALL PASS
- **Gate 1 (API):** market_overview (REST + MCP) reads the single source; envelope intact; MacroSignal additive (no break). ✅
- **Gate 2 (Function):** the distinguishing tests (store-value EQUAL, not hardcode; None→honest n/a not a number; source verbatim; never-persist-mock guard); band boundaries; fail-soft store-read; mypy clean; 0 errors. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step (full read + grep + scope) + team-lead live + backend evidence; commit format; git-status zero-left-dirty; FNG-only stage. ✅

## Assumptions (user-review)
- **ONE F&G source = the real macro `fear_greed` store** (alternative.me); market reads it (was a hardcoded mock 38); all surfaces cite the same value/source/asOf; store-None/read-error → honest "n/a" + source="mock" (never a fabricated number). **How to change:** macro_signals()'s store read in market/service.py.
- **BTC.d → real macro store too** (coingecko, stored daily); **Brent → source="mock"** (no free feed, value kept honestly-marked). **How to change:** the respective macro_signals() branches.
- **F&G status band = 3 {fear,neutral,greed}** (≤44 fear / 45-55 neutral / ≥56 greed; alternative.me's 5 bands fold — extreme-fear+fear→fear, greed+extreme-greed→greed). Display-only/cosmetic — the decision tower reads the RAW store value, not market.status, so it skews no rule. Collapsed (not the dispatch's 5-label) per team-lead decide-and-log. **How to change:** `_fng_status` thresholds + add Literal values if extremes are ever wanted.

## Notes
- Closes Cairn #44 + #54 (same bug; #54 = the market_overview=38 half). #47 dissolved (dropped, fixed #25). backend-w3 EDITS; architect commits (§3). Next: WIKI-RECONCILE (#53) — designed + approved, dispatch sequential-after this push.
- The honest-mirror pillar applied: never present a mock as real; one signal = one source = one value everywhere.
