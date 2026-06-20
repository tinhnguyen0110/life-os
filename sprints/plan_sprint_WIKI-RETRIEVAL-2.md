# Sprint WIKI-RETRIEVAL-2 — wiki_get modes + ranked wiki_search (Cairn #21 + #22)

> Created 2026-06-21 by architect. LANE B (parallel to reminders lane A). Grouped #21+#22 (both refine wiki RETRIEVAL + touch the SHARED wiki reader/router/mcp files — group to avoid the content-diff commit hazard, like #19+#26). Additive to the just-shipped wiki_tree (#20). Keep the #24 MCP≡REST byte-identical invariant.

## Objective
Make wiki retrieval token-cheap + agent-first so an agent navigates → drills WITHOUT reading full 6KB bodies:
- **#21 wiki_get +mode** — `full` (default, backward-compat) | `outline` (heading ToC + meta, NO body) | `section` (+heading → only that section). outline → spot the chapter → get that section.
- **#22 wiki_search ranked** — top-K (default 5, was flat-30), each `{id,title,folder,snippet,score}` so the agent sees WHY it matched + drills via wiki_get; `query` alias for `q`.

## Logic/Algorithm
### #21 — note_view(note, mode, heading) (NEW reader/note_view.py, shared by REST + MCP)
- **full** (DEFAULT / unknown mode): `note.model_dump()` UNCHANGED — the exact pre-#21 bare dict (backward-compat, no wrapper; existing FE/agent callers unaffected).
- **outline**: `{mode:'outline', title, meta:{kind,status,folder,tags}, headings:[{level,text,line,preview}]}`. ATX headings (`#{1,6} text`) parsed in doc order; preview = first non-blank non-heading line after the heading (None if the section has no body line). NO body.
- **section** (+heading): `{mode:'section', heading, section:{heading,level,content}|null, sectionFound:bool}`. content = from the heading line UP TO the next same-or-higher-level heading (exclusive). Unknown/missing heading → `sectionFound:false` (honest, not a crash). `sectionFound` deliberately named (NOT `found`) to avoid colliding with the MCP note-existence `found` wrapper when merged.
- **#24 invariant:** REST `/wiki/notes/{id}` and MCP `wiki_get_note` BOTH call `reader.note_view(...)` → byte-identical payload by construction. MCP adds only the `{found}` existence-flag (the same missing-note convention every wiki_get MCP tool uses); the PAYLOAD matches REST.

### #22 — ranked search (store/fts.py + reader/backlinks.py:search + REST/MCP)
- FTS query gains `n.folder AS folder` + `rank AS score` (FTS5 bm25 rank; more-negative = more relevant — surfaced RAW so the agent sees relevance).
- `reader.search` default limit 5 (was 30); per-result `{id,title,folder,snippet,score}` (dropped the flat `status`, added folder+score — agent-first lean, NO body).
- `q` OR `query` alias (q wins if both); same `reader.search` backs REST `/wiki/search` + MCP `wiki_search` (#24).

## HARD GATE (distinguishing)
- **#21 backward-compat:** default (no mode) == `mode=full` BYTE-IDENTICAL ({found, note}, MCP.note == REST data) — pre-#21 callers unaffected.
- **#21 outline:** drops body, has headings+meta+mode+title, smaller than full.
- **#21 section:** returns only that section's content; unknown heading → sectionFound:false (honest).
- **#22 search:** ranked top-5, each {id,title,folder,snippet,score}; `query` alias == `q` byte-identical.
- **#24:** REST payload == MCP payload byte-identical (MCP-minus-`found` == REST data) for BOTH wiki_get modes + wiki_search — do NOT re-introduce a payload-relocation drift (the #19 wrapper-bug class).
- pytest green, mypy clean.

## Baseline
pytest 1787 (post-#29/bedd888). Keep 0-failed.

## Assumptions (user-review)
- **wiki_get modes full|outline|section** — full is the backward-compat default (bare note, no wrapper); outline/section are token-cheap views; the SAME `note_view` fn backs REST + MCP (#24). **How to change:** `reader/note_view.py`.
- **wiki_search default top-5 ranked** (was flat-30); per-result +folder +score (FTS5 rank, more-negative=more-relevant), dropped `status`; `query` alias for `q`. **How to change:** `reader.search` default limit + the projected fields in `backlinks.py:search` + `store/fts.py`.
- `score` is the RAW FTS5 bm25 rank (negative; more-negative = more relevant) — surfaced raw, not normalized (agent-first: the agent sees the real signal).

## Notes
- LANE B; separate commit `feat(sprint-WIKI-RETRIEVAL-2)`. Grouped #21+#22 (shared wiki files).
- The lane-A #30 `_brief_reminders` in mcp_servers/read_server.py is in-flight (backend co-mingled it) — EXCLUDED from this commit (commit-content-diff-not-just-filenames). Stage ONLY the wiki #21+#22 files.
- Keeps the #24 byte-identical invariant (the #19 wrapper-drift class watched-for). Pipeline after: #23 (consolidate graph⊇backlinks⊇clusters → wiki_context) / #24 (test-gate REST≡MCP).
