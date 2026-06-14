"""tests/test_wiki_mcp_write.py — MCP WRITE server tests (Sprint W4c, closes M4).

Coverage:
  - ENQUEUE-ONLY: each propose tool creates a PENDING proposal AND writes nothing
    to the vault (the M4 loop-close gate — agent proposes, nothing lands).
  - THE FULL CHAIN: propose via the tool → it's pending in the queue → vault
    unchanged → a human accept (proposals_service) → NOW it lands.
  - rationale REQUIRED: empty rationale → RationaleRequired, no proposal created.
  - THE M4 GATE: write server imports create_proposal (enqueue) but NOT any
    note-mutation fn nor accept/reject — grep+AST proven.
  - AUDIT: every propose call appends one wiki_mcp_audit row (actor=mcp:writer).
  - server builds (FastMCP registers all 6 tools).
"""

from __future__ import annotations

import pytest

from modules.wiki import proposals_service as psvc
from modules.wiki import proposals_store as pstore
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.schema import NoteCreateInput
from modules.wiki.mcp import write_server


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    pstore.init_proposal_tables()
    return isolated_paths


def _seed_note(title="seed", content="body") -> int:
    return wsvc.create_note(NoteCreateInput(title=title, content=content)).id


# --------------------------------------------------------------------------- #
# Enqueue-only: each propose tool → pending proposal + NOTHING in the vault      #
# --------------------------------------------------------------------------- #
def test_propose_note_enqueues_pending_writes_nothing(wiki_db):
    before = wiki_store.count_notes()
    p = write_server.propose_note("AI idea", "body", rationale="agent thinks so")
    assert p["status"] == "pending" and p["kind"] == "note_create"
    assert p["actor"] == "mcp:writer"
    # the M4 invariant: nothing landed in the vault
    assert wiki_store.count_notes() == before


def test_propose_edit_enqueues(wiki_db):
    nid = _seed_note()
    p = write_server.propose_edit(nid, rationale="clarify", title="new title")
    assert p["status"] == "pending" and p["kind"] == "note_edit"
    assert p["targetId"] == nid and p["payload"]["title"] == "new title"
    # the note is unchanged until accept
    assert wsvc.get_note(nid).title == "seed"


def test_propose_link_enqueues(wiki_db):
    a, b = _seed_note("A"), _seed_note("B")
    p = write_server.propose_link(a, str(b), rationale="related")
    assert p["kind"] == "link_add" and p["payload"]["target"] == str(b)
    # not linked yet
    assert wsvc.get_note(a).content == "body"


def test_propose_unlink_enqueues(wiki_db):
    a = _seed_note("A", content="see [[2]]")
    p = write_server.propose_unlink(a, "2", rationale="not related after all")
    assert p["kind"] == "link_remove" and p["payload"]["target"] == "2"


def test_propose_merge_enqueues(wiki_db):
    s, t = _seed_note("dupe"), _seed_note("canon")
    p = write_server.propose_merge(s, t, rationale="duplicates")
    assert p["kind"] == "merge" and p["payload"] == {"sourceId": s, "targetId": t}
    # both notes still exist (not merged until accept)
    assert wsvc.get_note(s) is not None and wsvc.get_note(t) is not None


def test_propose_moc_enqueues(wiki_db):
    p = write_server.propose_moc("MOC: theme", "- [[1]]", rationale="cluster found")
    assert p["kind"] == "moc" and p["status"] == "pending"


# --------------------------------------------------------------------------- #
# THE FULL M4 CHAIN: propose (agent) → pending → vault unchanged → accept (human)#
# --------------------------------------------------------------------------- #
def test_full_loop_propose_then_human_accept_lands(wiki_db):
    before = wiki_store.count_notes()
    # agent proposes via MCP
    p = write_server.propose_note("Loop note", "via mcp", rationale="closes the loop")
    pid = p["id"]
    # it's pending in the queue, vault UNCHANGED
    pending = psvc.list_proposals("pending")
    assert any(x["id"] == pid for x in pending)
    assert wiki_store.count_notes() == before
    # human accepts (P1/REST path — NOT the agent)
    accepted = psvc.accept_proposal(pid, decided_by="human")
    assert accepted["status"] == "accepted"
    # NOW it lands in the vault
    assert wiki_store.count_notes() == before + 1
    landed = wsvc.get_note(accepted["appliedNoteId"])
    assert landed is not None and landed.title == "Loop note"
    # provenance: the agent-authored note carries the writer actor
    assert landed.author == "mcp:writer"


