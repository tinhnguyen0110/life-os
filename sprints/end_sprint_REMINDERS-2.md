# end_sprint_REMINDERS-2 — reminders MCP surface (Cairn #28)

> Result. LANE 2 (parallel to wiki #19+#26). Capability decision (A). Commit `<hash>` `feat(sprint-REMINDERS-2)`. Status: ✅ all 3 gates pass.

## Objective (met)
Reminders MCP surface for the agent ("what's on my plate today/this week" + set/tick alarms), MCP≡REST, mirroring the FROZEN #27 schema.

## What shipped (capability decision A + the read-server refinement)
| File | Change |
|---|---|
| `mcp_servers/read_server.py` | `reminders_list` read tool (reuse `modules.reminders.service.list_reminders`) — so any lifeos-read agent sees "what's on my plate" without a 2nd connection. read-gate-clean (read fn, no mutation import). TOOLS 40→41. |
| `mcp_servers/reminders_server.py` (NEW) | per-domain `lifeos-reminders` server (clones lifeos-finance): TOOLS = `reminders_list` (reference-imported → is-identity with the read-server's) + `reminder_create` + `reminder_tick` (DIRECT write-through — service.create/tick, return the real Reminder+id, NO proposal gate, MCP≡REST). build_server/main mirror finance. |
| `main.py` | +1 `_MCP_MOUNTS` line `("/mcp/reminders", "mcp_servers.reminders_server")` (inherits stateless/DNS-off). |
| tests | test_reminders_mcp_server.py (new) + count bumps (test_mcp_read, test_finance_mcp_shape, test_mcp_http rs.TOOLS 40→41). |

## Capability decision (A — team-lead-locked, logged to Instruction.md)
Reminders are single-user REVERSIBLE CRUD, no trust boundary → DIRECT write-through (no proposal gate). The whole-app write-server is STRUCTURALLY enqueue-ONLY (no-mutate AST gate) → reminder writes do NOT go there (would break it). Instead a per-domain lifeos-reminders server holds the writes. The gate-mirror: write-server CANNOT mutate (enqueue-only, AST-proven); lifeos-reminders CAN (it imports service.create/tick) — the inverse, by design.

## Verification (Rule #0 — 3-way + container)
- **architect 4-step:** read reminders_server.py — reference-imports reminders_list (is-identity), direct write-through (service.create/tick), NO enqueue/proposal, build_server mirrors finance. ✓
- **team-lead independent container:** /mcp/reminders + /mcp/read handshake 200, other 4 mounts unchanged; reminders_list byte-identical across read-server AND reminders-server (is-identity); reminder_create write-through → real id (20), GET found, due_at UTC-normalized (+07:00→19:00:00+00:00 — the #27/1A fix carries through MCP); reminder_tick → done_at set, idempotent; cleaned up; write-server gate INTACT (only the 4 propose_*, no reminder_create leaked). The reminders_list extra `warnings` key is the house MCP convention (REST envelope.warning vs MCP inline warnings, every read tool) — equivalent, NOT drift.
- **suite:** 1763 green.

## 3 Gates — ALL PASS
- **Gate 1 (API):** reminders_list (read), reminder_create/tick (write-through, MCP≡REST); new mount handshake 200; envelope/warnings per house convention. ✅
- **Gate 2 (Function):** is-identity (reminders_list same fn both servers); write-through create/tick; the gate-mirror (write-server no-mutate STILL green + reminders-server CAN mutate); 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; full-function spot-check; architect + team-lead container; commit format. ✅

## Assumptions (user-review)
- **reminders MCP writes are DIRECT write-through (no proposal gate)** — single-user reversible alarms, no trust boundary (capability decision A). **How to change:** route through the propose-queue (option B) if a gate is wanted.
- **reminders_list on BOTH read-server (any read-agent) AND lifeos-reminders** — like finance tools.

## Notes
- LANE 2, parallel to wiki #19+#26 (different module). Separate commit. Clones the per-domain pattern (memory `mcp-per-domain-server-pattern`). Unblocks #29/#30/#31.
- The reminders_list `warnings` key (vs REST envelope.warning) is the established MCP convention — verified NOT a wiki_tree-class drift.
