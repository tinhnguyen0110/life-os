# end_sprint_AGENT-ERROR-P5 — journal-cluster REST errors → agent_error (Cairn #46 Phase 5)

> Result. journal + decision_journal + reminders + notes REST errors now flat agent_error (reused the P3 helper). Commit `97fdf21` `fix(sprint-AGENT-ERROR-P5)`. Status: ✅ all gates pass. backend-w3 EDITED (4 routers + 4 tests); architect 4-step + committed (§3).

## What shipped
| File | Change |
|---|---|
| `modules/journal/router.py` (3) | bad-id 404 → NOT_FOUND, hint names /journal. |
| `modules/decision_journal/router.py` (3) | 2 plain 404 → NOT_FOUND + THE nuance: corrupt-file (entry_file_exists but parses None) → INVALID_INPUT (422), message names the corrupt-vs-not-found distinction; else-branch → NOT_FOUND. Hint corrected to the real mount /decision-journal (was about to ship /decisions). |
| `modules/reminders/router.py` (3) | bad-id 404 → NOT_FOUND. |
| `modules/notes/router.py` (3) | bad-id 404 → NOT_FOUND. |
| All 4 | RETURN not raise; removed now-unused HTTPException imports. |
| tests | test_journal_api, test_decision_journal (the corrupt-file distinguishing), test_reminders, test_notes_api. |

## Design (LOCKED)
- Reused the P3 `agent_error_response` helper. 12 NOT_FOUND + the 1 decision_journal corrupt-file → INVALID_INPUT (a valid id but unparseable stored data — honest, distinct from not-found). RETURN not raise.

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step:** all 4 routers 0 raw HTTPException; the corrupt-file branch → INVALID_INPUT "malformed" + else NOT_FOUND (the message names the distinction); all 4 use agent_error_response; scope exactly 8 files; mypy clean.
- **backend-w3 evidence:** FULL pytest 1973/0 + mypy 0; the corrupt-file distinguishing (corrupt → INVALID_INPUT, absent → NOT_FOUND — an all-NOT_FOUND impl FAILS the corrupt case); LIVE HTTP — all bad-id → 404 NOT_FOUND flat {error}, reminders valid-int-nonexistent → 404 flat, no {detail}.

## 3 Gates — ALL PASS
- **Gate 1 (API):** journal-cluster REST errors = flat agent_error (NOT_FOUND + the corrupt-file INVALID_INPUT). ✅
- **Gate 2 (Function):** the corrupt-file distinguishing (INVALID_INPUT vs NOT_FOUND); mypy clean; 0 errors. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step + backend live-HTTP; commit format; git-status clean; #46-P5-only (8 files). ✅

## Assumptions (user-review)
- **journal/decision_journal/reminders/notes REST errors → flat agent_error** (NOT_FOUND) via the P3 helper; decision_journal corrupt-file → INVALID_INPUT (valid id, unparseable stored data). **How to change:** the per-route calls + the corrupt-file branch.

## Out-of-scope finding (backend-flagged → new follow-up)
**FastAPI pydantic PATH-TYPE validation** — a non-integer id on an int-path route (e.g. /reminders/nope-x) → FastAPI's OWN 422 `{detail:[{int_parsing...}]}` BEFORE any handler runs. This is an app-level layer (RequestValidationError) shared by ALL int-path routes — NOT the in-handler not-found this audit migrates. Converting it to agent_error needs a custom RequestValidationError handler (app-level, bigger change). → a NEW follow-up slice ("agent-readable 422 for path/body validation"), NOT folded into the per-handler #46 audit. Logged to backlog.

## Notes
- #46 Phase 5 (P3/P4 done). backend-w3 EDITS; architect commits (§3). Next: P6 (FINAL — read_server feed-error + agent_proposals/automation/activity + wiki ~10 sites incl. #67 conflict-404; closes #46 parent + #67). + the NEW path-validation-422 follow-up. + #65 Daily Tracing (awaiting user scope-approval).
