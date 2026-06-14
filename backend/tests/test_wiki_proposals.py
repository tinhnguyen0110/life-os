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


def test_api_S1_rest_post_cannot_bypass_p1_even_with_agent_actor(client):
    # F1-S1 END-TO-END regression guard: toggle autonomy ON, then POST a proposal via
    # the REST endpoint sending actor="agent:evil" — it must STAY PENDING (the REST
    # router is the human channel, never auto_apply_eligible). The forged actor string
    # cannot bypass the human P1 queue.
    client.patch("/settings", json={"wikiAgentAutonomous": True})
    r = client.post("/wiki/proposals", json={
        "kind": "note_create", "payload": {"title": "forged"}, "actor": "agent:evil"})
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "pending"  # NOT accepted — P1 not bypassed
    client.patch("/settings", json={"wikiAgentAutonomous": False})  # restore


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


# --------------------------------------------------------------------------- #
# W4d — agent autonomy toggle (USER-ORDERED, reverses D8). Chokepoint in        #
# create_proposal: ON + auto_apply_eligible CALLER → auto-accept (agent:auto);   #
# OFF (default) → pending. F1-S1: auto-apply keys on the CALLER (auto_apply_     #
# eligible param), NOT inp.actor — a REST/human POST can't bypass P1 by sending  #
# actor="agent". Tests live here (test-where-the-reader-greps).                  #
# --------------------------------------------------------------------------- #
from modules.settings import service as cfg  # noqa: E402
from modules.settings.schema import AppConfigPatch  # noqa: E402


def _set_autonomous(on: bool) -> None:
    cfg.set_config(AppConfigPatch(wikiAgentAutonomous=on))


def test_autonomy_off_default_proposal_stays_pending(wiki_db):
    # default OFF (fresh config) — even an eligible caller's propose stays pending.
    before = wiki_store.count_notes()
    p = psvc.create_proposal(ProposalCreateInput(
        kind="note_create", payload={"title": "x"}, actor="mcp:writer",
    ), auto_apply_eligible=True)
    assert p["status"] == "pending"
    assert wiki_store.count_notes() == before


def test_autonomy_on_eligible_caller_auto_applies(wiki_db):
    # the MCP write-server channel (auto_apply_eligible=True) + toggle ON → auto-apply.
    _set_autonomous(True)
    before = wiki_store.count_notes()
    p = psvc.create_proposal(ProposalCreateInput(
        kind="note_create", payload={"title": "auto note", "content": "body"},
        actor="mcp:writer",
    ), auto_apply_eligible=True)
    assert p["status"] == "accepted" and p["decidedBy"] == "agent:auto"
    assert p["appliedNoteId"] is not None
    assert wiki_store.count_notes() == before + 1
    assert wsvc.get_note(p["appliedNoteId"]).title == "auto note"


def test_autonomy_on_ineligible_caller_does_not_auto_apply(wiki_db):
    # the REST/human channel (auto_apply_eligible defaults False) NEVER auto-applies,
    # even with toggle ON.
    _set_autonomous(True)
    before = wiki_store.count_notes()
    p = psvc.create_proposal(ProposalCreateInput(
        kind="note_create", payload={"title": "human draft"}, actor="human",
    ))
    assert p["status"] == "pending"
    assert wiki_store.count_notes() == before


def test_S1_rest_actor_string_cannot_bypass_p1(wiki_db):
    # F1-S1 REGRESSION GUARD (the security fix): a REST/human-channel POST that
    # SENDS actor="agent" (or any agent string) but is NOT auto_apply_eligible must
    # STAY PENDING when the toggle is ON. The trust boundary keys on the CALLER, not
    # the client's actor string — a forged actor cannot bypass the human P1 queue.
    _set_autonomous(True)
    before = wiki_store.count_notes()
    p = psvc.create_proposal(ProposalCreateInput(
        kind="note_create", payload={"title": "forged agent"}, actor="agent:evil",
    ))  # NOT auto_apply_eligible (the REST router never passes it)
    assert p["status"] == "pending", "a forged actor string must NOT auto-apply"
    assert wiki_store.count_notes() == before


