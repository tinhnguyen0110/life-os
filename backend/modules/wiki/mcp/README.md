# life-os Wiki MCP servers

External Claude Code plugs into the life-os wiki over **MCP** (Model Context
Protocol) to READ the vault and (via the separate write server) PROPOSE writes.

Two servers, **hard-separated by capability** (the M4 security gate, spec L142/L145):

| Server | Module | Capability |
|---|---|---|
| **Read** (W4b) | `modules/wiki/mcp/read_server.py` | search / overview / inbox / graph / get-note / backlinks / recent-ops. **ZERO write capability** — no import path to any mutation/enqueue fn (proven by `test_wiki_mcp_read.py`). |
| **Write** (W4c, next) | `modules/wiki/mcp/write_server.py` | `propose_*` tools that enqueue into the W4a proposal queue. Never a direct vault write. |

> **Naming:** the package is `modules/wiki/mcp`, NOT `mcp` — a top-level `mcp/` dir at `/app`
> (on `sys.path[0]`) would *shadow* the installed `mcp` SDK and break
> `from mcp.server.fastmcp import FastMCP`.

## Read server tools (7)

| Tool | Args | Returns |
|---|---|---|
| `wiki_search` | `q`, `limit?` | `{results: [...]}` ranked FTS hits |
| `wiki_overview` | — | `{overview: {stats, inbox, orphans, recentActivity, proposalCount}, warning?}` |
| `wiki_inbox` | — | fleeting notes awaiting triage |
| `wiki_graph` | `note_id`, `depth?` | `{found, graph: {center, nodes, edges, clusters}}` |
| `wiki_get_note` | `note_id` | `{found, note: {...}}` — the citable note (integer ID) |
| `wiki_backlinks` | `note_id` | `{linked, unlinked, outbound}` |
| `wiki_recent_ops` | `limit?` | `{ops: [...]}` op-log activity |

Every call appends a `wiki_mcp_audit` row (`actor=mcp:reader`, one `correlation_id`
per server session).

## Register in Claude Code

The read server runs over **stdio**. Add to your Claude Code MCP config
(`~/.claude.json` `mcpServers`, or project `.mcp.json`):

```json
{
  "mcpServers": {
    "lifeos-wiki-read": {
      "command": "python",
      "args": ["-m", "modules.wiki.mcp.read_server"],
      "cwd": "/path/to/life-os/backend"
    }
  }
}
```

(In the container the cwd is `/app`; `mcp` is installed via `pyproject.toml`.)

Then in Claude Code: the 7 `wiki_*` tools become available — the agent reads your
vault, cites notes by integer ID ("note 47"), and never writes directly.

## Run / smoke-test manually

```bash
cd backend
python -m modules.wiki.mcp.read_server        # serves stdio; Ctrl-D to exit

# one-shot handshake + list tools:
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | python -m modules.wiki.mcp.read_server
```
