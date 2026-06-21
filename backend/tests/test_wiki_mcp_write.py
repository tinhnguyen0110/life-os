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
from modules.wiki import reader
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


# --------------------------------------------------------------------------- #
# MCP-PROPOSE-FOLDER (#80): propose_note/propose_moc thread `folder` into the    #
# note so an agent can file a foldered note (e.g. Repos/ for #64-P2 repo_memory) #
# — was silently dropped (landed at root). folder=None → root (back-compat).      #
# --------------------------------------------------------------------------- #
def test_propose_note_folder_lands_in_folder(wiki_db):
    """#80: propose_note(folder="Repos") → the note LANDS at folder="Repos" (was '' before the fix).
    Verify on the stored note, not just the payload (behavior-test)."""
    r = write_server.propose_note("myrepo", "# myrepo\nmemo", folder="Repos")
    assert r["applied"] is True and r["noteId"] is not None
    note = wsvc.get_note(r["noteId"])
    assert note is not None and note.folder == "Repos", f"folder dropped — got {note.folder!r}"


def test_propose_note_no_folder_is_root_backcompat(wiki_db):
    """folder omitted → root (''), existing propose_note calls unaffected."""
    r = write_server.propose_note("rootnote", "body")
    note = wsvc.get_note(r["noteId"])
    assert note is not None and note.folder == ""  # back-compat: root


def test_propose_moc_folder_lands(wiki_db):
    """propose_moc also threads folder (#80)."""
    r = write_server.propose_moc("MyMOC", "links...", folder="Maps")
    note = wsvc.get_note(r["noteId"])
    assert note is not None and note.folder == "Maps" and note.noteType == "moc"


def test_repo_memory_round_trip_via_mcp_propose(wiki_db):
    """THE #64-P2 round-trip #80 unblocks: an agent proposes a Repos/<name> note via the MCP
    write-through → it AUTO-LANDS in Repos/ → repo_memory(<name>) FINDS it (end-to-end via the MCP
    write, not the REST-seed workaround). This is the gap the dropped-folder caused."""
    from modules.code_insight import reader as ci_reader
    r = write_server.propose_note("cairn", "# cairn\nstack: node\ndecisions: agent-first", folder="Repos")
    assert r["applied"] is True
    mem = ci_reader.get_memory("cairn")
    assert mem.found is True and mem.note is not None, "repo_memory must find the MCP-landed Repos/ note"
    assert "agent-first" in mem.note.body


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


# --------------------------------------------------------------------------- #
# WIKI-LINK-CORRECTNESS (#26) — propose_link target-resolution STATUS           #
# (a mistyped/nonexistent target isn't a SILENT ghost; the result surfaces it). #
# --------------------------------------------------------------------------- #
def test_propose_link_resolved_target_surfaces_id(wiki_db):
    a, b = _seed_note("A"), _seed_note("Target B")
    r = write_server.propose_link(a, "Target B")  # title that resolves to exactly 1
    assert r.get("targetResolved") == b, "an exact title match must surface targetResolved=<id>"
    assert "targetGhost" not in r and "targetAmbiguous" not in r


def test_propose_link_by_id_surfaces_resolved(wiki_db):
    a, b = _seed_note("A"), _seed_note("B")
    r = write_server.propose_link(a, str(b))  # id link to an existing note
    assert r.get("targetResolved") == b


def test_propose_link_ghost_target_surfaces_status_not_silent(wiki_db):
    """THE #26 fix: a non-existent title → result SURFACES targetGhost (NOT a silent ghost).
    The link STILL writes (a ghost can be intentional — auto-resolves later, B4)."""
    a = _seed_note("A")
    r = write_server.propose_link(a, "Nonexistent Title ZZZ")
    assert r.get("targetGhost") is True, "a nonexistent target must surface targetGhost"
    assert "matches no existing note" in r.get("targetNote", "")
    assert r["applied"] is True, "the ghost link still WRITES (not blocked)"
    assert "[[Nonexistent Title ZZZ]]" in wsvc.get_note(a).content


