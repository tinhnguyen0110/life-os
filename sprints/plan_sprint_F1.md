# Sprint F1 — Dogfood-audit High-tier fixes · S1 + H1 + P1 · PLAN

> From the post-A1→A5 dogfood + 3-way audit (memory `dogfood-audit-findings-2026-06-15`, all team-lead Rule#0-confirmed).
> 3 tasks parallel: S1 [backend] + P1 [backend] + H1 [frontend]. F2 (minors) after.

## Kickoff — 2026-06-15

### Code read (the 3 fix surfaces, confirmed on disk)
- **S1 (trust boundary):** `router.py:244` `create_proposal(body: ProposalCreateInput)` passes the client-settable
  `body.actor` straight to `proposals_service.create_proposal`. Schema default = `"agent"` (proposals_schema.py:64).
  `_actor_is_agent` (proposals_service.py:68) returns True for `agent*`/`mcp:*`. So a REST `POST /wiki/proposals`
  with NO actor + autonomy ON → `_actor_is_agent`=True → auto-applies, BYPASSING P1. **The boundary keys on a
  client string, not the caller.** Confirmed live in the audit (status=accepted, decidedBy=agent:auto).
- **P1 (perf, latent):** `reader.py` `ego_graph` (line ~318) calls `detect_clusters()` UNCONDITIONALLY every request;
  `detect_clusters` rescans ALL resolved edges per component (O(n²)). A bounded depth-2 ego-graph pays a full-graph
  scan. 48ms@1500 notes → crosses the <1s gate ~6-7k notes. Latent (vault=11 today).
- **H1 (north-star gap):** `decision_journal` has a FROZEN API (GET/POST/PUT/DELETE `/decision-journal` + stats
  brier/calibration/biasFlags) but **0 FE refs** (grep confirms) → user can't reach a real SPEC feature. The FE
  `/journal` screen already has the exact patterns to port: create form (thesis/negation/confidence), close-via-PUT,
  calibration panel (thesis-accuracy, outcome-based).

### Design decisions (logged)
- **S1 fix = router forces the caller identity.** The REST router defaults/forces `actor="human"` (a REST proposal
  IS a human's deliberate draft — it must never auto-apply as agent). ONLY the MCP write-server passes `mcp:writer`
  (it already does — `write_server.py` ACTOR="mcp:writer"). So the autonomy auto-apply path is reachable ONLY by a
  genuine MCP-agent proposal, never a REST one. Minimal + closes the hole at the boundary. (Schema default also
  flipped to "human" as defense-in-depth, but the router-force is the guarantee.)
- **P1 fix = scope cluster-tagging to the ego neighborhood** (don't run full-graph detect_clusters inside ego_graph).
  Behavior-preserving: ego_graph.clusters output IDENTICAL for current cases — the existing cluster tests are the gate.
  (Standalone `GET /wiki/clusters` keeps the full detect_clusters; only ego_graph's per-request call is scoped.)
- **H1 = decision-journal FE screen** consuming the frozen API; **reliability stays API/ops-only** (it's a harness,
  not a user feature — logged as an explicit decision, NOT a gap).

### Final task list (F1)
- **#18 S1 [backend]** — router forces actor=human; only MCP passes mcp:writer; regression: no-actor POST + autonomy ON → stays PENDING.
- **#20 P1 [backend]** — scope ego_graph cluster-tagging to the neighborhood (behavior-identical; cluster tests green = gate).
- **#19 H1 [frontend]** — `/decision-journal` screen (list/create/resolve/stats) + nav entry; port from `/journal`. Reliability ops-only (logged).

## Assumptions (user-review) — finalized in end_sprint_F1.md
- S1: trust boundary keys on the CALLER (REST→human, MCP→mcp:writer), not a client string. Schema default human (defense-in-depth).
- P1: ego_graph scopes cluster detection to the ego neighborhood (behavior-preserving); standalone /wiki/clusters unchanged.
- H1: decision-journal gets a FE screen; reliability stays API/ops-only (harness, not a user feature) — explicit decision.
