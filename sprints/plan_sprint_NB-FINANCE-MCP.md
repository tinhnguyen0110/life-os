# Sprint NB-FINANCE-MCP — surface existing finance/market analytics as MCP read tools

> Blank-context dogfood (memory `blank-context-dogfood-2026-06-15`): the agent eyeballed indicators / couldn't reach rebalance because the capabilities EXIST in-app but aren't named MCP tools. Pure NG2-class discoverability gap. Backend-only.

## Kickoff — 2026-06-15 (architect)

### Verified on disk (the safety + discoverability facts)
- **`simulate` IS read-safe** (the key safety question): `finance/service.py:686` `simulate(allocation: dict[str,float]) -> (SimulateResult, warnings)` — reads golden path + current channel %, computes HHI/concentration/drift/turnover/hhiDelta, builds `SimulateResult`. **Grepped the full body (686-745): ZERO `md_store.write`/snapshot/save/persist/db-execute** → pure compute, no side effects. SAFE on the read-server. Its own docstring: "PURE NUMBERS — explicitly NOT advice."
- **correlation/rel-strength are NOT in market_overview** (corrects the assumption) — they're separate REST endpoints with NO MCP tool: `GET /market/correlation` → `service.correlation(syms: list, hours=720) -> (data, warnings)`; `GET /market/relative-strength` → `service.relative_strength(symbol, vs="BTC", hours=720) -> (data, warnings)`. Both pure math in `market/ta.py` (Pearson matrix + rel-strength). The dogfood agent couldn't find them because there's no tool, not because they're buried. → each needs its OWN MCP read tool.
- Validation lives at the REST routes (422 on empty/negative/unknown-channel for simulate; <2 or >10 symbols for correlation). The MCP tools must replicate the honest-error handling (return a warning/error dict, never crash).

### 🔑 THE DECISION (architect call — decide-and-log) → 3 MCP read tools
1. **`finance_simulate(allocation: dict[str,float])`** — wraps `service.simulate(allocation)`. Returns the SimulateResult dict (hypothetical + current shape, hhiDelta, normalized, asOf) + warnings. Honest-input handling: empty/negative/unknown-channel → a warning/error in the result (mirror the route's 422 reasons as a `{error: ...}` or warnings list, NOT a raw exception — MCP tools return dicts, not HTTP codes). Read-only.
2. **`market_correlation(symbols: str, hours: int = 720)`** — wraps `service.correlation(parsed_syms, hours)`. `symbols` = comma-separated (mirror the route); parse + upper + bound to ≤10 (>10 → honest warning, not crash); <2 → honest warning. Returns the Pearson matrix dict + warnings.
3. **`market_relative_strength(symbol: str, vs: str = "BTC", hours: int = 720)`** — wraps `service.relative_strength(symbol, vs, hours)`. Returns the rel-strength dict + warnings.

Why 3 separate tools (not folding into market_overview): market_overview is a snapshot; these are parameterized analytics (the agent passes symbols/allocation/hours). They're genuinely distinct named capabilities — discoverability = a named tool the agent finds in the catalog. (Same reasoning as NG2's namespaced surface.)

### Capability gate (HARD — all 3 are READ tools)
- All wrap PURE-COMPUTE service fns (simulate verified zero-side-effect; correlation/rel-strength are math over the close series). They import NO write/snapshot/persist symbol. The read-server WRITE_SYMBOLS AST/namespace gate (`test_mcp_read.py`) MUST stay 0-leak with the 3 new fns added. If it flags → the tool reached a forbidden symbol → fix the tool.
- **Read-only invariant (like NB1+NB2):** a `finance_simulate` call must NOT mutate portfolio/holdings — assert no holdings/finance disk change after the call (the simulate is a pure compute; prove it).

### Final task list (single backend lane)
- **NB-FINANCE-MCP [backend]** — add `finance_simulate` + `market_correlation` + `market_relative_strength` to `read_server.py`, each wrapping the existing service fn, honest-error (not crash) on bad input, registered in TOOLS (catalog auto-derives → regen CATALOG.md). Behavior tests (each returns the real numbers for a valid input + honest handling of bad input + simulate read-only/no-mutation). WRITE_SYMBOLS gate green. Full suite green.

## Assumptions (user-review)
- 3 new MCP READ tools surface existing pure-compute capabilities: `finance_simulate` (what-if allocation → HHI/drift/turnover, verified zero side-effect), `market_correlation` (Pearson matrix, ≤10 symbols), `market_relative_strength` (vs a benchmark, default BTC). All read-only; honest-error (warning/error dict) on bad input, never a crash; no portfolio mutation on simulate.
- Validation mirrors the REST routes (simulate: non-empty/non-negative/known channels; correlation: 2-10 symbols) but returns warnings/error in the dict rather than HTTP 422 (MCP-tool convention).
