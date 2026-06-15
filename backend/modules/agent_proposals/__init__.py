"""modules/agent_proposals — the human review-and-apply surface for agent proposals (MCP-4).

Closes the gated-action loop. The MCP write-server (mcp_servers/write_server.py) lets an
external agent ENQUEUE pending proposals; this module is where a HUMAN reviews them and
either ACCEPTs (→ the proposal is applied to its target module's real service) or REJECTs
(→ status flip, no write). Mounts at ``/agent-proposals`` via the registry (``MODULE`` in
router.py) — auto-discovered, no edit to core/ or main.py.

The actual apply logic lives in ``mcp_servers/proposals_service.py`` (the apply layer the
write-server deliberately lacks — apply is human-triggered, reached only from here).
"""
