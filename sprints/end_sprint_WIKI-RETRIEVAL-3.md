# end_sprint_WIKI-RETRIEVAL-3 — wiki_context consolidation (Cairn #23)

> Result. LANE B. Consolidated the note-scoped wiki context tools into ONE `wiki_context` + REMOVED the granular wiki_graph/wiki_backlinks from the MCP surface (F1=b — the dogfood "17 tools too many" fix). Kept the #24 byte-identical invariant. Commit `<hash>` `feat(sprint-WIKI-RETRIEVAL-3)`. Status: ✅ all 3 gates pass.

## Objective (met)
Dogfood: "17 wiki MCP tools is too many — an agent navigating a note needs ~5-6, not a tool per edge-type." #23 folds the note-scoped graph + backlinks into ONE `wiki_context(note_id)` (fewer, fatter tools), and demotes the 2 granular tools to REST-only (F1=b). Net −1 MCP tool, ZERO capability lost.

## What shipped
| File | Change |
|---|---|
| `modules/wiki/reader/context.py` (NEW) | `context(note_id, depth=2)` — PURE COMPOSE over `ego_graph` + `backlinks` (no logic dup) → `{found, note_id, graph, backlinks}`; missing note (ego_graph None) → `{found:False, note_id}`. Lives in reader → MCP + REST byte-identical by construction. |
| `modules/wiki/reader/__init__.py` | export `context` (KEEPS ego_graph/backlinks exported — the granular reader fns survive). |
| `modules/wiki/mcp/read_server.py` | REMOVED `wiki_graph` + `wiki_backlinks` (from BOTH the TOOLS map AND build_server's add_tool — the 2 registration points); ADDED `wiki_context` (calls reader.context). MCP wiki-read count 12 → 11. |
| `modules/wiki/router.py` | ADDED `GET /wiki/notes/{id}/context` (reader.context, 404 on missing); KEPT `/wiki/graph` + `/wiki/notes/{id}/backlinks` (REST consumers unaffected — the F1=b guarantee). |
| tests | test_wiki_mcp_read.py (removed the granular-tool parity tests WITH a pointer comment; MIGRATED coverage to wiki_context tests) + test_wiki.py + test_mcp_http.py. |

## F1=(b) + the 5 guards — ALL HELD (team-lead-confirmed live)
- **(i) registrations-only removal:** wiki_graph + wiki_backlinks gone from the MCP TOOLS map + build_server; the reader FUNCTIONS (ego_graph, backlinks) KEPT + still exported. ✓
- **(ii) REST kept:** GET /wiki/graph, /wiki/notes/{id}/backlinks both still 200 (REST consumers unaffected). ✓
- **(iii) internal callers kept:** anything calling reader.ego_graph/backlinks directly (router, any synthesis surface) works off the FUNCTION, untouched. ✓
- **(iv) caller-grep first:** backend grepped — ONLY tests referenced the granular MCP *tools* (no synthesis surface needed them); coverage migrated, not deleted. ✓
- **(v) wiki_context SUPERSETS:** graph byte-identical to old wiki_graph(id)["graph"] (== reader.ego_graph), backlinks byte-identical to old wiki_backlinks(id) (== reader.backlinks) — ZERO capability lost. ✓
- **F2:** global wiki_clusters STAYS separate (vault-wide MOC ≠ note-scoped context). ✓

## Verification (Rule #0 — architect 4-step + team-lead container)
- **architect 4-step (full functions):** context.py = PURE compose (calls ego_graph + backlinks, no own logic); read_server removed BOTH registration points + added wiki_context (calls reader.context); router kept granular REST + added /context (404 on missing); reader.__init__ keeps ego_graph/backlinks exported (guard i). **Test coverage genuinely MIGRATED** (team-lead's specific concern): the removed test_graph_parity/test_backlinks_parity → replaced by test_wiki_context_subpayloads_byte_identical_to_granular (asserts ctx.graph == reader.ego_graph + ctx.backlinks == reader.backlinks, sort_keys-equal — the no-capability-lost proof) + test_wiki_context_respects_depth + test_wiki_context_missing_note_is_found_false + test_wiki_context_registered_and_audits; the tool-list test dropped the 2 names. NOT just deleted.
- **team-lead independent container (Rule#0):** wiki-read MCP count = 11 (was 12, −1, goal MET); wiki_graph + wiki_backlinks GONE from MCP (call → error); wiki_context PRESENT + works + supersets byte-identical; wiki_clusters kept; KEPT REST /wiki/graph + /notes/1/backlinks + /notes/1/context all 200. Full list = [clusters, context, get_note, inbox, list_proposals, overview, proposal_status, recent_ops, search, tree, verify_citations] = 11 clean. 1812 suite green, mypy clean.

## 3 Gates — ALL PASS
- **Gate 1 (API):** REST /wiki/notes/{id}/context == MCP wiki_context byte-identical (both reader.context); KEPT REST endpoints all 200; envelope intact; 404 on missing note. ✅
- **Gate 2 (Function):** wiki_context pure-compose, byte-identical sub-payloads (the no-capability-lost proof), depth threaded, missing-note arm, audit; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; full-function spot-check; architect 4-step (coverage-migrated verified) + team-lead container (count 11); commit format; staged ONLY #23 backend/wiki files — the #31 FE files (held for the user) EXCLUDED (clean directory split); no data/template. ✅

## Assumptions (user-review)
- **wiki_context(note_id) = graph + backlinks in ONE call** (pure compose over ego_graph + backlinks, no logic dup); the granular wiki_graph + wiki_backlinks REMOVED from the MCP surface (F1=b, team-lead-confirmed) but KEPT as REST endpoints + reader functions. **How to change:** reader/context.py + the MCP TOOLS map (re-add the granular tools) / the REST router.
- **net −1 MCP tool, ZERO capability lost** — wiki_context supersets both removed tools byte-identical. **wiki_clusters stays separate** (global vault-wide MOC, not note-scoped).

## Notes
- LANE B; separate commit. The #31 FE files (frontend/*) were in the working tree (held for the user's UI look) — EXCLUDED from this commit (clean directory split: #23=backend/wiki, #31=frontend). 
- DOCS: team-lead handles mcp_servers/CATALOG.md; the wiki mcp README tool list (swap graph/backlinks → context) — included if backend edited it, else a follow-up.
- Pipeline after: #24 (test-gate REST≡MCP across the WHOLE wiki surface — now stable at 11 tools, the right time). #31 still held for the user's UI look (separate, unaffected).
