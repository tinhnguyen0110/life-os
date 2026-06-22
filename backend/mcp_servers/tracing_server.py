"""mcp_servers/tracing_server.py — per-domain lifeos-tracing MCP server (DAILY-TRACING-P2 #65).

A specialized "habit/tracking agent" connects to THIS server's mount (``/mcp/tracing``) and gets the
tracing working set: read the board ("what did I do today / my streaks") + LOG a session ("ran 5km").
Clones the per-domain pattern (lifeos-reminders), a WRITABLE domain.

THE CAPABILITY DECISION (mirrors reminders): tracing logs are single-user, append-only, REVERSIBLE
data with NO trust boundary → DIRECT write-through (no proposal gate). So unlike the whole-app
write-server (STRUCTURALLY enqueue-ONLY — its AST gate forbids note-mutation imports), this
per-domain server is ALLOWED to call ``modules.tracing.service.log_session`` directly. Keeping
tracing writes OFF the whole-app write-server preserves that server's no-mutate gate.

Tools:
  - ``tracing_overview`` — the SAME read fn as the main read-server (reference-imported → is-identity:
    a read agent sees the board on lifeos-read OR lifeos-tracing, one fn, no drift).
  - ``tracing_log``      — DIRECT write-through: log a session, return the activity's updated view
    (today/streak reflect the new session) so the agent reads back the effect immediately.

NOTE: like the other MCP servers, this module deliberately does NOT use
``from __future__ import annotations`` — FastMCP introspects REAL (non-string) param annotations at
registration; stringized annotations crash that introspection.
"""

from typing import Any, Callable

from mcp_servers.read_server import tracing_overview as _tracing_overview
from mcp_servers.read_server import tracing_templates as _tracing_templates  # #109 prefill templates
from modules.tracing import service as _tracing_service
from modules.tracing.schema import LogInput


def tracing_log(activity_id: str, val: float, dur_min: int | None = None,
                note: str | None = None) -> dict[str, Any]:
    """Log one session against an activity — DIRECT write-through (no proposal gate; reversible
    single-user data). date defaults to today-VN; multiple logs the same day ACCUMULATE (summed).
    Returns ``{logged, activity}`` where ``activity`` is the freshly-DERIVED ActivityView (today/
    streak reflect the new session) so the agent reads the effect back immediately (MCP≡REST, same
    service.log_session the REST POST /tracing/{id}/log uses). Unknown activity_id → ``{found:False,
    activityId}`` (honest existence-contract, NOT a crash — like reminder_tick). val<0 → the LogInput
    validator raises (the agent sees the validation error, no row stored)."""
    if _tracing_service.get_activity(activity_id) is None:
        return {"found": False, "activityId": activity_id}
    inp = LogInput(val=val, dur_min=dur_min, note=note)  # val<0 raises here → agent sees it
    view = _tracing_service.log_session(activity_id, inp)
    return {"logged": True, "activityId": activity_id, "activity": view.model_dump()}


# Registry of (name → fn). tracing_overview IS the read-server's own fn object (is-identity, the
# per-domain anti-dup spine); tracing_log is this server's write tool (direct append).
TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "tracing_overview": _tracing_overview,  # reference-imported → is read_server.tracing_overview
    "tracing_templates": _tracing_templates,  # #109 reference-imported → is read_server.tracing_templates
    "tracing_log": tracing_log,
}


def build_server(transport_security: Any = None, stateless_http: bool = False) -> Any:
    """Construct the FastMCP lifeos-tracing server with the 2 tracing tools registered. Identical
    shape to reminders_server.build_server (transport_security / stateless_http threaded through so
    main.py can mount over streamable-http; defaults = stdio-identical)."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("life-os-tracing", transport_security=transport_security,
                  stateless_http=stateless_http)
    for fn in TOOLS.values():
        mcp.add_tool(fn, description=fn.__doc__)
    return mcp


def main() -> None:
    """stdio entrypoint — a tracking agent can launch this via its mcp config as `lifeos-tracing`."""
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
