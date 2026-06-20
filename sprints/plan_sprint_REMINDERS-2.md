# Sprint REMINDERS-2 — reminders MCP surface (Cairn #28)

> Created 2026-06-21 by architect. LANE 2 (parallel to wiki #19+#26 — different module). Capability decision (A) team-lead-locked. Builds on the FROZEN #27 schema. Unblocks #29(notify)/#30(brief)/#31(FE).

## Objective
The agent needs a reminders MCP surface ("what's on my plate today/this week" + set/tick alarms). Mirror the #27 REST surface to MCP, MCP≡REST.

## Capability decision (A — team-lead-locked, logged to Instruction.md)
Reminders are single-user REVERSIBLE CRUD with NO trust boundary (user CHỐT'd a simple alarm model: set → fires → user ticks). So writes are DIRECT write-through (no proposal gate) — consistent with the post-#25 write-through direction.
- The whole-app **write-server is STRUCTURALLY enqueue-ONLY** (no-mutate AST gate, least-privilege). Reminder direct-writes do NOT go there (would break the gate). 
- So: a per-domain `lifeos-reminders` server (the proven lifeos-finance pattern) holds the write tools.
- **Refinement:** `reminders_list` (read) ALSO goes on the main read-server (read-only, fits the read gate) — so any lifeos-read agent sees "what's on my plate" without a 2nd connection (exactly how finance tools live in both read-server + lifeos-finance).

## Design
1. **`reminders_list` on the main read-server** (read_server.py): reuse `modules.reminders.service.list_reminders`; lean/agent-first (filtered list + counts, filter today/week/undone/all). Read-only → read-gate-clean.
2. **NEW `mcp_servers/reminders_server.py`** (clone lifeos-finance): TOOLS = reminders_list (same read fn) + reminder_create + reminder_tick (DIRECT write-through — service.create/tick, return the real Reminder+id, no proposal gate, MCP≡REST) + build_server/main + `("/mcp/reminders", ...)` mount (inherits stateless/DNS-off).
3. **Capability tests (gate-mirror):** write-server no-mutate AST test STILL green (untouched); lifeos-reminders CAN mutate (the inverse); per-domain is-identity; reminders_list identical via both servers.

## Tasks
- **T1 (backend):** reminders_list on read-server + the reminders_server.py + mount + the capability tests. restart. Backend writes pytest.
- **T2 (tester):** reminders_list via /mcp/read AND /mcp/reminders (same); reminder_create write-through (MCP→GET /reminders/{id} found); reminder_tick; write-server no-mutate still green. Live container.
- **T3 (architect):** review + commit `feat(sprint-REMINDERS-2)` (SEPARATE from wiki lane-1).

## HARD GATE (distinguishing)
- reminders_list via both servers → same result (same fn object; read-agent sees it without a 2nd connect).
- reminder_create → write-through (real id, GET found, MCP≡REST); tick → done_at set.
- write-server no-mutate AST gate STILL green (untouched); lifeos-reminders CAN mutate (gate-mirror).
- per-domain is-identity (reminders_server.TOOLS == the reminders module fns).
- pytest green, mypy clean.

## Baseline
pytest 1741 (post-#27+1A). Keep 0-failed.

## Assumptions (user-review)
- **reminders MCP writes are DIRECT write-through (no proposal gate)** — single-user reversible alarms, no trust boundary (capability decision A). **How to change:** route reminder writes through the propose-queue (option B) if a gate is ever wanted.
- **reminders_list lives on BOTH the read-server (any read-agent) AND lifeos-reminders (the focused write-capable surface)** — like finance tools. **How to change:** the per-domain `lifeos-reminders` server + the read-server tool.

## Notes
- LANE 2, parallel to wiki #19+#26 (different module). Commits SERIAL (separate `feat(sprint-REMINDERS-2)`).
- Clones the per-domain pattern (memory `mcp-per-domain-server-pattern`). Unblocks #29/#30/#31.
