"""tests/test_mcp_e2e.py — END-TO-END smoke test of the full agent loop (MCP-7).

The proof that the SUPERVISION LAYER works end-to-end — the project thesis: an external
agent reads the user's life, PROPOSES changes, and a HUMAN disposes; the agent never
writes directly, and it can read back the verdict to learn. Every prior MCP sprint
tested one slice; this drives the WHOLE loop through the real tool/service entry points
and asserts OBSERVABLE state at each hop (DB row counts, appliedRef == the real created
id, stats numbers) — so it FAILS if the loop breaks anywhere. No self-confirming asserts.

The loop (one test, seven checkpoints):
  1. READ context   — read tools return real (non-fabricated) data
  2. PROPOSE        — write-server enqueues a pending proposal
  3. AGENT CHECK    — check_proposal_status sees it pending
  4. HUMAN APPLY    — proposals_service.accept applies → real entry in the target module
  5. AGENT VERIFY   — check_proposal_status=accepted, appliedRef == the created entry id
  6. IDEMPOTENCY    — a 2nd accept does NOT duplicate the entry
  7. CAPABILITY     — across the whole loop, NO agent-facing server can self-accept

Calls tool/service functions directly (no process spawn) on the app_db fixture, which
initialises every store the loop touches.
"""

from __future__ import annotations

import pytest

from mcp_servers import read_server as rs
from mcp_servers import write_server as ws
from mcp_servers import proposals_service as psvc
from mcp_servers import proposals_store as agent_pstore


