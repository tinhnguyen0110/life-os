# Life OS — MCP Configuration Guide

> How to connect an external Claude (Claude Code, a spawned agent, an MCP client) to life-os
> over MCP. This machine runs the servers directly, so the config below is concrete for THIS
> host — no placeholder paths.
>
> Canonical, always-current tool list = the MCP tool **`list_tools_catalog()`** on the
> read-server (derived from the live registries, never drifts). A human snapshot lives in
> [`backend/mcp_servers/CATALOG.md`](../backend/mcp_servers/CATALOG.md).

---

## 1. The four servers (two read/write pairs, least-privilege)

life-os exposes MCP as **four separate stdio processes** — read and write are split into
distinct processes with distinct capability sets (structural least-privilege, proven by
`test_mcp_read.py` / `test_mcp_write.py`, not by a flag). There are two pairs: a **whole-app**
pair and a deeper **wiki-only** pair.

| Server | Module | Tools | Capability |
|---|---|---|---|
| **whole-app read** | `mcp_servers.read_server` | **40** | reads ALL modules — writes nothing |
| **whole-app write** | `mcp_servers.write_server` | **10** | `propose_*` only — ENQUEUE pending, applies nothing |
| **wiki read** | `modules.wiki.mcp.read_server` | **9** | deep vault read (inbox/graph/clusters/verify_citations) |
| **wiki write** | `modules.wiki.mcp.write_server` | **6** | `propose_*` wiki only — ENQUEUE pending |

**Totals: whole-app = 50 tools (40 read + 10 write).** The wiki pair (9 + 6) is a *deeper,
vault-only* surface — it has tools the whole-app read does not (`wiki_inbox`, `wiki_graph`,
`wiki_clusters`, `wiki_recent_ops`, `wiki_verify_citations`). The whole-app read carries the
common wiki reads (`wiki_search`/`wiki_get`/`wiki_overview`/`wiki_backlinks`) plus everything
else (finance, market, projects, claude_usage, journals, brief, macro, news, …).

### Which pair to register

- **Want the whole life-os surface** (the usual case — finance + market + projects + wiki +
  brief + …): register the **whole-app pair** (`read_server` + `write_server`).
- **Want only the knowledge vault, with the deep wiki tools**: register the **wiki pair**.
- **Want both surfaces**: register all four (the wiki reads overlap, that's fine — distinct
  server names, the client lists both).

---

## 2. The capability boundary (the supervision contract)

This is WHY there are two processes per pair, never one. Do not collapse a read+write into a
single server — it breaks the boundary the tests guard.

```
external Claude  ── read_*   ─→  reads only, writes NOTHING
                 ── propose_* ─→  ENQUEUE a pending row (agent_proposals / wiki_proposals)
                                  ↓
                 (HUMAN reviews + ACCEPTS)  ←── apply is HUMAN-ONLY, never an MCP tool
```

- **read** — reads only — no mutation symbol is even imported (grep + AST asserted).
- **write** — `propose_*` ENQUEUEs a `status="pending"` proposal and returns it. NOTHING lands
  in any module. Every `propose_*` REQUIRES a non-empty `rationale` (the agent explains WHY) —
  empty rationale → `RationaleRequired`, rejected.
- **apply** — HUMAN-ONLY via `POST /agent-proposals/{id}/accept` (whole-app) or the P1 wiki
  queue screen / `POST /wiki/proposals/{id}` (wiki). The agent has **no** apply/accept handle.
- **feedback** — the agent READS its verdict via `check_proposal_status` / `list_my_proposals`
  / `proposal_stats` (whole-app) or `wiki_proposal_status` / `wiki_list_proposals` (wiki) —
  read-only, cannot ratify its own proposal.
- **neutrality** — analysis tools (macro/market/insights/life_brief) return NEUTRAL data — no
  buy/sell/should/rebalance advice. The agent does the reasoning.

> Two queues: whole-app `propose_*` → `agent_proposals`; wiki `propose_*` → `wiki_proposals`.
> Each has its OWN read-back tools (above). They are separate tables — a wiki propose is not
> visible to `check_proposal_status` and vice-versa.

---

## 3. Transport

All four servers run over **stdio** today — the MCP client spawns `python -m <module>` as a
child process per session and talks over stdin/stdout. This is the right fit when the client
runs **on this same machine** (Claude Code local, a locally-spawned agent), which is the
current setup.