def test_propose_link_ambiguous_target_surfaces_status(wiki_db):
    """A title matching >1 note → targetAmbiguous + the count + the lowest id used."""
    a = _seed_note("A")
    dup1 = _seed_note("Dup")
    dup2 = _seed_note("Dup")  # same title → ambiguous
    r = write_server.propose_link(a, "Dup")
    assert r.get("targetAmbiguous") is True and r.get("targetMatchCount") == 2
    assert r.get("targetResolvedTo") == min(dup1, dup2), "the index uses the lowest id"


def test_propose_link_ghost_id_target_surfaces_status(wiki_db):
    """An id-link to a non-existent id → targetGhost (the id branch of resolution)."""
    a = _seed_note("A")
    r = write_server.propose_link(a, "99999")
    assert r.get("targetGhost") is True and "does not exist" in r.get("targetNote", "")


# --------------------------------------------------------------------------- #
# #26 — correlationId is PER-OPERATION (not per-session)                         #
# --------------------------------------------------------------------------- #
def test_correlation_id_is_per_operation(wiki_db):
    """Two independent propose calls get DIFFERENT correlationIds (#26 — was per-session: the
    dogfood saw note + link share one id, couldn't tell two writes apart)."""
    r1 = write_server.propose_note("op1", "b")
    r2 = write_server.propose_note("op2", "b")
    assert r1["correlationId"] and r2["correlationId"]
    assert r1["correlationId"] != r2["correlationId"], "each propose op must get its own id"


# --------------------------------------------------------------------------- #
# #19+#26 JOIN — the IMMEDIACY round-trip: propose_link(A→B) → backlinks(B)      #
# IMMEDIATELY includes A (the index updates SYNCHRONOUSLY on the write-through). #
# --------------------------------------------------------------------------- #
def test_propose_link_immediacy_backlink_synchronous(wiki_db):
    """propose_link(A→B) → an IMMEDIATE backlinks(B) includes A. The link index (replace_links)
    updates synchronously in the writer's apply (single-writer, in-process) — no reindex lag."""
    a, b = _seed_note("A"), _seed_note("Target B")
    r = write_server.propose_link(a, "Target B")
    assert r["applied"] is True
    bl = reader.backlinks(b)  # IMMEDIATELY after the write — no sleep, no re-poll
    assert a in {x["id"] for x in bl.get("linked", [])}, \
        "backlinks(B) must IMMEDIATELY include A (synchronous index on write-through)"


# --------------------------------------------------------------------------- #
# DON'T-CORRUPT GUARD (#20 MOC regression) — directed-inbound semantic UNCHANGED #
# --------------------------------------------------------------------------- #
def test_moc_with_only_outbound_keeps_linked_empty(wiki_db):
    """THE #19 don't-corrupt guard: a MOC-like note (0 INbound, N OUTbound) STILL returns
    backlinks linked:[] + the outbound in `outbound` — proves the directed-INbound semantic is
    UNCHANGED (we did NOT fold outbound into linked, which would inject phantom inbound links).
    + a note WITH real inbound shows it in linked (the other direction)."""
    # moc links OUT to t1,t2,t3 (3 outbound) but has 0 inbound
    t1, t2, t3 = _seed_note("T1"), _seed_note("T2"), _seed_note("T3")
    moc = wsvc.create_note(NoteCreateInput(
        title="MOC", content=f"see [[{t1}]] [[{t2}]] [[{t3}]]")).id
    bl_moc = reader.backlinks(moc)
    assert bl_moc.get("linked", []) == [], "a MOC with 0 inbound must have linked:[] (NOT its outbound)"
    assert len(bl_moc.get("outbound", [])) == 3, "the 3 outbound are in `outbound`, not `linked`"
    # the OTHER direction: a target HAS real inbound (the moc) → it shows in linked
    bl_t1 = reader.backlinks(t1)
    assert moc in {x["id"] for x in bl_t1.get("linked", [])}, "a real inbound shows in linked"


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
    (the control that makes write-through reversible/inspectable). #26: audit rows are tagged with
    the PER-OP correlationId (not SESSION_ID), so query by the result's correlationId — which also
    proves the per-op id is what tags this operation's trace."""
    r = write_server.propose_note("a", "b", rationale="r")
    corr = r["correlationId"]
    rows = pstore.recent_audit(correlation_id=corr, limit=1000)
    tools = {row["tool"] for row in rows}
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
        "wiki_delete_note", "wiki_restore_note",  # #94 soft-delete + restore
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
