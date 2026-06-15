# Sprint NG2 — wiki propose-tools discoverability on the whole-app write-server

> Consumer-agent round-3 (memory `consumer-agent-round3-gaps-2026-06-15`), team-lead-recharacterized.
> Backend-only. The write-loop e2e is NOT a gap (already tested — team-lead verified); NG2 is.

## Kickoff — 2026-06-15 (architect)

### Verified the gap + the two-server architecture (confirms team-lead's recharacterization)
- **Whole-app write-server** (`mcp_servers/write_server.py`) TOOLS = `propose_decision`, `propose_note` (→ the lightweight `notes` module, NOT wiki — its docstring says "Distinct from the WIKI note proposal"), `propose_journal`, `propose_project_update` (4 tools). Enqueues via `mcp_servers.proposals_store.enqueue` → the **whole-app proposal queue**.
- **Wiki write-server** (`modules/wiki/mcp/write_server.py`) = 6 tools (propose_note/edit/link/unlink/merge/moc), its own TOOLS dict, a **SEPARATE stdio server**. Enqueues via the **wiki's `proposals_service.create_proposal`** → the **WIKI proposal queue** (the wiki P1 ratify screen).
- **THE GAP:** an agent connected to the whole-app write-server sees `propose_note`→notes and **CANNOT discover/reach the wiki's 6 propose tools** — the wiki write surface exists but isn't in the catalog the agent uses. "add this to my wiki" → the agent hits propose_note (wrong module) or can't find the wiki path.
- **Two genuinely separate proposal SYSTEMS** (whole-app queue vs wiki queue + ratify surfaces) — confirmed. This is NOT just a naming issue; they route to different ratify queues.

### 🔑 THE DECISION (architect call — decide-and-log) → Option A (surface, namespaced, route correctly)
**Surface the wiki's 6 propose tools in the whole-app write-server catalog, NAMESPACED (`wiki_propose_note`/`wiki_propose_edit`/`wiki_propose_link`/`wiki_propose_unlink`/`wiki_propose_merge`/`wiki_propose_moc`), each DELEGATING to the wiki write-server's existing propose fns** (which enqueue to the wiki queue). So:
- ONE discoverable surface — the agent on the whole-app write-server sees both note systems, clearly namespaced (`propose_note` = lightweight notes; `wiki_propose_note` = the wiki vault). No need to know there are two servers.
- **Correct routing preserved:** `wiki_propose_*` delegate to the wiki write-server's fns → land in the WIKI queue → the wiki P1 ratify screen (the right place). `propose_note` stays → whole-app queue. We do NOT merge the queues (they're intentionally separate ratify surfaces).
- **Capability gate INTACT:** the whole-app write-server imports the wiki write-server's propose fns (which are themselves enqueue-only — `create_proposal`, no mutation/accept). The existing no-mutate AST/namespace gate must still pass with the wiki propose fns added (they import no apply/mutate symbol). Add any wiki write-mutation fn to the forbidden set if needed.
- Catalog auto-includes the 6 new tools (derive-based, like the read-server) → regen CATALOG.md.

Why A over B (disambiguate-only): an agent shouldn't have to know about a second write-server's existence to propose a wiki note. Discoverability = the tool is IN the catalog the agent reads. Namespacing makes the two note-systems unambiguous. This is the honest, complete fix.

### Final task list (single backend lane)
- **NG2 [backend]** — surface the wiki's 6 propose tools in `mcp_servers/write_server.py` as `wiki_propose_*`, each delegating to `modules/wiki/mcp/write_server.py`'s fns (wiki-queue routing). Capability gate stays 0-mutate-leak (the wiki propose fns are enqueue-only). Behavior tests (each wiki_propose_* enqueues to the WIKI queue, pending, no apply). CATALOG regen. The whole-app + wiki e2e stay green.

### NOT a gap (team-lead-verified — don't build): the propose→accept→row-lands write-loop e2e — ALREADY tested (`test_mcp_e2e.py` test_full_agent_loop_decision/_reject_path/test_full_loop_journal, 5 green). The runtime queue being empty (no real proposals yet) ≠ untested.

## Assumptions (user-review)
- The wiki's 6 propose tools surface on the whole-app write-server namespaced `wiki_propose_*`, delegating to the wiki write-server (wiki-queue routing). The two proposal queues stay separate (whole-app vs wiki ratify); discoverability is the fix, not a merge.
- Capability gate intact (wiki propose fns are enqueue-only; no apply/mutate leak; AST+namespace gate green).
