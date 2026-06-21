# Sprint AGENT-ERROR-P7 — app-level RequestValidationError → agent_error (Cairn #69; = the #24 follow-up)

> Created 2026-06-21 by architect. The TRUE FINAL of the #46-family — the one error class the per-handler audit couldn't reach: FastAPI's RequestValidationError (path/body type) fires BEFORE any handler → raw {detail:[...]}. Value-safe, no-user-decision (NEVER-FREE fill while #65 awaits user). backend EDITS main.py; architect commits (§3).

## Context (Rule#0 kickoff)
After #46 PARENT (all per-handler errors → agent_error), the LAST raw-error surface is FastAPI's own validation: a bad path/body type (e.g. GET /reminders/NOTANINT → {detail:[{type:int_parsing}]}) returns BEFORE any route handler runs — so the per-handler audit (#46) couldn't touch it. team-lead verified live: still raw {detail}. This phase = ONE app-level handler.

## The fix (Rule#0-grounded — exact)
In `main.py create_app()` (after `app = FastAPI(...)` at :109), register:
```python
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from core.agent_errors import agent_error

@app.exception_handler(RequestValidationError)
async def _validation_handler(request, exc):
    errs = exc.errors()
    # summarize the first error into a readable message (loc + msg); keep status 422
    first = errs[0] if errs else {}
    loc = ".".join(str(p) for p in first.get("loc", []))
    msg = f"{loc}: {first.get('msg','invalid')}" if loc else (first.get("msg","validation failed"))
    return JSONResponse(status_code=422, content=agent_error(
        "INVALID_INPUT", f"request validation failed — {msg}",
        hint="check the path/query/body types against the endpoint's schema"))
```
- 422 status PRESERVED (only the BODY changes {detail:[...]} → {error:{code:INVALID_INPUT,message,hint,retryable:false}}).
- Summarize the first validation error into the message (loc+msg) so the agent gets a readable string — don't dump the raw list, don't drop the info. (Optional: keep the full structured list under an extra field if wanted — lean: just the summary message, no-overengineering.)
- ONE handler covers ALL routes' path+body validation (app-level).

## Scope
IN: main.py (the handler) + the tests that assert the {detail} BODY shape on a 422.
OUT: NO per-handler change (#46 done). NO status-code change (stays 422). NO touching the 422 tests that assert only status_code (they stay green).

## ⚠️ Test-update surface (the nuance)
~20 test files reference a `detail` key, BUT most 422 tests assert only `status_code == 422` (UNAFFECTED — status preserved). ONLY update tests that assert the `{detail}` BODY shape on a validation 422 → change to assert `{error:{code:"INVALID_INPUT"}}`. grep the body-shape assertions; leave status-only ones. (A blanket find-replace would wrongly touch status-only + the non-validation detail= cases.)

## HARD GATE (distinguishing)
- GET /reminders/NOTANINT (bad path-int) → 422 + `{error:{code:"INVALID_INPUT",message,hint,retryable:false}}`, NOT {detail:[...]}.
- POST /notes {title:""} (bad body) → 422 + {error:INVALID_INPUT} (body validation too).
- A VALID request → still 2xx (the handler only fires on validation failure — distinguishing: a happy path is untouched).
- pytest 0-failed, mypy clean. Verify on LIVE HTTP (the import-cache lesson).
- POST-P7: an agent hits NO raw {detail:[...]} on ANY validation error → the agent-error story is 100% complete.

## Baseline
pytest 1973 (post-#46-P6 origin). Keep 0-failed.

## Test ownership split
backend: a test for the handler (bad path-int → {error:INVALID_INPUT} not {detail}; bad body → same; valid → 2xx) + update the body-detail-asserting 422 tests. tester: live curl /reminders/NOTANINT + a bad body.

## Assumptions (user-review)
- **app-level RequestValidationError → agent_error INVALID_INPUT 422** (message summarizes the first validation error loc+msg; status preserved). One handler, all routes. **How to change:** the handler in create_app.
- the message summarizes the first error (not the full list) — no-overengineering; add the structured list under a field if an agent ever needs all of them.

## Notes
- = Cairn #69 (the #24 follow-up, prioritized). The TRUE final of the agent-error story (the pre-handler validation class). After P7: an agent NEVER meets a raw {detail} on any error. backend EDITS main.py; architect commits fix(sprint-AGENT-ERROR-P7). Value-safe NEVER-FREE fill (no user-decision). #65 unrelated (awaits user).
