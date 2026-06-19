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
| **whole-app write** | `mcp_servers.write_server` | **4** | `propose_*` only — ENQUEUE pending, applies nothing |
| **wiki read** | `modules.wiki.mcp.read_server` | **11** | ALL vault reads (search/get/overview/backlinks/inbox/graph/clusters/verify_citations) + wiki proposal read-back |
| **wiki write** | `modules.wiki.mcp.write_server` | **6** | `propose_*` wiki only — ENQUEUE pending |

**Totals: whole-app = 44 tools (40 read + 4 write); wiki pair = 17 (11 read + 6 write); 61 total.**
MCP-DEDUP #70: the wiki MCP tools now live ONLY on the wiki pair (the canonical surface) — the
whole-app servers no longer carry duplicate wiki tools. The whole-app read carries everything
NON-wiki (finance, market, projects, claude_usage, journals, brief, macro, news, …); the wiki
pair carries ALL vault reads + the wiki proposal read-back + the wiki `propose_*` writes. The
whole-app write `propose_note` was renamed **`propose_quicknote`** (the lightweight NOTES module)
to remove the clash with the wiki pair's `propose_note`.

> **Dogfood harness caveat:** `/tmp/mcp_call.py` loads ONLY the SHARED `read_server.TOOLS` +
> `write_server.TOOLS`, so after MCP-DEDUP #70 it no longer lists wiki tools — this is EXPECTED.
> The real `.mcp.json` connects all 4 servers; wiki tools live on `lifeos-wiki-read` /
> `lifeos-wiki-write`. (Extending `/tmp/mcp_call.py` to load the 2 wiki servers is a noted
> follow-up, not done here.)

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

Two transports, both live. Pick by **where the client runs**.

### 3a. stdio (local client, one process per session)

The MCP client spawns `python -m <module>` as a child process per session and talks over
stdin/stdout. This is the right fit when the client runs **on this same machine** (Claude Code
local, a locally-spawned agent). Registered in the client's MCP config — see §4.

### 3b. streamable-http (remote / multi-client) — Sprint MCP-HTTP

The same 4 servers are ALSO mounted as streamable-http ASGI sub-apps on the existing FastAPI
app (`:8686`), so a **remote or multi-client** MCP client can reach them over HTTP without
spawning a local process. This is an ADDITIONAL transport — stdio (§3a) still works unchanged.

The 4 servers stay 4 SEPARATE FastMCP instances (the read/write capability split is preserved
at the transport layer — no cross-import), each mounted at a distinct path:

| Mount path (in main.py) | Server | **Client URL** |
|---|---|---|
| `/mcp/read`       | whole-app read  | `http://<host>:8686/mcp/read/mcp` |
| `/mcp/write`      | whole-app write | `http://<host>:8686/mcp/write/mcp` |
| `/mcp/wiki-read`  | wiki read       | `http://<host>:8686/mcp/wiki-read/mcp` |
| `/mcp/wiki-write` | wiki write      | `http://<host>:8686/mcp/wiki-write/mcp` |

> **The URL has `/mcp` TWICE.** A FastMCP streamable-http app serves its tool endpoint at its
> own internal `streamable_http_path` (default `/mcp`); mounted at `/mcp/read`, the real client
> URL is therefore `/mcp/read/mcp`. This is SDK behaviour, not a typo — point the client at the
> full `<mount>/mcp`.

**No auth (single-user, no-auth, LAN — north-star).** The HTTP mounts are open on localhost /
the LAN, exactly like the REST API. FastMCP's DNS-rebinding protection is turned **OFF**
(`TransportSecuritySettings(enable_dns_rebinding_protection=False)`, set in `main.py` for the
HTTP build only) — with it ON (the SDK default) any non-`localhost` `Host` header gets
`421 Misdirected Request`, which would reject every remote client this transport exists to
serve. stdio is unaffected (it never builds with that setting → `None` → SDK default).

#### Verify a mount over HTTP (curl)

The MCP streamable-http endpoint **requires** `Accept: application/json, text/event-stream`
on the `initialize` POST. A JSON-only `Accept` returns **`406 Not Acceptable`** against a
perfectly healthy server — so if a curl 406s, fix the header, don't assume the mount is broken.

```bash
# Correct: returns 200 + an `mcp-session-id` response header.
curl -i -X POST http://127.0.0.1:8686/mcp/read/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
# → HTTP/1.1 200 OK   ...   mcp-session-id: <hex>

# Wrong header (JSON only) → 406 — the SDK needs text/event-stream advertised too:
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8686/mcp/read/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
# → 406
```

