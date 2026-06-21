# end_sprint_WIKI-WRITE-404 — agent-readable 404 on the 3 write note-id routes (Cairn #14)

> Result. Closes the #46-agent-error cluster for the note-id surface: all 7 note-id routes (4 GET + 3 WRITE) now return the flat agent_error 404. Commit `<hash>` `fix(sprint-WIKI-WRITE-404)`. Status: ✅ all gates pass. backend-w3 EDITED (wiki router + test); architect 4-step + committed (§3).

## The gap (from the WIKI-RECONCILE boundary)
WIKI-RECONCILE made the 4 GET note-id routes return the flat agent_error 404; the 3 WRITE note-id routes (POST refine / PUT / DELETE) still returned raw `{"detail":...}` — an open consistency gap in the #46-agent-error cluster (an agent gets a code-to-branch-on for a GET 404 but a raw string for a write 404).

## What shipped
| File | Change |
|---|---|
| `modules/wiki/router.py` | The 3 WRITE note-id routes' `except service.NoteNotFound:` now `return _note_not_found(note_id)` (the helper from WIKI-RECONCILE — RETURNS a JSONResponse, NOT raise) → flat `{error:{code:NOT_FOUND,hint,retryable:false}}`: POST /notes/{id}/refine (318), PUT /notes/{id} (333), DELETE /notes/{id} (346). RefineGateError→422 stays raw (not a note-id-404). |
| `tests/test_wiki_reconcile.py` | +4: parametrized 3 write routes → 404 + flat {error:NOT_FOUND,retryable:false} (NOT detail) + a boundary test (merge keeps its own 404 shape). |

## Design (LOCKED)
- **All 7 note-id routes** (4 GET + 3 WRITE) → byte-identical flat `{error:{code:NOT_FOUND,...}}` via the shared `_note_not_found` helper. Consistency complete for the note-id surface.
- **RETURN not raise** — `_note_not_found` returns a JSONResponse (a Response), so the write routes' except blocks `return` it (FastAPI accepts a returned Response). NOT `raise` (it's not an exception).
- **BOUNDARY (no scope creep):** conflict/sync/proposal/merge 404s stay raw `{detail}` (different entities) → a LOGGED follow-up slice (backend flagged; architect noted to backlog). The `_note_not_found` helper is note-id-specific.

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step:** all 3 WRITE routes `return _note_not_found` (grep-confirmed RETURN, guard confirmed NO `raise _note_not_found` — the wrong form); all 4 GET routes still flat (regression); the 8 remaining raw `detail=` 404s are merge/conflict/proposal (different entities, correctly untouched — boundary held); scope = exactly 2 files.
- **backend-w3 evidence:** FULL pytest 1962/0 (baseline 1958 + 4) + mypy clean; LIVE :8686 — PUT/DELETE/refine 99999 → flat {error:NOT_FOUND}, merge 99999 → raw {detail} (boundary).

## 3 Gates — ALL PASS
- **Gate 1 (API):** the 3 write routes' 404 envelope = the flat agent_error (consistent with the 4 GET); merge/conflict/proposal untouched. ✅
- **Gate 2 (Function):** the parametrized write-route 404-shape distinguishing (error.code=="NOT_FOUND", NOT a detail key) + the boundary test (merge keeps its shape) + GET regression; 0 errors; mypy clean. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step (return-not-raise + boundary verified) + backend live evidence; commit format; git-status clean; WIKI-WRITE-404-only stage. ✅

## Assumptions (user-review)
- **All 7 note-id routes (4 GET + 3 WRITE) return the flat agent_error NOT_FOUND 404** (via the shared `_note_not_found` helper). **How to change:** the helper / which routes call it.
- **BOUNDARY: conflict/sync/proposal/merge 404s stay raw** → a separate follow-up (different entities, the helper is note-id-specific). Logged to backlog.

## Notes
- Closes Cairn #14. backend-w3 EDITS; architect commits (§3). The #46-agent-error cluster is now complete for the note-id surface. Next: #56-part2 MACRO-HISTORY-WARNING (designed, held) → #43 (costUSD) → #46-P3 → #37-40. NEW follow-up logged: audit conflict/sync/proposal 404s for the same agent_error treatment (different-entity slice).
- agent-first error pillar: every 404 an agent can hit on a known surface gives a code to branch on + a hint, not a raw human string.
