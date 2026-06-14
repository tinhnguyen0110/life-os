# Sprint W-Explorer — Obsidian-style wiki file explorer + read/edit polish · PLAN

> User BUILD (Task #23): wiki should feel like Obsidian — folder-tree browse pane, click→read+edit markdown,
> "dễ tìm dễ đọc". **Mandate = QUALITY + CORRECTNESS, not speed/minimal-change. No patchwork.** (User's words.)

## Kickoff — 2026-06-15

### Code read (the surfaces, confirmed on disk)
- **Note schema** (`schema.py`): fields id/title/aliases/status/noteType/trustTier/author/tags/content/created/updated/contentHash. `folder` is a clean ADDITIVE field — exactly the `captureSource`/`trustTier` pattern (frontmatter field + a `wiki_notes` cache column).
- **store.py** = 752 LOC (the A5-deferred split). The folder change = 1 new column (via the existing `_migrate` ALTER pattern) + 1 tree query. **Small additive, not a restructure.**
- **service.py `_render`/`_parse`/`_commit_note`** — frontmatter round-trips all authored fields; folder slots in like captureSource. `move = change the field`, the .md write path is the SAME `_commit_note` (no special rewrite).
- **FE wiki**: routes vault/[id]/inbox/graph/moc/proposals/sync — **NO `layout.tsx`** (each route is standalone). The 2-pane explorer needs a NEW `app/wiki/layout.tsx`.
- **WikiEditor** (65 LOC) = plain `<textarea>` + a preview toggle via **WikiLinkRenderer** (135 LOC, hand-rolled minimal markdown: ONLY **bold** + paragraphs + `[[id|title]]` wikilinks — NO headings/lists/code/quotes). No markdown dep in package.json.

### Spec alignment
Spec line 84 `notes(id, PATH, title, ...)` — the original data model HAD a path field. team-lead's `folder` frontmatter field REALIZES that intent (deferred at M1). Virtual path, not physical folders → preserves D1 (flat `47.md`, integer-id citation = the anti-hallucination pillar) + rename/move-no-rewrite.

### 🔑 DECISION 1 — store.py split: KEEP DEFERRED (right-sized, not refactor-for-its-own-sake)
The folder change touches store.py, so this is the natural moment to ASK. **My call: do NOT split now.** Reasons:
- The folder addition is genuinely SMALL + CLEAN: 1 column (ALTER via `_migrate`) + 1 tree-aggregate query (`notes_for_tree()` returning `{id,title,folder}`) + threading `folder` through upsert. It does NOT restructure store.py — it's the same additive pattern as captureSource (which didn't trigger a split either).
- The A5 trip-wire was ">1000 LOC OR a real cohesion pain." 752 + ~25 LOC ≈ 777, still < 1000. No cohesion pain — the tree query sits cleanly in the existing search/aggregate concern.
- **Quality ≠ maximal change.** The user said don't AVOID refactor for being heavy — but also quality means RIGHT-SIZED. Splitting a load-bearing 752-LOC file (imported by service/reader/proposals/sync/both MCP) as a side-effect of adding one column is risk without proportional value. The split stays a clean standalone task for when the trip-wire actually trips.
- **I'll flag this to team-lead explicitly** — if team-lead/user wants the split bundled anyway, it's a separate parallel task, not entangled with the folder feature (so the folder feature's tests aren't gated on a 752-LOC restructure).

### 🔑 DECISION 2 — WikiEditor markdown render: ADD a light dep (quality > zero-deps HERE, team-lead-sanctioned)
The hand-rolled WikiLinkRenderer does ONLY bold+paragraphs+wikilinks. For an Obsidian-feel READ experience (the user's "dễ đọc"), that's too thin — no headings/lists/code/quotes/tables. team-lead explicitly sanctioned "quality over zero-deps here, still single-user-sane (no heavy editor framework)."
- **Proposal: `react-markdown` + `remark-gfm`** (light, well-maintained, NOT an editor framework — just a renderer) for the PREVIEW/read pane, with a **custom component/remark plugin that preserves `[[id|title]]` wikilink → clickable `/wiki/[id]`** (the existing WikiLinkRenderer logic becomes a react-markdown custom renderer, NOT thrown away). The EDIT surface stays a textarea (no CodeMirror/Lexical — that IS the heavy framework we avoid). So: textarea to write, proper markdown render to read.
- Flag to team-lead: confirm the dep (react-markdown+remark-gfm) is acceptable. If team-lead prefers extending the hand-rolled renderer (headings/lists/code) instead of a dep, that's viable but more code to maintain — I lean the dep (it's the quality call + standard).

### 🔑 DECISION 3 — explorer pane LEFT (Obsidian convention; user said "phải"/right) — FLAG for veto
The user said "bên phải" (right). Obsidian's file tree is LEFT (the universal convention). team-lead defaulted LEFT as correct/familiar. **My call: ship LEFT, log it in §Assumptions as a user-vetoable choice** (it's a CSS flip if the user insists on right). Flag in the dispatch.

### Final task list (WEXP)
- **WEXP-BE [backend]** — `folder` field (schema additive + cache column via `_migrate` + render/parse round-trip) + `GET /wiki/tree` (build virtual folder-tree from all notes' folder fields) + folder settable via PUT (move = field change, NO .md rewrite). Migration-safe (existing notes folder="" → root).
- **WEXP-FE [frontend]** — `app/wiki/layout.tsx` (2-pane: explorer-LEFT | content-outlet, across all wiki routes) + the explorer tree (collapsible folders, click file → open `/wiki/[id]`, move-note UX) + WikiEditor markdown-render polish (react-markdown + remark-gfm + wikilink-preserving renderer).

## Assumptions (user-review) — finalized in end_sprint
- Folder = virtual `folder` frontmatter field (NOT physical folders) — preserves flat `47.md` + integer-id citation + move-no-rewrite. (Spec line 84 path-field realized.)
- store.py split KEPT DEFERRED — the folder addition is small+clean, under the >1000-LOC trip-wire; splitting now = risk without value.
- WikiEditor read-render uses react-markdown+remark-gfm (light dep, quality>zero-deps per user mandate) preserving `[[id|title]]`; edit stays a textarea (no heavy editor framework).
- Explorer pane LEFT (Obsidian convention; user said right — vetoable CSS flip).
