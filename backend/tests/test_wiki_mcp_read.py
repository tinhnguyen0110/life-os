"""tests/test_wiki_mcp_read.py — MCP READ-only server tests (Sprint W4b).

Coverage:
  - PARITY: each tool returns the same data as its REST/reader source.
  - THE M4 GATE: the read server has NO write capability — no mutation/enqueue
    symbol is reachable in its module namespace (grep-proven, not a docstring).
  - AUDIT: every tool call appends one wiki_mcp_audit row (actor=mcp:reader).
  - graceful: a missing note → {found: False}, never a crash; bad FTS query → no crash.
  - server builds (FastMCP registers all 7 tools) without error.

Mirrors the wiki fixture: rebind the connection → re-register wiki + proposal tables.
"""

from __future__ import annotations

import pytest

from modules.wiki import proposals_store as pstore
from modules.wiki import reader
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.schema import NoteCreateInput
from modules.wiki.mcp import read_server


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    pstore.init_proposal_tables()
    # WIKI-WRITE-THROUGH (#25): the DEFAULT is now write-through (writes auto-apply, no pending
    # row). These proposal-READBACK tests need PENDING proposals in the queue to read back, so set
    # the toggle OFF (proposals-only) for this file — the readback tools are exercised against the
    # pending queue exactly as before the default flip.
    from modules.settings import service as _ssvc
    from modules.settings.schema import AppConfigPatch as _Patch
    _ssvc.set_config(_Patch(wikiAgentAutonomous=False))
    return isolated_paths


def _seed_linked_pair() -> tuple[int, int]:
    """Two notes, a→b linked, so graph/backlinks/search have real data."""
    b = wsvc.create_note(NoteCreateInput(title="Target note", content="target body")).id
    a = wsvc.create_note(NoteCreateInput(title="Source note", content=f"see [[{b}]]")).id
    return a, b


# --------------------------------------------------------------------------- #
# Parity — tool output == reader/service output                                 #
# --------------------------------------------------------------------------- #
def test_search_parity(wiki_db):
    _seed_linked_pair()
    assert read_server.wiki_search("note")["results"] == reader.search("note")


def _drop_volatile(ov: dict) -> dict:
    """overview embeds a fresh ``stats.asOf`` timestamp on every call, so two calls
    never compare equal byte-for-byte. Drop it to assert STRUCTURAL parity."""
    ov = {**ov, "stats": {k: v for k, v in ov["stats"].items() if k != "asOf"}}
    return ov


def test_overview_parity(wiki_db):
    _seed_linked_pair()
    data, warning = reader.overview()
    tool = read_server.wiki_overview()
    # structural parity (asOf is a per-call timestamp — excluded from the compare)
    assert _drop_volatile(tool["overview"]) == _drop_volatile(data)
    assert tool["warning"] == warning


def test_inbox_parity(wiki_db):
    _seed_linked_pair()
    assert read_server.wiki_inbox() == reader.inbox()


def test_graph_parity(wiki_db):
    a, _ = _seed_linked_pair()
    tool = read_server.wiki_graph(a)
    assert tool["found"] is True and tool["graph"] == reader.ego_graph(a, 2)


def test_get_note_parity(wiki_db):
    a, _ = _seed_linked_pair()
    tool = read_server.wiki_get_note(a)
    assert tool["found"] is True and tool["note"] == wsvc.get_note(a).model_dump()


def test_backlinks_parity(wiki_db):
    a, b = _seed_linked_pair()
    assert read_server.wiki_backlinks(b) == reader.backlinks(b)


def test_recent_ops_parity(wiki_db):
    _seed_linked_pair()
    assert read_server.wiki_recent_ops()["ops"] == reader.recent_ops()


# --------------------------------------------------------------------------- #
# Graceful failure (no crash)                                                   #
# --------------------------------------------------------------------------- #
def test_get_missing_note_is_found_false(wiki_db):
    assert read_server.wiki_get_note(99999) == {"found": False, "note_id": 99999}


