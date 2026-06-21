# Sprint FNG-HONEST — one honest Fear&Greed source (Cairn #44, honest-mirror HIGH)

> Created 2026-06-21 by architect. HIGH — a real honest-mirror BREACH (QA/dogfood-flagged): the same Fear&Greed signal reads CONTRADICTORY values across surfaces → an agent can't trust the system. DESIGN to team-lead before dispatch (cross-surface honest-mirror contract, like the alert engine).

## The bug (grounded — Rule#0)
There are TWO F&G sources, used inconsistently:
1. **REAL:** `macro/reader.fetch_fear_greed()` (alternative.me, free, live) → stored as the `fear_greed` macro indicator → consumed by the macro snapshot + the decision tower (decision/service.py:480 reads `fear_greed`). Real, today's value (e.g. 23).
2. **MOCK:** `market/service.py:599` — a HARDCODED `MacroSignal(name="Fear & Greed", value="38", status="fear", note="thị trường sợ hãi")` in the stub macro block of market_overview.

→ **market_overview presents F&G=38 "fear" (the mock, as if real); life_brief/guardian cite the REAL ~23 (via macro/decision).** Same signal, two numbers, one presented-as-real-but-mock. That's the honest-mirror breach: an agent reading 38 in one tool + 23 in another can't trust either.

## The fix (DECIDED — decide-and-log; team-lead sanity-check the source choice)
**ONE F&G source of truth = the REAL macro `fear_greed` indicator** (alternative.me, the live one the decision tower already trusts). market_overview's macro block reads THAT, not a hardcoded 38.
- **market_overview** (market/service.py:593-599 stub macro block): replace the hardcoded F&G MacroSignal with a read of the REAL macro fear_greed (latest stored point / fetch_fear_greed). So all surfaces cite the SAME number.
- **Honest-mirror when the real source is unavailable:** if fetch_fear_greed fails / no stored point → market_overview's F&G is `status="n/a"` / marked unavailable + a warning — NOT a fabricated "38 fear". (The decision tower already mock-excludes; market must too — never present a mock as real.)
- **The OTHER stub signals** (BTC Dominance, Brent in the same market mock block): out of #44's scope (the QA flag is F&G specifically) — BUT flag them: are they ALSO hardcoded-mock presented as real? If so, same honest-mirror treatment (mark mock or wire real) — decide-and-log whether to fix them this sprint or file a follow-up.

## ⚠️ FORK (team-lead — the source choice)
- (a) **market_overview reads the REAL macro fear_greed** (my rec — one source, the live one decision already trusts; market just stops duplicating with a stale mock). Honest-unavailable when the real source is down.
- (b) Keep market's F&G but MARK it mock (status/source="mock", value not presented as a real number). Weaker — still two code paths, just honestly-labeled.
- I lean (a): one source of truth eliminates the contradiction entirely (not just labels it). market_overview citing the same fear_greed the brief/guardian/decision cite = the agent sees ONE consistent number everywhere.

## HARD GATE (distinguishing)
- The SAME F&G value appears in market_overview AND life_brief AND the guardian/decision surface — IDENTICAL (read from the one source). The distinguishing: a test that reads F&G via all 3 surfaces and asserts they're EQUAL (today's contradiction = the test that was failing).
- Real-source-down → market_overview F&G = n/a/unavailable + warning, NOT a fabricated number (honest-mirror).
- No other surface still reads the hardcoded 38 (grep: the market/service.py:599 hardcode GONE or reads-real).
- pytest green, mypy clean. (market_overview has a REST + MCP twin → REST≡MCP byte-identical still holds.)

## Baseline
pytest 1922 (post-#46-P2). Keep 0-failed.

## Assumptions (user-review)
- **ONE F&G source = the real macro `fear_greed`** (alternative.me); market_overview reads it (was a hardcoded mock 38); all surfaces cite the same number; real-source-down → honest n/a + warning (never a fabricated value). **How to change:** the market_overview macro block's F&G read.
- BTC Dominance / Brent stubs in the same block: flagged — fix-or-file per team-lead.

## Notes
- HIGH honest-mirror. BRING DESIGN to team-lead (cross-surface contract). Separate commit `fix(sprint-FNG-HONEST)`. backend EDITS (market/service + maybe macro read) → architect 4-step + commits (§3).
- This is the honest-mirror pillar applied: never present a mock as real; one signal = one source = one number everywhere.

## Kickoff — 2026-06-21

### Drift since plan was written (Rule#0, on container :8686)
- **Distinguishing case CONFIRMED LIVE:** `/market` macro block reads `Fear & Greed = "38" status="fear"` (the hardcoded mock at `market/service.py:599`), while the REAL `fear_greed` macro store has latest `value=23.0 source="live"` (and the decision tower's `_q_flow` reads THAT). Breach is live — 38≠23.
- **The right read path = `macro/store.latest(indicator)`** → `sqlite3.Row {indicator, value, ts, source}` or `None`. This is the SAME store the decision tower reads (`_q_flow`→`macro_svc.get_history`→`store`), so reading it guarantees identical value/asOf/source. Using `store.latest` directly (not `get_history`) is leanest — no cold-start FRED-priming side effect (sentiment indicators have no FRED series to prime).
- **fear_greed AND btc_dominance both live in `macro_history`** (the daily `macro_sentiment_snapshot` routine records them, source `"live"` or `"mock"`). So BOTH wire to the SAME store, same pattern. btc_dominance store has real points → wire it.
- **Brent Oil has NO store point / no free feed** → KEEP the stub but mark `source="mock"` (honest-mirror; never present-as-real).
- **Schema change needed:** `MacroSignal` currently = `{name, value, status, note}` — has NO `source`/`asOf` field. Per AGENT-FIRST (derived nums carry source+asOf), ADD `source: str` and `asOf: str | None` to MacroSignal so every surface declares truth. Additive + defaulted → existing consumers unaffected, REST≡MCP twin preserved.
- The market endpoint is `@router.get("")` = `/market` (NOT `/market/overview`). Cross-tool DoD calls `/market` + `/macro/history?indicator=fear_greed` + `/decision/weight`.
- #54 (fngSource honesty) is the SAME fix: once the source field reflects truth (`store.latest().source` = "live"/"mock"), no surface claims live for a mock. Both #44 and #54 close together.

### Plan revisions
- **T1 (the only task):** confirmed scope — (1) add `source`/`asOf` to `MacroSignal` schema; (2) `macro_signals()` reads `macro/store.latest("fear_greed")` + `latest("btc_dominance")` → real value/asOf/source; real-source-missing (`None`) → honest n/a + `source` reflects it, NEVER a fabricated number; (3) Brent stays stub but `source="mock"`; (4) cross-surface test asserting the distinguishing case (market F&G == macro store F&G, EQUAL) + a None-source honest-n/a test.
- No fork remains — option (a) CONFIRMED by team-lead.

### Final task list
- **T1 — F&G single source of truth in market_overview** (backend, then architect 4-step + commit). One task, ~40-70 lines incl. test. Distinguishing-case gate HARD on the container.
