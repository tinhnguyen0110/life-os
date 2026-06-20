# end_sprint_WIKI-RETRIEVAL-2 — wiki_get modes + ranked wiki_search (Cairn #21 + #22)

> Result. LANE B (grouped #21+#22 — shared wiki reader/router/mcp files). Additive, kept the #24 MCP≡REST byte-identical invariant. Commit `<hash>` `feat(sprint-WIKI-RETRIEVAL-2)`. Status: ✅ all 3 gates pass.

## Objective (met)
Token-cheap, agent-first wiki retrieval: navigate (outline) → drill (section) without reading full bodies; ranked top-K search that shows WHY a result matched. Both kept REST + MCP byte-identical.

## What shipped
| File | Change |
|---|---|
| `modules/wiki/reader/note_view.py` (NEW) | `note_view(note, mode, heading)` — full (bare model_dump, backward-compat) \| outline (ATX heading ToC + meta + per-heading preview, NO body) \| section (only that section's content, heading→next-same-or-higher, `sectionFound` honest-null). The SHARED fn for REST + MCP (#24). |
| `modules/wiki/reader/__init__.py` | export `note_view`. |
| `modules/wiki/store/fts.py` | FTS query +`n.folder AS folder` +`rank AS score` (FTS5 bm25 rank, raw). |
| `modules/wiki/reader/backlinks.py` | `search()` default top-5 (was 30); per-result `{id,title,folder,snippet,score}` (dropped flat `status`, +folder+score — agent-first lean, no body). |
| `modules/wiki/router.py` | REST `/search` +`query` alias (q wins); `/notes/{id}` +`mode`+`heading` via `reader.note_view`. |
| `modules/wiki/mcp/read_server.py` | `wiki_search(q\|query, limit=5)` ranked; `wiki_get_note(note_id, mode, heading)` → full `{found,note}` (backward-compat) / outline\|section `{found, **view}` merge. Same reader fns as REST (#24). |
| tests | test_wiki_mcp_read.py (+95 lines — mode full/outline/section + ranked search + query-alias + byte-identical) + test_wiki.py (search shape). |

## Verification (Rule #0 — architect 4-step + team-lead container)
- **architect 4-step (full functions):** `note_view` full=bare-dict-unchanged (backward-compat, no wrapper), outline=headings+meta+preview no-body, section boundary = heading→next-same-or-higher (correct markdown sectioning) + `sectionFound` named to avoid colliding with the MCP `found` flag; mcp wiki_get_note merges the view for outline/section, keeps `{found,note}` for full; REST `/notes/{id}` + `/search` BOTH route through `reader.note_view` / `reader.search` → byte-identical BY CONSTRUCTION (#24). store/fts.py folder+score additive; search top-5 lean. Confirmed NO #30 reminders/brief content in any staged wiki file (the lane-A `_brief_reminders` in mcp_servers/read_server.py was EXCLUDED — git diff --cached verified).
- **team-lead independent container (Rule#0):** #21 default==full byte-identical (MCP.note==REST data); outline drops body (153<458 chars), has headings+meta+mode+title; #22 ranked top-5 each {id,title,folder,snippet,score}, `query`==`q` byte-identical. Investigated an apparent "REST outline ≠ MCP outline" → confirmed it's the MCP `{found}` existence-flag only: **MCP-minus-`found` == REST data BYTE-IDENTICAL** (the intended missing-note convention, same class as reminders_list `warnings` — NOT the #19 wiki_tree payload-relocation drift). The #24 invariant HOLDS. 1794 suite green (+7), mypy clean.

## 3 Gates — ALL PASS
- **Gate 1 (API):** REST `/wiki/notes/{id}` (mode/heading) + `/wiki/search` (query alias) == their MCP twins byte-identical (payload), via the shared reader fns; envelope intact; honest-null on missing section / empty query (never 500). ✅
- **Gate 2 (Function):** mode full(backward-compat)/outline/section incl. unknown-heading→sectionFound:false; ranked search top-5 +score; query-alias; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; full-function spot-check; architect 4-step + team-lead container; commit format; lane-A #30 (`_brief_reminders` in mcp_servers/read_server.py) EXCLUDED — staged ONLY wiki #21+#22 files, git diff --cached confirms no reminders/brief/template/data leak. ✅

## Assumptions (user-review)
- **wiki_get modes full|outline|section** — full = backward-compat default (bare note, no wrapper); outline/section = token-cheap views; same `note_view` backs REST + MCP (#24). **How to change:** `reader/note_view.py`.
- **wiki_search default top-5 ranked** (was flat-30); +folder +score (raw FTS5 bm25 rank, more-negative=more-relevant), dropped `status`; `query` alias for `q`. **How to change:** `reader.search` default + `backlinks.py:search` fields + `store/fts.py`.

## Notes
- LANE B; separate commit. The lane-A #30 `_brief_reminders` (mcp_servers/read_server.py) is in-flight on the architect/backend side — EXCLUDED here (commit-content-diff-not-just-filenames); it lands in feat(sprint-REMINDERS-4).
- Kept the #24 byte-identical invariant (the #19 wrapper-drift class watched-for; team-lead re-verified payload parity for both modes + search).
- Pipeline after: #30 (lane A, brief surface) → #31 (FE tick UI, completes GAP-4); lane B #23 (consolidate graph⊇backlinks⊇clusters → wiki_context) / #24 (test-gate REST≡MCP).