def test_graph_missing_note_is_found_false(wiki_db):
    assert read_server.wiki_graph(99999) == {"found": False, "note_id": 99999}


def test_bad_fts_query_does_not_crash(wiki_db):
    # FTS-special chars — reader sanitizes; tool must not raise.
    assert read_server.wiki_search('"))((* AND OR')["results"] == []


# --------------------------------------------------------------------------- #
# Audit — one row per call (D-W4b.3)                                            #
# --------------------------------------------------------------------------- #
def test_each_tool_call_audits(wiki_db):
    a, b = _seed_linked_pair()
    sess = read_server.SESSION_ID
    before = len(pstore.recent_audit(correlation_id=sess, limit=1000))
    read_server.wiki_search("x")
    read_server.wiki_overview()
    read_server.wiki_get_note(a)
    rows = pstore.recent_audit(correlation_id=sess, limit=1000)
    assert len(rows) == before + 3
    tools = {r["tool"] for r in rows}
    assert {"wiki_search", "wiki_overview", "wiki_get_note"} <= tools
    assert all(r["actor"] == "mcp:reader" for r in rows)


# --------------------------------------------------------------------------- #
# THE M4 GATE — no write capability (structural, grep-proven)                   #
# --------------------------------------------------------------------------- #
WRITE_SYMBOLS = [
    "create_note", "update_note", "delete_note", "merge_notes", "refine_note",
    "enqueue", "create_proposal", "accept_proposal", "reject_proposal",
    "batch_accept", "proposals_service",
]


def test_read_server_has_no_write_symbol_in_namespace():
    """No mutation/enqueue name is bound in the read server's module namespace.
    This is the M4 least-privilege gate (D-W4b.2): a read tool cannot be escalated
    to a write because the write symbols are not importable from here."""
    ns = vars(read_server)
    leaked = [s for s in WRITE_SYMBOLS if s in ns]
    assert leaked == [], f"read server leaked write symbols: {leaked}"


