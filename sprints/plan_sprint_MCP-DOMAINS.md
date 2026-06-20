# Sprint MCP-DOMAINS — per-domain MCP servers (start: `lifeos-finance`)

> Created 2026-06-20 by architect. Theme: tool-pool scoping (memory `mcp-tool-scoping-plan-2026-06-20`).
> User: "agent tài chính chỉ thấy tool tài chính." DECIDED: per-DOMAIN narrow servers, NOT per-key UI (#6 icebox).

## Objective
The shared read-server exposes **40** tools (mixes finance, market, macro, projects, wiki, claude_usage, journals, brief, …) → noisy for a specialized agent. Add a **narrow, ADDITIVE 5th MCP server** `lifeos-finance` exposing ONLY the finance-domain subset by **reference-importing the exact tool fns from `read_server`** (zero logic duplication). A finance agent connects to ONLY this server → sees ~14 tools instead of 40. The existing 4 servers stay UNCHANGED (read still has all 40 — full-access surface kept).

## Architecture (DECIDED — decide-and-log)
- **New module:** `backend/mcp_servers/finance_server.py`.
- Its `TOOLS` dict is a **SUBSET REFERENCE** to `read_server`'s existing tool fns — `from mcp_servers.read_server import finance_overview, market_overview, …` then `TOOLS = {"finance_overview": finance_overview, …}`. The SAME fn objects → a tool via `/mcp/finance` is byte-identical to via `/mcp/read` (no reimpl, can't drift).
- `build_server(transport_security=None, stateless_http=False)` — IDENTICAL signature + body shape to read_server's (FastMCP("life-os-finance"), loop `TOOLS.values()` → `add_tool`). stdio `main()` entrypoint too (consistency; registerable as a stdio server like the others).
- **Mount:** add `("/mcp/finance", "mcp_servers.finance_server")` to `main.py` `_MCP_MOUNTS`. The existing `_build_mcp_servers` loop already does `build_server(transport_security=sec, stateless_http=True)` for every mount → finance gets DNS-rebind-off + stateless **for free**, no main.py logic change beyond the one list entry. Client URL = `http://<host>:8686/mcp/finance/mcp`.
- **No `from __future__ import annotations`** (FastMCP introspects real annotations — same constraint as the other 4 servers; the AST test will enforce it).
- **NO duplication:** finance_server must NOT redefine any tool fn — grep-assert it only imports them from read_server.

## THE FINANCE TOOL SET (the key design call — DECIDED, 15 tools — team-lead approved +market_indicators 2026-06-20)
A finance/investment agent needs: the portfolio, the markets it's invested in, the macro backdrop that drives allocation, and the decision-tower the assistant arc built. NOT: projects, claude_usage, journals(trade-journal is borderline — see below), wiki, activity, graveyard, reliability, news, the cross-domain life_brief/insights/catalog, proposal-readback.

