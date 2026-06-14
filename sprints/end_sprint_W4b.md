# Sprint W4b — MCP READ-only server (wiki) · END

**Status:** ✅ implemented + verified live in-container (Rule#0, stdio handshake + tool call + audit).
**Commit:** (pending W4b commit — includes the mcp dep + container was rebuilt --no-cache).

## What shipped
External Claude Code can now plug into the wiki via MCP (stdio) and READ it — search, overview,
inbox, graph, get-note, backlinks, recent-ops. The server is structurally incapable of writing
(the M4 least-privilege gate). Every call is audited.

### Files
- NEW `backend/modules/wiki/mcp/__init__.py` + `read_server.py` — 7 read tools, TOOLS registry,
  build_server() (FastMCP), main() stdio entry. Deliberately NO `from __future__ import annotations`
  (FastMCP introspects real annotations; stringized ones crash it).
- NEW `backend/modules/wiki/mcp/README.md` — Claude Code mcp config snippet + tool table + smoke test.
- NEW `backend/tests/test_wiki_mcp_read.py` — 14 tests.
- MOD `backend/pyproject.toml` — +`"mcp>=1.12"` (container got 1.27.2 on rebuild; host venv 1.12.4).

### Entry point (for Claude Code mcp config)
`python -m modules.wiki.mcp.read_server` (cwd /app). Nested under modules/wiki so the package name
`mcp` doesn't shadow the installed `mcp` SDK (a top-level `backend/mcp/` WOULD shadow it — backend
reproduced that ModuleNotFoundError and moved to the nested location).

## Verified LIVE in CONTAINER (team-lead, Rule#0)
- pytest 899 (+46 = 32 W4a + 14 W4b), 14 W4b def==collected (no dup-shadow), mypy clean.
- **M4 GATE (no write capability)** — proven by my own AST analysis, not just the report's test:
  read_server imports ONLY `reader`, `proposals_store` (append_audit), and `service.get_note as
  _get_note` — NO proposals_service, NO create/update/delete/merge/refine. Append-audit is allowed
  (writes only to its own audit table, not a vault mutation). The two gate tests
  (namespace + AST) pass.
- **stdio handshake in-container**: `python -m modules.wiki.mcp.read_server` → initialize →
  serverInfo `life-os-wiki-read`. 7 tools in registry.
- **live tool call**: `tools/call wiki_overview` → result present, isError=False (real data).
- **audit**: each MCP call appends a wiki_mcp_audit row (actor=mcp:reader) — verified 0→1 live.

## Note (transient, not a bug)
Backend flagged one earlier full-run with 3 transient test_activity httpx failures (live container's
market-poll hitting CoinGecko mid-run) — did not reproduce in 2 clean runs; my own full run = 899
passed clean. Flaky external-network hiccup, not code.

## Infra (team-lead lane)
Container rebuilt `docker compose build --no-cache backend` + `up -d` to install the mcp dep (the
first plain --build hit a cached deps layer; --no-cache forced reinstall). Health 200, FastAPI app
unaffected (the MCP server is a separate process, not mounted on the app).

## Out of scope (W4c next)
- The WRITE server (W4c) — propose_* tools that enqueue into the W4a queue (never direct), the other
  half of the loop. depends on this. finance/projects/journal tools, SSE/HTTP transport, auth.
