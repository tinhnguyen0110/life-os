# Sprint CATALOG-ALL-MOUNTS — list_tools_catalog walks ALL 6 mounts (Cairn #32)

> Created 2026-06-21 by architect (dispatched by team-lead directly while architect did the docs sprint). Backend-only, low-priority-but-real. The self-discovery catalog covered only the shared read+write servers (2 of 6 mounts); #32 makes it walk EVERY mounted server so an agent enumerating its capabilities sees the wiki/finance/reminders tools too.

## Objective
`list_tools_catalog()` is the agent's self-discovery index — but it only enumerated the shared read-server + write-server TOOLS. The wiki pair + the per-domain servers (finance, reminders) were INVISIBLE to it. #32 walks all 6 mounts (mirroring main._MCP_MOUNTS) so the catalog is complete, with a sync-guard so a new mount can't be silently missed.

## Logic
- `_CATALOG_MOUNTS` = the 6 (label, module-path, capability) tuples mirroring main._MCP_MOUNTS.
- `list_tools_catalog()` walks each, LAZY-importing the module for METADATA only (name + docstring; the propose/write fns NEVER invoked, NEVER bound at module top-level → the read-server no-write gate stays pristine).
- counts: KEEP back-compat `read`/`write`/`total` (shared read / shared write / both) + add `byMount` (per-mount breakdown) + `allMounts` (listing length) + an honest `note` that per-mount counts OVERLAP (a domain server reference-imports shared fns → sum(byMount) > distinct).

## HARD GATE (distinguishing)
- catalog lists every mount's signature tools (read/write/wiki-read/wiki-write/finance/reminders).
- **sync-guard with TEETH:** `test_catalog_mounts_in_sync_with_main` asserts _CATALOG_MOUNTS modpaths == main._MCP_MOUNTS modpaths → a new app mount not added FAILS RED.
- byMount counts == live TOOLS counts (not hardcoded); the finance double-listing (under read + finance) asserted as intended.
- **no-write-gate preserved:** nothing write-capable bound at the read-server module level (lazy import inside the fn); test_mcp_read.py AST gate still passes.
- pytest green, mypy clean.

## Baseline
pytest 1829 (post-3780443). Keep 0-failed.

## Assumptions (user-review)
- **list_tools_catalog walks ALL 6 mounts** (read/write/wiki-read/wiki-write/finance/reminders), via _CATALOG_MOUNTS mirroring main._MCP_MOUNTS; counts keep back-compat read/write/total + add byMount/allMounts with an honest overlap note. **How to change:** _CATALOG_MOUNTS (kept in sync by the test-gate).
- per-mount counts OVERLAP by design (reference-imported domain tools); allMounts ≠ distinct total — the honest "what each agent sees per mount" view.

## Notes
- Backend-only; separate commit `feat(sprint-CATALOG-ALL-MOUNTS)`. CATALOG.md hand-synced (now covers wiki/finance/reminders + the missing reminders section).
- The LAST autonomously-dispatchable item. After #32, the board is COMPLETE except the user-gated items (#31 FE user-look + the next-direction gaps surfaced by dogfood).
