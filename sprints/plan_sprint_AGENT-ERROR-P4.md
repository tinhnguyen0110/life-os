# Sprint AGENT-ERROR-P4 — projects+career REST errors → agent_error (Cairn #46 Phase 4)

> Created 2026-06-21 by architect (pre-grounded ∥ while backend does HARDENING). #46-family Phase 4. Reuses the `agent_error_response` helper from P3 (the spine). HOLD dispatch until HARDENING commits (sequential, 1 backend/tree). backend EDITS; architect commits (§3).

## Context
P3 built `core/agent_errors.agent_error_response(code,msg,hint)` + the _CODE_STATUS map. P4 applies it to projects+career REST (~12 raw HTTPException). Mostly clean NOT_FOUND 404s + ONE custom-exc passthrough (the only nuance).

## Scope (Rule#0 pre-grounded — exact sites)
IN: projects/router.py + career/router.py (+ the helper import) + tests.
OUT: other modules (P5/P6). NO helper change (reuse P3's). NO service-logic change beyond the error shape. NO 200-path change.

### projects/router.py (6 sites)
- :65/78/100/111/122 "project {id} not found" 404 → `return agent_error_response("NOT_FOUND", f"project {project_id!r} not found", hint="GET /projects for valid ids")`.
- :91 `except service.ProjectError as exc: raise HTTPException(status_code=exc.code, ...)` — ProjectError carries `.code` (service.py:391 code=400 "not a git repo", :393 code=409 "id already exists"). MAP the code → agent_error code: **400→INVALID_INPUT, 409→CONFLICT**. e.g. `code = {400:"INVALID_INPUT", 409:"CONFLICT"}.get(exc.code, "INVALID_INPUT"); return agent_error_response(code, str(exc), hint=...)`. (RETURN not raise — the except returns the Response.)

### career/router.py (6 sites — all clean NOT_FOUND)
- :88/97/105 "blog post {id} not found" 404 → NOT_FOUND, hint "GET /career/blog for valid ids".
- :134/143/151 "demo {id} not found" 404 → NOT_FOUND, hint "GET /career/demos for valid ids".

## HARD GATE (distinguishing)
- projects bad-id → 404 flat {error:NOT_FOUND}; register a non-git-repo → 422/400 flat {error:INVALID_INPUT}; register a dup id → 409 flat {error:CONFLICT} (the ProjectError code-map distinguishing — a flat all-NOT_FOUND impl FAILS the 400/409 cases).
- career blog/demo bad-id → 404 flat {error:NOT_FOUND}.
- All flat {error:{code,...}}, NO raw {detail}. Verify on LIVE HTTP (import-cache lesson).
- pytest 0-failed, mypy clean.

## Baseline
pytest = post-HARDENING count (confirm at dispatch). Keep 0-failed.

## Assumptions (user-review)
- **projects+career REST errors → flat agent_error** via the P3 helper. projects ProjectError.code mapped: 400→INVALID_INPUT, 409→CONFLICT, else NOT_FOUND. **How to change:** the code-map in projects/router.py except + the per-route calls.

## Notes
- #46 Phase 4 of the phased audit (P3 done). The only nuance = the ProjectError code-passthrough (map .code→agent_error code). career is trivial. backend EDITS; architect commits fix(sprint-AGENT-ERROR-P4). HOLD until HARDENING commits. Verify LIVE HTTP.