**INCLUDED (14):**
| # | Tool | Why a finance agent needs it |
|---|---|---|
| 1 | `finance_overview` | the portfolio: per-channel allocations, golden-path targets, total, P&L, dry powder — the core |
| 2 | `finance_channel` | one channel's holdings + sell-ladder state |
| 3 | `finance_analytics` | rebalance amounts + risk(HHI)/concentration + returns |
| 4 | `finance_simulate` | what-if allocation → HHI/drift/turnover (the agent shapes a hypothesis) |
| 5 | `finance_guardian` | proactive NEUTRAL portfolio observations (the assistant's proactive scan) |
| 6 | `allocation_target` | reference channel weighting given capital + macro phase |
| 7 | `decision_weight` | the decision tower's tip: W=∏q + binding constraint (NEUTRAL) |
| 8 | `macro_cycle` | the Investment-Clock RL state (phase) — drives allocation reasoning |
| 9 | `nav_history` | daily NET-ASSET-VALUE series + confidence (portfolio trend) |
| 10 | `exchange_overview` | OKX balances + open positions (the live exchange book) |
| 11 | `macro_overview` | Fed funds / CPI / DXY + trend — the macro backdrop |
| 12 | `market_overview` | live quotes + alert triggers (the markets the book is in) |
| 13 | `market_summary` | rich watchlist + NEUTRAL technicals (RSI/trend) per symbol |
| 14 | `journal_entries` | the TRADE journal — entries + win-rate/P&L stats (a finance agent reviewing trade history) |
| 15 | `market_indicators` | TA indicators (RSI/MA/MACD/…) — a real investment agent judges ENTRY/timing on indicators, not just the overview quote (team-lead-approved add 2026-06-20) |

**EXCLUDED + why (so the boundary is explicit):**
- `market_history / market_ohlc / market_watchlist / market_correlation / market_relative_strength` — deeper TA/price-series tools. **DECIDED: finance's market view = `market_overview` + `market_summary` + `market_indicators` (entry/timing). The 5 remaining deep-TA tools are a MARKET-domain concern.** If a finance agent needs deeper TA, that's a signal to add a `lifeos-market` domain server later (logged as a follow-up), not to bloat finance.
- `macro_history` — the macro time-series; `macro_overview` (latest + trend) is enough for allocation reasoning. (Move in if you want historical macro.)
- `daily_brief / life_brief / insights / list_tools_catalog` — CROSS-domain composers (they pull projects/claude/wiki too). A domain-scoped server should NOT carry the whole-life synthesizer; that's exactly the noise we're cutting. The agent that wants the whole picture uses `lifeos-read`.
- `decision_entries` — the DECISION journal (general decisions across domains, calibration) — broader than finance; lives on read. (vs `journal_entries` = the TRADE journal, finance-specific, INCLUDED.)
- `projects_list / project_get / graveyard_overview / claude_usage / app_settings / reliability_report / activity_feed / activity_run / news_digest / news_list / brief_history` — non-finance domains.
- `check_proposal_status / list_my_proposals / proposal_stats` — proposal read-back is a WRITE-loop concern (the agent learning from its proposals); a read-only finance agent doesn't propose. (If a finance WRITE server is ever added — icebox — its read-back goes with it.)

**Scope decision: FINANCE ONLY this sprint.** Prove the per-domain pattern with one server; add `lifeos-market` / `lifeos-projects` later if the user wants more domains. (team-lead leaned this way; I concur — no-overengineering.)

## Tasks
- **T1 (backend, gating):** create `mcp_servers/finance_server.py` (subset-reference TOOLS + build_server + main) + add the `/mcp/finance` mount to `main.py` `_MCP_MOUNTS`. `docker compose restart backend` (main.py not in --reload-dir). Backend writes the unit/build tests (count==14, identical-fn-identity vs read_server, no-future-annotations, no-reimpl).
- **T2 (tester):** live verify on the restarted container — `/mcp/finance/mcp` handshake 200 (stateless, no session-id) + `tools/list` returns EXACTLY the 15 + a tool call (`finance_overview` + `market_indicators`) via `/mcp/finance/mcp` == via `/mcp/read/mcp` (identical payload). Other 4 mounts' counts UNCHANGED (40/4/11/6). pytest green.
- **T3 (architect, parallel):** update `docs/MCP-CONFIG.md` (§1 table + §3b mount table + §4 register entry — a 5th server, finance, 14 tools) + `backend/mcp_servers/CATALOG.md` if it lists servers. (Docs = my own surface; quick-fix-tier, folded into this sprint.)

## HARD GUARD (gates)
- Identical-payload: `finance_overview` (and ≥1 more) via `/mcp/finance/mcp` == via `/mcp/read/mcp` — SAME fn object (assert `finance_server.TOOLS["finance_overview"] is read_server.finance_overview`).
- Tool count on `/mcp/finance` == EXACTLY 15 (assert the name set). Other 4 servers UNCHANGED (40/4/11/6) — the existing `test_mcp_http.py::test_stdio_build_servers_unchanged` already pins those; do NOT regress them.
- `stateless_http=True` (restart no-drop) + DNS-rebind off — inherited from the `_build_mcp_servers` loop (verify the handshake issues no session-id, like the other mounts).
- No logic duplication — grep: `finance_server.py` defines NO tool fn body, only imports them from read_server.
- pytest green, mypy clean, 3 gates.

## Baseline (regression anchor — VERIFY at kickoff, these are from memory/last-sprint)
- pytest: confirm current count (memory cites ~1639 post-DEDUP; tester re-runs to anchor).
- The 4 mounts: read=40, write=4, wiki-read=11, wiki-write=6 (pinned by test_mcp_http.py).

## Assumptions (user-review)
- **lifeos-finance tool set: 15 tools** — finance domain = portfolio (overview/channel/analytics/simulate/guardian) + decision-tower (macro_cycle/decision_weight/allocation_target/nav_history) + macro backdrop (macro_overview) + market at-a-glance INCLUDING `market_indicators` (the agent judges entry/timing on indicators) + exchange book + trade journal_entries. Deeper TA (ohlc/watchlist/correlation/rel-strength/history) deferred to a future `lifeos-market` server; cross-domain composers (daily_brief/life_brief/insights/list_tools_catalog) excluded as the noise being cut. **How to change:** edit `finance_server.TOOLS` (add/remove a name→fn ref from read_server); the count test (==15) updates with it.
- **Finance-only this sprint (no 2nd domain server yet).** **How to change:** clone the same pattern for `lifeos-market` / `lifeos-projects` in a follow-up sprint; the pattern is now proven + cheap.

## Notes
- main.py NOT in uvicorn `--reload-dir` → `docker compose restart backend` after the mount edit, BEFORE live curl (memory mcp-wiki-dedup + the MCP-CONFIG §3b note).
- ADDITIVE only — does NOT remove tools from `lifeos-read` (full-access server kept). No per-key UI. No FE. No touching the other 4 servers' tool sets.
