# end_sprint_MCP-DOMAINS — per-domain MCP server `lifeos-finance`

> Result. Sprint theme: tool-pool scoping (memory `mcp-tool-scoping-plan-2026-06-20`).
> Commit: `<hash>` (filled at commit). Status: ✅ all 3 gates pass.

## Objective (met)
The shared read-server exposes 40 tools → noisy for a specialized agent. User: "agent tài chính chỉ thấy tool tài chính." Added a **narrow, ADDITIVE 5th MCP server `lifeos-finance`** (`/mcp/finance`) exposing ONLY a 15-tool finance subset, built by **reference-importing the exact tool fns from `read_server`** (zero logic duplication). The existing 4 servers are UNCHANGED — read keeps all 40 (full-access surface kept). A finance agent connects to `/mcp/finance` and sees 15 focused tools instead of 40.

## What shipped
| File | Change |
|---|---|
| `backend/mcp_servers/finance_server.py` | **NEW** — `TOOLS` = `{name: read_server.TOOLS[name]}` for the 15 curated names (reference, no copy). `_build_tools()` raises KeyError-loud if a name vanishes upstream. `build_server(transport_security, stateless_http)` + stdio `main()`, identical shape to read_server. NO tool fn redefined. No `from __future__`. |
| `backend/main.py` | **+1 mount line** — `("/mcp/finance", "mcp_servers.finance_server")` in `_MCP_MOUNTS` + a clarifying comment. NOTHING else: `_build_mcp_servers` already applies `transport_security=sec, stateless_http=True` to every mount → finance inherits stateless + DNS-rebind-off for free. |
| `backend/tests/test_finance_mcp_server.py` | **NEW** — 10 tests: count==15, exact name-set (both directions), identity `is` loop on all 15 + explicit on 2 reps, no-reimpl `__module__`, no-local-tool-binding guard, build registers 15, stdio-default-identical, no-future-annotations. |
| `backend/tests/test_mcp_http.py` | **EXTENDED** — `MOUNTS` 4→5 (added `/mcp/finance`) so the existing handshake-200 + stateless-no-session-id tests now exercise the finance mount; `test_stdio_build_servers_unchanged` adds `fs.TOOLS==15` + builds fs; no-future test includes fs; docstrings 4→5. (touched-existing-test per memory `commit-stage-touched-test-files-too`.) |
| `docs/MCP-CONFIG.md` | §1 server table (+finance read 15, framed as reference-subset → adds NO new tools to 61) + the 15-tool list + exclusion rationale + "which server to register" (finance-only agent → lifeos-finance alone) + §3b HTTP mount table + §4 stdio JSON entry + CLI line + §5 boot sanity-check + §3b curl-swap. |
| `backend/mcp_servers/CATALOG.md` | totals header (+finance domain narrow view; the 15 names; "adds NO new tools to 61"). |

## The 15 finance tools (team-lead approved, +market_indicators)
finance_overview · finance_channel · finance_analytics · finance_simulate · finance_guardian · exchange_overview · decision_weight · allocation_target · macro_cycle · nav_history · macro_overview · market_overview · market_summary · market_indicators · journal_entries

## Verification (Rule #0 — re-run, not trusted)
- **pytest:** baseline 1653 → **1662 passed, 6 skipped, 0 failed** (+9 = the 10 finance tests minus the 1 renamed http test; backend-reported, team-lead-confirmed). Architect re-ran the MCP subset: **107 passed, 0 failed, 0 errors** (test_mcp_http + test_finance_mcp_server + test_mcp_read).
- **Identity (direct, architect Rule#0):** `all(fs.TOOLS[n] is rs.TOOLS[n] for n in fs.TOOLS)` → **True**; `{fn.__module__}` == `{'mcp_servers.read_server'}`; finance=15, read=40 unchanged. Zero-dup proven structurally (same objects).
- **Live (team-lead, on the running container):** `/mcp/finance` tools/list → 15 exact names; other 4 mounts unchanged (40/4/11/6); finance_overview via /mcp/finance == via /mcp/read byte-identical (totalValue 10627.26, pnlTotal.pct −74.08, 8 holdings, 4 allocs); handshake 200 / stateless / no-session-id after restart.

## Code review (architect 4-step)
1. `git diff` — main.py +1 mount line, test_mcp_http.py MOUNTS 4→5 + count test + no-future test, 2 new files.
2. Read FULL `finance_server.py` + both test files entry→exit. `_build_tools()` is the right defensive shape (KeyError-loud at import, never a silent shrink). build_server/main mirror read_server. Capability gate inherited structurally (same objects read_server's no-write AST test already covers) — sound.
3. Verified vs plan — the 15 match the approved set incl. market_indicators; additive (read unchanged); zero-dup `is`-identity is the spine and it holds.
4. Hunted issues — **none found.** No core/registry edit (auto-mount loop used). No reimpl. The touched test_mcp_http.py is properly extended (not just a new file added). docker-compose.yml dirty is PRE-EXISTING (Tailscale API_BASE, not ours) → EXCLUDED from the commit.

## 3 Gates — ALL PASS
- **Gate 1 (API/transport):** additive mount only, no router/schema change; extended integration coverage; auto-mounted via the loop (no core edit). ✅
- **Gate 2 (Function):** 10 behavior-asserting unit tests; 0 errors/0 rejections (full tail read); drift caught both directions; KeyError-loud error path; real `is`-identity (no self-confirming asserts). ✅
- **Gate 3 (Sprint):** end doc w/ verified counts; full-function spot-check; tester+team-lead live-verified; counts ≥ baseline (+9); commit format match; out-of-scope (docker-compose) flagged + excluded. ✅

## Assumptions (user-review)
- **lifeos-finance tool set: 15 tools** — finance domain = portfolio (overview/channel/analytics/simulate/guardian) + decision-tower (macro_cycle/decision_weight/allocation_target/nav_history) + macro backdrop (macro_overview) + market at-a-glance INCLUDING `market_indicators` (the agent judges entry/timing on indicators) + exchange book + trade journal_entries. Deeper TA (ohlc/watchlist/correlation/rel-strength/history) deferred to a future `lifeos-market` server; cross-domain composers (daily_brief/life_brief/insights/list_tools_catalog) excluded as the noise being cut. **How to change:** edit `finance_server._FINANCE_TOOL_NAMES` (add/remove a name that exists in read_server.TOOLS); the count test (==15) + exact-set test update with it.
- **Finance-only this sprint (no 2nd domain server yet).** **How to change:** clone the same pattern for `lifeos-market` / `lifeos-projects` in a follow-up sprint; the pattern is now proven + cheap (1 new file ~120 lines + 1 mount line + tests).

## Out-of-scope / follow-ups (flagged, NOT done)
- **`lifeos-market` / `lifeos-projects` domain servers** — clone this pattern if the user wants more domain-scoped agents.
- **Per-key UI** (UI creates a key + picks tools) — ICEBOX (#6), only if custom-per-tool keys / sharing-to-others ever becomes a real need. Per-domain solves 90% at a fraction of the cost.
- **docker-compose.yml** Tailscale `API_BASE` change is in the working tree (pre-existing, not this sprint) — left untouched, NOT committed.