# --------------------------------------------------------------------------- #
# rationale required                                                            #
# --------------------------------------------------------------------------- #
def test_empty_rationale_rejected_no_proposal(wiki_db):
    before = len(psvc.list_proposals("all" if False else None) or [])
    with pytest.raises(write_server.RationaleRequired):
        write_server.propose_note("x", "y", rationale="   ")
    # no proposal was created
    assert len(psvc.list_proposals(None)) == before


def test_each_tool_requires_rationale(wiki_db):
    nid = _seed_note()
    with pytest.raises(write_server.RationaleRequired):
        write_server.propose_edit(nid, rationale="")
    with pytest.raises(write_server.RationaleRequired):
        write_server.propose_link(nid, "2", rationale="")
    with pytest.raises(write_server.RationaleRequired):
        write_server.propose_merge(nid, 2, rationale="")


# --------------------------------------------------------------------------- #
# AUDIT — one row per propose call (actor=mcp:writer)                            #
# --------------------------------------------------------------------------- #
def test_propose_audits(wiki_db):
    """Each MCP propose call produces an audit row tagged with the MCP TOOL name
    (propose_note/propose_moc, actor=mcp:writer). NOTE: create_proposal ALSO audits
    a 'propose' queue-action row under the same correlationId (the double trail,
    D-W4c.4: MCP-tool granularity + queue-action). Both carry actor=mcp:writer here
    because the writer passes its actor through. We assert the TOOL-named rows are
    present (the W4c contract), not an exact total."""
    sess = write_server.SESSION_ID
    write_server.propose_note("a", "b", rationale="r")
    write_server.propose_moc("m", "c", rationale="r")
    rows = pstore.recent_audit(correlation_id=sess, limit=1000)
    tools = {r["tool"] for r in rows}
    assert {"propose_note", "propose_moc"} <= tools  # the MCP-tool audit rows
    assert "propose" in tools  # create_proposal's queue-action audit (W4a)
    assert all(r["actor"] == "mcp:writer" for r in rows)


def test_rejected_rationale_does_not_audit(wiki_db):
    sess = write_server.SESSION_ID
    before = len(pstore.recent_audit(correlation_id=sess, limit=1000))
    with pytest.raises(write_server.RationaleRequired):
        write_server.propose_note("a", "b", rationale="")
    # rationale check happens BEFORE audit → no audit row for a rejected propose
    assert len(pstore.recent_audit(correlation_id=sess, limit=1000)) == before


# --------------------------------------------------------------------------- #
# THE M4 GATE — enqueue-only, no direct-mutate / no accept (structural)          #
# --------------------------------------------------------------------------- #
FORBIDDEN_SYMBOLS = [
    "create_note", "update_note", "delete_note", "merge_notes", "refine_note",
    "enqueue", "accept_proposal", "reject_proposal", "batch_accept",
    "proposals_service",  # importing the module would expose accept/reject
]


def test_write_server_namespace_has_no_mutate_or_accept():
    """No direct note-mutation fn, no accept/reject, and not the proposals_service
    module are bound in the write server's namespace. It may ONLY enqueue
    (create_proposal). This is the M4 gate inverted from the read server."""
    ns = vars(write_server)
    leaked = [s for s in FORBIDDEN_SYMBOLS if s in ns]
    assert leaked == [], f"write server leaked forbidden symbols: {leaked}"
    # sanity: it DOES have the enqueue entry
    assert "create_proposal" in ns


def test_write_server_imports_no_mutate_or_accept_ast():
    """AST-parse the imports (not a string grep — the docstring legitimately names
    the excluded symbols): the write server imports create_proposal (+schema/audit)
    but NOT any mutation/accept symbol nor the proposals_service module."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(write_server))
    imported_names: set[str] = set()
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_modules.add(node.module or "")
            for alias in node.names:
                imported_names.add(alias.name)
                imported_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)

    forbidden = {
        "create_note", "update_note", "delete_note", "merge_notes", "refine_note",
        "enqueue", "accept_proposal", "reject_proposal", "batch_accept",
    }
    leaked = forbidden & imported_names
    assert leaked == set(), f"write server imports forbidden symbols: {leaked}"
    # it must NOT import the whole proposals_service module (only the bare fn).
    assert "modules.wiki.proposals_service" in imported_modules  # the from-import source
    assert "create_proposal" in imported_names  # the only thing taken from it
    # nothing named proposals_service bound as a module alias
    assert "proposals_service" not in imported_names


def test_write_server_builds_with_all_tools():
    server = write_server.build_server()
    assert server is not None
    assert set(write_server.TOOLS.keys()) == {
        "propose_note", "propose_edit", "propose_link", "propose_unlink",
        "propose_merge", "propose_moc",
    }
