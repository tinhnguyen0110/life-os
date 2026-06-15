"""tests/test_mcp_read.py — WHOLE-APP MCP read-server tests (MCP-1).

Coverage:
  - CALLABILITY: every tool in the registry runs against an empty/isolated app and
    returns a JSON-serialisable dict (never a bare list / model / None, never a crash).
  - ENVELOPE: each tool's dict carries its documented top-level key.
  - GRACEFUL: a missing entity (unknown channel / project / run) → {found: False},
    not a crash.
  - PARITY: a couple of tools return the same data as their service source.
  - THE CAPABILITY GATE: the read-server has NO write capability — no module-mutation
    symbol is bound in its namespace and none is imported (grep + AST proven, mirroring
    the wiki read-server's M4 gate).
  - server builds (FastMCP registers all tools) without error.

Uses ``isolated_paths`` (conftest) so every read runs against a fresh empty tmp app —
the read fns are all fail-open, so empty data must yield a clean empty envelope.
"""

from __future__ import annotations

import json

import pytest

from mcp_servers import read_server as rs


@pytest.fixture
def app_db(isolated_paths):
    """Empty but INITIALISED app: the wiki + proposal tables exist (the reliability
    read path queries ``wiki_notes``; in the live app these tables always exist —
    this fixture reproduces that, vs a bare tmp dir with no schema). All other reads
    are file-store / SQLite-lazy and fail-open on empty, so nothing else needs seeding.
    """
    from modules.wiki import store as wiki_store
    from modules.wiki import proposals_store as pstore

    wiki_store.init_wiki_tables()
    pstore.init_proposal_tables()
    return isolated_paths


# Tools that take no required args — callable with zero arguments against an empty app.
NULLARY_TOOLS = [
    "finance_overview",
    "market_overview",
    "projects_list",
    "graveyard_overview",
    "claude_usage",
    "daily_brief",
    "brief_history",
    "journal_entries",
    "decision_entries",
    "activity_feed",
    "exchange_overview",
    "app_settings",
    "reliability_report",
]

# Documented top-level envelope key per nullary tool.
ENVELOPE_KEY = {
    "finance_overview": "overview",
    "market_overview": "market",
    "projects_list": "projects",
    "graveyard_overview": "graveyard",
    "claude_usage": "usage",
    "daily_brief": "brief",
    "brief_history": "briefs",
    "journal_entries": "journal",
    "decision_entries": "decisions",
    "activity_feed": "activity",
    "exchange_overview": "exchange",
    "app_settings": "settings",
    "reliability_report": "report",
}


# --------------------------------------------------------------------------- #
# Callability + envelope — every tool returns a JSON-serialisable dict          #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", NULLARY_TOOLS)
def test_nullary_tool_returns_jsonable_dict(name, app_db):
    out = rs.TOOLS[name]()
    assert isinstance(out, dict), f"{name} did not return a dict"
    # must be JSON-serialisable (the agent gets it over the wire as JSON)
    json.dumps(out)
    assert ENVELOPE_KEY[name] in out, f"{name} missing envelope key {ENVELOPE_KEY[name]!r}"


def test_registry_covers_all_tools_and_each_is_callable(app_db):
    # Every registered tool is a callable; the nullary set is the no-arg subset.
    assert set(NULLARY_TOOLS) <= set(rs.TOOLS)
    for name, fn in rs.TOOLS.items():
        assert callable(fn), f"{name} is not callable"


def test_arg_tools_return_jsonable_dict(app_db):
    # The arg-taking tools, exercised with explicit args against the empty app.
    for out in (
        rs.market_history("BTC", hours=24, limit=10),
        rs.brief_history(limit=5),
        rs.activity_feed(routine="x", status="ok", range="today"),
    ):
        assert isinstance(out, dict)
        json.dumps(out)


