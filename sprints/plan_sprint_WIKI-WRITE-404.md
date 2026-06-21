# Sprint WIKI-WRITE-404 — agent-readable 404 on the 3 write note-id routes (Cairn #14)

> Created 2026-06-21 by architect. Reactive sprint (follow-up from the WIKI-RECONCILE boundary — the 3 WRITE note-id 404s deferred from #61). Closes the #46-agent-error cluster for the note-id surface. backend-w3 EDITS wiki router; architect commits (§3).

## The gap
WIKI-RECONCILE (#61 item#3) made the 4 GET note-id routes return the flat agent_error 404, but the 3 WRITE note-id routes (POST refine / PUT / DELETE) still returned raw `{"detail":...}` — an open consistency gap in the #46-agent-error cluster. An agent gets a code-to-branch-on for a GET 404 but a raw string for a write 404.

## The fix (reuse the existing helper)
The 3 WRITE note-id routes' `except service.NoteNotFound:` → `return _note_not_found(note_id)` (the helper from WIKI-RECONCILE — RETURNS a JSONResponse with the flat `{error:{code:NOT_FOUND,hint,retryable:false}}`):
1. POST /notes/{id}/refine (router.py:318) — RefineGateError→422 stays raw (not a note-id-404).
2. PUT /notes/{id} (router.py:333).
3. DELETE /notes/{id} (router.py:346).

⚠️ **RETURN not raise** — `_note_not_found` returns a Response, not an exception. `return` it in the except block (NOT `raise`). FastAPI accepts a returned Response.

## BOUNDARY (no scope creep)
NO new helper (reuse _note_not_found). NO touching conflict/sync/proposal/merge 404s (different entities) — a separate follow-up slice. NO macro #56 (different module).

## HARD GATE (distinguishing)
- PUT/DELETE/POST-refine note-id-9999 → 404 + flat `{error:{code:"NOT_FOUND",retryable:false}}` (NOT raw {detail}). Assert error.code, NOT a "detail" key.
- The 4 GET routes still flat (regression). merge/conflict 404s UNCHANGED (boundary).
- pytest 0-failed, mypy clean.

## Baseline
pytest 1958 (post-RSI-FLAT). Keep 0-failed.

## Assumptions (user-review)
- **All 7 note-id routes (4 GET + 3 WRITE) → the flat agent_error NOT_FOUND 404** via the shared _note_not_found helper. **How to change:** the helper / call-sites.
- **BOUNDARY: conflict/sync/proposal/merge 404s stay raw** → a separate follow-up (different entities). Logged to backlog.

## Notes
- Reactive sprint (§3.4b), same theme as the #46-agent-error cluster. backend EDITS; architect commits. Tiny (3 one-line changes + 4 tests).
