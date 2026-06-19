"""tests/test_mcp_write.py — GATED MCP write-server tests (MCP-3).

Coverage:
  - ENQUEUE: each propose_* tool enqueues exactly one PENDING proposal carrying the
    right module/kind/payload + actor=mcp:writer, and returns it.
  - RATIONALE GATE: a propose with an empty/whitespace rationale is REJECTED.
  - PENDING-ONLY: a freshly proposed row is status='pending' — never applied; the
    target module's data is unchanged (proof the agent path does NOT mutate).
  - QUEUE: list/count/get reflect the enqueued rows.
  - HUMAN DISPOSE: mark_decided flips status but does NOT write the target module.
  - THE CAPABILITY GATE: the write-server has enqueue-ONLY capability — no module
    mutation / apply / accept symbol is bound in its namespace nor imported (grep +
    AST proven, mirroring the wiki write-server's gate).
  - server builds (FastMCP registers all tools) without error.
"""

from __future__ import annotations

import json

import pytest

from mcp_servers import proposals_store as ps
from mcp_servers import write_server as ws


@pytest.fixture
def queue_db(isolated_paths):
    """Empty but initialised agent-proposal queue (the table exists)."""
    ps.init_proposal_tables()
    return isolated_paths


# --------------------------------------------------------------------------- #
# Enqueue — each tool drops one pending proposal with the right shape           #
# --------------------------------------------------------------------------- #
def test_propose_decision_enqueues_pending(queue_db):
    p = ws.propose_decision("Trim crypto to 30%", 65, "portfolio",
                            "8pp over golden-path target")
    assert p["status"] == "pending"
    assert p["module"] == "decision_journal"
    assert p["kind"] == "decision_create"
    assert p["actor"] == "mcp:writer"
    assert p["payload"]["decision"] == "Trim crypto to 30%"
    assert p["payload"]["confidence"] == 65
    assert p["rationale"] == "8pp over golden-path target"


def test_propose_note_enqueues_pending(queue_db):
    p = ws.propose_quicknote("Idea: ladder rebalance", "captures a recurring thought",
                        body="body text", tags=["idea"])
    assert p["status"] == "pending"
    assert p["module"] == "notes"
    assert p["kind"] == "note_create"
    assert p["payload"]["title"] == "Idea: ladder rebalance"
    assert p["payload"]["tags"] == ["idea"]


def test_propose_journal_enqueues_pending(queue_db):
    p = ws.propose_journal("buy", "BTC", "DCA per plan", "trade fits the ladder")
    assert p["status"] == "pending"
    assert p["module"] == "journal"
    assert p["kind"] == "journal_create"
    assert p["payload"]["asset"] == "BTC"
    assert p["payload"]["action"] == "buy"


def test_propose_project_update_enqueues_only_given_fields(queue_db):
    p = ws.propose_project_update("life-os", "progress moved this week", progress=40)
    assert p["status"] == "pending"
    assert p["module"] == "projects"
    assert p["kind"] == "project_update"
    assert p["payload"] == {"projectId": "life-os", "progress": 40}
    # omitted optional fields are NOT in the payload (partial update intent)
    assert "next" not in p["payload"]
    assert "desc" not in p["payload"]


def test_proposal_is_jsonable(queue_db):
    p = ws.propose_decision("x", 50, "general", "because")
    json.dumps(p)


# --------------------------------------------------------------------------- #
# Rationale gate — empty/whitespace rationale rejected for EVERY tool           #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("call", [
    lambda: ws.propose_decision("d", 50, "dom", "   "),
    lambda: ws.propose_quicknote("t", ""),
    lambda: ws.propose_journal("buy", "BTC", "reason", "\t\n"),
    lambda: ws.propose_project_update("p", "  "),
])
def test_empty_rationale_is_rejected(queue_db, call):
    with pytest.raises(ws.RationaleRequired):
        call()


def test_rejected_proposal_is_not_enqueued(queue_db):
    before = ps.count_by_status().get("pending", 0)
    with pytest.raises(ws.RationaleRequired):
        ws.propose_quicknote("t", "")
    after = ps.count_by_status().get("pending", 0)
    assert after == before, "a rejected (no-rationale) propose must not enqueue a row"


# --------------------------------------------------------------------------- #
# Queue + pending-only (the gate's observable effect: nothing is applied)        #
# --------------------------------------------------------------------------- #
def test_queue_list_count_get(queue_db):
    a = ws.propose_decision("a", 50, "dom", "r1")
    b = ws.propose_quicknote("b", "r2")
    assert ps.count_by_status()["pending"] == 2
    listed = ps.list_proposals(status="pending")
    assert {x["id"] for x in listed} == {a["id"], b["id"]}
    # module filter works
    assert [x["id"] for x in ps.list_proposals(module="notes")] == [b["id"]]
    got = ps.get_proposal(a["id"])
    assert got is not None and got["kind"] == "decision_create"


def test_proposed_decision_does_NOT_appear_in_the_module(queue_db):
    """The strongest gate proof: proposing a decision must NOT create a real
    decision-journal entry — it sits in the queue only, until a human applies it."""
    from modules.decision_journal import service as dsvc

    before, _ = dsvc.list_entries()
    ws.propose_decision("should NOT be created", 70, "portfolio", "gate proof")
    after, _ = dsvc.list_entries()
    assert after.count == before.count, "propose must not write the decision module"