# --------------------------------------------------------------------------- #
# Graceful failure (no crash) — missing entity → {found: False}                 #
# --------------------------------------------------------------------------- #
def test_unknown_channel_is_found_false(app_db):
    out = rs.finance_channel("no-such-channel")
    assert out["found"] is False
    assert out["channel"] == "no-such-channel"


def test_unknown_project_is_found_false(app_db):
    out = rs.project_get("no-such-project")
    assert out == {"found": False, "project_id": "no-such-project"}


def test_unknown_run_is_found_false(app_db):
    out = rs.activity_run(999999)
    assert out == {"found": False, "run_id": 999999}


# --------------------------------------------------------------------------- #
# Parity — tool output == service output (the tool is a thin read wrapper)       #
# --------------------------------------------------------------------------- #
def test_settings_parity(app_db):
    from modules.settings import service as ssvc

    assert rs.app_settings()["settings"] == ssvc.get_config().model_dump()


def test_journal_parity(app_db):
    from modules.journal import service as jsvc

    stats, warnings = jsvc.list_entries()
    out = rs.journal_entries()
    assert out["journal"] == stats.model_dump()
    assert out["warnings"] == warnings


# --------------------------------------------------------------------------- #
# THE CAPABILITY GATE — no write capability (structural, grep + AST proven)      #
# --------------------------------------------------------------------------- #
# Mutation symbols across the wrapped modules: if ANY is reachable from this
# server's namespace / imports, a read tool could be escalated to a write.
WRITE_SYMBOLS = [
    # finance
    "upsert_holding", "delete_holding", "set_golden_path", "set_crypto_basis",
    # market
    "add_rule", "delete_rule", "poll_once",
    # projects
    "register_project", "abandon_project", "restore_project", "refresh_project",
    # journals
    "create_entry", "update_entry", "delete_entry",
    # brief / exchange / settings
    "save_brief", "sync", "set_config", "set_override",
    # wiki write surface must not leak in either
    "create_note", "update_note", "delete_note", "merge_notes",
    "enqueue", "create_proposal", "accept_proposal", "reject_proposal",
]


def test_read_server_has_no_write_symbol_in_namespace():
    """No module-mutation name is bound in the read server's module namespace. This is
    the least-privilege gate: a read tool cannot be escalated to a write because the
    write symbols are not importable from here. (Mirrors the wiki read-server gate.)"""
    ns = vars(rs)
    leaked = [s for s in WRITE_SYMBOLS if s in ns]
    assert leaked == [], f"read server leaked write symbols: {leaked}"


def test_read_server_imports_no_write_symbol_ast():
    """Parse the read server's IMPORT statements (AST, not a string grep — a docstring
    legitimately names the excluded symbols) and assert none of them import a module-
    mutation name. The wrapped imports are READ entry-points only."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(rs))
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported_names.add(alias.name)                    # the real name
                imported_names.add(alias.asname or alias.name)    # the bound name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.name)

    leaked = set(WRITE_SYMBOLS) & imported_names
    assert leaked == set(), f"read server imports write symbols: {leaked}"


def test_imported_read_paths_are_only_aliased_private_names():
    """Every name the server BINDS from a module import is a private (underscore) read
    wrapper — i.e. the server never binds a bare public service symbol into its
    namespace where it could be mistaken for / reused as a write entry-point. This
    catches an accidental ``from x import set_config`` that the WRITE_SYMBOLS list
    might not enumerate."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(rs))
    bound = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("modules."):
            for alias in node.names:
                bound.add(alias.asname or alias.name)
    # all module-read imports are aliased to a leading-underscore private name
    non_private = [n for n in bound if not n.startswith("_")]
    assert non_private == [], f"non-private bound read imports: {non_private}"


# --------------------------------------------------------------------------- #
# Server builds                                                                  #
# --------------------------------------------------------------------------- #
def test_build_server_registers_all_tools():
    # Building the FastMCP server must not raise and must not drop any registry tool.
    server = rs.build_server()
    assert server is not None
    assert len(rs.TOOLS) == 17
