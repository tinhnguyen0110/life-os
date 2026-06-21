"""tests/test_wiki_write_feedback.py — WIKI-WRITE-FEEDBACK (#35).

When a HUMAN overrides (edits/deletes) an AGENT-written note, capture WHY ({reason
enum, text}) into the EXISTING op_log detail, + a read-back surface (wiki_my_feedback
MCP + GET /wiki/feedback REST) so a consumer-agent reads its own feedback and writes
less junk. NO new store/table (reuses wiki_op_log.detail). The KEY distinguishing case:
a human overriding a HUMAN-written note → NO feedback row (only agent work is feedback).

BEHAVIOR-TESTED (not field-read): drive create→override→read-back through the real
single-writer queue + assert value-by-value against what was seeded.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.wiki import reader, service
from modules.wiki import store as wiki_store
from modules.wiki.mcp import read_server as wiki_read_server
from modules.wiki.schema import NoteCreateInput, NoteUpdateInput


@pytest.fixture
def wiki_db(isolated_paths):
    """isolated_paths + wiki tables on the fresh connection."""
    wiki_store.init_wiki_tables()
    return isolated_paths


@pytest.fixture
def client(wiki_db):
    from main import create_app
    return TestClient(create_app())


def _agent_note(title="Agent Note", body="agent body", actor="mcp:writer") -> int:
    return service.create_note(NoteCreateInput(title=title, content=body), actor=actor).id


# --------------------------------------------------------------------------- #
# Capture — human overrides an AGENT note WITH feedback                          #
# --------------------------------------------------------------------------- #
def test_human_edit_of_agent_note_captures_feedback(wiki_db):
    """Human EDITS an agent-written note with {off-scope, text} → wiki_my_feedback
    returns exactly that row, value-by-value."""
    nid = _agent_note(title="Off-Topic Note")
    service.update_note(nid, NoteUpdateInput(content="human fixed it"), actor="human",
                        feedback={"reason": "off-scope", "text": "not in scope for this vault"})

    fb = reader.my_feedback()
    assert fb["count"] == 1
    row = fb["feedback"][0]
    assert row["noteId"] == nid
    assert row["reason"] == "off-scope"
    assert row["text"] == "not in scope for this vault"
    assert row["originalTitle"] == "Off-Topic Note"   # title AT override time
    assert row["overrideKind"] == "edit"
    assert row["overriddenAt"]   # ISO ts present


def test_human_delete_of_agent_note_captures_feedback(wiki_db):
    """Human DELETES an agent-written note with {duplicate, text} → captured, kind=delete,
    originalTitle survives the delete (snapshotted into the op detail)."""
    nid = _agent_note(title="Dup Note", actor="agent")
    service.delete_note(nid, actor="human",
                        feedback={"reason": "duplicate", "text": "same as note #2"})

    fb = reader.my_feedback()
    assert fb["count"] == 1
    row = fb["feedback"][0]
    assert row["noteId"] == nid
    assert row["reason"] == "duplicate"
    assert row["overrideKind"] == "delete"
    assert row["originalTitle"] == "Dup Note"   # survived the delete (note row is gone)


# --------------------------------------------------------------------------- #
# THE distinguishing case — human overrides a HUMAN note → NO feedback           #
# --------------------------------------------------------------------------- #
def test_human_edit_of_human_note_is_NOT_feedback(wiki_db):
    """DISTINGUISHING: a human editing their OWN (human-written) note is NOT feedback to
    an agent — even WITH a reason supplied, no feedback row appears. Proves the agent-actor
    gate is real, not a catch-all on any override."""
    nid = service.create_note(NoteCreateInput(title="My Note", content="mine"), actor="human").id
    service.update_note(nid, NoteUpdateInput(content="my own edit"), actor="human",
                        feedback={"reason": "wrong", "text": "must NOT be captured"})

    fb = reader.my_feedback()
    assert fb["count"] == 0, f"human-override-of-human-note must NOT capture feedback, got {fb}"


def test_human_delete_of_human_note_is_NOT_feedback(wiki_db):
    """Same gate on the delete path: human deletes own note → no feedback row."""
    nid = service.create_note(NoteCreateInput(title="Mine 2", content="x"), actor="human").id
    service.delete_note(nid, actor="human", feedback={"reason": "outdated", "text": "skip"})
    assert reader.my_feedback()["count"] == 0


def test_second_human_override_prior_op_human_not_captured(wiki_db):
    """Edge (decided + logged): agent creates → human edits (FIRST override, captured) →
    human edits AGAIN. The 2nd edit's PRIOR op is human → NOT captured. Only the FIRST
    human override of agent work is the learning signal."""
    nid = _agent_note(title="Edge Note")
    service.update_note(nid, NoteUpdateInput(content="first human edit"), actor="human",
                        feedback={"reason": "wrong", "text": "first"})
    service.update_note(nid, NoteUpdateInput(content="second human edit"), actor="human",
                        feedback={"reason": "low-quality", "text": "second — should NOT capture"})

    fb = reader.my_feedback()
    assert fb["count"] == 1, "only the FIRST human override of agent work is captured"
    assert fb["feedback"][0]["reason"] == "wrong"   # the first one


# --------------------------------------------------------------------------- #
# Silent override (no feedback) + honest-empty                                   #
# --------------------------------------------------------------------------- #
def test_silent_override_of_agent_note_no_feedback_row(wiki_db):
    """A human can override an agent note SILENTLY (no reason) → no feedback detail,
    wiki_my_feedback doesn't return that op. Feedback is OPTIONAL."""
    nid = _agent_note()
    service.update_note(nid, NoteUpdateInput(content="silent fix"), actor="human")  # no feedback
    assert reader.my_feedback()["count"] == 0


