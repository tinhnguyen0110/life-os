# Sprint WIKI-RETRIEVAL-1 — wiki_tree folder-meta + note kind/status (Cairn #20)

> Created 2026-06-21 by architect. LANE B (parallel to reminders #29; backend does #29 first). Additive enrichment of the just-shipped wiki_tree (f50ba34) — keep the #24 MCP≡REST byte-identical invariant.

## Objective
Enrich wiki_tree so an agent navigating the vault (like `ls`) understands folders + note kinds WITHOUT reading bodies (token-cheap retrieval). Additive to the existing nested tree; both REST + MCP stay byte-identical.

## Logic (additive)
1. **folder `meta: {desc} | null`** — absent → null (honest-mirror, never fabricate). Storage DECISION (decide-and-log): a light module-local `folder_meta` KV table (folder_path PK, desc) — single-purpose, honest-null; NOT a readme/_folder-note convention (avoids body-parsing + which-note ambiguity). Start with ONLY `desc` + counts (not 6 fields).
2. **note-stub +kind +status** — `{id,title,kind,status}` from the note's EXISTING fields (kind note/moc, status draft/active — read, don't invent). So an agent reads the MOC first.
3. **counts** per folder; NO body; `wiki_tree(folder?, depth?)` (scoped subtree + depth limit; folders nest).

## HARD GATE (distinguishing)
- wiki_tree REST==MCP byte-identical WITH the new fields (the #24 invariant — don't re-introduce a parity drift like the wrapper bug).
- folder without meta → meta:null (honest); with a folder_meta row → meta:{desc}.
- note-stubs carry kind+status (real fields); MOC shows kind=moc.
- depth limits nesting; folder scopes subtree; NO body.
- pytest green, mypy clean.

## Baseline
pytest 1763 (post-f50ba34). Keep 0-failed.

## Assumptions (user-review)
- **folder_meta = a light module-local KV table** (folder_path, desc), honest-null when absent — NOT a readme-note convention. **How to change:** the folder_meta store + the tree reader's meta-join.
- **kind/status read from the note's existing fields** (never fabricated). Tree is body-less (navigation, not content).

## Notes
- LANE B, after #29 (lane A priority). Separate commit `feat(sprint-WIKI-RETRIEVAL-1)`.
- Keeps the #24 byte-identical invariant (just established in #19's wiki_tree fix). The remaining #21(outline)/#22(search)/#23(consolidate)/#24(test-gate) pipeline after — likely group #21+#22 (retrieval refinements, shared reader files).
