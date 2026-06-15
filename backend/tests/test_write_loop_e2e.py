"""tests/test_write_loop_e2e.py — WRITE-LOOP-E2E (Task #51): the agent write loop, LOCKED.

The loop: propose_* (MCP write-server) → human accept (proposals_service.accept /
POST /agent-proposals/{id}/accept) → the row LANDS in the target module. Every prior MCP
test exercised one slice; this drives the WHOLE loop per kind and BEHAVIOR-TESTS THE SIDE
EFFECT — re-GET the target module and assert the row exists with the right fields (the
module is the source of truth), NOT "the handler was called" / applied_ref is non-None.

Coverage:
  - LANDS (decision_create, note_create, journal_create) — re-GET asserts the real row.
    For journal: propose LOWERCASE "buy" → assert landed action == "BUY" (the bug-killer —
    a "BUY"-uppercase fixture would pass even against the pre-fix code; lowercase is the
    distinguishing case that exercises the #51 normalization fix).
  - project_update honest-defer (pinned, NOT a bug) — accept → apply_error + 0 projects
    rows + proposal recorded. Locks the intentional defer so it can't drift to a fake write.
  - reject — propose → reject → rejected, appliedRef None, module unchanged.
  - idempotent double-accept — accept the SAME id twice → module count stays 1 (no re-apply),
    applied_ref unchanged.
  - natural REST-call shape — POST /agent-proposals/{id}/accept with the id only (decided_by
    is a query param, no body) → applies (verify-with-consumers-natural-call: the minimal
    client call works, no create-schema 422).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mcp_servers import write_server as ws
from mcp_servers import proposals_service as psvc
from mcp_servers import proposals_store as agent_pstore


@pytest.fixture
def loop_db(isolated_paths):
    """The agent-proposal queue table exists; target modules are file-store/SQLite-lazy +
    fail-open on empty. (Mirrors test_mcp_e2e's app_db, minus the wiki/macro bits this loop
    doesn't touch.)"""
    agent_pstore.init_proposal_tables()
    return isolated_paths


# --------------------------------------------------------------------------- #
# LANDS — propose → accept → the row really exists in the target module         #
# --------------------------------------------------------------------------- #
def test_decision_create_lands_with_fields(loop_db):
    from modules.decision_journal import service as dsvc
    before, _ = dsvc.list_entries()
    p = ws.propose_decision("Trim crypto to 30%", 65, "portfolio",
                            rationale="8pp over the golden-path target")
    res = psvc.accept(p["id"], decided_by="user")
    assert res["status"] == "accepted" and res["appliedRef"] is not None
    after, _ = dsvc.list_entries()
    assert after.count == before.count + 1, "decision did not land in the module"
    # the EXACT created entry (DIVERGENT values so a wrong apply differs)
    created = dsvc.get_entry(res["appliedRef"])
    assert created is not None
    assert created.decision == "Trim crypto to 30%"
    assert created.confidence == 65
    assert created.domain == "portfolio"


def test_note_create_lands_with_fields(loop_db):
    from modules.notes import service as nsvc
    before = nsvc.list_notes()[0]
    p = ws.propose_note("Ladder rebalance idea", rationale="worth capturing",
                        body="re-weight crypto down 8pp", tags=["idea", "rebalance"])
    res = psvc.accept(p["id"], decided_by="user")
    assert res["status"] == "accepted" and res["appliedRef"] is not None
    after = nsvc.list_notes()[0]
    assert len(after) == len(before) + 1, "note did not land in the module"
    landed = next(n for n in after if n.id == res["appliedRef"])
    assert landed.title == "Ladder rebalance idea"
    assert "idea" in landed.tags and "rebalance" in landed.tags


def test_journal_create_lands_lowercase_buy_becomes_BUY(loop_db):
    """THE BUG-KILLER (#51): propose action LOWERCASE "buy" → accept → the landed journal row
    has action == "BUY". A test proposing "BUY" uppercase would pass even against the pre-fix
    code (which passed the action RAW → pydantic literal_error on accept → nothing landed);
    LOWERCASE is the distinguishing case that proves the apply-boundary normalization fix.
    Behavior-test the SIDE EFFECT (re-GET the journal), not applied_ref alone."""
    from modules.journal import service as jsvc
    before, _ = jsvc.list_entries()
    p = ws.propose_journal("buy", "BTC", "DCA per plan", rationale="fits the ladder")
    assert p["payload"]["action"] == "buy"  # the agent stored it lowercase (the trigger)
    res = psvc.accept(p["id"], decided_by="user")
    # the apply SUCCEEDED (no apply_error) and recorded a real ref
    assert res["status"] == "accepted"
    assert res["appliedRef"] is not None, f"journal did not apply: {res.get('applyError')}"
    assert res["applyError"] is None
    after, _ = jsvc.list_entries()
    assert after.count == before.count + 1, "journal trade did not land in the module"
    landed = next(e for e in after.entries if e.id == res["appliedRef"])
    assert landed.action == "BUY", f"lowercase 'buy' must land as 'BUY', got {landed.action!r}"
    assert landed.asset == "BTC"
    assert landed.reason == "DCA per plan"


def test_journal_create_lowercase_sell_becomes_SELL(loop_db):
    """The SELL arm of the distinguishing fix — lowercase "sell" lands as "SELL"."""
    from modules.journal import service as jsvc
    p = ws.propose_journal("sell", "ETH", "take profit at target", rationale="hit the rung")
    res = psvc.accept(p["id"], decided_by="user")
    assert res["appliedRef"] is not None and res["applyError"] is None
    after, _ = jsvc.list_entries()
    landed = next(e for e in after.entries if e.id == res["appliedRef"])
    assert landed.action == "SELL"


# --------------------------------------------------------------------------- #
# project_update — the INTENTIONAL honest-defer (pinned, NOT a bug to fix)       #
# --------------------------------------------------------------------------- #
def test_project_update_accept_is_honest_apply_error_no_row(loop_db):
    """PINNED (T2): project_update has NO apply handler by design (no public partial-update
    service on the projects module). Accepting it → status accepted + apply_error set + NO
    projects row created + the proposal still recorded (left the pending queue). This locks
    the intentional defer so it can't silently drift into a fabricated write."""
    from modules.projects import service as proj_svc
    projects_before, _ = proj_svc.list_projects()
    p = ws.propose_project_update("life-os", rationale="progress moved this week", progress=40)
    res = psvc.accept(p["id"], decided_by="user")
    # accepted (left the queue) but NOT applied — honest apply_error, no fabricated write
    assert res["status"] == "accepted"
    assert res["appliedRef"] is None
    assert res["applyError"] is not None
    assert "no apply handler" in res["applyError"] and "project_update" in res["applyError"]
    # NO projects row created (the defer is real — it did not invent a project mutation)
    projects_after, _ = proj_svc.list_projects()
    assert len(projects_after) == len(projects_before), "project_update must NOT create a row"
    # the proposal is still recorded as decided (not stuck pending)
    stored = psvc.get_proposal(p["id"])
    assert stored is not None and stored["status"] == "accepted"


# --------------------------------------------------------------------------- #
# reject — flip to rejected, NOTHING applied                                    #
# --------------------------------------------------------------------------- #
def test_reject_applies_nothing(loop_db):
    from modules.notes import service as nsvc
    notes_before = nsvc.list_notes()[0]
    p = ws.propose_note("should NOT land", rationale="testing reject")
    res = psvc.reject(p["id"], decided_by="user")
    assert res["status"] == "rejected"
    assert res.get("appliedRef") is None
    # NO note created
    assert len(nsvc.list_notes()[0]) == len(notes_before), "reject must not apply to the module"


# --------------------------------------------------------------------------- #
# idempotency — accept the SAME proposal twice → applied exactly once            #
# --------------------------------------------------------------------------- #
def test_double_accept_does_not_double_apply(loop_db):
    """Accepting the same proposal twice must NOT create the entry twice (the 2nd accept is
    a no-op). Assert the MODULE row count is stable (the source-of-truth side effect), not
    just that applied_ref is unchanged."""
    from modules.decision_journal import service as dsvc
    before, _ = dsvc.list_entries()
    p = ws.propose_decision("d", 50, "general", rationale="r")
    res1 = psvc.accept(p["id"], decided_by="user")
    after1, _ = dsvc.list_entries()
    assert after1.count == before.count + 1
    ref1 = res1["appliedRef"]
    # 2nd accept — idempotent no-op
    res2 = psvc.accept(p["id"], decided_by="user")
    after2, _ = dsvc.list_entries()
    assert after2.count == after1.count, "second accept duplicated the entry — idempotency broken"
    assert res2["appliedRef"] == ref1, "applied_ref changed on re-accept"
    # exactly ONE accept audit row despite two accept calls
    audit = agent_pstore.list_audit(proposal_id=p["id"])
    assert len([a for a in audit if a["action"] == "accept"]) == 1


# --------------------------------------------------------------------------- #
# natural REST-call shape — the minimal client body the real consumer sends      #
# --------------------------------------------------------------------------- #
def test_natural_rest_accept_applies(loop_db):
    """The real client calls POST /agent-proposals/{id}/accept with NO request body
    (decided_by is a query param, default 'user'). Exercise that minimal natural call via
    TestClient and assert it APPLIES — no create-schema 422 (verify-with-consumers-natural-
    call: a convenient full-body resend would mask a required-field trap; the partial natural
    call is what the consumer sends)."""
    import main
    from modules.journal import service as jsvc
    app = main.create_app()
    with TestClient(app) as client:
        # propose via the in-process write-server (the agent channel)
        p = ws.propose_journal("buy", "SOL", "starter position", rationale="thesis intact")
        pid = p["id"]
        before, _ = jsvc.list_entries()
        # NATURAL call: id in the path, no body (decided_by defaults)
        r = client.post(f"/agent-proposals/{pid}/accept")
        assert r.status_code == 200, f"natural accept failed: {r.status_code} {r.text[:200]}"
        body = r.json()
        assert body["success"] is True
        assert body["data"]["status"] == "accepted"
        assert body["data"]["appliedRef"] is not None, "natural accept did not apply"
        after, _ = jsvc.list_entries()
        assert after.count == before.count + 1
        landed = next(e for e in after.entries if e.id == body["data"]["appliedRef"])
        assert landed.action == "BUY" and landed.asset == "SOL"


def test_natural_rest_accept_with_decided_by_query(loop_db):
    """The decided_by query param flows through (still no body) → recorded on the proposal."""
    import main
    app = main.create_app()
    with TestClient(app) as client:
        p = ws.propose_decision("call it", 70, "portfolio", rationale="natural call w/ decided_by")
        r = client.post(f"/agent-proposals/{p['id']}/accept", params={"decided_by": "tester"})
        assert r.status_code == 200
        assert r.json()["data"]["decidedBy"] == "tester"
