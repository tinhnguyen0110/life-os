# plan_sprint_WIKI-WORKDIR — wiki as a dev work-dir (Cairn #127 → build, AFTER review/greenlight)

> Design: `DESIGN_WIKI-WORKDIR.md`. This is the build breakdown for review. BE-first → FE. Each task gets a full §3.3b dispatch at dispatch-time (kickoff first). NOT dispatched until team-lead + user greenlight the design.

## Tasks
| # | Task | Lane | Dep |
|---|---|---|---|
| W1 | Folder lifecycle (BE) — create/delete/rename-move + the empty-folder anchor model | be | — |
| W2 | File ops (BE) — strict .md/.txt import + move-note + rename-note | be | (parallel W1 if disjoint files; else after W1) |
| W3 | WikiExplorer ops menu (FE) — new-folder/import/rename/move/delete | fe | W1+W2 freeze |

## W1 (BE) — folder lifecycle + empty-folder model
- **POST /wiki/folders** `{path, desc?}` → create an (empty) folder = INSERT a `wiki_folder_meta` row (the anchor, per the §3 decision); 422 on a bad/duplicate path; honest. The folder now appears in /tree even with 0 notes.
- **`folder_tree` UNION** — extend `reader/tree.py` to seed folder nodes from `all_folder_meta()` keys ∪ the note-prefixes (today it only reads prefixes). An empty folder (meta-only) → an honest node (counts:0, meta:{desc}|null). The load-bearing change.
- **DELETE /wiki/folders/{path}** → SCOPED (#72): soft-delete (recommend, #94 tombstone) every note whose folder == path or starts with `path/`, + remove the folder_meta row. NEVER a blanket. FE confirms. Return {deleted:[ids], folder}.
- **PUT /wiki/folders/{path}/move** `{to}` → rename/move = re-prefix every note under `path` → `to` (scoped bulk `folder` rewrite) + move the folder_meta row (path→to). Fail-soft per note + a warning on partial. 422 if `to` collides.
- Verify: create empty → appears in /tree (counts:0); delete → notes gone (scoped, soft) + meta gone + other folders untouched; move → notes re-prefixed + meta moved; mypy --no-incremental; FORWARD+REVERSE 0-failed. FREEZE the folder-op shapes for W3.
- Decide-and-log: empty-folder = folder_meta anchor (not .keep); folder-delete = soft (recoverable). → ## Assumptions.

## W2 (BE) — file ops
- **Strict .md/.txt import** — VERIFY `import_one` rejects non-.md/.txt (it does today → agent-error row); ADD a test asserting a .pdf/.docx/.png filename → INVALID_INPUT, NO note. Tighten if any gap.
- **Move note between folders** — VERIFY `PUT /wiki/notes/{id}` already accepts a `folder` field (the store comment says "a move updates it"). If yes → "move" is a thin endpoint/UI over it (small); if no → add the folder-set to the update. 
- **Rename note** — VERIFY PUT /notes/{id} updates title → rename is thin.
- (W2 is likely SMALL — mostly verify-existing + a strict-import test + thin move/rename. If PUT /notes/{id} already does folder+title, W2 may fold into W3's FE wiring + 1 BE test. Decide at kickoff.)
- Verify: .pdf import → rejected (no note); move note A→B → its folder field == B + it leaves A's tree node + joins B's; rename → title updated; suite fwd+reverse; mypy.

## W3 (FE) — WikiExplorer ops menu
- Extend WikiExplorer (#108) with an ops menu: **new-folder** (→ POST /folders), **import** (.md/.txt file picker → POST /import; reject other types client-side too + show the BE agent-error honestly), **rename** (folder/note), **move** (folder/note — to another folder), **delete** (folder/note — 🔴 in-page confirm, #72, NOT window.confirm).
- Empty folders render (the W1 union → the tree shows them; the FE shows an empty folder node).
- Mirror the W1/W2 frozen shapes in lib/types + lib/api.
- Verify: tsc + vitest + Chrome (create folder → appears; import .md → note in folder; import .pdf → honest reject; rename/move/delete with confirm; empty folder shows; dark-mode; console clean).

## Notes
- BE-first (W1 the folder model + tree union is the foundation; W2 file ops; both freeze before W3 FE). W1+W2 may parallel if disjoint files (W1 = folder_meta/tree/a folders router; W2 = import/notes — likely disjoint → parallel-able); confirm at kickoff. W3 after both freeze.
- Reuse-not-rebuild: import (#93), soft-delete (#94), tree (#20), folder_meta (#20), WikiExplorer (#108) all EXIST — W1–W3 ADD the missing ops + the empty-folder anchor, they don't rebuild.
- The empty-folder anchor (folder_meta row) is the one real design decision — everything else is wiring missing ops onto existing surfaces.
