# Sprint W4b — MCP READ-only server (wiki) · plan

> External Claude Code plugs into the wiki via MCP and READS it — search, overview, graph,
> backlinks, get-note. ZERO write capability (the read server must have no import path to any
> mutation/enqueue fn — spec L142/L145 "read server has no write capability" = the M4 gate).

## Spec anchors
- M4 L139-146: MCP server over the API · audit every call + correlation_id · **separate READ-ONLY
  and WRITE servers** (least-privilege) · no wildcard scope. Gate: external agent reads via MCP;
  read server has NO write capability.
- L124 (M2 carryover): retrieval tools must be READ-ONLY (an agent reading can't mutate notes).

## Decisions (decide-and-log)

### D-W4b.1 — stdio entrypoint, in-process calls to reader/service-read
`backend/mcp/wiki_read_server.py` is a standalone MCP **stdio** server (Claude Code launches it via
its mcp config: `command:"python", args:["-m","mcp.wiki_read_server"]` or a path). It calls the
EXISTING wiki read fns in-process (same SQLite via store/db) — `reader.search/backlinks/ego_graph/
recent_ops`, `service.get_note`, the overview/inbox aggregators. **Why stdio:** simplest for a local
single-user Claude Code integration, no port/network exposure. **How to change:** add an SSE/HTTP
transport later if a remote agent needs it.

### D-W4b.2 — least-privilege is STRUCTURAL, not a flag
`wiki_read_server.py` imports ONLY read functions. It must NOT import `proposals_service` (enqueue),
`service.create_note/update_note/merge_notes/delete_note`, or anything that writes. The M4 gate is
proven by GREP: no write/enqueue symbol importable from the read server's module graph. **Why:** a
confused-deputy / tool-poisoning attack can't escalate a read tool to a write. **How to change:**
never — the WRITE server (W4c) is a separate module; keep capability split by module boundary.

### D-W4b.3 — audit every MCP call via the existing wiki_mcp_audit
Each tool call appends to `wiki_mcp_audit` (reuse `proposals_store.append_audit`) with tool name,
params, actor (the connecting agent, default "mcp:reader"), correlation_id (per server session).
Reads ARE audited (spec "every call"). **Why:** immutable audit / forensics. Importing
`append_audit` does NOT violate D-W4b.2 — it's an append to an audit log, not a vault mutation
(audit is write-only-to-its-own-table, never touches notes). **How to change:** retention later.

### D-W4b.4 — tools = the read endpoints, 1:1
wiki_search(q, limit?) · wiki_overview() · wiki_inbox() · wiki_graph(note_id, depth?) ·
wiki_get_note(note_id) · wiki_backlinks(note_id) · wiki_recent_ops(limit?). Each returns the same
data the REST endpoint returns (the agent gets the integer-ID citable note: "note 47"). **Why:**
the agent reads exactly what the app exposes; integer IDs are the citation key (D1). 

## Deps
- **ADD `mcp` to backend/requirements.txt** (the official Python MCP SDK / FastMCP). This is a deps
  change → the container needs `docker compose up -d --build backend` (memory: --build only for deps).
  team-lead will rebuild after backend confirms the requirement pin.

## Scope
IN: `backend/mcp/__init__.py` + `backend/mcp/wiki_read_server.py` (stdio MCP server, 7 read tools,
audit each, no write imports) · a `mcp.json` / README snippet showing how to register it in Claude
Code · unit/integration test that each tool returns the same shape as the REST reader + a
GREP-based test asserting the read server module imports no write symbol.
OUT: the WRITE server (W4c) · finance/projects/journal tools · SSE/HTTP transport · auth (single-user).

## Gates
- Each MCP tool returns the same data as its REST endpoint (parity test).
- **Read server has NO write capability** — grep/import test: `wiki_read_server` (and its transitive
  imports) expose no create/update/delete/merge/enqueue symbol. (The M4 gate L145.)
- Every tool call lands one `wiki_mcp_audit` row (actor=mcp:reader, correlation_id set).
- Server starts (stdio handshake) without error; mcp added to requirements; container rebuilds clean.
- pytest green (count ≥ baseline + new), mypy clean, no dup-name.
