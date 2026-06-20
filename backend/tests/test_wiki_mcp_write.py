"""tests/test_wiki_mcp_write.py — MCP WRITE server tests (Sprint W4c → WIKI-WRITE-THROUGH #25).

WIKI-WRITE-THROUGH (#25, USER-CHỐT + team-lead-approved): the DEFAULT is now write-through —
an agent wiki_write applies NOW (via the create_proposal→accept chokepoint, audited + reversible)
and returns the REAL noteId. The escape hatch: wikiAgentAutonomous OFF → proposals-only restored.

Coverage (the REWORKED M4 boundary — replaces the old "agent proposes, nothing lands"):
  - WRITE-THROUGH: each write tool CREATES the note NOW (default) → returns the real noteId,
    applied=True, get→found:true (the dogfood fix — a note-id the agent can immediately get).
  - rationale OPTIONAL: omitting it works (the required-friction is dropped).
  - TOGGLE OFF → proposals-only (write → pending, applied=False) — THE distinguishing: proves
    it's a FLIPPED-DEFAULT, not a removed gate (the escape hatch + the fail-safe).
  - the STRUCTURAL gate STILL holds: write server imports create_proposal (the chokepoint) but
    NOT any note-mutation fn nor accept/reject directly — grep+AST (the write goes THROUGH the
    one chokepoint, auto-apply is the chokepoint's job, not a bypass).
  - AUDIT: every write appends audit rows (propose + accept when applied) — the trace/control.
  - human-override: a human can edit/delete the agent's note via the note CRUD.
  - server builds (FastMCP registers all 6 tools).
"""

from __future__ import annotations

import pytest

from modules.settings import service as ssvc
from modules.settings.schema import AppConfigPatch
from modules.wiki import proposals_service as psvc
from modules.wiki import proposals_store as pstore
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.schema import NoteCreateInput, NoteUpdateInput
from modules.wiki.mcp import write_server


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    pstore.init_proposal_tables()
    # #25: write-through is the DEFAULT (wikiAgentAutonomous default True). A fresh config (no
    # config.md) already defaults ON; assert it so the tests run against the real default.
    assert ssvc.get_config().wikiAgentAutonomous is True
    return isolated_paths


def _seed_note(title="seed", content="body") -> int:
    return wsvc.create_note(NoteCreateInput(title=title, content=content)).id


# --------------------------------------------------------------------------- #
# WRITE-THROUGH (default): each write tool creates the note NOW + returns noteId #
# --------------------------------------------------------------------------- #
def test_propose_note_writes_through_returns_noteid(wiki_db):
    before = wiki_store.count_notes()
    r = write_server.propose_note("AI idea", "body", rationale="agent thinks so")
    assert r["applied"] is True and r["status"] == "accepted"
    assert r["noteId"] is not None, "write-through must return the REAL note-id (not a proposal-id)"
    # the note LANDED in the vault NOW
    assert wiki_store.count_notes() == before + 1
    # get the returned id → found:true (the dogfood fix)
    note = wsvc.get_note(r["noteId"])
    assert note is not None and note.title == "AI idea"
    assert note.author == "mcp:writer"  # provenance: the agent-authored note carries the actor


def test_propose_edit_writes_through(wiki_db):
    nid = _seed_note()
    r = write_server.propose_edit(nid, title="new title", rationale="clarify")
    assert r["applied"] is True and r["noteId"] == nid
    assert wsvc.get_note(nid).title == "new title", "the edit applied NOW"


def test_propose_link_writes_through(wiki_db):
    a, b = _seed_note("A"), _seed_note("B")
    r = write_server.propose_link(a, str(b), rationale="related")
    assert r["applied"] is True
    assert f"[[{b}]]" in wsvc.get_note(a).content, "the link was added NOW"


