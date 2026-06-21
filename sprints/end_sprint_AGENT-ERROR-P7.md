# end_sprint_AGENT-ERROR-P7 — app-level RequestValidationError → agent_error (Cairn #69)

> Result. **The agent-error story is 100% COMPLETE** — the last raw-error class (FastAPI's pre-handler path/query/body validation) is now agent_error. An agent NEVER meets a raw {detail:[...]} on any error. Commit `9b4c59b` `fix(sprint-AGENT-ERROR-P7)`. Status: ✅ all gates pass. backend-w3 EDITED (main.py + new test); architect 4-step + committed (§3). = the #24 follow-up, prioritized as #69.

## What shipped (2 files — ONE handler, all routes)
| File | Change |
|---|---|
| `main.py create_app()` (+30/-2) | `@app.exception_handler(RequestValidationError)` → `JSONResponse(422, agent_error("INVALID_INPUT", f"request validation failed — {loc}: {msg}", hint))`. Status STAYS 422 (only body changes {detail:[...]} → flat {error:{...}}). Message = the first validation error summarized as `loc: msg` (e.g. "body.asset: Field required") so the agent knows WHICH field — doesn't dump the list, doesn't drop info. retryable auto-False (deterministic). Imports: RequestValidationError + JSONResponse + agent_error. |
| `tests/test_validation_handler.py` (NEW, 5) | app-level fixture (real create_app + isolated paths, mirrors test_cors). bad-path-int, missing-body-field, bad-type-body, + THE distinguishing (valid request → 2xx, NOT intercepted). `_assert_flat_invalid_input` asserts 422 + NO top-level detail + code==INVALID_INPUT. |

## Design (LOCKED)
- ONE app-level handler covers ALL routes' path/query/body validation (the pre-handler class the per-handler #46 audit couldn't reach). Status preserved (422), only the body → agent_error. Message summarizes the first error (loc+msg) — readable, not a dump.

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step:** the handler returns agent_error 422 (status preserved, message = loc:msg summary, retryable auto-False); the test covers the distinguishing (valid→2xx not intercepted) + NO-top-level-detail assert; scope exactly 2 files.
- **backend-w3 evidence:** RED-proof (without handler → raw {detail:[int_parsing]}; with → flat {error:INVALID_INPUT}); mypy clean (149 files); FULL pytest 1978/0 (baseline 1973 + 5 — count reconciled: a transient 21-skipped was a mid-suite container restart gating live-server tests; re-run stable → deterministic 1978/6/0); LIVE curl — /reminders/NOTANINT + /agent-proposals/NOTANINT + bad/missing journal body → 422 flat INVALID_INPUT (ONE handler, all routes); valid /health → 200, valid-typed /reminders/999999 → 404 (handler fires ONLY on failure); completeness sweep → NO raw {detail} leak anywhere.
- **Test-scope (architect-confirmed):** ZERO existing tests asserted the old {detail} body on a validation 422 (all status-only or already-flat) → NO old test updated, NO blanket find-replace. Only the new file.

## 3 Gates — ALL PASS
- **Gate 1 (API):** the last raw-error class → flat agent_error; status 422 preserved; one handler all routes; the agent-error story complete. ✅
- **Gate 2 (Function):** the distinguishing (valid→2xx not intercepted) + NO-top-level-detail + per-route coverage; mypy clean; 0 errors. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step + backend live-HTTP + RED-proof; commit format; git-status clean; #69-only (2 files). ✅

## Assumptions (user-review)
- **app-level RequestValidationError → agent_error INVALID_INPUT 422** (status preserved; message = first-error loc:msg summary; one handler, all routes). **How to change:** the `_validation_handler` in create_app.
- ops note: main.py is NOT in uvicorn's --reload allowlist → a restart is needed for handler changes to take live effect (not a code issue; team-lead confirmed it fires).

## Notes
- **🎯 THE AGENT-ERROR STORY IS 100% COMPLETE** — every error class an agent can meet (per-handler #46-P1..P6 + this pre-handler validation P7) is now flat agent_error {code,message,hint,retryable}. The full arc: P1/P2 (read_server) → #61/#14 (wiki note-id) → P3/P4/P5/P6 (per-handler REST, #46 parent) → P7 (pre-handler validation, #69). backend-w3 EDITS; architect commits (§3). Next (auto-run, no user-gate): #68 (reindex-FTS) → #65 (Daily Tracing) → #63 → #64.
