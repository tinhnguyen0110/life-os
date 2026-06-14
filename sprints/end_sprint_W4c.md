# Sprint W4c — MCP WRITE server (wiki) · END — CLOSES THE M4 LOOP

**Status:** ✅ implemented + verified live in-container (Rule#0). The M4 loop closes end-to-end.
**Commit:** (pending W4c commit).

## What shipped — the loop closes
External Claude Code PROPOSES wiki mutations via MCP; every write tool ENQUEUES a proposal into the
W4a queue (pending), NEVER touches the vault directly, NEVER accepts. The human ratifies in P1/REST.
M4 wiki MCP is now functionally complete: **read (W4b) → propose (W4c) → human-accept (P1) → vault.**

### Files
- NEW `modules/wiki/mcp/write_server.py` — 6 propose_* tools, TOOLS registry, build_server()
  (FastMCP), main() stdio. Same nested location as read_server (shadow-safe). No future-annotations.
- NEW `tests/test_wiki_mcp_write.py` — 14 tests.
- MOD `modules/wiki/mcp/README.md` — write-server registration (separate `lifeos-wiki-write` entry) +
  6 propose tools + "agent proposes, you dispose".

### 6 propose tools (each ENQUEUES, rationale REQUIRED, actor=mcp:writer, correlationId per session)
propose_note→note_create · propose_edit→note_edit · propose_link→link_add · propose_unlink→link_remove
· propose_merge→merge · propose_moc→moc.

## Verified LIVE in CONTAINER (team-lead, Rule#0 — the whole chain exercised)
- pytest 913 (+60 = 32 W4a + 14 W4b + 14 W4c), 14 W4c def==collected no dup, mypy clean.
- **M4 GATE (enqueue-only, no mutate/accept)** — proven by my own AST analysis: write_server imports
  the BARE `create_proposal` (enqueue) and NONE of create_note/update_note/delete_note/merge_notes/
  refine/accept_proposal/reject_proposal/batch_accept, and does NOT import the proposals_service
  module (which would expose accept). The agent can ONLY propose. 2 gate tests pass.
- **THE M4 LOOP-CLOSE (live):** agent `propose_note` via MCP stdio → proposal #29 pending
  (actor=mcp:writer) → appears in REST queue, **vault stays 0 (nothing landed)** → human accepts via
  POST /wiki/proposals/29/accept → note lands (id, title "MCP Loop Proof", author=mcp:writer) →
  vault 0→1. The agent proposed; the vault was unchanged until the HUMAN accepted. The whole pillar.
- rationale-required: empty rationale → rejected, NO proposal created (count unchanged).
- stdio handshake clean (serverInfo life-os-wiki-write, 6 tools). audit row(s) per propose (mcp:writer).

## Assumptions (user-review)
1. **Double-audit per propose (intentional, ACCEPTED):** each propose_* writes TWO wiki_mcp_audit rows
   (same correlationId, both actor=mcp:writer): `tool=propose_<x>` (write-server _audit — MCP-tool-name
   granularity) + `tool=propose` (create_proposal's own W4a audit). Kept both: more forensic +
   satisfies the tool-name requirement (create_proposal alone logs only generic `propose`). —
   to change: drop the write-server _audit (loses tool-name granularity). DECIDED: keep both.
2. **Agent-proposed notes land author=mcp:writer** (consistent with W4a actor-provenance). DECIDED.

## M4 status
✅ W4a proposal/approval queue · ✅ W4b MCP read server · ✅ W4c MCP write server · ✅ P1 ratify screen.
M4 wiki MCP COMPLETE. OUT-of-scope-this-build (per spec): finance/projects/journal MCP tools,
SSE/HTTP transport, auth. Next milestone = M3 Sync (multi-device CRDT over the op-log) — user-prioritized.
