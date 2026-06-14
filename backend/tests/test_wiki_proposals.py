"""tests/test_wiki_proposals.py — Wiki proposal / approval-queue tests (Sprint W4a).

Coverage:
  - schema: ProposalCreateInput defaults, actor strip, BatchAccept min_length.
  - store: table init idempotent, insert→get, list+filter, count_by_status,
    mark_decided pending-guard, audit append + recent.
  - service apply-on-accept: note_create / note_edit / link_add / link_remove /
    merge / moc each ACCEPT → the M1 mutation actually lands (re-GET reflects it).
  - reject applies NOTHING. double-accept → AlreadyDecided. bad payload → ApplyError
    + row stays pending (fail-closed). batch-accept partial success.
  - API: full propose→GET pending→accept→re-GET note reflects round-trip + 404/409/422.

Mirrors test_wiki.py: the ``wiki_db`` fixture rebinds the connection, so BOTH
wiki tables and proposal tables are re-registered on the fresh per-test conn.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from modules.wiki import proposals_service as psvc
from modules.wiki import proposals_store as pstore
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.proposals_schema import (
    BatchAcceptInput,
    ProposalCreateInput,
)
from modules.wiki.schema import NoteCreateInput


@pytest.fixture
def wiki_db(isolated_paths):
    """isolated_paths + wiki AND proposal tables on the fresh connection."""
    wiki_store.init_wiki_tables()
    pstore.init_proposal_tables()
    return isolated_paths


def _mk_note(title="seed", content="body") -> int:
    return wsvc.create_note(NoteCreateInput(title=title, content=content)).id


# --------------------------------------------------------------------------- #
# schema                                                                       #
# --------------------------------------------------------------------------- #
def test_proposal_create_input_defaults():
    inp = ProposalCreateInput(kind="note_create")
    assert inp.kind == "note_create"
    assert inp.targetId is None
    assert inp.payload == {}
    assert inp.actor == "agent"
    assert inp.correlationId is None


def test_proposal_actor_blank_defaults_to_agent():
    assert ProposalCreateInput(kind="note_create", actor="   ").actor == "agent"


def test_proposal_rejects_bad_kind():
    with pytest.raises(ValidationError):
        ProposalCreateInput(kind="nuke_everything")


def test_batch_accept_requires_nonempty_ids():
    with pytest.raises(ValidationError):
        BatchAcceptInput(ids=[])


# --------------------------------------------------------------------------- #
# store                                                                        #
# --------------------------------------------------------------------------- #
def test_init_proposal_tables_idempotent(wiki_db):
    pstore.init_proposal_tables()
    pstore.init_proposal_tables()  # second call must not raise


def test_insert_get_proposal(wiki_db):
    pid = pstore.insert_proposal(
        kind="note_create", target_id=None, payload={"title": "x"},
        rationale="why", actor="agent:claude", correlation_id="sess-1",
        created="2026-06-14T00:00:00+00:00",
    )
    p = pstore.get_proposal(pid)
    assert p is not None
    assert p["kind"] == "note_create"
    assert p["payload"] == {"title": "x"}
    assert p["status"] == "pending"
    assert p["correlationId"] == "sess-1"
    assert p["decided"] is None


def test_list_and_filter_by_status(wiki_db):
    a = pstore.insert_proposal(kind="note_create", target_id=None, payload={},
                               rationale="", actor="agent", correlation_id=None,
                               created="t1")
    pstore.insert_proposal(kind="note_edit", target_id=1, payload={},
                           rationale="", actor="agent", correlation_id=None,
                           created="t2")
    pstore.mark_decided(proposal_id=a, status="accepted", decided="t3",
                        decided_by="human", applied_note_id=9)
    pending = pstore.list_proposals(status="pending")
    accepted = pstore.list_proposals(status="accepted")
    assert len(pending) == 1 and pending[0]["kind"] == "note_edit"
    assert len(accepted) == 1 and accepted[0]["appliedNoteId"] == 9
    assert pstore.count_by_status() == {"pending": 1, "accepted": 1}
    # unknown status → empty
    assert pstore.list_proposals(status="bogus") == []


def test_mark_decided_only_when_pending(wiki_db):
    pid = pstore.insert_proposal(kind="note_create", target_id=None, payload={},
                                 rationale="", actor="agent", correlation_id=None,
                                 created="t")
    assert pstore.mark_decided(proposal_id=pid, status="accepted", decided="t",
                               decided_by="human", applied_note_id=1) is True
    # second decide is a no-op (already terminal)
    assert pstore.mark_decided(proposal_id=pid, status="rejected", decided="t",
                               decided_by="human", applied_note_id=None) is False


def test_audit_append_and_recent(wiki_db):
    pstore.append_audit(tool="search", params={"q": "x"}, actor="agent",
                        correlation_id="s1", ts="t1")
    pstore.append_audit(tool="get_note", params={"id": 3}, actor="agent",
                        correlation_id="s2", ts="t2")
    rows = pstore.recent_audit()
    assert len(rows) == 2 and rows[0]["tool"] == "get_note"  # newest first
    scoped = pstore.recent_audit(correlation_id="s1")
    assert len(scoped) == 1 and scoped[0]["params"] == {"q": "x"}


# --------------------------------------------------------------------------- #
# service — create records intent only                                          #
# --------------------------------------------------------------------------- #
def test_audit_row_appended_per_action(wiki_db):
    # create → 1 audit row (tool=propose)
    p = psvc.create_proposal(ProposalCreateInput(
        kind="note_create", payload={"title": "audited"}, actor="agent:x",
        correlationId="sess-audit",
    ))
    audit = pstore.recent_audit(correlation_id="sess-audit")
    assert [a["tool"] for a in audit] == ["propose"]
    # accept → +1 audit row (tool=accept)
    psvc.accept_proposal(p["id"], decided_by="human")
    tools = [a["tool"] for a in pstore.recent_audit(correlation_id="sess-audit")]
    assert "accept" in tools and "propose" in tools and len(tools) == 2
    # reject path on a fresh proposal → audit tool=reject
    p2 = psvc.create_proposal(ProposalCreateInput(
        kind="note_create", payload={}, correlationId="sess-rej",
    ))
    psvc.reject_proposal(p2["id"])
    assert {a["tool"] for a in pstore.recent_audit(correlation_id="sess-rej")} == {"propose", "reject"}


def test_create_proposal_writes_nothing_to_vault(wiki_db):
    before = wiki_store.count_notes()
    p = psvc.create_proposal(ProposalCreateInput(
        kind="note_create", payload={"title": "AI idea", "content": "x"},
        rationale="agent thinks this matters",
    ))
    assert p["status"] == "pending"
    # NOTHING applied — note count unchanged, no note created yet.
    assert wiki_store.count_notes() == before


# --------------------------------------------------------------------------- #
# service — apply-on-accept lands the real M1 mutation                          #
# --------------------------------------------------------------------------- #
def test_accept_note_create_lands_a_note(wiki_db):
    p = psvc.create_proposal(ProposalCreateInput(
        kind="note_create", payload={"title": "Spaced repetition", "content": "body"},
        actor="agent:claude",
    ))
    before = wiki_store.count_notes()
    accepted = psvc.accept_proposal(p["id"])
    assert accepted["status"] == "accepted"
    assert wiki_store.count_notes() == before + 1
    # the landed note actually exists with the proposed content
    landed = wsvc.get_note(accepted["appliedNoteId"])
    assert landed is not None and landed.title == "Spaced repetition"
    # provenance: the proposing actor becomes the note's author (spec §2b)
    assert landed.author == "agent:claude"


def test_accept_note_create_respects_explicit_author(wiki_db):
    # an explicit author in the payload wins over the proposing actor.
    p = psvc.create_proposal(ProposalCreateInput(
        kind="note_create", payload={"title": "x", "author": "human"},
        actor="agent:claude",
    ))
    accepted = psvc.accept_proposal(p["id"])
    assert wsvc.get_note(accepted["appliedNoteId"]).author == "human"


def test_accept_note_edit_lands_the_edit(wiki_db):
    nid = _mk_note(title="old", content="old body")
    p = psvc.create_proposal(ProposalCreateInput(
        kind="note_edit", targetId=nid,
        payload={"title": "new title", "status": "evergreen"},
    ))
    psvc.accept_proposal(p["id"])
    edited = wsvc.get_note(nid)
    assert edited.title == "new title" and edited.status == "evergreen"


def test_accept_link_add_adds_a_wikilink(wiki_db):
    a = _mk_note(title="Source", content="source body")
    b = _mk_note(title="Target", content="target body")
    p = psvc.create_proposal(ProposalCreateInput(
        kind="link_add", targetId=a, payload={"target": b},
    ))
    psvc.accept_proposal(p["id"])
    src = wsvc.get_note(a)
    assert f"[[{b}]]" in src.content
    # the resolved edge actually landed in the graph
    assert any(r["target_id"] == b for r in wiki_store.links_from(a))


def test_accept_link_remove_strips_the_wikilink(wiki_db):
    a = _mk_note(title="Source", content="see [[2]] here")
    _mk_note(title="Target", content="t")  # note 2
    p = psvc.create_proposal(ProposalCreateInput(
        kind="link_remove", targetId=a, payload={"target": 2},
    ))
    psvc.accept_proposal(p["id"])
    src = wsvc.get_note(a)
    assert "[[2]]" not in src.content


def test_accept_merge_merges_notes(wiki_db):
    src = _mk_note(title="dupe", content="dupe body")
    tgt = _mk_note(title="canonical", content="canon body")
    p = psvc.create_proposal(ProposalCreateInput(
        kind="merge", payload={"sourceId": src, "targetId": tgt},
    ))
    accepted = psvc.accept_proposal(p["id"])
    assert accepted["appliedNoteId"] == tgt
    # source merged away → resolves via redirect to target
    note, warning = wsvc.resolve_note(src)
    assert note is not None and note.id == tgt and warning is not None


def test_accept_moc_creates_a_note(wiki_db):
    a = _mk_note(title="member-a")
    b = _mk_note(title="member-b")
    p = psvc.create_proposal(ProposalCreateInput(
        kind="moc",
        payload={"title": "MOC: theme", "content": f"- [[{a}]]\n- [[{b}]]"},
    ))
    accepted = psvc.accept_proposal(p["id"])
    moc = wsvc.get_note(accepted["appliedNoteId"])
    assert moc is not None and moc.title == "MOC: theme"
    # MOC's links to members resolved
    assert len([r for r in wiki_store.links_from(moc.id) if r["is_resolved"]]) == 2


# --------------------------------------------------------------------------- #
# service — reject applies nothing; guards; fail-closed                         #
# --------------------------------------------------------------------------- #
def test_reject_applies_nothing(wiki_db):
    before = wiki_store.count_notes()
    p = psvc.create_proposal(ProposalCreateInput(
        kind="note_create", payload={"title": "rejected idea"},
    ))
    rejected = psvc.reject_proposal(p["id"])
    assert rejected["status"] == "rejected" and rejected["appliedNoteId"] is None
    assert wiki_store.count_notes() == before  # nothing created


def test_double_accept_raises_already_decided(wiki_db):
    p = psvc.create_proposal(ProposalCreateInput(
        kind="note_create", payload={"title": "once"},
    ))
    psvc.accept_proposal(p["id"])
    with pytest.raises(psvc.AlreadyDecided):
        psvc.accept_proposal(p["id"])


def test_accept_after_reject_raises(wiki_db):
    p = psvc.create_proposal(ProposalCreateInput(kind="note_create", payload={}))
    psvc.reject_proposal(p["id"])
    with pytest.raises(psvc.AlreadyDecided):
        psvc.accept_proposal(p["id"])


def test_accept_missing_proposal_raises(wiki_db):
    with pytest.raises(psvc.ProposalNotFound):
        psvc.accept_proposal(99999)


def test_bad_payload_fails_closed_row_stays_pending(wiki_db):
    # note_edit with a non-existent target → ApplyError, row remains pending.
    p = psvc.create_proposal(ProposalCreateInput(
        kind="note_edit", targetId=4242, payload={"title": "x"},
    ))
    with pytest.raises(psvc.ApplyError):
        psvc.accept_proposal(p["id"])
    still = psvc.get_proposal(p["id"])
    assert still["status"] == "pending"  # NOT consumed — retriable


def test_merge_missing_ids_fails_closed(wiki_db):
    p = psvc.create_proposal(ProposalCreateInput(kind="merge", payload={"sourceId": 1}))
    with pytest.raises(psvc.ApplyError):
        psvc.accept_proposal(p["id"])
    assert psvc.get_proposal(p["id"])["status"] == "pending"


# --------------------------------------------------------------------------- #
# service — batch accept partial success                                        #
# --------------------------------------------------------------------------- #
def test_batch_accept_partial_success(wiki_db):
    good = psvc.create_proposal(ProposalCreateInput(
        kind="note_create", payload={"title": "good"},
    ))
    bad = psvc.create_proposal(ProposalCreateInput(
        kind="note_edit", targetId=7777, payload={"title": "x"},  # missing target
    ))
    result = psvc.batch_accept([good["id"], bad["id"], 99999])
    assert result["accepted"] == 1 and result["failed"] == 2
    ok_ids = {r["id"] for r in result["results"] if r["ok"]}
    bad_ids = {r["id"] for r in result["results"] if not r["ok"]}
    assert ok_ids == {good["id"]} and bad_ids == {bad["id"], 99999}
    # results preserve order + one entry per requested id
    assert [r["id"] for r in result["results"]] == [good["id"], bad["id"], 99999]
    # the good one applied; the bad one stays pending
    assert psvc.get_proposal(good["id"])["status"] == "accepted"
    assert psvc.get_proposal(bad["id"])["status"] == "pending"


# --------------------------------------------------------------------------- #
# API — full round-trip + status codes                                         #
# --------------------------------------------------------------------------- #
@pytest.fixture
def client(wiki_db):
    from main import app
    return TestClient(app)


def test_api_propose_list_accept_roundtrip(client):
    # propose
    r = client.post("/wiki/proposals", json={
        "kind": "note_create",
        "payload": {"title": "API note", "content": "via api"},
        "rationale": "agent proposes",
    })
    assert r.status_code == 200
    pid = r.json()["data"]["id"]
    # appears pending in the list with a counts badge
    lst = client.get("/wiki/proposals?status=pending").json()["data"]
    assert any(p["id"] == pid for p in lst["proposals"])
    assert lst["counts"]["pending"] >= 1
    # accept → applies
    acc = client.post(f"/wiki/proposals/{pid}/accept")
    assert acc.status_code == 200
    landed_id = acc.json()["data"]["appliedNoteId"]
    # re-GET the NOTE reflects the proposal (the mutation truly persisted)
    note = client.get(f"/wiki/notes/{landed_id}")
    assert note.status_code == 200 and note.json()["data"]["title"] == "API note"


def test_api_reject_then_accept_is_409(client):
    pid = client.post("/wiki/proposals", json={"kind": "note_create",
                                               "payload": {"title": "x"}}).json()["data"]["id"]
    assert client.post(f"/wiki/proposals/{pid}/reject").status_code == 200
    assert client.post(f"/wiki/proposals/{pid}/accept").status_code == 409


def test_api_accept_missing_is_404(client):
    assert client.post("/wiki/proposals/424242/accept").status_code == 404


def test_api_accept_bad_payload_is_422(client):
    pid = client.post("/wiki/proposals", json={
        "kind": "note_edit", "targetId": 555, "payload": {"title": "x"},
    }).json()["data"]["id"]
    assert client.post(f"/wiki/proposals/{pid}/accept").status_code == 422


def test_api_batch_accept(client):
    p1 = client.post("/wiki/proposals", json={"kind": "note_create",
                                              "payload": {"title": "b1"}}).json()["data"]["id"]
    p2 = client.post("/wiki/proposals", json={"kind": "note_create",
                                              "payload": {"title": "b2"}}).json()["data"]["id"]
    r = client.post("/wiki/proposals/accept-batch", json={"ids": [p1, p2]})
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["accepted"] == 2 and d["failed"] == 0
    assert all(res["ok"] for res in d["results"])


def test_api_empty_queue_honest(client):
    data = client.get("/wiki/proposals").json()["data"]
    assert data["proposals"] == [] and data["counts"] == {}


def test_api_list_defaults_to_pending_and_all_filter(client):
    # one accepted + one pending
    acc_id = client.post("/wiki/proposals", json={"kind": "note_create",
                                                  "payload": {"title": "a"}}).json()["data"]["id"]
    client.post(f"/wiki/proposals/{acc_id}/accept")
    client.post("/wiki/proposals", json={"kind": "note_create",
                                         "payload": {"title": "b"}})
    # default (no status) → pending only
    default = client.get("/wiki/proposals").json()["data"]["proposals"]
    assert all(p["status"] == "pending" for p in default) and len(default) == 1
    # status=all → both
    every = client.get("/wiki/proposals?status=all").json()["data"]["proposals"]
    assert len(every) == 2
    # status=accepted → just the accepted one
    accepted = client.get("/wiki/proposals?status=accepted").json()["data"]["proposals"]
    assert len(accepted) == 1 and accepted[0]["id"] == acc_id
