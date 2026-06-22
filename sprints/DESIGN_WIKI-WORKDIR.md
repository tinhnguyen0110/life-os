# DESIGN — Wiki as a dev WORK-DIR (Cairn #127, architect deliverable for review)

> User-CHỐT: the wiki should operate like a dev WORK-DIR but restricted to **.md/.txt files + folders**. Ops: add-folder · import-file (md/txt-only) · delete-folder · delete-file · rename/move. This is the DESIGN (architecture + missing-ops + the folder-model decision) for **review + user-greenlight BEFORE building**. Not built yet.

## 1. Audit-first — what EXISTS (do NOT re-build)
Verified against `backend/modules/wiki/` (Rule#0 — read the code, not the task's claim):

| Capability | Status | Where |
|---|---|---|
| Import .md/.txt → note | ✅ EXISTS | `POST /import` (#93); `service/import_notes.py` `import_one`/`import_files`. Already REJECTS bad/unsupported-ext → an agent-error ROW (`INVALID_INPUT`, "only small .md/.txt import"), NO note created, never raises. |
| Delete a note | ✅ EXISTS | `DELETE /notes/{id}` (#94 SOFT-delete, recoverable tombstone) + `POST /notes/bulk-delete` + `/notes/{id}/restore` + `GET /trash`. (A HARD delete exists internally too.) |
| Folder tree | ✅ EXISTS | `GET /tree` → `reader/tree.py` `folder_tree` (VIRTUAL tree from notes' `folder` prefixes). |
| Folder description (meta) | ✅ EXISTS | `PUT /folders/{path}/meta` + `store/folder_meta.py` (`wiki_folder_meta`: folder_path PK, desc). |
| Create/update a note | ✅ EXISTS | `POST /notes`, `PUT /notes/{id}` (the note has a `folder` field). |
| FE explorer | ✅ EXISTS | WikiExplorer (#108). |

**Storage model (the key fact):** notes are **flat `.md` files** (`<id>.md`); a "folder" is a **VIRTUAL path-prefix** stored in the note's `folder` field (`""`=root, `"A/B/C"`=nested). `folder_tree` derives folders by splitting every note's `folder` on `/`. There is NO folder table — **a folder exists only if a note carries its prefix.** `wiki_folder_meta` (folder_path PK → desc) is OVERLAID onto existing folder nodes; it does NOT create them.

## 2. MISSING ops to build (the gap)
Confirmed absent (grep found no rename/move/create_folder/delete_folder):

| Op | Missing piece |
|---|---|
| **Create folder** (mkdir empty) | no way to make an EMPTY folder (see §3 — the model decision). |
| **Delete folder** (+ contents) | no folder-delete; must SCOPED-delete all notes under the prefix + the folder_meta row + confirm (#72). |
| **Rename / move folder** | no folder rename/move (re-prefix every note under it + move the folder_meta row). |
| **Move a note between folders** | the note has a `folder` field + the store comment says "a move updates it" — but there's no MOVE endpoint exposing it (PUT /notes/{id} may already allow setting folder — VERIFY in the build; if so, "move note" = a thin endpoint/UI, not new logic). |
| **Rename a note** | PUT /notes/{id} likely already updates title — VERIFY; rename = thin. |
| **Import strictly .md/.txt** | import already rejects unsupported-ext → confirm it's STRICT (the build adds a test asserting a .pdf/.docx → agent-error, no note). |
| **FE ops menu** | WikiExplorer needs new-folder / import / rename / move / delete affordances (+ in-page confirm for delete, #72). |

## 3. 🔴 Folder-model decision (the crux — DECIDE + log)
**Problem:** folders are pure path-prefixes → an EMPTY folder has no note to anchor it → it can't exist / vanishes the moment its last note moves out.

**Options:**
- (A) **`.keep` marker file** per empty folder — a physical `<folder>/.keep` (or a hidden marker note). CON: pollutes git + the note list + the flat-file model (notes are flat `<id>.md`, not pathed — a `.keep` doesn't fit the flat layout); messy.
- (B) **Reuse `wiki_folder_meta` as the folder ANCHOR (RECOMMENDED).** A folder EXISTS if it has notes (prefix) OR a `wiki_folder_meta` row. Create-empty-folder = INSERT a folder_meta row (blank desc OK). `folder_tree` UNIONs note-prefixes ∪ folder_meta paths (today it only reads prefixes — the build extends it to also seed folder nodes from `all_folder_meta()` keys). Delete-folder removes the notes + the folder_meta row. PRO: no marker files, no new table, reuses the existing KV (folder_path PK is exactly a folder identity), git-clean (folder_meta is SQLite cache, not a committed file). CON: folder existence now lives in 2 places (prefix ∪ meta) — but the tree builder unions them in ONE place, so it's coherent.
- (C) a new `wiki_folders` table — over-engineering (folder_meta already IS a folder-keyed table; single-user, no need).

**DECISION: Option B.** Empty folder = a `wiki_folder_meta` row (anchor); `folder_tree` unions prefixes ∪ meta-paths. → log to `## Assumptions`: "an empty wiki folder is anchored by a wiki_folder_meta row (folder_path), not a .keep file; folder_tree = note-prefixes ∪ folder_meta keys; how to change: the tree union + create_folder."

## 4. Cross-cutting contracts
- **md/txt-ONLY:** import + any new file-create rejects non-.md/.txt with an agent-error (`{code,message,hint,retryable}`), NO file created (the existing import contract — extend the strictness + test).
- **SCOPED + confirm on destructive ops** (#72): delete-folder = SCOPED delete of exactly that prefix's notes + its meta row (NEVER a blanket); FE in-page confirm (the #109 pattern, not window.confirm). Soft-delete where the note model supports it (#94 tombstone) so a folder-delete is recoverable per-note.
- **git-per-write** (md_store): each op = 1 commit (the existing store contract).
- **rename/move = re-prefix:** moving/renaming a folder re-writes the `folder` field of every note under it (a scoped bulk update) + moves the folder_meta row. One transaction, fail-soft per note + a warning on partial.
- **agent-first + honest:** every new endpoint returns the agent-readable envelope; empty folder → honest empty node (counts:0), not omitted.

## 5. Sprint breakdown → `plan_sprint_WIKI-WORKDIR.md` (BE-first → FE)
(3-6 tasks, deps; see the plan file for the dispatch contracts.)
- **W1 (BE):** folder lifecycle — create_folder (folder_meta anchor) + folder_tree UNION (prefixes ∪ meta) + delete_folder (SCOPED notes+meta) + rename/move folder (re-prefix). Endpoints: POST /folders, DELETE /folders/{path}, PUT /folders/{path}/move. The folder-model decision lands here.
- **W2 (BE):** file ops — verify/strict import .md/.txt-only (+ reject test) + move-note-between-folders + rename-note (thin over PUT /notes/{id} if it already sets folder/title — VERIFY first; if yes, this is small).
- **W3 (FE):** WikiExplorer ops menu — new-folder / import / rename / move / delete (in-page confirm, #72) wired to W1+W2.
- (Optional W4: MCP parity for the folder ops if agents need them — DECIDE at kickoff; default REST-only since the FE is the human surface.)

Deps: W1 BE-first (the folder model) → W2 BE (can parallel W1 if disjoint files) → W3 FE (after W1+W2 freeze). BE-first so the FE mirrors frozen shapes.

## 6. Open questions for user-greenlight
1. **Folder-delete recoverability:** soft (the notes go to #94 trash, the folder_meta row removed) vs hard? RECOMMEND soft (recoverable, the #94 model) — confirm.
2. **MCP parity** for folder ops (W4) — needed, or REST/FE-only? RECOMMEND REST/FE-only (folders are a human-curation surface) unless agents need to mkdir.
3. **Import source** — file-upload (browser) only, or also a path/paste? The existing /import takes filename+content (paste-able). RECOMMEND keep filename+content (works for upload + paste).

---
**Status:** DESIGN for review. NOT built. → SendMessage team-lead for review + user-greenlight; then team-lead dispatches the W1–W3 build (I kickoff each per §3.3a at dispatch time).
