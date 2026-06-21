# Sprint DAILY-TRACING-P2 — MCP tracing_overview + tracing_log (Cairn #65 Phase 2)

> Created 2026-06-21 by architect (designed ∥ while #65-P1 pushes). #65 Phase 2 of 4. The agent surface for the tracing module (P1 built the BE). HOLD dispatch until #65-P1 commits (sequential). backend EDITS; architect commits (§3).

## Context
P1 built modules/tracing/ (store + derivations + REST). P2 = the MCP agent surface: an agent can READ "what did I do today / my streaks" (tracing_overview) + LOG a session ("ran 5km" → tracing_log). Mirrors the reminders_server per-domain pattern (read fn reference-imported = is-identity anti-dup + write tool direct write-through).

## Scope
IN: read_server.py (add `tracing_overview` to the shared read surface) + a new `mcp_servers/tracing_server.py` (per-domain) + main.py _MCP_MOUNTS (1 line) + tests + CATALOG.md.
OUT: P3 FE, P4 brief. NO change to the tracing module's service/derivations (P1, frozen). NO new derivation.

## Logic/Algorithm (reuse P1's service fns — zero new logic)
1. **read_server.py:** add `tracing_overview()` → `_jsonable(reader.get_overview())` wrapped in the read-server's envelope (mirror how other read tools wrap a reader fn). This is the SHARED agent read surface. Shared-read count +1 (→ update the 3 count consumers + CATALOG, the recurring count-gotcha — grep `== <N>` multi-line-aware).
2. **mcp_servers/tracing_server.py** (clone reminders_server):
   - `tracing_overview` = reference-import from read_server (is-identity, anti-dup spine).
   - `tracing_log(activity_id, val, dur_min=None, note=None)` = DIRECT write-through: `service.log_session(activity_id, LogInput(...))` → return the updated ActivityView (so the agent reads back the new today/streak). Unknown activity_id → honest {found:False} (like reminder_tick) OR the agent_error NOT_FOUND (match the REST router's choice — check P1's router; reminders uses found:False for tick, agent_error for the REST). Use the per-domain convention: write-through returns the entity; missing → found:False (the MCP existence-contract, not an error).
   - TOOLS = {tracing_overview (ref-import), tracing_log}.
   - build_server/main mirror + the _MCP_MOUNTS line in main.py (inherits stateless_http + DNS-off, per the per-domain-server pattern).

## REST≡MCP parity
tracing_overview (MCP) == GET /tracing (REST) byte-identical (#24 — both call reader.get_overview). tracing_log write-through == POST /tracing/{id}/log.

## HARD GATE (distinguishing)
- tracing_overview (MCP) → the SAME payload as GET /tracing (byte-identical, #24).
- tracing_log("run", val=5) → returns the updated ActivityView (today.val reflects); a 2nd log SAME day → accumulates (the write-through round-trip: log → overview reflects).
- unknown activity_id → honest found:False (not a crash).
- count consumers updated (shared-read +1 everywhere; no stray old count).
- pytest 0-failed, mypy clean. Verify LIVE HTTP (curl /mcp/tracing/mcp tools/call — the import-cache lesson: HTTP not harness).

## Baseline
pytest = post-P1 count (1994). Keep 0-failed.

## Test ownership split
backend: tracing_overview byte-identical to REST; tracing_log write-through (log → overview reflects + accumulates); unknown→found:False; the count-consumer update. tester: live MCP curl on /mcp/tracing/mcp.

## Assumptions (user-review)
- MCP tracing_overview (read, ref-imported is-identity) + tracing_log (write-through, returns ActivityView, missing→found:False) on a per-domain tracing_server (clone of reminders_server). REST≡MCP. **How to change:** the tracing_server TOOLS.

## Notes
- #65 Phase 2 (P1 done). Per-domain MCP pattern (the mcp-per-domain-server precedent — clone reminders_server, reference-import the read fn for is-identity anti-dup). The count-gotcha: shared-read +1 → update ALL count asserts in the same commit (multi-line grep). backend EDITS; architect commits fix(sprint-DAILY-TRACING-P2). HOLD until P1 commits. Verify LIVE HTTP.
