# end_sprint_92-LIFE-BRIEF-MOCK-FLAG — life_brief tier-1 isMock + warning (Cairn #92, honest-mirror)

> Result. life_brief.market.assets listed MOCK assets (VNINDEX/FUEVFVND, source="mock") in the SAME list + shape as LIVE (BTC/ETH/SOL/XAU coingecko) with the mock-ness BURIED in quote.source → an agent skimming misreads them as live. Fixed (mirror macro.DXY): a tier-1 `isMock` flag per asset + an explicit top-level warning listing the mock assets. Commit `<hash>` `fix(sprint-92-life-brief-mock-flag): tier-1 isMock + warning, mirror macro.DXY (#92)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT live MCP distinguishing teeth). Cairn #92 — tool-hardening lane 2 (agent-first honest-mirror).

## What shipped (read_server.py + test)
| File | Change |
|---|---|
| `mcp_servers/read_server.py` (`_brief_market`) | per-asset `isMock: bool` (= `quote.source == "mock"`) lifted to tier-1 (the agent reads it in ONE pass, no drilling quote.source); collect mock symbols → an explicit top-level warning "mock (no live feed): VNINDEX, FUEVFVND — placeholder values, NOT live data" (mirrors macro.DXY's no-live-feed line). The mock value is KEPT (just clearly tagged). |
| `tests/test_mcp_read.py` (+N) | the distinguishing tests: mock-asset→isMock True, live-asset→isMock False, the warning, None-quote→isMock False, no-data-lost. |

## Design (LOCKED — mirror macro.DXY, tier-1 flag, honest discriminator)
- **mirror macro.DXY (the existing honest-mock pattern):** a feed-less/mock data point is surfaced with an explicit flag + a top-level warning — NOT buried in a sub-field. life_brief's market assets now match (the pillar surface must be unambiguously honest).
- **tier-1 isMock = source=="mock" SPECIFICALLY:** a placeholder value with no live feed. The agent reads `isMock` at the asset level, not by drilling `quote.source`.
- **None-quote → isMock False (DECIDED + confirmed):** a null quote (no data at all) is a DIFFERENT honest case — it's already-honest (no value presented), not a fabricated-as-live mock VALUE. So it's not flagged isMock (it's a no-quote case, separate).
- **"last-known" → NOT flagged (DECIDED + confirmed):** real-but-stale ≠ placeholder. isMock is the placeholder discriminator; last-known is real data aged (a different honest tag in quote.source).
- **honest-mirror:** the mock value is MARKED, not removed, not fabricated-as-live. no data lost.

## Verification (Rule#0 — architect INDEPENDENT, live MCP)
- **architect 4-step (read FULL):** isMock = `bool(quote) and quote.source=="mock"` (tier-1); the None-quote=False + last-known≠mock decisions sound; the top-level warning mirrors DXY; mock value kept. ✅
- **🔴 INDEPENDENT live MCP distinguishing teeth (restart-then-curl, read_server not in reload allowlist):** life_brief over MCP → **MOCK (VNINDEX/FUEVFVND, source=mock) → isMock=True; LIVE (BTC/ETH/SOL coingecko, XAU coingecko:pax-gold) → isMock=False**; the top-level warning "mock (no live feed): VNINDEX, FUEVFVND — placeholder values, NOT live data" present. The discriminator is REAL (live-not-flagged / mock-flagged), not a blanket flag. ✅ (A first-parse looked at the wrong nesting [brief.market, not top-level market] — a parse error, not a code bug; re-parsed correctly → the teeth pass.)
- **Suite:** the #92 tests (18 in the file's relevant block) green; DEFAULT (`-m 'not slow'` deterministic) = **2218 passed / 6 skipped / 3 deselected / 0 failed** forward AND reverse (2213→2218 = +5 #92 tests) 0-failed; never staged backend/data/.

## 3 Gates
- **Gate 1 (MCP/agent):** tier-1 isMock (agent reads in one pass) + top-level warning (mirror DXY); mock value kept (no data lost); NEUTRAL (a flag, no advice verb). ✅
- **Gate 2 (Function):** the distinguishing teeth (mock→True / live→False — a real discriminator) + None-quote=False + no-data-lost; independent live MCP; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent live MCP; staged set EXACTLY read_server.py + test + end doc (NO frontend, no data/.env/template); commit format. ✅

## Assumptions (user-review)
- **isMock = source=="mock" specifically** (placeholder, no live feed). **How to change:** the is_mock predicate in _brief_market.
- **None-quote → isMock False** (a no-data case, already honest — not a fabricated-as-live mock). **How to change:** add a separate "noQuote" flag if the agent should distinguish no-data from live.
- **"last-known" → NOT flagged** (real-but-stale ≠ placeholder). **How to change:** widen the predicate if stale should also flag (NOT recommended — last-known is real data).

## Notes
- Cairn #92 — tool-hardening lane 2 (agent-first honest-mirror). The user's brief market section now flags mock assets unambiguously at tier-1 (mirroring macro.DXY) — an agent reads "VNINDEX is mock" in one pass instead of misreading it as live. backend-w3 built; architect committed (§3 sole-committer). BE-only (the MCP/brief surface; no FE, no market-module quote-logic change — surfaces the existing source='mock' tag). The live-MCP distinguishing teeth (mock→True/live→False) are the load-bearing proof. After #92: #99 (wiki_search score) → #98 (WorkspaceCreate) → re-scoped hash-validate. #91+#92 = the agent-first OUTPUT fixes the user asked for (bounded + honest).