def test_propose_merge_writes_through(wiki_db):
    s, t = _seed_note("dupe"), _seed_note("canon")
    r = write_server.propose_merge(s, t, rationale="duplicates")
    assert r["applied"] is True and r["noteId"] == t
    # source merged away (resolve follows the redirect to the target)
    note, _w = wsvc.resolve_note(s)
    assert note is not None and note.id == t


def test_propose_moc_writes_through(wiki_db):
    r = write_server.propose_moc("MOC: theme", "- [[1]]", rationale="cluster found")
    assert r["applied"] is True and r["noteId"] is not None
    assert wsvc.get_note(r["noteId"]) is not None


# --------------------------------------------------------------------------- #
# rationale OPTIONAL (#25 — the required-friction is dropped)                    #
# --------------------------------------------------------------------------- #
def test_rationale_is_optional(wiki_db):
    """A write with NO rationale (None / omitted / whitespace) still WORKS — write-through, the
    note lands. (The old RationaleRequired rejection is gone.)"""
    r1 = write_server.propose_note("no-rationale", "body")          # omitted entirely
    assert r1["applied"] is True and r1["noteId"] is not None
    r2 = write_server.propose_note("none-rationale", "body", rationale=None)
    assert r2["applied"] is True
    r3 = write_server.propose_note("blank-rationale", "body", rationale="   ")
    assert r3["applied"] is True


def test_each_tool_accepts_no_rationale(wiki_db):
    nid = _seed_note()
    assert write_server.propose_edit(nid, title="t2")["applied"] is True
    a = _seed_note("A")
    assert write_server.propose_link(a, str(nid))["applied"] is True


# --------------------------------------------------------------------------- #
# THE DISTINGUISHING — toggle OFF → proposals-only (write → pending, not applied) #
# (proves #25 is a FLIPPED-DEFAULT, not a REMOVED gate — a test without this      #
#  can't tell flipped-default from removed-gate.)                                 #
# --------------------------------------------------------------------------- #
def test_toggle_off_restores_proposals_only(wiki_db):
    ssvc.set_config(AppConfigPatch(wikiAgentAutonomous=False))
    before = wiki_store.count_notes()
    r = write_server.propose_note("pending note", "body", rationale="r")
    # NOT applied — the escape hatch: proposals-only restored
    assert r["applied"] is False, "toggle OFF → write must NOT auto-apply"
    assert r["noteId"] is None and r["status"] == "pending"
    assert wiki_store.count_notes() == before, "the vault is UNCHANGED when toggle is OFF"
    # it IS a pending proposal in the queue (a human can ratify it in P1)
    assert any(x["id"] == r["proposalId"] for x in psvc.list_proposals("pending"))


def test_toggle_off_then_on_again_writes_through(wiki_db):
    """The toggle is live + reversible per-write: OFF → pending, ON again → write-through."""
    ssvc.set_config(AppConfigPatch(wikiAgentAutonomous=False))
    assert write_server.propose_note("off", "b", rationale="r")["applied"] is False
    ssvc.set_config(AppConfigPatch(wikiAgentAutonomous=True))
    r = write_server.propose_note("on", "b", rationale="r")
    assert r["applied"] is True and r["noteId"] is not None


# --------------------------------------------------------------------------- #
# human-override — a human can edit/delete the agent's written note             #
# --------------------------------------------------------------------------- #
def test_human_can_override_agent_note(wiki_db):
    """The control: after the agent writes through, a HUMAN edits/deletes that note via the note
    CRUD (the override mechanism — write-through is safe BECAUSE the human can correct/revert)."""
    r = write_server.propose_note("agent note", "agent body", rationale="r")
    nid = r["noteId"]
    # human edits it (the REST/CRUD path — actor defaults human)
    wsvc.update_note(nid, NoteUpdateInput(content="human corrected"))
    assert wsvc.get_note(nid).content == "human corrected"
    # human deletes it
    wsvc.delete_note(nid)
    assert wsvc.get_note(nid) is None