> Remote / multi-client access (**streamable-http**) is a planned follow-on — the installed SDK
> (`mcp 1.27.2`) supports `transport="streamable-http"`, the servers don't expose an HTTP
> entrypoint yet. When that lands, this doc gets an HTTP section; until then, stdio only.

---

## 4. Register in the MCP client

stdio servers are registered in the client's MCP config — for Claude Code that's
`~/.claude.json` under `mcpServers`, or a project-local `.mcp.json`. Each server is one entry:
a `command`, its `args`, and the `cwd` it runs from.

### Run requirements (per server)

- `command`: `python` (the interpreter that has the `mcp` SDK installed — see §5).
- `args`: `["-m", "<module path>"]` — the module is invoked as a package (`-m`), NOT a file
  path, because each server resolves sibling imports as a package.
- `cwd`: **`backend/`** (the package root). On this host:
  `/home/watercry/Disk_C/Data/Tinhdev/life-os/backend`.
  Inside the prod container the cwd is `/app`.

### The four entries (this host)

```json
{
  "mcpServers": {
    "lifeos-read": {
      "command": "python",
      "args": ["-m", "mcp_servers.read_server"],
      "cwd": "/home/watercry/Disk_C/Data/Tinhdev/life-os/backend"
    },
    "lifeos-write": {
      "command": "python",
      "args": ["-m", "mcp_servers.write_server"],
      "cwd": "/home/watercry/Disk_C/Data/Tinhdev/life-os/backend"
    },
    "lifeos-wiki-read": {
      "command": "python",
      "args": ["-m", "modules.wiki.mcp.read_server"],
      "cwd": "/home/watercry/Disk_C/Data/Tinhdev/life-os/backend"
    },
    "lifeos-wiki-write": {
      "command": "python",
      "args": ["-m", "modules.wiki.mcp.write_server"],
      "cwd": "/home/watercry/Disk_C/Data/Tinhdev/life-os/backend"
    }
  }
}
```

Register only the pair(s) you need (§1 "Which pair to register"). Each entry is independent —
omit the wiki pair if you only want the whole-app surface.

### Or via the Claude Code CLI

```bash
cd /home/watercry/Disk_C/Data/Tinhdev/life-os/backend
claude mcp add lifeos-read       -- python -m mcp_servers.read_server
claude mcp add lifeos-write      -- python -m mcp_servers.write_server
claude mcp add lifeos-wiki-read  -- python -m modules.wiki.mcp.read_server
claude mcp add lifeos-wiki-write -- python -m modules.wiki.mcp.write_server
```

---

## 5. The interpreter (which `python`)

The `mcp` SDK and the app deps must be importable by whatever `python` the config uses. On this
host the project venv has them:

- venv: `/tmp/los-venv/bin/python` (the test/dev venv — `mcp` installed).
- or the container's `/app` env (`mcp` installed via `pyproject.toml`).

If `python` on `PATH` is not that interpreter, point `command` at the absolute path, e.g.
`"command": "/tmp/los-venv/bin/python"`. Sanity check a server boots:

```bash
cd /home/watercry/Disk_C/Data/Tinhdev/life-os/backend
/tmp/los-venv/bin/python -c "import mcp_servers.read_server as s; print(len(s.TOOLS), 'read tools')"
/tmp/los-venv/bin/python -c "import mcp_servers.write_server as s; print(len(s.TOOLS), 'write tools')"
```

> `FastMCP` introspects real parameter annotations at registration, so the servers deliberately
> do NOT use `from __future__ import annotations` (stringized annotations crash `issubclass`).
> Don't add it.

---

## 6. Verify the connection

After registering, in the client:

- the read tools resolve and return correct-shaped data — start with `life_brief` (one call →
  the whole life snapshot) or `list_tools_catalog()` (the live tool list).
- the `propose_*` tools each enqueue a PENDING proposal — confirm via `proposal_stats` /
  `list_my_proposals` (whole-app) or `wiki_list_proposals` (wiki). Nothing lands in a module
  until you ACCEPT it at the REST/queue surface (§2).

Dev/test harness (no client needed) — call any tool directly:

```bash
python /tmp/mcp_call.py <tool_name> '<json-args>'
# loads read_server.TOOLS + write_server.TOOLS and invokes the tool
```
