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
| `wiki_get_note` | `note_id` | `{found, note: {...}}` — the citable note (integer ID) |
| `wiki_context` | `note_id`, `depth?` | `{found, note_id, graph: {center, nodes, edges, clusters}, backlinks: {linked, unlinked, outbound}}` — a note's full neighborhood (graph + backlinks) in ONE call. SUPERSEDES the removed `wiki_graph` + `wiki_backlinks` (#23, F1=b). REST mirror: `GET /wiki/notes/{id}/context`. |
| `wiki_recent_ops` | `limit?` | `{ops: [...]}` op-log activity |

Every call appends a `wiki_mcp_audit` row (`actor=mcp:reader`, one `correlation_id`
per server session).

## Register in Claude Code

The read server runs over **stdio**. Add to your Claude Code MCP config
(`~/.claude.json` `mcpServers`, or project `.mcp.json`):

Both servers run over **stdio**, registered SEPARATELY (least-privilege — read and
write are distinct processes with distinct capability sets). Add to your Claude Code
MCP config (`~/.claude.json` `mcpServers`, or project `.mcp.json`):

```json
{
  "mcpServers": {
    "lifeos-wiki-read": {
      "command": "python",
      "args": ["-m", "modules.wiki.mcp.read_server"],
      "cwd": "/path/to/life-os/backend"
    },
    "lifeos-wiki-write": {
      "command": "python",
      "args": ["-m", "modules.wiki.mcp.write_server"],
      "cwd": "/path/to/life-os/backend"
    }
  }
}
```

(In the container the cwd is `/app`; `mcp` is installed via `pyproject.toml`.)

Then in Claude Code:
- the 9 `wiki_*` read tools — the agent reads your vault, cites notes by integer ID
  ("note 47"), never writes directly. (search / overview / inbox / graph / get_note /
  backlinks / recent_ops / clusters / **verify_citations**.)
- the 6 `propose_*` write tools (`propose_note` / `propose_edit` / `propose_link` /
  `propose_unlink` / `propose_merge` / `propose_moc`) — each ENQUEUES a PENDING
  proposal into the review queue (`GET /wiki/proposals`); **nothing lands in the
  vault until you ACCEPT it in the P1 queue screen.** Every propose requires a
  `rationale` (the agent must explain WHY). The agent proposes; you dispose.

## Citation contract (W6 A1b — the anti-fabrication gate)

When the agent answers a wiki query, it cites sources as `{claim, noteId, span}`.
**Before presenting that answer, the agent is expected to call `wiki_verify_citations`**
(or `POST /wiki/citations/verify`) with its citations. The service deterministically
checks each one and returns a per-claim status — a fabricated citation cannot pass:

| status | meaning |
|---|---|
| `verified` | the note exists AND the cited `span` literally occurs in its title+body |
| `rejected` | `note_not_found` (no such note) OR `span_not_in_note` (the span is NOT in the note — fabricated/hallucinated) |
| `ungrounded` | the claim has no `noteId` (asserted with no citation) |
| `weakly_grounded` | cites a real note but gives no `span` (names a source without quoting it) |

A `verified` result for a citation that pointed at a *merged-away* note id includes
`resolvedNoteId` (the live target — the citation survived the merge). Span match is
whitespace-normalized + case-sensitive substring. The agent should drop/flag any
claim that isn't `verified` before showing it to the user — that is what makes
"grounded in your notes" a code guarantee, not a prompt hope.

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
