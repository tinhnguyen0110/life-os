# Sprint MCP-DEDUP — consolidate wiki MCP (canonical = standalone) (Task #70)

Wiki MCP tools are double-implemented: embedded `wiki_*` in the SHARED `mcp_servers/read_server.py` + `write_server.py`, AND the standalone `modules/wiki/mcp/` (W4b, fuller, canonical). Direction A: remove wiki from the shared servers; port the 2 proposals-status reads to the standalone; rename the NOTES `propose_note` → `propose_quicknote` to kill the name clash. HARD: lose NO tool (port before delete), preserve each behavior + the audit trail. Backend (MCP server code).

## Kickoff — 2026-06-19 (§3.3a — BOTH impls inventoried tool-by-tool, the DIFF pinned)

### Architecture (confirmed): ALL 4 servers already mounted (main.py `_MCP_MOUNTS`)
- `/mcp/read` = `mcp_servers.read_server` (shared — has embedded wiki) · `/mcp/write` = `mcp_servers.write_server` (shared — has embedded wiki) · `/mcp/wiki-read` = `modules.wiki.mcp.read_server` (CANONICAL) · `/mcp/wiki-write` = `modules.wiki.mcp.write_server` (CANONICAL).
- **So the embedded `wiki_*` in the SHARED servers is pure DUPLICATION — the standalone wiki-read/wiki-write are already live + connected.** Removing the embedded copies loses NO connectivity (the canonical mount serves them).

### INVENTORY + DIFF (the port-before-delete map)

**SHARED read_server.py — embedded wiki tools (to REMOVE):**
| embedded tool | standalone equivalent | action |
|---|---|---|
| `wiki_search` | `wiki_search` ✅ | delete (dupe) |
| `wiki_get` | `wiki_get_note` ✅ (name differs) | delete (dupe; canonical name = wiki_get_note) |
| `wiki_overview` | `wiki_overview` ✅ | delete (dupe) |
| `wiki_backlinks` | `wiki_backlinks` ✅ | delete (dupe) |
| **`wiki_proposal_status`** | **❌ NOT in standalone** | **PORT → standalone read_server, THEN delete** |
| **`wiki_list_proposals`** | **❌ NOT in standalone** | **PORT → standalone read_server, THEN delete** |

