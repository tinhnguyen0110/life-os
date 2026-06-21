# Sprint AGENT-ERROR-P3 — REST finance+market errors → agent_error (Cairn #46, Phase 3)

> Created 2026-06-21 by architect. #46-family Phase 3 (the REST audit; #61+#14 did wiki note-id 404s, #46-P1/P2 did read_server MCP). HIGH. Phased — P3 = finance+market (highest agent-traffic). backend EDITS; architect commits (§3).

## Context (Rule#0 kickoff)
The MCP twins ALREADY return agent_error (#46-P2: finance_simulate/market_correlation in read_server return `agent_error("INVALID_INPUT",...)`). But the REST routers still `raise HTTPException(detail=str)` raw → REST≠MCP for errors. P3 brings finance+market REST to parity (the heavily-MCP-consumed surfaces). ~16 raw HTTPException across the 2 modules.

## The shared helper (the key reusable decision — pays forward to P4/P5/P6)
ADD to `core/agent_errors.py`:
```python
_CODE_STATUS = {"NOT_FOUND":404, "INVALID_INPUT":422, "AMBIGUOUS":409, "UPSTREAM_DOWN":502, "RATE_LIMITED":429, "CONFLICT":409}
def agent_error_response(code, message, hint="", retryable=None) -> JSONResponse:
    """REST: agent_error as a flat-body JSONResponse with the HTTP status mapped from the code.
    The canonical REST error helper (generalizes wiki's _note_not_found). RETURN it (not raise)."""
    return JSONResponse(status_code=_CODE_STATUS[code], content=agent_error(code, message, hint, retryable))
```
(JSONResponse import in agent_errors.py. wiki's _note_not_found can later be refactored to call this — NOT in P3, keep P3 scoped.)

## Scope
IN: core/agent_errors.py (the agent_error_response helper) + finance/router.py + market/router.py (migrate raw HTTPException → return agent_error_response) + tests.
OUT: other modules (P4+). NO refactor of wiki's _note_not_found (later). NO touching the MCP twins (already agent_error). NO 200-path behavior change.

## Logic/Algorithm (per-site migration — RETURN not raise, like #14)
**finance/router.py:**
- :50 DELETE /holdings/{symbol} 404 → `return agent_error_response("NOT_FOUND", f"no holding {symbol!r}", hint="GET /finance/holdings for valid symbols")`
- :115/119/123 POST /simulate 422 → `return agent_error_response("INVALID_INPUT", <same msg>, hint=<valid set>)` (mirror the MCP twin's wording — read_server finance_simulate already has these exact messages)
- :155 GET /{channel} 404 → `return agent_error_response("NOT_FOUND", f"channel {channel!r} not found", hint="GET /finance for valid channels")`

**market/router.py:**
- :49/68/86/150 "asset not tracked" 404 → `return agent_error_response("NOT_FOUND", f"asset {symbol!r} is not tracked", hint="GET /market for tracked assets")`
- :104/106 correlation 422 → `return agent_error_response("INVALID_INPUT", <msg>, hint=...)` (mirror market_correlation MCP twin)
- :176 backfill 422 → INVALID_INPUT
- :199/234/263 "no alert rule / not in watchlist" 404 → NOT_FOUND
- :225 indicator-alert "asset not tracked" 404 → NOT_FOUND

⚠️ **RETURN not raise** (the #14 nuance) — agent_error_response returns a JSONResponse. In a `raise HTTPException` site, replace with `return agent_error_response(...)`. If the raise is inside a helper that's CALLED (e.g. market's _parse_symbols at :104 raises — used by the route), the helper pattern differs: a raise-in-a-called-helper can't become a return (the caller wouldn't get the Response). For THOSE: either (a) the helper returns a sentinel + the route returns the response, or (b) keep that one as HTTPException but with agent_error as the detail's content via a custom exception handler. SIMPLEST for P3: migrate the in-route raises (return); for raises inside called-helpers (_parse_symbols), note them — if non-trivial, scope to a follow-up. backend judges per-site; flag any that can't cleanly become return.

## Schema/field list
No schema change. Body = agent_error's `{error:{code,message,hint,retryable}}`. Status from _CODE_STATUS.

## Runtime
BE container :8686. pytest = venv. mypy clean. ⚠️ Verify MCP/REST error on the LIVE HTTP surface (curl), NOT an import-process (harness caches stale module — the #43 lesson). curl `POST :8686/finance/simulate` with bad input → flat {error:INVALID_INPUT}.

## Baseline
pytest 1967 (post-#43 origin). Keep 0-failed.

## Test ownership split
You write/update finance+market error tests: each migrated route with bad input → flat `{error:{code,...}}` (NOT raw {detail}), correct status (404/422). Distinguishing: the body has error.code, NOT a "detail" key. + REST now matches its MCP twin's error shape (finance_simulate REST == MCP shape). tester does live curl.

## Verification
finance+market REST errors → flat agent_error (404 NOT_FOUND / 422 INVALID_INPUT), matching their MCP twins. agent_error_response helper reusable (code→status map). pytest 0-failed, mypy clean. Live HTTP curl (not import-cache).

## Ownership
pytest fails = yours; report to team-lead with repro.

## Idle behavior
DONE → SendMessage team-lead + me: stage-list, pytest count (FULL, 0-failed), the per-route distinguishing evidence (live curl flat-error), any raise-in-helper sites flagged for follow-up, git status --porcelain. Blocked → SendMessage team-lead.

## Notes
- #46 Phase 3 of N (phased audit). The agent_error_response helper is the reusable spine for P4+ (projects/career, journal/decision_journal/reminders/notes, the last read_server free-text). architect commits fix(sprint-AGENT-ERROR-P3). Verify on LIVE HTTP (the import-cache lesson).
