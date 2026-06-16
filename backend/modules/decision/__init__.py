"""modules/decision — the DECISION TOWER (FINANCE-ASSISTANT Phase 2, #54).

Turns the P1 data substrate into "how hard can I bet right now". Three layers, one shared
confidence math:

  compute_q(inputs) → q = freshness × coverage × agreement   (the ONE q-engine; nothing
                                                              else reimplements it)
  macro_cycle   → the Investment-Clock RL state (phase + q_cycle)
  decision_weight → W = ∏ qᵢ (pure product, NO inter-layer clamp) + binding_constraint

NEUTRAL by contract: every output is DATA + q numbers — no advice verb (should/buy/sell/
rebalance). The agent reads the tower and decides; the tower never tells it what to do.

Auto-discovered by core.registry (adding this folder IS the wiring — core/main.py is NOT
edited). REST at /decision; MCP read wrappers in mcp_servers.read_server.
"""
