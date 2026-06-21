# Sprint WIKI-SUGGEST-LINK — auto-suggest links on wiki write (Cairn #34)

> Created 2026-06-21 by architect. Parallel lane to #33 (different module — wiki vs alerts; no collision). Additive, agent-first, no fork → dispatch directly. Pipelines behind #33 (backend = 1 implementer; #33 is priority).

## Objective
Post-#25 write-through, an agent writes a note but may not link it → the graph fragments. #34: on a wiki write-through, FTS the new note's content → return `suggestedLinks: [{id, title, relevance}]` top 3-5 so the agent (or the user) can add `[[...]]` and keep the graph connected. Agent-first, deterministic (no AI — FTS relevance).

## Logic/Algorithm
- On a wiki note WRITE (the write-through path post-#25 — create/edit that lands a note), AFTER the note is persisted: run the existing FTS (`reader.search` / `store.fts_search`) over the new note's CONTENT (or title+content) → top matches, EXCLUDING the note itself.
- Map to `suggestedLinks: [{id, title, relevance}]` (relevance = the FTS5 rank/score, raw — the #22 precedent; more-relevant first), top 3-5.
- EXCLUDE notes already linked from this note (don't suggest an existing `[[id]]`) — only NEW link candidates.
- Return it on the write response (the write-through result gains `suggestedLinks`), AND/OR a read tool `wiki_suggest_links(note_id)` if the agent wants it on demand. (decide-and-log: attach to the write-through response is the primary surface — the agent sees suggestions right after writing; a standalone tool is a nice-to-have, include if cheap.)
- Honest-empty: no FTS matches → `suggestedLinks: []`.

## Scope
IN: the FTS-based suggestion on write-through + the `suggestedLinks` shape (+ optional `wiki_suggest_links(note_id)` tool). Reuse the existing FTS reader (no new index). Tests.
OUT: auto-APPLYING the links (suggest only — the agent/user decides); any AI; changing the FTS index.

## HARD GATE (distinguishing)
- Write a note whose content matches an existing note → `suggestedLinks` includes that note (id/title/relevance), top 3-5, EXCLUDING self + already-linked.
- Write a note with content matching NOTHING → `suggestedLinks: []` (honest-empty).
- An already-linked target is NOT re-suggested (the distinguishing: a note that links [[X]] + matches X in FTS → X excluded from suggestions).
- relevance = the FTS rank (deterministic, no AI). REST≡MCP byte-identical if exposed as a tool (#24 gate covers it).
- pytest green, mypy clean.

## Baseline
pytest 1832 (post-877b24e; #33 may bump it — rebaseline at start). Keep 0-failed.

## Assumptions (user-review)
- **wiki write-through returns suggestedLinks** (FTS top 3-5 {id,title,relevance}, self + already-linked excluded, honest-empty) so the agent can link + keep the graph connected. Deterministic FTS, NO AI; suggest-only (never auto-applies). **How to change:** the suggest step on the write-through path + the top-N constant.

## Notes
- Parallel to #33 (wiki module vs alerts module — no collision); pipelines behind #33 (backend 1 implementer). Dispatch directly (additive, agent-first, no fork). Separate commit `feat(sprint-WIKI-SUGGEST-LINK)`.
- If exposed as a tool, the #24 REST≡MCP gate auto-covers it (add the pair to the gate's map).
