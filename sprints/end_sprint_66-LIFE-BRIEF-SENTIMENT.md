# end_sprint_66-LIFE-BRIEF-SENTIMENT — life_brief surfaces the daily "market mood" (Cairn #66)

> Result. life_brief's macro section now carries a `sentiment` block (Crypto Fear & Greed + BTC dominance) beside Fed/CPI/DXY — so the consumer-agent can read "market mood today". Honest-mirror: mock never persisted → real-or-honest-unavailable, never a fabricated mood. Commit `<hash>` `fix(sprint-66-life-brief-sentiment)`. Status: ✅ all gates pass. backend-w3 BUILT; architect 4-step + committed (§3). The value-safe agent-first lane (chosen over the deferred risky #78). Additive — no new tool, no new fetch.

## What shipped (2 files — read_server + tests; modules/ UNTOUCHED)
| File | Change |
|---|---|
| `mcp_servers/read_server.py` (+59/-4) | NEW `_brief_sentiment()` → folded into `_brief_macro` (life_brief's macro section). Reads `macro.store.latest("fear_greed")` / `latest("btc_dominance")` (the SAME store the decision tower + market block cite — #44 FNG-HONEST), classifies the band via the EXISTING `market.service._fng_status` (reused, not re-implemented). `sentiment: {fearGreed:{available,value,band,asOf,source}, btcDominance:{available,value,asOf,source}}`. + the life_brief docstring. |
| `tests/test_mcp_read.py` (+88, 6 tests) | the distinguishing set. |
| modules/ | UNTOUCHED (reused existing reads — no fetch change, no new tool). |

## Design (LOCKED — honest-mirror at the store, reuse, NEUTRAL)
- **honest-mirror (the load-bearing gate, enforced at the store):** `macro.store.record_point` NEVER persists `source=='mock'` (#15 DXY-REAL early-return) → `latest()` returns a REAL row or None → no live point → `available:false` + `value:None` (honest "unavailable"), NEVER a fabricated mood. source carried verbatim (an agent can age/trust it).
- reuses `_fng_status` (the #44 3-band: ≤44 fear / 45-55 neutral / ≥56 greed — single source, no re-impl) + the existing macro store reads (no new fetch).
- NEUTRAL (no advice): the sentiment is a SIGNAL (value + band), NO buy/sell/forecast verb (the NEUTRAL-no-advice gate). ADDITIVE — the existing Fed/CPI/DXY/phase/guardian intact.

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step (read full):** _brief_sentiment honest (latest()→None→available:false/value:None, never fabricated; legacy-mock source carried; fail-soft store-error→unavailable) ✅; reuses _fng_status (no re-impl) ✅; the 6 distinguishing tests (when-real, band-tracks, honest-no-live, additive-intact, NEUTRAL-no-advice, daily-brief-no-macro-consumer-pin via inspect.getsource) ✅; 2-file surface (modules clean — no fetch change); the dirty conftest/test_suite_isolation are #79 (already committed 881ce45 — backend's stale-local; NOT in #66) ✅.
- **backend-w3 evidence:** DEFAULT 2079/0 (2073 + 6); mypy clean. LIVE MCP HTTP (restarted — read_server not in the reload allowlist): life_brief.macro.sentiment = fearGreed{value:20, band:fear, source:live, asOf} + btcDominance{value:60, source:live} (REAL live store, honest-marked) + the Fed/CPI/DXY intact. No new tool → catalog count unchanged.
- **architect re-run:** test_mcp_read 104/0.

## 3 Gates — ALL PASS
- **Gate 1 (API/MCP):** life_brief.macro.sentiment additive + agent-readable (value/band/asOf/source); honest available:false on no-live; no new tool (count unchanged). ✅
- **Gate 2 (Function):** the distinguishing set (real/honest-no-live/band/additive/NEUTRAL/daily-brief-pin); DEFAULT 2079/0; mypy clean; honest-mirror enforced at the store. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + backend evidence + LIVE MCP; 2-file surgical stage (no #79 leak — its files were already committed, backend's stale-local flagged); commit format. ✅

## Assumptions (user-review)
- life_brief.macro carries a `sentiment` block (F&G + BTC dominance — "market mood"). honest-mirror: mock never persisted → real-or-honest-unavailable (never fabricated). reuses the macro store + _fng_status (no new fetch). NEUTRAL (signal, no advice). **How to change:** _brief_sentiment / the band thresholds (_fng_status).

## Notes
- Cairn #66. The value-safe AGENT-FIRST lane (team-lead DEFERRED #78 as risky-for-marginal — this is the higher-value safer alternative). The consumer-agent's life_brief now answers "market mood today". backend BUILT; architect committed (§3). Committed from a tree where backend's stale-local showed #79 files as dirty (they were already committed 881ce45 — my committer-tree is the source of truth, dirty = ONLY the 2 #66 files). Next: dogfood/user-direction (#78 held; board → low/icebox). The roadmap is delivered; this is post-roadmap agent-first polish.
