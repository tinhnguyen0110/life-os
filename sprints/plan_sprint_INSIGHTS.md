# Sprint INSIGHTS (D1) — cross-domain insights composer (the answer-quality headline)

> Answer-quality audit (memory `answer-quality-audit-data-gaps-2026-06-15`): the #1 lever. The app answers literal queries but never volunteers the cross-module "so what." One composer lifts 4-5 weak answers (Q1/Q2/Q6/Q11/Q12) to A. Backend-only (MCP read tool, lives in read_server like life_brief — no new module).

## Kickoff — 2026-06-15 (architect)

### Verified on disk (data sources for each rule — the dispatch-verify-fields discipline)
- **finance** ✓ `ChannelAlloc.stablePct` (schema.py:71), `.driftAlert` (:57), `FinanceOverview.dryPowder` (:108). Read via `_fin_overview()` (already aliased read_server.py:72).
- **market RSI** ✓ `compute_indicators(symbol, ["summary"])` → `rsi_signal: overbought|oversold|neutral` (ta.py:469-473 `summarize`); `["rsi"]` → raw `.last` value. Read via `_mkt_indicators` (aliased :87) over `_mkt_tracked()` (aliased :88).
- **market changePct** ✓ `Quote.changePct` (schema.py:41) via `_mkt_market()` (aliased :82).
- **wiki** ✓ `_wiki_search(query)` (aliased :121) — to find an investment/strategy MOC for the framework-vs-execution rule.
- **projects** ✓ stall/idle-days via `_proj_list()` (the projects reader, already used by life_brief).

### 🔑 DECISION — DROP the Fear&Greed divergence rule (no real data source)
team-lead's seed rule 3 (Fear&Greed vs price divergence) has **NO real data**: F&G is a STUB MOCK (`market/schema.py:159`, `service.py:524` — "stub mock this build, deterministic"). An insight citing mock F&G as evidence would VIOLATE the evidence-grounded / no-fabrication spine that is the whole point of this composer (every insight cites real source tools). **So: drop F&G-divergence from D1's live rules; add it as a DEFERRED rule (same pattern as the FRED-key deferral) that lights up when real F&G data exists.** The other 4 rules all have verified-real sources. (decide-and-log; flag to user-review.)

### 🔑 THE COMPOSER (architect call — reuse the life_brief `_section` fail-soft pattern)
New MCP read tool `insights()` in `read_server.py`, mirroring the `life_brief`/`_section` architecture (read_server.py:679-806 — fail-soft per source, source-tagged). It runs cross-domain RULES, each producing `{insight, severity, evidence, sources[]}` ONLY when its real condition fires:

**Rule data + fire conditions (NEUTRAL — describe, never advise; each cites its source tools):**
1. **Undeployed capital** — `crypto ChannelAlloc.stablePct > 90` → `{insight: "crypto channel is {stablePct}% stablecoin (cash-equivalent) — undeployed vs target, not crypto exposure", severity: "high", evidence: {stablePct, dryPowder, cryptoTarget}, sources: ["finance_overview"]}`.
2. **All-crypto overbought** — for every tracked CRYPTO asset, `compute_indicators(sym,["summary"]).rsi_signal == "overbought"` (ALL of them) → `{insight: "all tracked crypto overbought (RSI {sym}:{val}...)", severity: "medium", evidence: {perAsset: {sym: rsiValue}}, sources: ["market_indicators"]}`. Fire ONLY if ≥2 crypto assets AND all overbought (one overbought asset isn't "all").
3. **Framework-vs-execution gap** — `_wiki_search("investment OR strategy OR framework")` finds an investment/strategy MOC AND finance shows a target channel (etf/vn) at ~0% deployed → `{insight: "you have a written framework (note #{id} '{title}') but finance shows {pct}% deployed to {channel}", severity: "medium", evidence: {noteId, noteTitle, channel, deployedPct, targetPct}, sources: ["wiki_search","finance_overview"]}`. Only fire if BOTH sides present (a real wiki note AND a real under-deployment) — the join is the insight.
4. **Stalled project** — a project idle > STALL_DAYS (30) → `{insight: "project '{name}' idle {days}d", severity: "low", evidence: {projectId, idleDays}, sources: ["projects_list"]}`.

**Output:** `{insights: [...], asOf, sources: [all tools touched]}` ranked by severity (high→low). **Honest-empty:** no rule fires → `{insights: [], note: "nothing notable across modules right now"}` (NOT a fabricated insight). Each insight is fail-soft (one rule erroring → that rule yields nothing + a source-error tag, never breaks the whole composer — the `_section` pattern).

**NEUTRAL invariant (HARD):** NO advice verb (should/buy/sell/rebalance/move/consider) in ANY insight string — they're composition statements + evidence. A test asserts the forbidden-verb set is absent from every insight.

**Evidence-grounded (the anti-hallucination spine):** every insight carries `evidence` (the real numbers it's derived from) + `sources` (the tools). No insight without a real fired condition. This is what makes it trustworthy vs an LLM guessing.

### Capability / read-only invariant
- `insights()` wraps READ fns only (`_fin_overview`/`_mkt_indicators`/`_mkt_market`/`_wiki_search`/`_proj_list`) — NO write/mutate symbol. WRITE_SYMBOLS AST/namespace gate stays 0-leak with the new fn. Registered in TOOLS → catalog auto-derives.
- Read-only: a test asserts no disk mutation after an `insights()` call.

### Final task list (single backend lane)
- **INSIGHTS [backend]** — `insights()` MCP read tool in read_server.py: the 4 real-data rules (undeployed / all-crypto-overbought / framework-vs-execution / stalled-project), `_section`-style fail-soft per rule, evidence + sources on each, NEUTRAL (no advice verb — tested), honest-empty, ranked by severity. Register in TOOLS + regen CATALOG. WRITE_SYMBOLS gate green. Distinguishing cases below.

## Verification (distinguishing cases — locked)
- **Live data fires the right rules:** stablePct 97.74 → undeployed insight FIRES (evidence stablePct+dryPowder, source finance_overview); all tracked crypto RSI overbought → all-overbought FIRES; a wiki investment MOC + 0%-deployed etf/vn → framework-gap FIRES. Each with evidence + source citation.
- **Healthy state does NOT fire** (the anti-blanket proof): a hypothetical diversified portfolio (stablePct 20, RSI neutral, all channels deployed) → those insights DON'T fire. Proves rules key on REAL conditions, not blanket text.
- **NEUTRAL:** no advice verb in any insight string (asserted against the forbidden set).
- **Evidence-grounded:** every emitted insight has non-empty `evidence` + `sources` (no bare claim).
- **Honest-empty:** nothing fires → `{insights:[], note:"nothing notable..."}`, not a fabricated insight.
- Read-only (no disk mutation, asserted); WRITE_SYMBOLS gate green; full suite ≥ baseline, 0 errors/unhandled.

## Assumptions (user-review)
- INSIGHTS composer = `insights()` MCP read tool, 4 cross-domain rules over REAL data (undeployed-capital / all-crypto-overbought / wiki-framework-vs-finance-execution / stalled-project). Each fires only on a real condition + cites evidence + source tools. NEUTRAL (no advice). Honest-empty when nothing notable.
- **Fear&Greed-divergence rule DROPPED from D1** — F&G is a stub mock (no real data); an insight citing it would fabricate evidence. Deferred: lights up when real F&G data exists (same as the FRED-key deferral). To enable: wire a real Fear&Greed feed, then add the rule.
- Thresholds: stablePct>90 (undeployed), RSI overbought via the existing `summarize` overbought band (≥70), STALL_DAYS=30, all-overbought requires ≥2 crypto assets all overbought. To change: edit the rule constants.