def test_autonomy_on_bad_target_fails_soft_stays_pending(wiki_db):
    # D-W4d.3: auto-apply of a bad edit fails-closed → proposal stays pending + warning.
    _set_autonomous(True)
    p = psvc.create_proposal(ProposalCreateInput(
        kind="note_edit", targetId=4242, payload={"title": "x"}, actor="agent:claude",
    ), auto_apply_eligible=True)
    assert p["status"] == "pending"
    assert "auto-apply failed" in (p.get("warning") or "")
    # it's still retriable in the queue
    assert psvc.get_proposal(p["id"])["status"] == "pending"


def test_autonomy_live_flip(wiki_db):
    # ON → lands; flip OFF → next propose is pending again (read per-call, no restart).
    _set_autonomous(True)
    on = psvc.create_proposal(ProposalCreateInput(
        kind="note_create", payload={"title": "on"}, actor="mcp:writer"),
        auto_apply_eligible=True)
    assert on["status"] == "accepted"
    _set_autonomous(False)
    off = psvc.create_proposal(ProposalCreateInput(
        kind="note_create", payload={"title": "off"}, actor="mcp:writer"),
        auto_apply_eligible=True)
    assert off["status"] == "pending"


def test_autonomy_auto_apply_audits_both_rows(wiki_db):
    # an auto-applied write has BOTH the propose audit row AND the accept row
    # (accept's actor = the decidedBy = agent:auto).
    _set_autonomous(True)
    p = psvc.create_proposal(ProposalCreateInput(
        kind="note_create", payload={"title": "audited auto"}, actor="agent:claude",
        correlationId="auto-sess",
    ), auto_apply_eligible=True)
    tools = [(r["tool"], r["actor"]) for r in pstore.recent_audit(correlation_id="auto-sess", limit=50)]
    assert ("propose", "agent:claude") in tools  # the create audit
    assert ("accept", "agent:auto") in tools      # the auto-accept audit


# --------------------------------------------------------------------------- #
# _apply — payload-translation error branches not covered by the accept tests   #
# above. _apply is the dispatch core; calling it directly exercises the guards   #
# that create_proposal's schema validation would otherwise mask.                 #
# --------------------------------------------------------------------------- #
def test_apply_note_edit_without_target_is_apply_error(wiki_db):
    # note_edit needs a targetId; a proposal dict lacking one → ApplyError, with a
    # message that names the missing field (distinct from a wrong-but-present id).
    with pytest.raises(psvc.ApplyError) as ei:
        psvc._apply({"kind": "note_edit", "targetId": None, "payload": {"title": "x"}})
    assert "targetId" in str(ei.value) or "no targetId" in str(ei.value)


def test_apply_unknown_kind_is_apply_error(wiki_db):
    # A kind the dispatcher doesn't recognise → ApplyError naming the kind. (The
    # schema blocks this at create-time, so only a direct/forged dict reaches it.)
    with pytest.raises(psvc.ApplyError) as ei:
        psvc._apply({"kind": "teleport", "payload": {}})
    assert "teleport" in str(ei.value)


def test_apply_link_add_without_target_is_apply_error(wiki_db):
    # link_add with no targetId → ApplyError (the _apply_link_add guard).
    with pytest.raises(psvc.ApplyError):
        psvc._apply({"kind": "link_add", "targetId": None, "payload": {"target": "Note"}})


def test_autonomous_enabled_defaults_off_when_config_read_raises(wiki_db, monkeypatch):
    # Fail-soft: if reading the config raises, autonomy must resolve to OFF (the
    # SAFE default — never auto-apply on an unreadable config), not propagate.
    import modules.settings.service as settings_service
    def boom():
        raise RuntimeError("config store unreadable")
    monkeypatch.setattr(settings_service, "get_config", boom)
    assert psvc._autonomous_enabled() is False


def test_audit_failure_does_not_break_the_action(wiki_db, monkeypatch):
    # Fail-soft add-on: if the audit append RAISES, the primary proposal mutation
    # must still succeed (audit is best-effort). Patch append_audit to blow up and
    # assert the proposal was still created and is queryable.
    def boom(**kwargs):
        raise RuntimeError("audit table gone")
    monkeypatch.setattr(psvc.pstore, "append_audit", boom)

    p = psvc.create_proposal(ProposalCreateInput(
        kind="note_create", payload={"title": "survives audit failure"},
    ))
    assert p["id"] is not None
    assert psvc.get_proposal(p["id"]) is not None  # the action completed despite audit error
