# end_sprint_127-W3-WIKI-EXPLORER-OPS — WikiExplorer ops menu (nested-create + delete-on-UI) (Cairn #127 W3 = #134)

> Result. The headline UX: create a sub-folder INSIDE a folder + delete, ON the browser UI. Extended WikiExplorer (#108) with a folder ops menu (new-sub-folder / delete / rename / move) + import (.md/.txt upload+paste), wiring the W1 folder lifecycle + W2 file ops. Commit `<hash>` `feat(sprint-127-w3-wiki-explorer-ops)`. Status: ✅ verified (frontend-w3-2 built; architect 4-step + tsc + vitest 1063/0; team-lead INDEPENDENT Chrome — nested-create + scoped-soft-delete-on-UI both PASS). Cairn #127 W3 (#134) — fe-only, CLOSES on this commit → **#127 COMPLETE** (W1 418bcef + W2 46f0414 + W3). The wiki is now a dev work-dir.

## What shipped (FE — 5 files)
| File | Change |
|---|---|
| `components/shared/WikiExplorer.tsx` | toolbar: "+ Thư mục" (new root folder) + "Nhập" (import .md/.txt — file picker AND paste). Per-folder ⋯ menu: 🔴 "Thư mục con mới" (NESTED create → POST /wiki/folders {path: parent/child}) · 🔴 "Xóa" (in-page confirm #72 — NOT window.confirm → DELETE /wiki/folders/{path}, soft/recoverable) · rename/move (PUT /wiki/folders/{path}/move). All ops `reload()` the tree (the W1 gotcha: observe via the refetched tree, NOT get_note). |
| `lib/api.ts` | createWikiFolder / deleteWikiFolder / moveWikiFolder / importWiki (the W1/W2 endpoints). |
| `lib/types.ts` | WikiTreeNode/Note + WikiImportResult + the folder-op shapes (mirror the W1/W2 freeze). |
| `lib/tokens.css` | the ops-menu + in-page-confirm-modal + import tokens. |
| `__tests__/WikiExplorer.test.tsx` (+10 → 1063) | new-sub-folder → POST nested path; delete → in-page-confirm → DELETE + tree reload; import .md → POST, .pdf → honest reject; rename/move; #108 features kept. |

## Design (LOCKED — the headline ops on the UI, in-page confirm, reload-not-get_note)
- 🔴 **NESTED create on the UI** (the user's headline): per-folder ⋯ → "Thư mục con mới" → in-page name input → POST /wiki/folders {path: parentPath + "/" + name} → the sub-folder appears nested (the W1 tree-union shows it even empty).
- 🔴 **DELETE on the UI** (the headline): ⋯ → "Xóa" → IN-PAGE confirm modal (#72 — NOT window.confirm, which blocks the browser extension) → DELETE /wiki/folders/{path} → the subtree leaves the tree (soft, recoverable; siblings untouched — the W1 SCOPED delete).
- import (.md/.txt, upload + paste — both, user CHỐT) → POST /wiki/import; .pdf etc → the BE INVALID_INPUT agent-error surfaced honestly (the W2 contract). rename/move via the frozen W1/W2 endpoints.
- 🔴 **the W1 get_note-tombstone gotcha applied:** all ops `reload()` the /wiki/tree (the live authoritative view), NOT get_note (which returns the tombstone after a soft-delete).

## Verification (Gate-2 FE — frontend-w3-2 + architect 4-step + team-lead Chrome)
- **architect 4-step (read FULL):** the ⋯ menu (nested-create POST {parent/child}, delete via in-page-confirm + DELETE, move via PUT); reload-not-get_note; the new client fns; in-page confirm (NOT window.confirm). Staged EXACTLY the 5 W3 files (🔴 NOT the untracked `frontend/app/projects/__tests__/` [#123 leftover] or the untracked docs/.env — team-lead flagged the hazard; explicit-path stage avoided it). ✅
- **tsc clean; vitest 89 files / 1063 passed / 0 failed** (independent; +10). ✅
- **🔴 team-lead INDEPENDENT Chrome :3010 (drove the real UI, the headline cases):** NESTED CREATE — PKM ⋯ → "Thư mục con mới" → "tl-verify-sub" → appeared NESTED inside PKM (indented, count 0) ✓; DELETE on UI — ⋯ → "Xóa" → IN-PAGE confirm modal (recoverable copy) → confirmed → gone, **siblings Zettel + Evergreen Notes SURVIVED** (scoped, soft) ✓; ops on nested folders; tree fast; console clean (0 errors); probe cleaned. ✅
- **the 83s /wiki/tree perf finding did NOT reproduce** (team-lead curl'd 5×: localhost 1.8-2.3ms, Tailscale 3-5ms — transient, the /tracing-28s pattern; NO BE bug, no perf task). ✅

## 3 Gates
- **Gate 2 (Function):** the +10 ops tests (nested-create / delete-in-page-confirm / import-reject / rename-move / #108-kept) + tsc + vitest 1063/0 + team-lead Chrome (the headline). ✅
- **Gate 3 (Sprint):** end-doc; frontend-w3-2 + architect 4-step + team-lead Chrome; staged EXACTLY the 5 W3 files (NO projects/__tests__/docs/.env/BE leak — the flagged hazard avoided via explicit-path stage); commit format. ✅

## Assumptions (user-review)
- **nested-create + delete are folder ⋯ menu ops on the UI; delete = in-page confirm (#72), soft/recoverable.** **How to change:** the WikiExplorer ops menu.
- **import = .md/.txt upload + paste; non-text → honest reject** (the W2 contract). **How to change:** the import handler / _ALLOWED_EXT (BE).

## Notes
- Cairn #127 W3 (= board #134) — fe-only; **COMPLETES #127 (the wiki dev work-dir): W1 folders (418bcef) + W2 file ops (46f0414) + W3 explorer ops (this).** user-CHỐT headline (nested folder + delete on the UI) — delivered + team-lead Chrome-verified (nested-create appeared indented; delete kept siblings, scoped soft). frontend-w3-2 built + Chrome; architect committed (§3 sole-committer). 🔴 **The staging-hazard catch:** team-lead flagged `frontend/app/projects/__tests__/` untracked (#123 leftover) + untracked docs/.env in the tree — I staged ONLY the 5 W3 files by EXPLICIT path (the verify-staged-set-before-every-commit discipline; `git diff --cached` = exactly the 5, no leak). The W1 get_note-tombstone gotcha was correctly applied (ops reload the tree). The empty-folder anchor (W1 design §3 — folder_meta as the anchor) is what makes the nested-empty folder show on the UI. The wiki is now a dev work-dir: nested folders, .md/.txt files, create/delete/rename/move/import, all on the browser UI. REST/FE-only (no MCP, user CHỐT). No restart (FE).