Swap `/mcp/read/mcp` for `/mcp/write/mcp`, `/mcp/wiki-read/mcp`, or `/mcp/wiki-write/mcp` to
check the other three. (`main.py` is not in uvicorn's `--reload-dir` allowlist, so after
editing it, `docker compose restart backend` before testing the live container — a hot-reload
won't pick up the mounts.)

---

## 4. Register in the MCP client

stdio servers are registered in the client's MCP config — for Claude Code that's
`~/.claude.json` under `mcpServers`, or a project-local `.mcp.json`. Each server is one entry:
a `command`, its `args`, and the `cwd` it runs from.

### Run requirements (per server)

- `command`: an **ABSOLUTE path** to the interpreter that has the `mcp` SDK + app deps
  installed — **NOT the bare string `"python"`**. The MCP client spawns the server with its
  own `PATH`, which often does NOT resolve `python` to the env you expect → the server fails to
  start (or starts on an interpreter missing deps). On this host:
  `/home/watercry/anaconda3/envs/tinhnv/bin/python` (verified: imports all 4 servers + answers
  the stdio `initialize` handshake). See §5.
- `args`: `["-m", "<module path>"]` — the module is invoked as a package (`-m`), NOT a file
  path, because each server resolves sibling imports as a package.
- `cwd`: **`backend/`** (the package root). On this host:
  `/home/watercry/Disk_C/Data/Tinhdev/life-os/backend`.
  Inside the prod container the cwd is `/app`.
- `env.PYTHONPATH`: **set this to the same `backend/` path** — do NOT rely on `cwd` alone.
  Some MCP clients (observed) do NOT honor the `cwd` field when spawning the server, so
  `python -m mcp_servers.read_server` fails with `ModuleNotFoundError: No module named
  'mcp_servers'`. Setting `PYTHONPATH=backend/` makes the import work regardless of the spawn
  directory. This is the fix for the all-four-`✘ failed` symptom when a binary server in the
  same config connects fine.

### The four entries (this host)

```json
{
  "mcpServers": {
    "lifeos-read": {
      "type": "stdio",
      "command": "/home/watercry/anaconda3/envs/tinhnv/bin/python",
      "args": ["-m", "mcp_servers.read_server"],
      "cwd": "/home/watercry/Disk_C/Data/Tinhdev/life-os/backend",
      "env": { "PYTHONPATH": "/home/watercry/Disk_C/Data/Tinhdev/life-os/backend" }
    },
    "lifeos-write": {
      "type": "stdio",
      "command": "/home/watercry/anaconda3/envs/tinhnv/bin/python",
      "args": ["-m", "mcp_servers.write_server"],
      "cwd": "/home/watercry/Disk_C/Data/Tinhdev/life-os/backend",
      "env": { "PYTHONPATH": "/home/watercry/Disk_C/Data/Tinhdev/life-os/backend" }
    },
    "lifeos-wiki-read": {
      "type": "stdio",
      "command": "/home/watercry/anaconda3/envs/tinhnv/bin/python",
      "args": ["-m", "modules.wiki.mcp.read_server"],
      "cwd": "/home/watercry/Disk_C/Data/Tinhdev/life-os/backend",
      "env": { "PYTHONPATH": "/home/watercry/Disk_C/Data/Tinhdev/life-os/backend" }
    },
    "lifeos-wiki-write": {
      "type": "stdio",
      "command": "/home/watercry/anaconda3/envs/tinhnv/bin/python",
      "args": ["-m", "modules.wiki.mcp.write_server"],
      "cwd": "/home/watercry/Disk_C/Data/Tinhdev/life-os/backend",
      "env": { "PYTHONPATH": "/home/watercry/Disk_C/Data/Tinhdev/life-os/backend" }
    }
  }
}
```

> ⚠️ Three things make stdio connect reliably (the all-four-`✘ failed` fix):
> 1. **ABSOLUTE interpreter path**, not bare `"python"` — the client spawns with its own PATH,
>    which does NOT inherit a conda-activated shell's `python`. See §5.
> 2. **`env.PYTHONPATH`** = the `backend/` path — some clients do NOT honor `cwd`, so `-m`
>    fails with `ModuleNotFoundError: No module named 'mcp_servers'`. PYTHONPATH fixes it
>    regardless of spawn dir. (Keep `cwd` too — harmless, helps clients that DO honor it.)
> 3. **`"type": "stdio"`** — explicit, matches a known-good binary entry in the same file.
>
> **Simpler alternative: use streamable-http (§3b)** — `{"type":"http","url":"http://localhost:8686/mcp/read/mcp"}`
> needs no interpreter / cwd / PYTHONPATH at all (the running container serves it). Prefer it
> when the container is up.

Register only the pair(s) you need (§1 "Which pair to register"). Each entry is independent —
omit the wiki pair if you only want the whole-app surface.

### Or via the Claude Code CLI

```bash
cd /home/watercry/Disk_C/Data/Tinhdev/life-os/backend
PY=/home/watercry/anaconda3/envs/tinhnv/bin/python   # absolute — NOT bare "python"
claude mcp add lifeos-read       -- $PY -m mcp_servers.read_server
claude mcp add lifeos-write      -- $PY -m mcp_servers.write_server
claude mcp add lifeos-wiki-read  -- $PY -m modules.wiki.mcp.read_server
claude mcp add lifeos-wiki-write -- $PY -m modules.wiki.mcp.write_server
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