# --------------------------------------------------------------------------- #
# Human dispose — mark_decided flips status, still does NOT apply                #
# --------------------------------------------------------------------------- #
def test_mark_decided_flips_status_without_applying(queue_db):
    from modules.decision_journal import service as dsvc

    p = ws.propose_decision("d", 50, "dom", "r")
    before, _ = dsvc.list_entries()
    # mark_decided returns (transitioned, row); the STORE flip never applies — the
    # apply layer (proposals_service.accept) is what calls the module create.
    transitioned, updated = ps.mark_decided(
        p["id"], status="accepted", decided="2026-06-15T00:00:00+00:00", decided_by="user")
    assert transitioned is True
    assert updated is not None and updated["status"] == "accepted"
    assert updated["decidedBy"] == "user"
    # the store flip does NOT itself write the target module
    after, _ = dsvc.list_entries()
    assert after.count == before.count
    # IDEMPOTENT pivot: a 2nd flip does not transition (already decided)
    transitioned2, _ = ps.mark_decided(
        p["id"], status="accepted", decided="t", decided_by="user")
    assert transitioned2 is False


def test_mark_decided_rejects_bad_status(queue_db):
    p = ws.propose_quicknote("t", "r")
    with pytest.raises(ValueError):
        ps.mark_decided(p["id"], status="applied", decided="t", decided_by="user")


# --------------------------------------------------------------------------- #
# THE CAPABILITY GATE — enqueue-only, no mutate/apply/accept reachable           #
# --------------------------------------------------------------------------- #
# Symbols that would let the agent channel write a module / apply / accept. If ANY
# is reachable from the write server's namespace / imports, the gate is broken.
FORBIDDEN_SYMBOLS = [
    # generic queue: the human-side / apply surface must NOT be reachable from the agent
    "mark_decided", "apply", "apply_proposal", "accept", "accept_proposal",
    "reject_proposal",
    # module mutations the proposals target
    "create_entry", "update_entry", "delete_entry",   # decision / journal
    "upsert_holding", "delete_holding",                # finance
    "register_project", "abandon_project", "restore_project", "refresh_project",
    "set_config", "set_override", "save_brief",
    # wiki write surface must not leak either
    "create_note", "update_note", "delete_note", "merge_notes", "create_proposal",
]


def test_write_server_has_no_forbidden_symbol_in_namespace():
    """Only ``enqueue`` (aliased _enqueue) is the write surface. No apply/accept/
    module-mutation symbol is bound in the write server's namespace — the agent path
    is structurally incapable of changing a module or ratifying its own proposal."""
    ns = vars(ws)
    leaked = [s for s in FORBIDDEN_SYMBOLS if s in ns]
    assert leaked == [], f"write server leaked forbidden symbols: {leaked}"


def test_write_server_imports_only_enqueue_ast():
    """AST-parse the write server's imports: it imports ``enqueue`` (the queue append)
    and NOTHING that applies / accepts / mutates a module. (A docstring legitimately
    names the excluded symbols, so this checks IMPORTS, not a string grep.)"""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(ws))
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

    leaked = set(FORBIDDEN_SYMBOLS) & imported_names
    assert leaked == set(), f"write server imports forbidden symbols: {leaked}"
    # it DOES import the enqueue append (the sole write surface)
    assert "enqueue" in imported_names or "_enqueue" in imported_names
    # it must NOT import any module's service/router (where mutations live), nor the
    # wiki proposals_service (the enqueue+apply layer).
    assert not any(m.endswith(".service") or m.endswith(".router")
                   for m in imported_modules), \
        f"write server imports a module service/router: {imported_modules}"
    assert not any("proposals_service" in m for m in imported_modules), \
        "write server must not import a proposals_service (the apply layer)"


def test_proposals_store_has_no_module_mutation_import():
    """The generic queue store itself must not import any module mutation — it only
    knows SQLite. (Closes the indirect path: agent → enqueue → store → module write.)"""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(ps))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_modules.add(node.module or "")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
    # the store talks ONLY to the shared db + stdlib — no modules.* import
    assert not any(m.startswith("modules.") for m in imported_modules), \
        f"proposals_store imports a module (should be db-only): {imported_modules}"


# --------------------------------------------------------------------------- #
# Read / write capability separation — the two servers are disjoint              #
# --------------------------------------------------------------------------- #
def test_read_and_write_servers_are_capability_disjoint():
    """The read server has NO enqueue; the write server has enqueue-ONLY. Proven by
    namespace: 'enqueue' / '_enqueue' is in write's namespace, absent from read's."""
    from mcp_servers import read_server as rs

    assert "_enqueue" in vars(ws)
    assert "enqueue" not in vars(rs) and "_enqueue" not in vars(rs)


# --------------------------------------------------------------------------- #
# Server builds                                                                  #
# --------------------------------------------------------------------------- #
def test_build_server_registers_all_tools():
    server = ws.build_server()
    assert server is not None
    # MCP-DEDUP #70: 4 generic propose tools (propose_decision/quicknote/journal/
    # project_update). The 6 wiki_propose_* delegators were REMOVED — canonical = the
    # standalone wiki write-server (tested in test_wiki_mcp_write.py).
    assert len(ws.TOOLS) == 4
    assert set(ws.TOOLS) == {"propose_decision", "propose_quicknote",
                             "propose_journal", "propose_project_update"}
    assert not any(k.startswith("wiki") for k in ws.TOOLS)
