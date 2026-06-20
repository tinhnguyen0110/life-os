"""mcp_servers/finance_server.py — NARROW finance-domain MCP READ server (MCP-DOMAINS T1).

A specialized agent (the "finance agent") should see ONLY finance-domain tools, not the
whole 40-tool read surface. This server exposes a CURATED 15-tool subset by
REFERENCE-IMPORTING the exact tool fns from ``mcp_servers.read_server`` — NO logic is
re-implemented here, so a finance tool is byte-identical to the same tool on ``/mcp/read``
and can never drift (it's the same fn object).

This is PURELY ADDITIVE (MCP-DOMAINS, user request "agent tài chính chỉ thấy tool tài
chính"): the existing 4 servers are UNCHANGED — ``read_server`` keeps all 40 tools as the
full-access surface. An agent that wants only finance connects to THIS server's mount
(``/mcp/finance``) and gets the 15 below; an agent that wants everything keeps using
``/mcp/read``.

THE CAPABILITY GATE (inherited STRUCTURALLY, not re-asserted):
Every fn here is the SAME object imported by ``read_server`` — read_server's own no-write
capability gate (it imports zero mutation symbols) therefore covers these too. This module
binds NO module-level tool fn of its own; it only re-references read_server's. So the
"no mutation symbol bound" property holds here by construction.

The curated 15 (finance ×6 + decision-tower ×4 + macro ×2 + market ×3 ... = the finance
agent's working set):
  finance:        finance_overview, finance_channel, finance_analytics, finance_simulate,
                  finance_guardian, exchange_overview
  decision-tower: decision_weight, allocation_target, macro_cycle, nav_history
  macro:          macro_overview
  market:         market_overview, market_summary, market_indicators
  trade journal:  journal_entries

Run:  python -m mcp_servers.finance_server   (stdio; can be registered as `lifeos-finance`)

NOTE: like ``read_server``, this module deliberately does NOT use
``from __future__ import annotations``. FastMCP introspects each tool's REAL (non-string)
param annotations at registration; stringized (future) annotations crash that introspection.
The fns we register are read_server's own, so their real annotations must remain real here too.
"""

from typing import Any, Callable

from mcp_servers import read_server as _read_server

# The curated finance-domain tool NAMES. Each MUST exist in read_server.TOOLS — the
# dict below references read_server's own fn objects by these keys, so there is zero
# re-implementation and the identity (`finance_server.TOOLS[n] is read_server.TOOLS[n]`)
# holds by construction. Order is the natural finance reading order, not significant.
_FINANCE_TOOL_NAMES: tuple[str, ...] = (
    # finance core (×6)
    "finance_overview",
    "finance_channel",
    "finance_analytics",
    "finance_simulate",
    "finance_guardian",
    "exchange_overview",
    # decision tower (×4)
    "decision_weight",
    "allocation_target",
    "macro_cycle",
    "nav_history",
    # macro context (×1)
    "macro_overview",
    # market (×3)
    "market_overview",
    "market_summary",
    "market_indicators",
    # trade journal (×1)
    "journal_entries",
)


def _build_tools() -> dict[str, Callable[..., dict[str, Any]]]:
    """Reference-resolve each curated name to read_server's own fn object.

    Raises KeyError at import if any name is missing from read_server.TOOLS — that is a
    loud, intended failure: a curated finance name that no longer exists upstream must
    break the build, not silently shrink the surface.
    """
    return {name: _read_server.TOOLS[name] for name in _FINANCE_TOOL_NAMES}


# Registry of (name → logic fn) — the SAME fn objects as read_server.TOOLS (no copies).
# Tests iterate this for the 15-count + identity (is) + no-reimpl (__module__) gates;
# FastMCP registration iterates it below.
TOOLS: dict[str, Callable[..., dict[str, Any]]] = _build_tools()


def build_server(transport_security: Any = None, stateless_http: bool = False) -> Any:
    """Construct the FastMCP server with the 15 finance read tools registered.

    Identical shape to ``read_server.build_server`` (separated from import so tests can
    import TOOLS without spinning up the SDK). FastMCP infers each tool's schema from the
    fn signature + docstring — and since these are read_server's own fns, the schemas are
    byte-identical to the same tools on ``/mcp/read``.

    ``transport_security`` (default None = stdio-identical) is passed through so main.py can
    mount this over streamable-http with DNS-rebinding protection OFF for remote/LAN clients.

    ``stateless_http`` (default False = stdio-identical) → MCP-STATELESS: True = no per-session
    state, so a backend RESTART does not drop HTTP clients. These are read-only tools (pure
    request/response, no server-push/subscribe), so stateless loses nothing. main.py passes
    True for the HTTP mount.
    """
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("life-os-finance", transport_security=transport_security,
                  stateless_http=stateless_http)
    for fn in TOOLS.values():
        mcp.add_tool(fn, description=fn.__doc__)
    return mcp


def main() -> None:
    """stdio entrypoint — a finance agent can launch this via its mcp config as `lifeos-finance`."""
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
