"""tests/test_wiki_mcp_read.py — MCP READ-only server tests (Sprint W4b).

Coverage:
  - PARITY: each tool returns the same data as its REST/reader source.
  - THE M4 GATE: the read server has NO write capability — no mutation/enqueue
    symbol is reachable in its module namespace (grep-proven, not a docstring).
  - AUDIT: every tool call appends one wiki_mcp_audit row (actor=mcp:reader).
  - graceful: a missing note → {found: False}, never a crash; bad FTS query → no crash.
  - server builds (FastMCP registers the full TOOLS set) without error.

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


# WIKI-RETRIEVAL-3 #23 (F1=b): test_graph_parity + test_backlinks_parity + test_graph_missing_note
# removed — they exercised the granular wiki_graph / wiki_backlinks MCP tools, which were removed
# from the surface (wiki_context supersets). The graph/backlinks byte-identity (== reader.ego_graph
# / reader.backlinks) is now asserted by test_wiki_context_subpayloads_byte_identical_to_granular,
# and the missing-note arm by test_wiki_context_missing_note_is_found_false. The REST graph/backlinks
# parity (which stays) lives in test_wiki.py.


def test_get_note_parity(wiki_db):
    a, _ = _seed_linked_pair()
    tool = read_server.wiki_get_note(a)
    assert tool["found"] is True and tool["note"] == wsvc.get_note(a).model_dump()


# --------------------------------------------------------------------------- #
# WIKI-RETRIEVAL-2 (#21) — wiki_get_note modes (full | outline | section)        #
# --------------------------------------------------------------------------- #
def _seed_structured_note() -> int:
    body = ("Intro line.\n\n## Career\ncareer planning content.\n\n"
            "## Finance\nfinance content.\n\n### Sub\nsub detail.")
    from modules.wiki.schema import NoteCreateInput
    return wsvc.create_note(NoteCreateInput(title="Big", content=body, folder="A",
                                            noteType="moc", tags=["x"])).id


def test_get_mode_full_is_backward_compat(wiki_db):
    """mode=full (+ no-mode default) → the bare full note dict UNCHANGED (the pre-#21 shape)."""
    nid = _seed_structured_note()
    default = read_server.wiki_get_note(nid)
    full = read_server.wiki_get_note(nid, mode="full")
    bare = wsvc.get_note(nid).model_dump()
    assert default["note"] == bare and full["note"] == bare, "full = the bare note, unchanged"


def test_get_mode_outline_has_headings_no_body(wiki_db):
    """mode=outline → headings (the ## ToC) + meta (kind/status/folder/tags), NO body."""
    nid = _seed_structured_note()
    out = read_server.wiki_get_note(nid, mode="outline")
    assert out["found"] is True and out["mode"] == "outline"
    texts = [(h["level"], h["text"]) for h in out["headings"]]
    assert texts == [(2, "Career"), (2, "Finance"), (3, "Sub")]
    assert out["meta"]["kind"] == "moc" and out["meta"]["folder"] == "A"
    # NO body anywhere in the outline (token-cheap)
    assert "note" not in out and "content" not in out


def test_get_mode_section_returns_only_that_section(wiki_db):
    """mode=section&heading=X → only that section's content (to the next same/higher heading)."""
    nid = _seed_structured_note()
    sec = read_server.wiki_get_note(nid, mode="section", heading="Career")
    assert sec["sectionFound"] is True
    assert sec["section"]["content"] == "career planning content."
    # an unknown heading → sectionFound False (honest, not a crash); the note still 'found'
    miss = read_server.wiki_get_note(nid, mode="section", heading="Nope")
    assert miss["found"] is True and miss["sectionFound"] is False and miss["section"] is None


def test_get_modes_rest_mcp_byte_identical(wiki_db):
    """#24 invariant for the new modes: the MCP wiki_get_note payload == REST /wiki/notes/{id}
    data (reader.note_view) byte-identical. (full → MCP wraps {found, note:<view>}; outline/section
    → MCP merges {found, **view} — compare the view portion vs REST's note_view directly.)"""
    import json
    nid = _seed_structured_note()
    note = wsvc.get_note(nid)
    for mode, heading in (("full", None), ("outline", None), ("section", "Finance")):
        rest = reader.note_view(note, mode=mode, heading=heading)  # == REST data
        mcp = read_server.wiki_get_note(nid, mode=mode, heading=heading)
        mcp_view = mcp["note"] if mode == "full" else {k: v for k, v in mcp.items() if k != "found"}
        assert json.dumps(mcp_view, sort_keys=True) == json.dumps(rest, sort_keys=True), \
            f"mode={mode}: MCP payload must == REST note_view byte-identical"


# --------------------------------------------------------------------------- #
# WIKI-RETRIEVAL-2 (#22) — wiki_search ranked top-5 + query alias                #
# --------------------------------------------------------------------------- #
def test_search_ranked_top5_with_score(wiki_db):
    """search → ≤5 RANKED results, each {id,title,folder,snippet,score}; NOT a flat dump."""
    from modules.wiki.schema import NoteCreateInput
    for i in range(8):
        wsvc.create_note(NoteCreateInput(title=f"career note {i}", content="career career stuff"))
    res = read_server.wiki_search(q="career")["results"]
    assert len(res) <= 5, "ranked top-5, not flat-all"
    for r in res:
        assert set(r) == {"id", "title", "folder", "snippet", "score"}
    # ranked: scores are in FTS rank order (ascending = best-first; rank is more-negative=better)
    scores = [r["score"] for r in res]
    assert scores == sorted(scores), "results are in rank order"


def test_search_query_alias_equals_q(wiki_db):
    """The dogfood-hit `query` alias works == `q` (both name the same search)."""
    from modules.wiki.schema import NoteCreateInput
    wsvc.create_note(NoteCreateInput(title="career plan", content="career"))
    import json
    by_q = read_server.wiki_search(q="career")["results"]
    by_query = read_server.wiki_search(query="career")["results"]
    assert json.dumps(by_q, sort_keys=True) == json.dumps(by_query, sort_keys=True)


def test_search_rest_mcp_byte_identical(wiki_db):
    """#24: MCP wiki_search results == REST /wiki/search data (reader.search) byte-identical."""
    import json
    from modules.wiki.schema import NoteCreateInput
    wsvc.create_note(NoteCreateInput(title="career", content="career"))
    mcp = read_server.wiki_search(q="career")["results"]
    rest = reader.search("career")
    assert json.dumps(mcp, sort_keys=True) == json.dumps(rest, sort_keys=True)


# --------------------------------------------------------------------------- #
# WIKI-RETRIEVAL-3 (#23) — wiki_context: graph + backlinks in ONE composed call  #
# --------------------------------------------------------------------------- #
def test_wiki_context_shape_present(wiki_db):
    """A present note → the composed payload: found + note_id + graph + backlinks, exactly
    those 4 keys (no more, no less)."""
    a, b = _seed_linked_pair()
    ctx = read_server.wiki_context(b)
    assert set(ctx) == {"found", "note_id", "graph", "backlinks"}
    assert ctx["found"] is True and ctx["note_id"] == b
    # graph carries its own 4 keys; backlinks its 3
    assert set(ctx["graph"]) == {"center", "nodes", "edges", "clusters"}
    assert set(ctx["backlinks"]) == {"linked", "unlinked", "outbound"}


def test_wiki_context_subpayloads_byte_identical_to_granular(wiki_db):
    """THE no-capability-lost proof (F1=b): wiki_context's ``graph`` is BYTE-IDENTICAL to what the
    removed granular wiki_graph returned (its ``graph`` == reader.ego_graph) and its ``backlinks``
    to the removed wiki_backlinks (== reader.backlinks) — because all three compose the SAME reader
    fns, the single source of truth. So consolidating the 2 tools into wiki_context loses NO fidelity.
    (The old tools are gone, so we assert against the reader fns they wrapped — the authoritative
    source the old tools and wiki_context both delegate to.)"""
    import json
    a, b = _seed_linked_pair()
    ctx = read_server.wiki_context(b)
    # graph == what old wiki_graph(b)["graph"] returned (it was {found, graph: reader.ego_graph(b,2)})
    assert json.dumps(ctx["graph"], sort_keys=True) == \
        json.dumps(reader.ego_graph(b, 2), sort_keys=True)
    # backlinks == what old wiki_backlinks(b) returned (it was reader.backlinks(b) verbatim)
    assert json.dumps(ctx["backlinks"], sort_keys=True) == \
        json.dumps(reader.backlinks(b), sort_keys=True)
    assert ctx["graph"] == reader.ego_graph(b, 2)
    assert ctx["backlinks"] == reader.backlinks(b)


def test_wiki_context_respects_depth(wiki_db):
    """``depth`` is threaded to ego_graph (not silently fixed at 2) — depth=1 graph matches
    ego_graph(id, 1)."""
    a, b = _seed_linked_pair()
    assert read_server.wiki_context(b, depth=1)["graph"] == reader.ego_graph(b, 1)


def test_wiki_context_missing_note_is_found_false(wiki_db):
    """A missing note → {found:False, note_id} (the wiki convention), never a crash."""
    assert read_server.wiki_context(99999) == {"found": False, "note_id": 99999}


def test_wiki_context_registered_and_audits(wiki_db):
    """wiki_context is in the TOOLS registry and (like every read tool) audits exactly one row."""
    a, b = _seed_linked_pair()
    assert "wiki_context" in read_server.TOOLS
    sess = read_server.SESSION_ID
    before = len(pstore.recent_audit(correlation_id=sess, limit=1000))
    read_server.wiki_context(b)
    rows = pstore.recent_audit(correlation_id=sess, limit=1000)
    assert len(rows) == before + 1 and rows[0]["tool"] == "wiki_context"


def test_recent_ops_parity(wiki_db):
    _seed_linked_pair()
    assert read_server.wiki_recent_ops()["ops"] == reader.recent_ops()


def test_wiki_tree_mcp_byte_identical_to_rest_data(wiki_db):
    """WIKI-LINK-CORRECTNESS #19 (the wrapper-drift fix): the FULL MCP wiki_tree result is
    BYTE-IDENTICAL to REST /wiki/tree's ``data`` — NOT wrapped in a {tree:...} key REST doesn't
    have. REST returns ok(data=reader.folder_tree()) → data IS the tree dict; the MCP tool must
    return that SAME dict directly. Compare the FULL result (sort_keys dumps), so a wrapper drift
    fails RED (the old test compared the inner tree only + missed the {tree:...} wrapper)."""
    import json
    _seed_linked_pair()
    rest_data = reader.folder_tree()          # == REST /wiki/tree's `data`
    mcp_result = read_server.wiki_tree()      # the FULL MCP tool result
    assert json.dumps(mcp_result, sort_keys=True) == json.dumps(rest_data, sort_keys=True), \
        "MCP wiki_tree must be byte-identical to REST /wiki/tree data (no {tree:...} wrapper)"
    # explicit: the top-level keys are the tree node's (name/path/meta/counts/folders/notes — #20
    # added meta/counts), NOT a {tree} wrapper
    assert "tree" not in mcp_result, "no {tree:...} wrapper — return the tree dict directly"
    assert set(mcp_result.keys()) == set(rest_data.keys())


def test_wiki_tree_is_registered_and_audits(wiki_db):
    """wiki_tree is in the TOOLS registry + the build, and (like every read tool) audits one row."""
    assert "wiki_tree" in read_server.TOOLS
    sess = read_server.SESSION_ID
    before = len(pstore.recent_audit(correlation_id=sess, limit=1000))
    read_server.wiki_tree()
    rows = pstore.recent_audit(correlation_id=sess, limit=1000)
    assert len(rows) == before + 1 and rows[0]["tool"] == "wiki_tree"


# --------------------------------------------------------------------------- #
# Graceful failure (no crash)                                                   #
# --------------------------------------------------------------------------- #
def test_get_missing_note_is_found_false(wiki_db):
    assert read_server.wiki_get_note(99999) == {"found": False, "note_id": 99999}


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
        "wiki_search", "wiki_overview", "wiki_inbox",
        "wiki_get_note",
        # WIKI-RETRIEVAL-3 #23 (F1=b): wiki_graph + wiki_backlinks REMOVED — wiki_context supersets both.
        "wiki_context",
        "wiki_suggest_links",  # WIKI-SUGGEST-LINK #34
        "wiki_stale",  # WIKI-STALE-DETECTOR #41
        "wiki_recent_ops",
        "wiki_my_feedback",  # WIKI-WRITE-FEEDBACK #35: agent reads WHY a human overrode its notes
        "wiki_tree",  # WIKI-LINK-CORRECTNESS #19: MCP mirror of REST /wiki/tree
        "wiki_clusters", "wiki_verify_citations",
        # PORTED #70 — wiki-proposal read-back (was embedded in the shared read_server)
        "wiki_proposal_status", "wiki_list_proposals",
        "wiki_reindex",  # WIKI-RECONCILE #53: bulk prune orphan cache rows
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
