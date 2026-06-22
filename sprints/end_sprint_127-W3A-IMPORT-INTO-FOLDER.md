# end_sprint_127-W3A-IMPORT-INTO-FOLDER — WikiExplorer: Note-mới + Import INTO a folder (Cairn #127 W3A = #135)

> Result. A #127-W3 follow-up (user fix): a note/import can land INSIDE a chosen folder, not root-only. WikiExplorer's per-folder ⋯ menu gains "＋ Note mới" (create a note IN this folder) + "📥 Import vào đây" (import pre-targeted to this folder). Commit `<hash>` `feat(sprint-127-w3a-import-into-folder)`. Status: ✅ verified (frontend-w3-2 built + Chrome; architect 4-step + tsc/vitest; team-lead INDEPENDENT Chrome — note LANDED UNDER PKM, not root). Cairn #127 W3A (#135) — fe-only, CLOSES on this commit → #136-FE next in queue. 🔴 Committed via a hunk-split (W3A interleaved with #136-FE in shared lib files — see Notes).

## What shipped (FE — W3A files, surgically staged)
| File | Change |
|---|---|
| `components/shared/WikiExplorer.tsx` | per-folder ⋯ menu: "＋ Note mới" (new-note IN the folder → in-page title modal, NOT window.prompt → POST a note with `folder=node.path`) + "📥 Import vào đây" (the import modal PRE-TARGETED to this folder). FolderOpKind +new-note/import-here. |
| `components/shared/__tests__/WikiExplorer.test.tsx` (+6 → 1069) | note-in-folder lands under the target; import-into-folder (2-step); import-vào-đây pre-target; root-no-regression. |
| `lib/types.ts` (the W3A hunk only) | `WikiNoteCreateInput +folder` ("" = root; the BE NoteCreateInput accepts it → "Note mới" lands in a folder). |
| `lib/tokens.css` | `.wex-ops-sep` (the ops-menu separator) + W3A menu tokens. |

## Design (LOCKED — note/import INTO a folder, in-page modal)
- the user's fix: a note (or import) must be creatable INSIDE a folder (the prior W3 created at root; the user wanted folder-scoped). "＋ Note mới" on a folder node → POST a note with `folder = node.path` (the BE NoteCreateInput accepts `folder` — verified live). "📥 Import vào đây" pre-targets the import modal to that folder.
- in-page title modal (NOT window.prompt — the #72/extension-safe pattern).

## Verification (Gate-2 FE — architect 4-step + team-lead Chrome)
- **architect 4-step (read FULL):** the ⋯ menu new-note/import-here ops; note POST carries `folder=node.path`; the WikiNoteCreateInput +folder type. 🔴 **Staged via hunk-split (the tangle):** W3A interleaved with #136-FE in lib/types.ts (W3A's +folder @@914 + #136's +remindChannel @@1969) and lib/api.ts (100% #136 untickActivity) → I staged ONLY the W3A hunk of types.ts (`git add -p`, took @@914, left @@1969) + EXCLUDED lib/api.ts entirely (it's 100% #136) + the #136 files (tracing/page.tsx, useTracing.ts, tracing/{store,service,router}.py). `git diff --cached` = exactly the 4 W3A files; remindChannel in staged types.ts = 0; #136 left dirty. ✅
- **tsc clean; vitest 1069/0** (frontend, full working tree, +6). team-lead INDEPENDENT Chrome: "＋ Note mới" → in-page modal → note LANDED UNDER PKM (count 1→2, nested, total 49→50, op-log create) = the user's exact fix; import-into-folder + pre-target + root-no-regression; console clean; SCOPED probe cleanup (note 103 by-id). ✅

## 3 Gates
- **Gate 2 (Function):** the +6 tests (note-in-folder / import-into-folder / pre-target / root-no-regression) + tsc + vitest 1069/0 + team-lead Chrome. ✅
- **Gate 3 (Sprint):** end-doc; frontend + architect 4-step + team-lead Chrome; staged EXACTLY the 4 W3A files via hunk-split (NO #136 leak: api.ts excluded, types.ts W3A-hunk-only, remindChannel=0 staged; NO projects/__tests__/docs/.env); commit format. ✅

## Assumptions (user-review)
- **a note/import can be created INSIDE a folder** (folder=node.path), not root-only. **How to change:** the new-note/import-here ops in WikiExplorer.

## Notes
- Cairn #127 W3A (= board #135) — fe-only; the user's note-in-a-folder fix on top of W3. frontend-w3-2 built + Chrome; architect committed (§3 sole-committer). 🔴 **The shared-file tangle (the #111/#112 lesson, recurred):** #136-FE was built by the SAME FE agent in PARALLEL with W3A, and BOTH touched the shared lib/types.ts + lib/api.ts before W3A committed → interleaved. Caught at the staging leak-check (grep'd the staged shared files for #136 symbols). Resolved via `git add -p` hunk-split (took the W3A hunk of types.ts, left the #136 remindChannel hunk; excluded api.ts = 100% #136) — NOT a blind whole-file commit (would've swept #136's untickActivity + remindChannel into W3A). The #136 work (untickActivity, remindChannel, tracing/page, useTracing, the #136-BE store/service/router) stays dirty for the #136 commits. **Lesson reinforced:** when one FE agent runs two tasks in parallel into shared lib files, the commits MUST hunk-split — the serialization is on the SHARED FILE, not just the agent. After commit → #136-FE + #136-BE follow (their own commits). team-lead Chrome-verified the user fix. FE-only, no restart.
