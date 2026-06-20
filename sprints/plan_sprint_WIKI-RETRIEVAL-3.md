# Sprint WIKI-RETRIEVAL-3 — wiki_context consolidation (Cairn #23) [+ #24 test-gate after]

> Created 2026-06-21 by architect. LANE B (parallel to #31 FE — different surface, no collision). Contract-ish (consolidating MCP tools) → ONE FORK flagged to team-lead below. Keep the #24 MCP≡REST byte-identical invariant. #24 (the REST≡MCP test-gate) runs AFTER #23 once the wiki surface is stable.

## Objective
The dogfood finding: "17 wiki tools is too many — an agent navigating a note needs ~5-6, not a tool per edge-type." Consolidate the NOTE-SCOPED context tools into one `wiki_context(note_id)` so an agent gets a note's full neighborhood in ONE call instead of 3 (wiki_graph + wiki_backlinks [+ the note's clusters]).

## Current surface (the 3 note-context tools)
- `wiki_graph(note_id, depth)` → `{found, graph:{center, nodes, edges, clusters}}` — ego-graph (1-2 hop) AROUND a note. ALREADY includes the note's local clusters.
- `wiki_backlinks(note_id)` → `{linked, unlinked, outbound}` — inbound/outbound edges of a note.
- `wiki_clusters()` → `{clusters}` — GLOBAL (NO note_id) — vault-wide MOC candidates. **Different concern (not note-scoped).**

## Design — `wiki_context(note_id, depth=2)`
ONE call returns a note's full context:
```
{found: bool, note_id: int,
 graph: {center, nodes, edges, clusters},   # from reader.ego_graph (the neighborhood)
 backlinks: {linked, unlinked, outbound}}   # from reader.backlinks (the edges)
```
- Missing note → `{found: False, note_id}` (the wiki missing-note convention).
- Reuses `reader.ego_graph` + `reader.backlinks` UNCHANGED (no logic dup — `wiki_context` is a composing wrapper). The sub-payloads are byte-identical to what wiki_graph.graph / wiki_backlinks return today.
- A matching REST `GET /wiki/notes/{id}/context` returns the SAME composed dict (`data`) → MCP≡REST byte-identical (#24).

## ⚠️ FORK (team-lead heads-up — consolidating tools is a contract call)
**F1 — do the old tools STAY or get REMOVED from the MCP surface?**
- (a) **KEEP wiki_graph + wiki_backlinks AS-IS, ADD wiki_context** — net +1 tool (the opposite of the dogfood goal of FEWER tools), but zero breakage; the agent just prefers the 1-call.
- (b) **REMOVE wiki_graph + wiki_backlinks from the MCP read-server, keep ONLY wiki_context** — net −1 tool (advances the "fewer tools" goal); the composed payload still exposes both sub-shapes; REST keeps its granular endpoints (REST consumers unaffected). The dogfood goal is FEWER MCP tools, so (b) serves it. **MY RECOMMENDATION: (b)** — remove the 2 granular MCP tools, keep wiki_context (the note-context 1-call) + wiki_clusters (the global one). Net tool count drops; the agent gets the consolidated call; REST stays granular.
- (c) keep all 3 + add context = +1, worst for the goal.

**F2 — does the GLOBAL wiki_clusters fold in?** NO (my call, decide-and-log): wiki_clusters has no note_id — it's vault-wide MOC discovery, a different use than "context of THIS note." Folding a global into a note-scoped call is wrong. Keep wiki_clusters separate. (Surface in case team-lead disagrees.)

## HARD GATE (distinguishing)
- `wiki_context(id)` = `{found, note_id, graph, backlinks}`; `graph` byte-identical to old `wiki_graph(id).graph`; `backlinks` byte-identical to old `wiki_backlinks(id)`.
- Missing note → `{found:False, note_id}` (no crash).
- REST `GET /wiki/notes/{id}/context` == MCP `wiki_context` byte-identical (#24).
- If fork (b): wiki_graph + wiki_backlinks REMOVED from the MCP read-server tool list (grep the TOOLS map — absent); REST endpoints for graph/backlinks STILL present (REST unaffected); the MCP tool count dropped by the net amount; no other tool/test references the removed MCP tools.
- pytest green, mypy clean.

## Baseline
pytest 1806 (post-fa39630). Keep 0-failed.

## Assumptions (user-review)
- **wiki_context(note_id) = graph + backlinks in one call** (the note's full neighborhood); reuses ego_graph + backlinks unchanged (composing wrapper, no logic dup). **How to change:** the wiki_context fn + the REST /context endpoint.
- **wiki_clusters stays SEPARATE** (global MOC discovery, not note-scoped) — not folded into wiki_context.
- **[PENDING team-lead F1]** keep-vs-remove the granular wiki_graph/wiki_backlinks MCP tools (recommend REMOVE for the fewer-tools dogfood goal; REST keeps them).

## Notes
- LANE B; separate commit `feat(sprint-WIKI-RETRIEVAL-3)`. Parallel to #31 FE (different surface).
- #24 (test-gate REST≡MCP byte-identical across the WHOLE wiki surface) runs AFTER #23 — it gates the stable surface, so it should come last in the wiki track.
- Keep the #24 byte-identical invariant for the new wiki_context (graph/backlinks sub-payloads == the granular tools / REST).