def test_read_server_imports_no_write_symbol_ast():
    """Parse the read server's IMPORT statements (AST, not a string grep — a
    docstring legitimately names the excluded symbols) and assert none of them
    import a note-mutation / enqueue name or the proposals_service module. The
    audit appender IS allowed (it writes only to its own table, not a vault note).
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(read_server))
    imported_names: set[str] = set()
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_modules.add(node.module or "")
            for alias in node.names:
                imported_names.add(alias.name)        # the real name
                imported_names.add(alias.asname or alias.name)  # the bound name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)

    forbidden = {
        "create_note", "update_note", "delete_note", "merge_notes", "refine_note",
        "enqueue", "create_proposal", "accept_proposal", "reject_proposal",
        "batch_accept",
    }
    leaked = forbidden & imported_names
    assert leaked == set(), f"read server imports write symbols: {leaked}"
    # the write-server logic module must not be imported at all
    assert not any("proposals_service" in m for m in imported_modules), \
        "read server must not import proposals_service (the enqueue layer)"
    # sanity: it DOES import the audit appender (allowed — append-only to its own
    # table). Imported as `from modules.wiki import proposals_store`, so the bound
    # name "proposals_store" lands in imported_names.
    assert "append_audit" in imported_names or "proposals_store" in imported_names


def test_server_builds_with_all_tools():
    """FastMCP server constructs + registers all tools without error (incl. the 2
    proposal-readback tools ported from the shared server in MCP-DEDUP #70)."""
    server = read_server.build_server()
    assert server is not None
    assert set(read_server.TOOLS.keys()) == {
        "wiki_search", "wiki_overview", "wiki_inbox", "wiki_graph",
        "wiki_get_note", "wiki_backlinks", "wiki_recent_ops", "wiki_clusters",
        "wiki_verify_citations",
        # PORTED #70 — wiki-proposal read-back (was embedded in the shared read_server)
        "wiki_proposal_status", "wiki_list_proposals",
    }


def test_wiki_clusters_parity(wiki_db):
    """W5a: the wiki_clusters MCP tool returns the same data as reader.detect_clusters."""
    # seed a ≥3-note dense cluster
    a = wsvc.create_note(NoteCreateInput(title="Cluster A", content="x")).id
    b = wsvc.create_note(NoteCreateInput(title="Cluster B", content=f"[[{a}]]")).id
    wsvc.create_note(NoteCreateInput(title="Cluster C", content=f"[[{a}]] [[{b}]]"))
    assert read_server.wiki_clusters()["clusters"] == reader.detect_clusters()


# --------------------------------------------------------------------------- #
# Wiki proposal read-back (PORTED #70 from the shared read_server — NB3). The     #
# agent reads the disposition of its WIKI proposals (the wiki_proposals queue).   #
# Created via the canonical standalone wiki WRITE server (propose_note → the      #
# wiki queue), read via these ported READ tools. READ-ONLY (no ratify here).      #
# --------------------------------------------------------------------------- #
def test_wiki_proposal_status_reads_wiki_queue(wiki_db):
    """wiki_proposal_status reads back a wiki proposal's disposition — found + pending,
    with kind/rationale. Created via the canonical wiki write server's propose_note."""
    from modules.wiki.mcp import write_server as wws
    pid = wws.propose_note("NB3 note", "body", rationale="because NB3 read-back")["proposalId"]
    out = read_server.wiki_proposal_status(pid)
    assert out["found"] is True
    assert out["proposalId"] == pid
    assert out["status"] == "pending"
    assert out["kind"] == "note_create"
    assert out["rationale"] == "because NB3 read-back"


def test_wiki_proposal_status_missing_and_malformed(wiki_db):
    """Unknown id → found False; a non-int id must NOT leak a ValueError (honest)."""
    assert read_server.wiki_proposal_status(999999) == {"found": False, "proposalId": 999999}
    assert read_server.wiki_proposal_status("nope") == {"found": False, "proposalId": "nope"}


def test_wiki_list_proposals_and_counts(wiki_db):
    """wiki_list_proposals returns the wiki proposals newest-first + a counts roll-up;
    the status filter scopes it; empty queue is honest-empty."""
    from modules.wiki.mcp import write_server as wws
    empty = read_server.wiki_list_proposals()
    assert empty["proposals"] == [] and empty["counts"].get("pending", 0) == 0
    p1 = wws.propose_note("first", "b", rationale="r1")["proposalId"]
    p2 = wws.propose_note("second", "b", rationale="r2")["proposalId"]
    out = read_server.wiki_list_proposals()
    ids = [p["id"] for p in out["proposals"]]
    assert ids == [p2, p1]  # newest-first
    assert out["counts"]["pending"] == 2
    assert read_server.wiki_list_proposals(status="accepted")["proposals"] == []


def test_wiki_proposal_readback_byte_identical_to_old_embedded(wiki_db):
    """PORT INVARIANT (#70): the ported tools' payload == what the OLD embedded shared
    tools produced. Pin the exact shape so the move didn't drift a field."""
    from modules.wiki.mcp import write_server as wws
    pid = wws.propose_note("Pin shape", "b", rationale="exact-shape pin")["proposalId"]
    status = read_server.wiki_proposal_status(pid)
    assert set(status) == {"found", "proposalId", "kind", "status", "targetId",
                           "appliedNoteId", "decidedBy", "decided", "rationale"}
    lst = read_server.wiki_list_proposals()
    assert set(lst) == {"proposals", "counts"}


def test_wiki_proposal_readback_tools_audit(wiki_db):
    """The ported reads audit too (the standalone convention — every call appends one
    wiki_mcp_audit row). Fail-soft: an audit failure never breaks the read."""
    from modules.wiki.mcp import write_server as wws
    pid = wws.propose_note("audited", "b", rationale="audit me")["proposalId"]
    read_server.wiki_proposal_status(pid)
    read_server.wiki_list_proposals()
    rows = pstore.recent_audit(limit=50)
    tools = {r["tool"] for r in rows}
    assert {"wiki_proposal_status", "wiki_list_proposals"} <= tools