# --------------------------------------------------------------------------- #
# AUDIT — write-through keeps the trace (propose + accept rows)                  #
# --------------------------------------------------------------------------- #
def test_write_through_audits_propose_and_accept(wiki_db):
    """A write-through keeps the trace: the MCP-tool audit row + the queue propose + accept rows
    (the control that makes write-through reversible/inspectable). actor=mcp:writer on the tool/
    propose rows; the accept row is decided_by agent:auto."""
    sess = write_server.SESSION_ID
    write_server.propose_note("a", "b", rationale="r")
    rows = pstore.recent_audit(correlation_id=sess, limit=1000)
    tools = {r["tool"] for r in rows}
    assert "propose_note" in tools  # the MCP-tool audit row
    assert "propose" in tools       # create_proposal's queue-action audit
    assert "accept" in tools        # the auto-accept audit (write-through trace)


# --------------------------------------------------------------------------- #
# THE STRUCTURAL GATE — STILL holds (unchanged by #25): the write goes THROUGH   #
# the create_proposal chokepoint; it does NOT import accept/reject or a mutate fn #
# directly (the auto-apply is the chokepoint's job, not a bypass).               #
# --------------------------------------------------------------------------- #
FORBIDDEN_SYMBOLS = [
    "create_note", "update_note", "delete_note", "merge_notes", "refine_note",
    "enqueue", "accept_proposal", "reject_proposal", "batch_accept",
    "proposals_service",  # importing the module would expose accept/reject
]


def test_write_server_namespace_has_no_mutate_or_accept():
    """No direct note-mutation fn, no accept/reject, and not the proposals_service module are
    bound in the write server's namespace. It may ONLY enqueue (create_proposal) — the auto-apply
    happens INSIDE create_proposal (the chokepoint), so this gate STILL holds under write-through."""
    ns = vars(write_server)
    leaked = [s for s in FORBIDDEN_SYMBOLS if s in ns]
    assert leaked == [], f"write server leaked forbidden symbols: {leaked}"
    assert "create_proposal" in ns  # the one chokepoint it goes through


def test_write_server_imports_no_mutate_or_accept_ast():
    """AST-parse the imports: the write server imports create_proposal (+schema/audit) but NOT any
    mutation/accept symbol nor the proposals_service module — still true under #25 (write-through
    auto-applies inside create_proposal, this module never imports accept directly)."""
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
    assert "modules.wiki.proposals_service" in imported_modules  # the from-import source
    assert "create_proposal" in imported_names  # the only thing taken from it
    assert "proposals_service" not in imported_names


def test_write_server_builds_with_all_tools():
    server = write_server.build_server()
    assert server is not None
    assert set(write_server.TOOLS.keys()) == {
        "propose_note", "propose_edit", "propose_link", "propose_unlink",
        "propose_merge", "propose_moc",
    }


# --------------------------------------------------------------------------- #
# supersede_pending — the legacy queue is archived (audit kept), idempotent      #
# --------------------------------------------------------------------------- #
def test_supersede_pending_archives_queue_keeps_audit(wiki_db):
    """#25 one-shot: seed pending proposals (toggle OFF), then supersede_pending → they leave the
    open queue (rejected, decided_by superseded:write-through) but the audit HISTORY is kept."""
    ssvc.set_config(AppConfigPatch(wikiAgentAutonomous=False))
    write_server.propose_note("p1", "b", rationale="r")
    write_server.propose_note("p2", "b", rationale="r")
    assert len(psvc.list_proposals("pending")) == 2

    n = psvc.supersede_pending()
    assert n == 2
    assert len(psvc.list_proposals("pending")) == 0, "the open queue is cleared"
    # the rows survive as rejected with the superseded marker (history kept, not hard-deleted)
    rejected = psvc.list_proposals("rejected")
    assert len(rejected) >= 2
    assert all(p["decidedBy"] == "superseded:write-through"
               for p in rejected if p["decidedBy"]), "superseded marker on the archived rows"
    # idempotent — re-run with nothing pending → 0
    assert psvc.supersede_pending() == 0
