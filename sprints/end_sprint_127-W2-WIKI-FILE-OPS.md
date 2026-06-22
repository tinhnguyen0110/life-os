# end_sprint_127-W2-WIKI-FILE-OPS — wiki file ops: strict import + note move/rename (Cairn #127 W2 = #133)

> Result. The wiki work-dir FILE half — and a DON'T-OVER-BUILD win: the functionality ALREADY EXISTED (strict .md/.txt import via `_ALLOWED_EXT`; note move/rename via the existing `PUT /wiki/notes/{id}` {folder}/{title}), so W2 = VERIFY + lock it with tests, ZERO source change. Commit `<hash>` `test(sprint-127-w2-wiki-file-ops)` (+ folds the #127 design docs). Status: ✅ verified (backend-w3 verify-only; architect 4-step + INDEPENDENT test-only-confirm + live). Cairn #127 W2 (#133) — be-only test-only, CLOSES on this commit → W3/#134 (FE) unblocks. REST-only.

## What shipped (TEST-ONLY — zero source change)
| File | Change |
|---|---|
| `tests/test_wiki_import.py` (+28 cases) | 🔴 STRICT .md/.txt import: `test_W2_unsupported_ext_rejected_no_note` parametrized over .pdf/.png/.docx/.zip/.exe/.PDF/.DOCX (case-insensitive) → INVALID_INPUT agent-error (retryable:false) + NO note (createdCount:0); .md/.txt → accepted. Locks the rejection contract (`_ALLOWED_EXT={.md,.txt}` already enforced it). |
| `tests/test_wiki_note_move_rename.py` (NEW, 9) | move note via PUT /notes/{id} {folder} → verified via the TREE/all_notes (the W1 gotcha: NOT get_note, which returns the tombstone); rename via PUT {title}; folder+title in one PUT. |
| `sprints/DESIGN_WIKI-WORKDIR.md` + `plan_sprint_WIKI-WORKDIR.md` | the #127 design + plan deliverables, folded into git (were untracked review artifacts — now landed alongside the build, per team-lead approval). |

## Design (LOCKED — verify-existing, no redundant endpoint, the gotcha applied)
- **don't-over-build:** strict-import + move + rename ALREADY worked (W2's kickoff confirmed it). W2 did NOT add a redundant /move endpoint — the existing `PUT /wiki/notes/{id}` {folder}/{title} IS the move/rename surface (frozen for W3). W2 = the tests that PROVE + lock it. Zero source change (verified: `git status backend/modules/` clean).
- **strict-import contract:** `_ALLOWED_EXT={.md,.txt}`; anything else (case-insensitive) → INVALID_INPUT agent-error + NO note. Now test-locked.
- **🔴 the W1 gotcha applied:** move/membership verified via the TREE/all_notes (the live authoritative view), NOT get_note (which still returns a tombstone after soft-delete) — the right surface.

## Verification (Rule#0 — architect INDEPENDENT)
- **architect 4-step:** 🔴 **TEST-ONLY confirmed** (`git status backend/modules/` CLEAN — zero source change, the don't-over-build claim verified); the strict-import reject test asserts ok=False/INVALID_INPUT/retryable=false/no-note (real, parametrized over 7 bad exts incl case-variants); the move/rename tests verify via tree/all_notes (the gotcha applied), via the existing PUT. Staged tests + sprints/ ONLY. ✅
- **INDEPENDENT suite:** the 2 W2 test files pass; backend FORWARD 2458/0 == REVERSE; mypy clean (no source change). + team-lead live (move 94 A→B: B counts:1 / A counts:0 via tree; rename; .pdf→INVALID_INPUT no-note; .md→noteId; SCOPED cleanup by-id). ✅

## 3 Gates
- **Gate 1 (API):** strict-import reject (agent-error + hint + retryable:false); move/rename via the existing PUT (frozen for W3). ✅
- **Gate 2 (Function):** the +28 import cases + 9 move/rename (verify via tree per the gotcha) — real, not self-confirming; FORWARD==REVERSE 2458/0; mypy clean. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + test-only-confirm + live; staged EXACTLY tests + the 3 sprints/ docs (NO source/tracing/FE/read_server leak); commit format `test(sprint-127-w2-...)`. ✅

## Assumptions (user-review)
- **move/rename note = the existing PUT /wiki/notes/{id} {folder}/{title}** (no dedicated /move endpoint — it already works). **How to change:** add a /move endpoint if the FE wants one (W3 uses the PUT).
- **strict-import = `_ALLOWED_EXT={.md,.txt}`** (non-text rejected). **How to change:** the _ALLOWED_EXT set.

## Notes
- Cairn #127 W2 (= board #133) — be-only TEST-ONLY (the don't-over-build win: verify-existing, lock with tests, zero source). backend-w3 verify-only; architect committed (§3 sole-committer). The W2 dispatch said "likely SMALL — don't over-build" + backend correctly delivered exactly that (the move/rename were already wired; strict-import already enforced; W2 = the proof). 🔴 the W1 get_note-tombstone gotcha was correctly applied in the move tests (verify via tree/all_notes). **Folded the 2 #127 design docs** (DESIGN + plan) into this commit (team-lead approved — one commit, wiki tests + sprints/ only, no source/leak) so the design is in git alongside the build. **W3/#134 (FE WikiExplorer ops menu — nested-create + delete-on-UI + import/rename/move) unblocks** — I kickoff + dispatch frontend-w3-2 next; team-lead runs the headline Chrome verify. REST-only, no restart. The wiki-work-dir BE is complete (W1 folders + W2 file ops); W3 is the FE.