def test_honest_empty_no_overrides(wiki_db):
    """No overrides at all → honest-empty {feedback: [], count: 0} (not omitted)."""
    assert reader.my_feedback() == {"feedback": [], "count": 0}


def test_text_optional_reason_only(wiki_db):
    """text is OPTIONAL — a reason with no text is captured (text → None)."""
    nid = _agent_note()
    service.update_note(nid, NoteUpdateInput(content="x"), actor="human",
                        feedback={"reason": "other", "text": None})
    row = reader.my_feedback()["feedback"][0]
    assert row["reason"] == "other" and row["text"] is None


# --------------------------------------------------------------------------- #
# REST API — PUT/DELETE override params + GET /wiki/feedback                      #
# --------------------------------------------------------------------------- #
def test_rest_put_with_override_captures(client):
    """PUT /wiki/notes/{id}?overrideReason=...&overrideText=... on an agent note →
    GET /wiki/feedback returns it."""
    nid = _agent_note(title="REST Edit")
    r = client.put(f"/wiki/notes/{nid}?overrideReason=off-scope&overrideText=nope",
                   json={"content": "human via REST"})
    assert r.status_code == 200

    data = client.get("/wiki/feedback").json()["data"]
    assert data["count"] == 1
    assert data["feedback"][0]["reason"] == "off-scope"
    assert data["feedback"][0]["text"] == "nope"
    assert data["feedback"][0]["overrideKind"] == "edit"


def test_rest_delete_with_override_captures(client):
    """DELETE /wiki/notes/{id}?overrideReason=... on an agent note → captured kind=delete."""
    nid = _agent_note(title="REST Delete", actor="agent")
    r = client.delete(f"/wiki/notes/{nid}?overrideReason=outdated")
    assert r.status_code == 200
    data = client.get("/wiki/feedback").json()["data"]
    assert data["count"] == 1
    assert data["feedback"][0]["reason"] == "outdated"
    assert data["feedback"][0]["overrideKind"] == "delete"
    assert data["feedback"][0]["text"] is None   # text omitted → None


def test_rest_bad_reason_is_422(client):
    """A reason NOT in the enum → 422 (Pydantic Literal at the boundary)."""
    nid = _agent_note()
    r = client.put(f"/wiki/notes/{nid}?overrideReason=not-a-reason",
                   json={"content": "x"})
    assert r.status_code == 422


def test_rest_feedback_honest_empty(client):
    """GET /wiki/feedback with nothing captured → {feedback: [], count: 0}."""
    data = client.get("/wiki/feedback").json()["data"]
    assert data == {"feedback": [], "count": 0}


# --------------------------------------------------------------------------- #
# REST ≡ MCP parity (#24) — same data, MCP adds the `found` wrapper              #
# --------------------------------------------------------------------------- #
def test_rest_mcp_byte_identical_data(client):
    """The wiki_my_feedback MCP tool returns the byte-identical `feedback`+`count` as
    REST GET /wiki/feedback's `data`, modulo the MCP `found` existence-wrapper (#24)."""
    nid = _agent_note(title="Parity Note")
    client.put(f"/wiki/notes/{nid}?overrideReason=low-quality&overrideText=thin",
               json={"content": "human"})

    rest = client.get("/wiki/feedback").json()["data"]   # {feedback, count}
    mcp = wiki_read_server.wiki_my_feedback()            # {feedback, count, found}
    # byte-identical on the shared keys
    assert mcp["feedback"] == rest["feedback"]
    assert mcp["count"] == rest["count"]
    # MCP existence wrapper
    assert mcp["found"] is True


def test_mcp_found_false_when_empty(wiki_db):
    """wiki_my_feedback honest-empty → {feedback: [], count: 0, found: false}."""
    out = wiki_read_server.wiki_my_feedback()
    assert out == {"feedback": [], "count": 0, "found": False}


def test_mcp_tool_registered(wiki_db):
    """wiki_my_feedback is in the wiki-read TOOLS registry (the count-bump consumer)."""
    assert "wiki_my_feedback" in wiki_read_server.TOOLS