@pytest.fixture
def app_db(isolated_paths, monkeypatch):
    """Initialised app: wiki + wiki-proposal + agent-proposal tables exist (the loop
    reads market/finance/decision + the agent-proposal queue). File-store modules are
    lazy + fail-open on empty."""
    from modules.wiki import store as wiki_store
    from modules.wiki import proposals_store as pstore

    wiki_store.init_wiki_tables()
    pstore.init_proposal_tables()
    agent_pstore.init_proposal_tables()
    # FRED-MACRO: life_brief triggers a macro cold-start whose no-key CSV would hit the
    # LIVE network — neutralize → deterministic mock (keeps the e2e loop hermetic).
    from modules.macro import reader as macro_reader
    monkeypatch.setattr(macro_reader.httpx, "get",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network off in e2e")))
    return isolated_paths


# --------------------------------------------------------------------------- #
# THE FULL LOOP — read → propose → check → apply → verify → idempotency          #
# --------------------------------------------------------------------------- #
def test_full_agent_loop_decision(app_db):
    from modules.decision_journal import service as dsvc

    # ---- 1. READ context: the agent pulls real life data --------------------
    brief = rs.life_brief()["brief"]
    # the brief must be a real, fully-shaped snapshot — not a fabricated empty stub.
    # R2-G1: life_brief folds in macro + news + wiki context.
    # FINANCE-FINISH G1: + the decision tower section (9th). REMINDERS-4 (#30): + reminders (10th).
    assert set(brief) == {"portfolio", "market", "projects", "claude", "decisions",
                          "macro", "news", "wiki", "decision", "reminders"}
    assert all("source" in section for section in brief.values()), \
        "every brief section must carry its source tag (traceable data)"
    # finance has default holdings → totalValue is a real number the agent can reason on
    assert isinstance(brief["portfolio"].get("totalValue"), (int, float))
    # market_summary returns the neutral analysis surface
    summary = rs.market_summary()
    assert isinstance(summary["watchlist"], list)

    # ---- 2. PROPOSE: agent enqueues a decision via the WRITE server ----------
    decisions_before, _ = dsvc.list_entries()
    proposal = ws.propose_decision(
        "Trim crypto allocation to 30%", 65, "portfolio",
        rationale="crypto is 8pp over the golden-path target",
    )
    pid = proposal["id"]
    assert proposal["status"] == "pending"
    assert proposal["actor"] == "mcp:writer"
    # PROPOSE must NOT have written the target module — it's pure intent
    after_propose, _ = dsvc.list_entries()
    assert after_propose.count == decisions_before.count, \
        "propose leaked a real write — the gate is broken"

    # ---- 3. AGENT CHECK: it sees its own proposal pending --------------------
    status1 = rs.check_proposal_status(pid)
    assert status1["found"] is True
    assert status1["status"] == "pending"
    assert status1["appliedRef"] is None
    # it appears in the agent's own pending list + the pending count
    assert pid in {p["id"] for p in rs.list_my_proposals(status="pending")["proposals"]}
    assert rs.proposal_stats()["counts"]["pending"] == 1
    assert rs.proposal_stats()["acceptanceRate"] is None  # nothing decided yet

    # ---- 4. HUMAN APPLY: accept → the proposal becomes a REAL entry ----------
    applied = psvc.accept(pid, decided_by="user")
    assert applied["status"] == "accepted"
    assert applied["appliedRef"] is not None
    after_apply, _ = dsvc.list_entries()
    assert after_apply.count == decisions_before.count + 1, \
        "accept did not create the real decision entry — the apply path is broken"
    # the created entry is the EXACT one appliedRef points at (not just 'some' new row)
    created = dsvc.get_entry(applied["appliedRef"])
    assert created is not None
    assert created.decision == "Trim crypto allocation to 30%"
    assert created.confidence == 65

    # ---- 5. AGENT VERIFY: it reads back the verdict --------------------------
    status2 = rs.check_proposal_status(pid)
    assert status2["status"] == "accepted"
    assert status2["appliedRef"] == applied["appliedRef"] == created.id, \
        "the agent's verdict appliedRef must match the real created entry id"
    assert status2["decidedBy"] == "user"
    stats = rs.proposal_stats()
    assert stats["counts"]["accepted"] == 1
    assert stats["acceptanceRate"] == 1.0  # 1 accepted / 1 decided

    # ---- 6. IDEMPOTENCY: a 2nd accept must NOT duplicate the entry -----------
    reaccept = psvc.accept(pid, decided_by="user")
    after_reaccept, _ = dsvc.list_entries()
    assert after_reaccept.count == after_apply.count, \
        "second accept duplicated the entry — idempotency is broken"
    assert reaccept["appliedRef"] == applied["appliedRef"]  # same ref, no new write
    # exactly ONE accept audit row despite two accept calls
    audit = agent_pstore.list_audit(proposal_id=pid)
    assert len([a for a in audit if a["action"] == "accept"]) == 1


def test_full_agent_loop_reject_path(app_db):
    """The reject arm of the loop: propose → human rejects → agent sees rejected, NO
    entry created, stats reflect the rejection."""
    from modules.notes import service as nsvc

    notes_before = nsvc.list_notes()[0]
    p = ws.propose_quicknote("Capture: ladder idea", rationale="worth keeping")
    assert rs.check_proposal_status(p["id"])["status"] == "pending"

    rejected = psvc.reject(p["id"], decided_by="user")
    assert rejected["status"] == "rejected"
    assert rejected["appliedRef"] is None
    # NO note created
    assert len(nsvc.list_notes()[0]) == len(notes_before)
    # agent reads the rejection back + stats updated
    assert rs.check_proposal_status(p["id"])["status"] == "rejected"
    assert rs.proposal_stats()["counts"]["rejected"] == 1
    assert rs.proposal_stats()["acceptanceRate"] == 0.0  # 0 accepted / 1 decided


# --------------------------------------------------------------------------- #
# 7. CAPABILITY — across the whole loop, the agent-facing servers can NEVER      #
#    self-accept. The human apply path is the ONLY way a proposal mutates.       #
# --------------------------------------------------------------------------- #
HUMAN_ONLY_SYMBOLS = ["accept", "reject", "mark_decided", "set_applied_ref",
                      "append_audit", "enqueue"]


def test_agent_servers_cannot_self_dispose(app_db):
    """Neither the read-server nor the write-server binds any accept/reject/decide
    symbol — the agent literally has no in-process handle to ratify its own proposal.
    (Structural proof, complementing the per-server gate tests.)"""
    read_ns = vars(rs)
    write_ns = vars(ws)
    # the read-server has NO dispose AND no enqueue (it only reads)
    for sym in HUMAN_ONLY_SYMBOLS:
        assert sym not in read_ns, f"read-server leaked dispose symbol {sym!r}"
    # the write-server has enqueue (aliased _enqueue) but NO accept/reject/decide
    for sym in ("accept", "reject", "mark_decided", "set_applied_ref"):
        assert sym not in write_ns, f"write-server leaked dispose symbol {sym!r}"


def test_only_human_service_can_apply(app_db):
    """End-to-end capability assertion: a proposal moves off 'pending' ONLY via the
    human apply service. Proven by exhaustion — propose, then confirm the proposal is
    pending and stays pending until proposals_service.accept (the human path) is the
    thing that flips it. There is no agent-facing call that transitions it."""
    from modules.decision_journal import service as dsvc

    p = ws.propose_decision("d", 50, "general", rationale="r")
    pid = p["id"]
    # exercise EVERY agent-facing read tool that touches the proposal — none may flip it
    rs.check_proposal_status(pid)
    rs.list_my_proposals()
    rs.proposal_stats()
    assert rs.check_proposal_status(pid)["status"] == "pending", \
        "an agent READ tool transitioned the proposal — capability boundary breached"
    before, _ = dsvc.list_entries()
    # only now, the HUMAN service applies
    psvc.accept(pid, decided_by="user")
    after, _ = dsvc.list_entries()
    assert after.count == before.count + 1
    assert rs.check_proposal_status(pid)["status"] == "accepted"


# --------------------------------------------------------------------------- #
# Cross-module loop — the loop works for journal too (not just decision)         #
# --------------------------------------------------------------------------- #
def test_full_loop_journal(app_db):
    from modules.journal import service as jsvc

    before, _ = jsvc.list_entries()
    p = ws.propose_journal("BUY", "BTC", "DCA per plan", rationale="fits the ladder")
    assert rs.check_proposal_status(p["id"])["status"] == "pending"
    applied = psvc.accept(p["id"], decided_by="user")
    after, _ = jsvc.list_entries()
    assert applied["status"] == "accepted" and applied["appliedRef"]
    assert len(after.entries) == len(before.entries) + 1
    # verdict round-trips to the agent
    assert rs.check_proposal_status(p["id"])["appliedRef"] == applied["appliedRef"]
