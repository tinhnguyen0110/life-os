# End Sprint MCP-STATELESS — 4 MCP servers → stateless_http (Task #75)

> Status: **REVIEWED — gates green, committing.** Task #75 (reactive, agent-first). The 4 streamable-http MCP servers were STATEFUL (per-session mcp-session-id) → a backend restart invalidated the session → dropped the connected client. Switched all 4 to `stateless_http=True` → no per-session state → a restart can't drop a client (nothing to invalidate). Transport-only change; ZERO tool-surface change.

## What shipped
- **`build_server(transport_security, stateless_http=False)`** on all 4 servers (shared read/write + wiki read/write) → `FastMCP(..., stateless_http=stateless_http)`. Default `False` = stdio-identical (the stdio path unchanged); `main.py` passes `stateless_http=True` for the HTTP mount. Native FastMCP flag — NO fastmcp-v2 migration.
- **`session_manager.run()` KEPT** (the subtle trap): the comment documents that `run()` starts the StreamableHTTPSessionManager's task group REGARDLESS of stateful/stateless — removing it (thinking "stateless = no session manager needed") → 500 every call. The AsyncExitStack lifespan stays.
- **The win (agent-first):** stateless → the handshake issues NO `mcp-session-id` → a backend restart can't drop a session that doesn't exist → an MCP client (the external agent) survives a `docker compose restart` with no reconnect/re-initialize. The old stateful code needed the session-id from `initialize`; a restart invalidated it → drop.

### Verified counts (architect re-ran independently — Rule #0)
- mcp + http suites: **151 passed, 0 errors**. Full suite (backend-2): **1653 passed**. mypy clean on the 5 touched files.
- **Tool-surface UNCHANGED (Rule #0 — stateless is transport-only):** imported `.TOOLS` on all 4 → shared-read 40 / shared-write 4 / wiki-read 11 / wiki-write 6 (the MCP-DEDUP counts, no regression).
- **team-lead LIVE-verified the restart-no-drop spine (the distinguishing test):** initialize → 200 with NO mcp-session-id header (genuinely stateless); tools/list with no session → 200 (pre-restart); `docker compose restart backend` (up 3s); SAME tools/list, no re-initialize, post-restart → **200** (CLIENT SURVIVED — the old stateful code would've dropped). My disk review confirms the code matches (stateless_http=True on all 4, run() kept).

## Code review (architect — 4-step)
1. **git status/diff** — 5 source/test files: main.py + the 4 servers' build_server + test_mcp_http. `template/*` + `docker-compose.yml`/`.env` + `docs/MCP-COMPARISON-PROMPT.md` (a separate abstract MCP design-discussion doc, NOT this sprint — for the upcoming user discuss) EXCLUDED.
2. **Read full functions** — build_server (the stateless_http param threaded into FastMCP, default False); main.py (passes True for HTTP, run() kept in the AsyncExitStack); the test docstrings (no-session-id + restart-survivable assertions).
3. **Verify against the spine** — restart-no-drop (team-lead live + the test) + no tool regression (40/4/11/6) + run()-kept (no 500).
4. **Hunt additional issues** — stdio path unchanged (default False); the session_manager.run() retained (the trap backend-2 documented); no fastmcp migration; DNS-rebinding-off preserved (the 421 guard from the earlier MCP-HTTP sprint). ✅

## Assumptions (user-review)
- **All 4 MCP HTTP servers are stateless_http=True** (no per-session state). **Why:** agent-first — a backend restart must not drop the connected agent (the user's requirement). **How to change:** the `stateless_http=` arg in main.py's `_build_mcp_servers`. The stdio path stays stateful-default (build_server default False) — only the HTTP mount is stateless.
- **session_manager.run() is retained** even when stateless — it starts the SDK's session-manager task group regardless; removing it → 500. Don't "optimize" it away.

## The 3 Quality Gates
- **Gate 1 — API:** ☑ all 4 /<mount>/mcp endpoints respond (stateless handshake, no session-id) · ☑ no tool-surface change (40/4/11/6) · ☑ no auth · ☑ DNS-rebinding-off preserved. **PASS**
- **Gate 2 — Function:** ☑ restart-no-drop (team-lead live + the no-session-id/restart-survivable tests) · ☑ run() kept (no 500) · ☑ stdio path unchanged (default False) · ☑ 151 mcp+http green, 0 errors · ☑ mypy clean. **PASS**
- **Gate 3 — Sprint:** ☑ end doc + verified counts + the live restart proof · ☑ architect spot-checked the build_server + main.py + tool counts · ☑ team-lead LIVE-verified the distinguishing restart test · ☑ assumptions logged (2) · ☑ commit format `fix(sprint-MCP-STATELESS)`. **PASS**

## Risks / follow-ups
- **Stateless is the right model for an agent-first single-user app** — no session affinity needed (one client, one machine); a restart is invisible to the agent. No multi-client session-isolation concern (single-user).
- **EXCLUDED:** `docs/MCP-COMPARISON-PROMPT.md` (an abstract MCP-design-decision guide, prep for the user's upcoming MCP-architecture discuss — NOT sprint code) + infra (docker-compose/.env).
- This is the last of the 2 in-flight items before the user-requested PAUSE (the other: SIDEBAR-UX-A, frontend-2). The per-domain MCP-server plan stays iceboxed until the user discusses.
