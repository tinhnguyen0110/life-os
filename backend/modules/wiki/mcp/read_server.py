"""modules/wiki/mcp/read_server.py — MCP READ-only server for the wiki (Sprint W4b).

External Claude Code connects over **stdio** and READS the vault: search, overview,
inbox, ego-graph, get-note, backlinks, recent-ops. It then synthesizes and (via the
SEPARATE write server, W4c) PROPOSES writes into the W4a queue. This server can
NEVER write — that capability split IS the M4 security gate (spec L142/L145).

THE M4 GATE (D-W4b.2 — least-privilege, STRUCTURAL not a flag):
This module imports ONLY:
  - read fns: ``reader`` (search/overview/inbox/ego_graph/backlinks/recent_ops),
    ``service.get_note`` (the read path — no queue),
  - ``proposals_store.append_audit`` — appends to the audit table ONLY; it is NOT a
    vault mutation (write-only-to-its-own-table), so auditing reads does not give
    this server note-write capability.
It does NOT import the write-proposal service layer, nor any note-mutation fn
(create/update/merge/delete), nor the queue ``enqueue``. A test
(test_wiki_mcp_read.py) asserts none of those write symbols are reachable in this
module's namespace — the gate proven by grep+AST, not a docstring claim.

Run:  python -m modules.wiki.mcp.read_server   (stdio; registered in Claude Code config)

NAMING: nested under modules/wiki (not a top-level ``mcp/``) so it doesn't shadow
the SDK at /app — see the package __init__ for why.

NOTE: this module deliberately does NOT use ``from __future__ import annotations``.
FastMCP introspects each tool's parameter annotations at registration via
``issubclass(annotation, Context)`` — with stringized (future) annotations that call
raises ``TypeError: issubclass() arg 1 must be a class``. Real (non-string)
annotations are required for the SDK to build the tool schema.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

# READ-ONLY imports only (the M4 gate — see module docstring + the no-write test).
from modules.wiki import reader
from modules.wiki import proposals_store
from modules.wiki.service import get_note as _get_note

# One correlation id per server process (groups this agent session's calls, D-W4b.3).
SESSION_ID = uuid.uuid4().hex
ACTOR = "mcp:reader"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit(tool: str, params: dict[str, Any]) -> None:
    """Append one audit row per MCP call (D-W4b.3 — spec "every call"). Fail-soft:
    an audit failure must NOT break the read the agent asked for (audit is a
    secondary add-on; the read already succeeded — memory
    fail-closed-write-fail-soft-addon)."""
    try:
        proposals_store.append_audit(
            tool=tool, params=params, actor=ACTOR,
            correlation_id=SESSION_ID, ts=_now_iso(),
        )
    except Exception:  # noqa: BLE001 — audit is best-effort; never break a read
        pass


# --------------------------------------------------------------------------- #
# Tool logic — plain fns returning JSON-serializable dicts. Each = call the      #
# existing read fn + audit. Kept separate from the FastMCP registration so tests #
# can exercise the logic without standing up stdio.                              #
# Every tool returns a dict (never a bare list/None) so the agent gets a stable  #
# envelope; a missing note returns {found: False, ...} not a crash.              #
# --------------------------------------------------------------------------- #
def wiki_search(q: str, limit: int = 30) -> dict[str, Any]:
    """Full-text search the vault → ranked results. Bad/empty/FTS-special ``q`` →
    empty results (reader sanitizes; never raises)."""
    _audit("wiki_search", {"q": q, "limit": limit})
    return {"results": reader.search(q, limit=limit)}


def wiki_overview() -> dict[str, Any]:
    """Vault overview: stats, inbox, orphans, recentActivity, proposalCount."""
    _audit("wiki_overview", {})
    data, warning = reader.overview()
    return {"overview": data, "warning": warning}


def wiki_inbox() -> dict[str, Any]:
    """Fleeting notes awaiting triage (oldest→newest)."""
    _audit("wiki_inbox", {})
    return reader.inbox()


def wiki_graph(note_id: int, depth: int = 2) -> dict[str, Any]:
    """Ego-graph (1–2 hop) around a note: {center, nodes, edges, clusters}. A
    missing center note → {found: False} (not a crash)."""
    _audit("wiki_graph", {"note_id": note_id, "depth": depth})
    g = reader.ego_graph(int(note_id), int(depth))
    if g is None:
        return {"found": False, "note_id": int(note_id)}
    return {"found": True, "graph": g}


def wiki_get_note(note_id: int) -> dict[str, Any]:
    """One note by its INTEGER id (the citation key — the agent cites "note 47",
    D1). A missing note → {found: False} (not a crash)."""
    _audit("wiki_get_note", {"note_id": note_id})
    note = _get_note(int(note_id))
    if note is None:
        return {"found": False, "note_id": int(note_id)}
    return {"found": True, "note": note.model_dump()}


def wiki_backlinks(note_id: int) -> dict[str, Any]:
    """Backlinks for a note: {linked, unlinked, outbound}."""
    _audit("wiki_backlinks", {"note_id": note_id})
    return reader.backlinks(int(note_id))


def wiki_recent_ops(limit: int = 50) -> dict[str, Any]:
    """Recent wiki mutations (the op-log activity feed), newest first."""
    _audit("wiki_recent_ops", {"limit": limit})
    return {"ops": reader.recent_ops(limit=int(limit))}


# Registry of (name → logic fn) — the single source of truth for what tools exist.
# Tests iterate this for parity + audit; FastMCP registration iterates it below.
TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "wiki_search": wiki_search,
    "wiki_overview": wiki_overview,
    "wiki_inbox": wiki_inbox,
    "wiki_graph": wiki_graph,
    "wiki_get_note": wiki_get_note,
    "wiki_backlinks": wiki_backlinks,
    "wiki_recent_ops": wiki_recent_ops,
}


# --------------------------------------------------------------------------- #
# FastMCP server — registers each TOOLS entry as an MCP tool over stdio.         #
# Built lazily in build_server() so importing this module (for tests / the       #
# no-write-capability check) does NOT require the SDK to spin up a server.       #
# --------------------------------------------------------------------------- #
def build_server() -> Any:
    """Construct the FastMCP server with all 7 read tools registered. Separated
    from import so tests can import TOOLS without constructing the server."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("life-os-wiki-read")
    # Register each tool. FastMCP infers the schema from the fn signature +
    # docstring, so the wrappers' type hints + docstrings ARE the tool contract.
    mcp.add_tool(wiki_search, description=wiki_search.__doc__)
    mcp.add_tool(wiki_overview, description=wiki_overview.__doc__)
    mcp.add_tool(wiki_inbox, description=wiki_inbox.__doc__)
    mcp.add_tool(wiki_graph, description=wiki_graph.__doc__)
    mcp.add_tool(wiki_get_note, description=wiki_get_note.__doc__)
    mcp.add_tool(wiki_backlinks, description=wiki_backlinks.__doc__)
    mcp.add_tool(wiki_recent_ops, description=wiki_recent_ops.__doc__)
    return mcp


def main() -> None:
    """stdio entrypoint — Claude Code launches this via its mcp config."""
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
