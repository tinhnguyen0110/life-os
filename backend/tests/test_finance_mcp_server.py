"""tests/test_finance_mcp_server.py — MCP-DOMAINS T1: the narrow lifeos-finance MCP server.

The finance server is a CURATED 15-tool subset that REFERENCE-IMPORTS read_server's own fns
(no logic duplication). These tests are the anti-dup gates:
  (1) TOOLS == exactly the 15 expected names (count + exact set).
  (2) IDENTITY: every finance TOOLS value IS the same object as read_server.TOOLS[name]
      (a copy/reimpl would fail `is`). This is THE no-drift guarantee.
  (3) NO-REIMPL: every TOOLS value's __module__ == "mcp_servers.read_server" (proves it's
      the imported fn, not a redefinition in finance_server).
  (4) build_server() registers exactly 15 tools on the FastMCP.
  (5) no `from __future__ import annotations` (FastMCP needs real annotations) — same AST
      check the other servers have.
"""

from __future__ import annotations

import ast
import inspect

import mcp_servers.finance_server as fs
import mcp_servers.read_server as rs


# The EXACT 15 finance-domain tool names (team-lead approved, dispatch §Schema). Kept here
# as the authoritative set so a drift in either direction (added or removed) fails loudly.
EXPECTED_FINANCE_TOOLS = {
    "finance_overview",
    "finance_channel",
    "finance_analytics",
    "finance_simulate",
    "finance_guardian",
    "exchange_overview",
    "decision_weight",
    "allocation_target",
    "macro_cycle",
    "nav_history",
    "macro_overview",
    "market_overview",
    "market_summary",
    "market_indicators",
    "journal_entries",
}


# --------------------------------------------------------------------------- #
# (1) exact 15-name set                                                         #
# --------------------------------------------------------------------------- #
def test_finance_tools_count_is_15():
    assert len(fs.TOOLS) == 15, f"expected 15 finance tools, got {len(fs.TOOLS)}: {sorted(fs.TOOLS)}"


def test_finance_tools_name_set_exact():
    """The curated set is EXACTLY the 15 — no extra, none missing (catches both directions)."""
    assert set(fs.TOOLS.keys()) == EXPECTED_FINANCE_TOOLS, (
        f"finance tool set drifted.\n  extra:   {set(fs.TOOLS) - EXPECTED_FINANCE_TOOLS}\n"
        f"  missing: {EXPECTED_FINANCE_TOOLS - set(fs.TOOLS)}"
    )


# --------------------------------------------------------------------------- #
# (2) IDENTITY — the anti-dup spine: same fn object as read_server, not a copy  #
# --------------------------------------------------------------------------- #
def test_every_finance_tool_is_the_read_server_fn():
    """For EVERY curated name, finance_server.TOOLS[name] IS read_server.TOOLS[name] (the
    SAME object). A reimplemented/copied fn would be a different object and fail `is` — so
    this is the structural proof of zero duplication (the finance tool can't drift from the
    read tool because it's literally the same callable)."""
    for name in EXPECTED_FINANCE_TOOLS:
        assert name in rs.TOOLS, f"{name!r} curated for finance but not in read_server.TOOLS"
        assert fs.TOOLS[name] is rs.TOOLS[name], (
            f"finance tool {name!r} is NOT the read_server fn object — duplication/drift"
        )


def test_identity_explicit_for_two_representative_tools():
    """Explicit `is` on a representative finance tool and a market tool (per dispatch — at
    minimum these two), in addition to the loop above. Belt-and-suspenders on the two the
    tester also cross-checks via the live /mcp/finance vs /mcp/read payload."""
    assert fs.TOOLS["finance_overview"] is rs.TOOLS["finance_overview"]
    assert fs.TOOLS["market_indicators"] is rs.TOOLS["market_indicators"]


# --------------------------------------------------------------------------- #
# (3) NO-REIMPL — every value lives in read_server, none redefined here         #
# --------------------------------------------------------------------------- #
def test_no_tool_fn_redefined_in_finance_server():
    """Every finance TOOLS value's __module__ is read_server — i.e. it's the imported fn,
    not a fn redefined inside finance_server. (Complements the `is` check: even a fn that
    happened to compare equal would be caught here if it lived in the wrong module.)"""
    for name, fn in fs.TOOLS.items():
        assert getattr(fn, "__module__", None) == "mcp_servers.read_server", (
            f"finance tool {name!r} __module__={getattr(fn, '__module__', None)!r} — "
            f"must be the imported mcp_servers.read_server fn, not a local redefinition"
        )


def test_finance_server_defines_no_local_tool_callables():
    """finance_server's own module namespace must not bind any of the 15 tool NAMES to a
    local callable (it should only re-reference them inside TOOLS). Guards against someone
    later pasting a tool body into this module."""
    for name in EXPECTED_FINANCE_TOOLS:
        bound = getattr(fs, name, None)
        # the name may legitimately be unbound at module level (we reference via the dict);
        # if it IS bound, it must be the read_server fn, never a local def.
        if bound is not None:
            assert bound is rs.TOOLS[name], (
                f"finance_server binds {name!r} to a non-read_server object — looks like a local def"
            )


# --------------------------------------------------------------------------- #
# (4) build_server() registers exactly 15                                       #
# --------------------------------------------------------------------------- #
def test_build_server_registers_15_tools():
    """build_server() (stdio path, default args) returns a FastMCP with all 15 registered."""
    srv = fs.build_server()
    assert srv is not None and type(srv).__name__ == "FastMCP"
    assert len(srv._tool_manager.list_tools()) == 15
    # the registered tool names match the curated set (FastMCP registers by fn name)
    registered = {t.name for t in srv._tool_manager.list_tools()}
    assert registered == EXPECTED_FINANCE_TOOLS, (
        f"registered names != curated set: extra {registered - EXPECTED_FINANCE_TOOLS}, "
        f"missing {EXPECTED_FINANCE_TOOLS - registered}"
    )


def test_build_server_default_is_stdio_identical():
    """build_server() with no arg (stdio) and with transport_security=None both build — the
    default keeps the stdio main() entrypoint behaviourally unchanged (same as the others)."""
    assert fs.build_server() is not None
    assert fs.build_server(transport_security=None) is not None


# --------------------------------------------------------------------------- #
# (5) no `from __future__ import annotations` in finance_server                 #
# --------------------------------------------------------------------------- #
def test_no_future_annotations_in_finance_server():
    """FastMCP introspects REAL param annotations (stringized annotations crash issubclass).
    finance_server must NOT add `from __future__ import annotations`. AST check (a real
    ImportFrom node), not a substring — the module MENTIONS the string in its docstring."""
    tree = ast.parse(inspect.getsource(fs))
    future_imports = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.module == "__future__"
        and any(a.name == "annotations" for a in n.names)
    ]
    assert not future_imports, (
        "finance_server must NOT `from __future__ import annotations` (FastMCP introspection)"
    )
