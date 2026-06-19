"""tests/test_agent_proposals_apply.py — human review-apply surface tests (MCP-4).

Closes the gated-action loop: accept APPLIES a proposal to its target module's REAL
service; reject does not; both are idempotent + audited.

Coverage (service layer + HTTP endpoints):
  - ACCEPT applies: accepting a decision/note/journal proposal creates a REAL entry in
    the target module (count goes up by exactly 1), appliedRef = the created id.
  - REJECT does not apply: status→rejected, target module unchanged.
  - IDEMPOTENT: accept twice creates the entry ONCE (not twice); reject-after-accept is
    a no-op (does not un-apply / re-apply).
  - AUDIT: each accept/reject appends exactly one immutable audit row (who/what/when).
  - project_update has no apply handler → accepted but applyError recorded (no crash,
    no fabricated write, no module edit).
  - unknown id → ProposalNotFound (404 on the endpoint).
  - endpoints: GET list/get/audit, POST accept/reject return the locked envelope.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcp_servers import proposals_service as svc
from mcp_servers import proposals_store as ps
from mcp_servers import write_server as ws


@pytest.fixture
def queue_db(isolated_paths):
    ps.init_proposal_tables()
    return isolated_paths


@pytest.fixture
def client(queue_db):
    """A FastAPI app with ONLY the agent-proposals module mounted (its router calls the
    apply layer). Mounting just this module keeps the test focused + fast."""
    from modules.agent_proposals.router import router

    app = FastAPI()
    app.include_router(router, prefix="/agent-proposals")
    return TestClient(app)


# --------------------------------------------------------------------------- #
# ACCEPT applies to the real target module                                      #
# --------------------------------------------------------------------------- #
def test_accept_decision_creates_real_entry(queue_db):
    from modules.decision_journal import service as dsvc

    p = ws.propose_decision("Trim crypto to 30%", 65, "portfolio", "over target")
    before, _ = dsvc.list_entries()
    result = svc.accept(p["id"], decided_by="user")
    after, _ = dsvc.list_entries()

    assert result["status"] == "accepted"
    assert result["appliedRef"] is not None
    assert result["applyError"] is None
    assert after.count == before.count + 1, "accept must create exactly one real entry"
    # the created entry is the one referenced by appliedRef
    created = dsvc.get_entry(result["appliedRef"])
    assert created is not None and created.decision == "Trim crypto to 30%"


def test_accept_note_creates_real_note(queue_db):
    from modules.notes import service as nsvc

    p = ws.propose_quicknote("Idea: ladder rebalance", "worth capturing", tags=["idea"])
    before = nsvc.list_notes()[0]
    result = svc.accept(p["id"])
    after = nsvc.list_notes()[0]
    assert result["status"] == "accepted" and result["appliedRef"]
    assert len(after) == len(before) + 1
    assert nsvc.get_note(result["appliedRef"]) is not None


def test_accept_journal_creates_real_entry(queue_db):
    from modules.journal import service as jsvc

    # JournalInput.action is Literal['BUY','SELL'] (uppercase) — use the real enum value.
    p = ws.propose_journal("BUY", "BTC", "DCA per plan", "fits ladder")
    before, _ = jsvc.list_entries()
    result = svc.accept(p["id"])
    after, _ = jsvc.list_entries()
    assert result["status"] == "accepted", f"apply failed: {result.get('applyError')}"
    assert result["appliedRef"]
    assert after.entries and len(after.entries) == len(before.entries) + 1


# --------------------------------------------------------------------------- #
# REJECT does not apply                                                          #
# --------------------------------------------------------------------------- #
def test_reject_does_not_apply(queue_db):
    from modules.decision_journal import service as dsvc

    p = ws.propose_decision("should NOT exist", 50, "general", "r")
    before, _ = dsvc.list_entries()
    result = svc.reject(p["id"], decided_by="user")
    after, _ = dsvc.list_entries()
    assert result["status"] == "rejected"
    assert result["appliedRef"] is None
    assert after.count == before.count, "reject must NOT create an entry"


# --------------------------------------------------------------------------- #
# IDEMPOTENCY — accept twice applies once                                        #
# --------------------------------------------------------------------------- #
def test_accept_twice_applies_once(queue_db):
    from modules.decision_journal import service as dsvc

    p = ws.propose_decision("apply once", 50, "general", "r")
    base, _ = dsvc.list_entries()
    r1 = svc.accept(p["id"])
    mid, _ = dsvc.list_entries()
    r2 = svc.accept(p["id"])           # second accept — must NOT re-apply
    end, _ = dsvc.list_entries()

    assert mid.count == base.count + 1
    assert end.count == mid.count, "second accept must not create a second entry"
    assert r1["appliedRef"] == r2["appliedRef"], "appliedRef stable across re-accept"
    assert r2["status"] == "accepted"


def test_reject_after_accept_is_noop(queue_db):
    from modules.decision_journal import service as dsvc

    p = ws.propose_decision("d", 50, "g", "r")
    svc.accept(p["id"])
    after_accept, _ = dsvc.list_entries()
    result = svc.reject(p["id"])       # already accepted — reject is a no-op
    end, _ = dsvc.list_entries()
    assert result["status"] == "accepted", "reject must not override an accepted apply"
    assert end.count == after_accept.count


# --------------------------------------------------------------------------- #
# AUDIT — one immutable row per accept/reject                                    #
# --------------------------------------------------------------------------- #
def test_accept_appends_one_audit_row(queue_db):
    p = ws.propose_decision("d", 50, "g", "r")
    svc.accept(p["id"], decided_by="user")
    svc.accept(p["id"], decided_by="user")  # idempotent — must NOT add a 2nd audit row
    audit = ps.list_audit(proposal_id=p["id"])
    assert len(audit) == 1
    assert audit[0]["action"] == "accept"
    assert audit[0]["decidedBy"] == "user"


def test_reject_appends_one_audit_row(queue_db):
    p = ws.propose_quicknote("t", "r")
    svc.reject(p["id"], decided_by="user")
    svc.reject(p["id"], decided_by="user")  # no-op — no 2nd row
    audit = ps.list_audit(proposal_id=p["id"])
    assert len(audit) == 1 and audit[0]["action"] == "reject"


# --------------------------------------------------------------------------- #
# project_update — no apply handler → accepted but applyError (no crash)         #
# --------------------------------------------------------------------------- #
def test_project_update_accept_records_apply_error(queue_db):
    p = ws.propose_project_update("life-os", "progress moved", progress=40)
    result = svc.accept(p["id"])
    assert result["status"] == "accepted"
    assert result["appliedRef"] is None
    assert result["applyError"] and "project_update" in result["applyError"]


# --------------------------------------------------------------------------- #
# unknown id                                                                     #
# --------------------------------------------------------------------------- #
def test_accept_unknown_id_raises(queue_db):
    with pytest.raises(svc.ProposalNotFound):
        svc.accept(999999)


def test_reject_unknown_id_raises(queue_db):
    with pytest.raises(svc.ProposalNotFound):
        svc.reject(999999)


# --------------------------------------------------------------------------- #
# HTTP endpoints                                                                 #
# --------------------------------------------------------------------------- #
def test_endpoint_list_defaults_to_pending(client):
    ws.propose_decision("d", 50, "g", "r")
    resp = client.get("/agent-proposals")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]["proposals"]) == 1
    assert body["data"]["proposals"][0]["status"] == "pending"
    assert body["data"]["counts"].get("pending") == 1


def test_endpoint_accept_applies_and_returns_envelope(client):
    from modules.decision_journal import service as dsvc

    p = ws.propose_decision("via http", 60, "portfolio", "r")
    before, _ = dsvc.list_entries()
    resp = client.post(f"/agent-proposals/{p['id']}/accept")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "accepted" and data["appliedRef"]
    after, _ = dsvc.list_entries()
    assert after.count == before.count + 1


def test_endpoint_reject_then_audit(client):
    p = ws.propose_quicknote("t", "r")
    assert client.post(f"/agent-proposals/{p['id']}/reject").status_code == 200
    audit = client.get(f"/agent-proposals/{p['id']}/audit").json()["data"]["audit"]
    assert len(audit) == 1 and audit[0]["action"] == "reject"


def test_endpoint_unknown_id_404(client):
    assert client.post("/agent-proposals/999999/accept").status_code == 404
    assert client.get("/agent-proposals/999999").status_code == 404


def test_endpoint_accept_project_update_warns(client):
    p = ws.propose_project_update("life-os", "r", progress=10)
    resp = client.post(f"/agent-proposals/{p['id']}/accept")
    assert resp.status_code == 200
    body = resp.json()
    # applyError surfaces as the envelope warning
    assert body["data"]["status"] == "accepted"
    assert body.get("warning") and "project_update" in body["warning"]