**SHARED write_server.py — embedded wiki tools (to REMOVE):**
- `wiki_propose_note/edit/link/unlink/merge/moc` — thin DELEGATORS that already forward to `modules.wiki.mcp.write_server.propose_*`. The standalone HAS them (as `propose_*`). → delete the delegators + the 6 imports.
- `propose_note(title, rationale, body, ...)` → `module="notes"` — **THIS is the NOTES-module quicknote, NOT a wiki note. RENAME → `propose_quicknote`** (the ambiguity: same name as the standalone wiki `propose_note`). Standalone wiki `propose_note(title, content, rationale, tags)` KEEPS its name (it's the canonical wiki propose).

**STANDALONE canonical (modules/wiki/mcp/) — unchanged + 2 ported in:**
- read (9): wiki_search, wiki_overview, wiki_inbox, wiki_graph, wiki_get_note, wiki_backlinks, wiki_recent_ops, wiki_clusters, wiki_verify_citations **+ wiki_proposal_status, wiki_list_proposals (PORTED IN)**.
- write (6): propose_note, propose_edit, propose_link, propose_unlink, propose_merge, propose_moc.

### The 2 tools to PORT (the only genuine port-before-delete)
- `wiki_proposal_status(proposal_id)` + `wiki_list_proposals(status, limit)` — read the `wiki_proposals` queue via `proposals_service.get_proposal` / `list_proposals` / `count_by_status` (all exist, READ-ONLY, L141/145/149). Port verbatim to `modules/wiki/mcp/read_server.py` (they belong there — they read wiki proposals). No audit needed (reads).

### The `propose_note` rename (the ambiguity)
- TWO `propose_note`s today: (1) SHARED write_server `propose_note` → notes module (a quicknote) — the test callers `test_mcp_e2e`/`test_write_loop_e2e`/`test_agent_proposals_apply` use THIS; (2) standalone wiki `propose_note` → wiki proposal.
- **RENAME (1) → `propose_quicknote`** (it's a notes-quicknote). Update its TOOLS-registry key + every caller (the ~6 test call-sites: ws.propose_note → ws.propose_quicknote). The wiki `propose_note` (standalone) is untouched.

### Audit trail (PRESERVED by the canonical path)
- Standalone write_server `_audit` → `proposals_store.append_audit` (fail-soft add-on, memory `fail-closed-write-fail-soft-addon`) on every propose. The deleted shared `wiki_propose_*` were thin delegators to these SAME standalone fns → the audit was always the standalone's. Removing the delegators removes nothing from the audit path. The ported proposals-status tools are READ-only (no audit).

## Scope
- IN: (a) PORT wiki_proposal_status + wiki_list_proposals → standalone read_server (+ the proposals_service imports there); (b) DELETE the embedded wiki tools + imports from the shared read_server + write_server (the 4 read dupes + the 6 write delegators + 6 imports); (c) RENAME shared `propose_note`(notes) → `propose_quicknote` + all callers; (d) update the TOOLS registries + the tests that referenced removed/renamed tools.
- OUT: NO change to the standalone wiki tools' BEHAVIOR (port verbatim) · NO change to the audit trail · NO change to .mcp.json mounts (the 4 stay) · NO change to the non-wiki shared tools (finance/market/etc) · NO new server.

## HARD ACCEPTANCE
- **NO tool lost:** after the change, the canonical surface = every tool that existed before (the 9+2 read, the 6 write) — assert each is callable on the standalone server. A removed-without-ported tool = FAIL.
- **proposals-status ported + identical behavior:** wiki_proposal_status / wiki_list_proposals on the STANDALONE return the same shape as the old embedded ones (same proposals_service calls).
- **propose_note disambiguated:** shared `propose_quicknote` (notes) callable; standalone wiki `propose_note` callable; no name collision; all renamed callers updated (tests green).
- **audit trail intact:** a wiki propose still writes an audit row (the standalone path unchanged) — behavior-test the audit row lands.
- **agent surface is CLEANER:** the shared read/write servers no longer expose `wiki_*` (the agent reads wiki via the canonical wiki-read/wiki-write); distinct names (propose_quicknote vs wiki propose_note). team-lead (the consumer) gets a deduped, unambiguous surface.
- pytest green incl the MCP e2e + the wiki tests; 0 errors; mypy clean.

## Locks (team-lead, 2026-06-19 — approved, hướng A)
- **before/after tool-count list IS the gate:** total callable wiki tools (across the 4 servers) AFTER == BEFORE. Enumerate both. wiki_get → deleted (canonical = wiki_get_note; team-lead's consumer uses wiki_get_note).
- **`main.py` is NOT in `--reload-dir`** → after editing the server files, `docker compose restart backend` BEFORE any live verify (else live hits stale code — the canonical-stack gotcha). Tester curls /mcp/wiki-read/mcp + /mcp/wiki-write/mcp post-restart.
- Update `docs/MCP-CONFIG.md` (new tool counts) + document .mcp.json keeps 4 servers (no wiring change).
- propose_quicknote keeps field `body` + module=notes/kind=note_create byte-identical (rename only).

## Risks / seams
- **Port-before-delete ORDER:** port wiki_proposal_status + wiki_list_proposals to the standalone FIRST (+ test they work there), THEN delete the embedded ones. If deleted first, the 2 tools vanish until ported (a window with a lost tool). Same-commit is fine but the DIFF must show the port present.
- **The `wiki_get` → `wiki_get_note` name:** the embedded `wiki_get` is a dupe of the standalone `wiki_get_note` (same fn, different name). Deleting `wiki_get` is safe — the canonical name is `wiki_get_note`. If any consumer hard-codes `wiki_get`, it must switch to `wiki_get_note` (grep the harness/tests).
- **propose_note callers:** ~6 test call-sites use the NOTES propose_note → all must rename to propose_quicknote. Grep ALL (tests + any agent harness) — a missed caller = a broken test or a 404 tool.
- **The shared write_server's 6 wiki imports** (`from modules.wiki.mcp.write_server import propose_note as _wiki_propose_note` etc.) must be removed with the delegators (else dead imports).
- This is a DEDUP refactor: the win is a cleaner, unambiguous agent surface with ZERO tool loss + the audit preserved. The standalone was always canonical; we're removing the shared server's redundant mirror.
