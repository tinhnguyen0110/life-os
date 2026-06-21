"""core/agent_errors.py — AGENT-ERROR Phase-1 (#46): a structured, agent-readable error shape.

The MCP tools + API are consumed by an AI AGENT (agent-first-tool-output): when a tool can't do what
was asked, a free-text ``{error: "..."}`` string forces the agent to PARSE prose to decide what to do.
``agent_error`` returns a SELF-DESCRIBING structured error the agent can ACT on directly:

    {"error": {"code": <ErrorCode>, "message": <human>, "hint": <what to do>, "retryable": <bool>}}

- ``code`` — a SMALL CLOSED enum (6) so the agent can branch on a known set, not parse text.
- ``message`` — the human-readable what-went-wrong.
- ``hint`` — what the agent should DO about it ("supply a valid id", "back off and retry", …).
- ``retryable`` — can the SAME call succeed if retried? The agent uses this to decide retry-vs-fix-vs-stop.

THE RETRYABLE INVARIANT (enforced here, not just documented): a DETERMINISTIC failure must NOT be
marked retryable — retrying it is a guaranteed-useless loop. So NOT_FOUND / INVALID_INPUT / CONFLICT
are ALWAYS retryable=False (the helper rejects retryable=True for them). TRANSIENT failures
(UPSTREAM_DOWN / RATE_LIMITED) MAY be retryable=True (the caller decides; default True). AMBIGUOUS
(the input matched >1 thing) is not transient — retrying the same ambiguous input won't help → default
False (the agent must disambiguate, not retry).

Phase 1 = this helper + the enum + tests ONLY. NO per-server migration (Phase 2+, worst-offender
first), and this does NOT touch ``found: False`` — a not-found RESULT (e.g. wiki_get_note of a missing
id) is a normal answer, NOT an error; agent_error is for "the tool could not perform the operation".
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, get_args

if TYPE_CHECKING:
    from fastapi.responses import JSONResponse

# The closed set the agent branches on. Keep SMALL — a new code is a deliberate addition, not a
# free-for-all (a sprawling enum is as unreadable as free text).
ErrorCode = Literal[
    "NOT_FOUND",      # the referenced thing doesn't exist (a wrong id passed as an operation target)
    "INVALID_INPUT",  # the input is malformed / out of range / wrong type
    "AMBIGUOUS",      # the input matched MORE THAN ONE thing — the agent must disambiguate
    "UPSTREAM_DOWN",  # a dependency (feed/network/external service) is unavailable
    "RATE_LIMITED",   # throttled — back off and retry later
    "CONFLICT",       # the operation conflicts with current state (e.g. already-decided, duplicate)
]

# Deterministic failures: the SAME call will fail the SAME way → retrying is a useless loop, so these
# are ALWAYS retryable=False (the helper enforces it). The agent must FIX the input / target, not retry.
_NEVER_RETRYABLE: frozenset[str] = frozenset({"NOT_FOUND", "INVALID_INPUT", "CONFLICT"})

# Transient failures MAY succeed on retry (the caller decides; default True for these). AMBIGUOUS is
# NOT transient (same ambiguous input → same ambiguity) → defaults False.
_RETRYABLE_DEFAULT: dict[str, bool] = {
    "UPSTREAM_DOWN": True,
    "RATE_LIMITED": True,
    "AMBIGUOUS": False,
    "NOT_FOUND": False,
    "INVALID_INPUT": False,
    "CONFLICT": False,
}


def agent_error(
    code: ErrorCode,
    message: str,
    hint: str = "",
    retryable: bool | None = None,
) -> dict[str, Any]:
    """Build the agent-readable error envelope (see module docstring).

    ``retryable`` defaults per code (transient codes → True, deterministic → False). The DETERMINISTIC
    codes (NOT_FOUND/INVALID_INPUT/CONFLICT) are ALWAYS retryable=False — passing retryable=True for
    one is a programming error (retrying a deterministic failure loops forever) → raises ValueError.

    Returns ``{"error": {"code", "message", "hint", "retryable"}}``. ``code`` is validated against the
    closed ErrorCode enum (an unknown code → ValueError, never a silent bad-code).
    """
    if code not in get_args(ErrorCode):
        raise ValueError(f"unknown error code {code!r}; must be one of {get_args(ErrorCode)}")

    resolved = _RETRYABLE_DEFAULT[code] if retryable is None else bool(retryable)
    if code in _NEVER_RETRYABLE and resolved:
        raise ValueError(
            f"error code {code!r} is deterministic — retryable must be False "
            f"(retrying a {code} loops forever; fix the input/target instead)"
        )

    return {
        "error": {
            "code": code,
            "message": message,
            "hint": hint,
            "retryable": resolved,
        }
    }


# AGENT-ERROR-P3 (#46): the REST status code each error code maps to. NOT_FOUND→404, bad-input→422,
# AMBIGUOUS/CONFLICT→409, upstream→502, throttle→429. (No auth → no 401/403 — single-user.)
_CODE_STATUS: dict[str, int] = {
    "NOT_FOUND": 404,
    "INVALID_INPUT": 422,
    "AMBIGUOUS": 409,
    "UPSTREAM_DOWN": 502,
    "RATE_LIMITED": 429,
    "CONFLICT": 409,
}


def agent_error_response(
    code: ErrorCode,
    message: str,
    hint: str = "",
    retryable: bool | None = None,
) -> "JSONResponse":
    """AGENT-ERROR-P3 (#46): the agent_error body as a flat-body REST JSONResponse with the HTTP
    status mapped from the code (the canonical REST error helper — generalizes wiki's _note_not_found).
    RETURN it from a route (it's a Response, NOT an exception — do not raise). The body is the flat
    ``{error:{code,message,hint,retryable}}`` (not nested under "detail"), byte-identical to the MCP
    twins' agent_error → REST≡MCP error parity. Reuses agent_error (incl. its retryable invariant +
    unknown-code guard)."""
    from fastapi.responses import JSONResponse  # local import: core shouldn't hard-depend on fastapi at import
    return JSONResponse(status_code=_CODE_STATUS[code], content=agent_error(code, message, hint, retryable))
