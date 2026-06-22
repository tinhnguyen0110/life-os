"""mcp_servers/reminders_server.py — per-domain lifeos-reminders MCP server (REMINDERS-2 #28).

A specialized "reminders agent" connects to THIS server's mount (``/mcp/reminders``) and gets the
reminders working set: read the agenda + CREATE + TICK reminders. Clones the per-domain pattern
(lifeos-finance), with one deliberate difference: reminders are a WRITABLE domain.

THE CAPABILITY DECISION (A, team-lead-locked): reminders are single-user, REVERSIBLE CRUD with
NO trust boundary → DIRECT write-through (no proposal gate). So unlike the whole-app write-server
(which is STRUCTURALLY enqueue-ONLY — its AST gate forbids any note-mutation import), this
per-domain server is ALLOWED to call ``modules.reminders.service.create``/``tick`` directly. The
two are the inverse of each other: the write-server CANNOT mutate (it enqueues); lifeos-reminders
CAN mutate (direct, reversible, single-user). Keeping reminder writes OFF the whole-app
write-server preserves that server's no-mutate gate.

Tools:
  - ``reminders_list``  — the SAME read fn as the main read-server (reference-imported → is-identity:
    a read agent sees the agenda on lifeos-read OR lifeos-reminders, one fn, no drift).
  - ``reminder_create`` — DIRECT write-through: create a reminder, return the real Reminder (+id).
  - ``reminder_tick``   — DIRECT write-through: mark done (idempotent), return the Reminder.

NOTE: like the other MCP servers, this module deliberately does NOT use
``from __future__ import annotations`` — FastMCP introspects REAL (non-string) param annotations
at registration; stringized annotations crash that introspection.
"""

from typing import Any, Callable

from mcp_servers.read_server import reminders_channels as _reminders_channels
from mcp_servers.read_server import reminders_list as _reminders_list
from modules.reminders import service as _reminders_service
from modules.reminders.schema import ReminderInput


def reminder_create(title: str, due_at: str, note: str | None = None,
                    repeat: str = "once", re_notify_every: int | None = None,
                    max_times: int | None = None,
                    channel: str = "in_app") -> dict[str, Any]:
    """Create a reminder — DIRECT write-through (no proposal gate; reversible single-user CRUD).
    Returns the real Reminder (with its ``id``) so the agent can immediately read it back (MCP≡REST,
    same service.create the REST POST /reminders uses). ``due_at`` is validated + UTC-normalized by
    the frozen #27 ReminderInput validator (a blank title / unparseable due_at raises → the agent
    sees the validation error, no row stored). ``repeat`` ∈ once|daily|weekly.

    #111 ``channel`` ∈ in_app|email|discord (default in_app; a bad value raises via the Literal). An
    email/discord channel that is NOT configured FALLS BACK to in_app + a ``warning`` (honest-mirror,
    same as REST POST /reminders — the reminder is created, the warning explains the downgrade).
    Read the available channels first via reminders_channels."""
    inp = ReminderInput(
        title=title, due_at=due_at, note=note, repeat=repeat,  # type: ignore[arg-type]
        re_notify_every=re_notify_every, max_times=max_times, channel=channel,  # type: ignore[arg-type]
    )
    inp, warning = _reminders_service.resolve_channel(inp)  # #111 unavailable→in_app+warning
    reminder = _reminders_service.create(inp)
    out: dict[str, Any] = {"created": True, "id": reminder.id, "reminder": reminder.model_dump()}
    if warning:
        out["warning"] = warning
    return out


def reminder_tick(reminder_id: int) -> dict[str, Any]:
    """Mark a reminder done — DIRECT write-through, IDEMPOTENT (re-ticking keeps the first done_at,
    no-op, not an error; reuses service.tick). Returns ``{found, reminder}``; found=False if the
    reminder doesn't exist (honest, not a crash)."""
    reminder = _reminders_service.tick(int(reminder_id))
    if reminder is None:
        return {"found": False, "id": int(reminder_id)}
    return {"found": True, "id": reminder.id, "reminder": reminder.model_dump()}


# Registry of (name → fn). reminders_list IS the read-server's own fn object (is-identity, the
# per-domain anti-dup spine); reminder_create/tick are this server's write tools (direct CRUD).
TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "reminders_list": _reminders_list,   # reference-imported → is read_server.reminders_list
    "reminders_channels": _reminders_channels,  # #111 reference-imported → is read_server.reminders_channels
    "reminder_create": reminder_create,
    "reminder_tick": reminder_tick,
}


def build_server(transport_security: Any = None, stateless_http: bool = False) -> Any:
    """Construct the FastMCP lifeos-reminders server with the 3 reminder tools registered.
    Identical shape to finance_server.build_server (transport_security / stateless_http threaded
    through so main.py can mount over streamable-http; defaults = stdio-identical)."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("life-os-reminders", transport_security=transport_security,
                  stateless_http=stateless_http)
    for fn in TOOLS.values():
        mcp.add_tool(fn, description=fn.__doc__)
    return mcp


def main() -> None:
    """stdio entrypoint — a reminders agent can launch this via its mcp config as `lifeos-reminders`."""
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
