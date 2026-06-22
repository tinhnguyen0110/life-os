"""tests/test_tracing_mcp_server.py — DAILY-TRACING-P2 (#65): the lifeos-tracing MCP server +
the tracing_overview read tool on the main read-server.

The capability decision (mirrors reminders): tracing logs are single-user REVERSIBLE append data
with NO trust boundary → DIRECT write-through (no proposal gate). So the per-domain lifeos-tracing
server CAN mutate (imports service.log_session), the INVERSE of the whole-app write-server (no-mutate
AST gate). Both gates asserted here (the gate-mirror).

Coverage:
  - tracing_overview on read-server AND lifeos-tracing → same result (is-identity: same fn object).
  - tracing_overview MCP == REST GET /tracing payload (#24 byte-identical parity).
  - tracing_log → write-through, accumulates same-day, returns the updated view (today/streak).
  - unknown activity_id → {found:False}; val<0 → the LogInput validator raises.
  - the whole-app write-server's no-mutate AST gate STILL green (untouched).
  - lifeos-tracing CAN mutate (imports service.log_session — the inverse of the write-server).
  - build_server registers 2; read_server has tracing_overview.
"""

from __future__ import annotations

import json

import pytest

import mcp_servers.read_server as rs
import mcp_servers.tracing_server as trc
from modules.tracing import service, store
from modules.tracing.schema import ActivityInput, LogInput


@pytest.fixture
def trc_db(isolated_paths):
    store.init_tracing_tables()
    return isolated_paths


def _mk(activity_id="run", *, goal=10.0):
    return service.create_activity(ActivityInput(id=activity_id, name=activity_id.title(), goal=goal))


# --------------------------------------------------------------------------- #
# is-identity — tracing_overview is the SAME fn on both servers                  #
# --------------------------------------------------------------------------- #
def test_tracing_overview_is_identity_across_servers():
    """The per-domain anti-dup spine: lifeos-tracing's tracing_overview IS read_server's own fn
    object (reference-imported, not a copy) → one fn, can't drift."""
    assert trc.TOOLS["tracing_overview"] is rs.tracing_overview
    assert trc.TOOLS["tracing_overview"].__module__ == "mcp_servers.read_server"


def test_tracing_overview_same_result_both_servers(trc_db):
    _mk("run", goal=10.0)
    service.log_session("run", LogInput(val=4.0))
    via_read = rs.tracing_overview()
    via_trc = trc.TOOLS["tracing_overview"]()
    assert via_read == via_trc
    assert via_read["score"]["total"] == 1


def test_tracing_overview_byte_identical_to_rest(trc_db):
    """#24 parity: the MCP tracing_overview payload == the REST GET /tracing `data` (both return
    reader.get_overview().model_dump()). Byte-identical via json.dumps(sort_keys)."""
    from main import create_app
    from fastapi.testclient import TestClient

    _mk("run", goal=10.0)
    service.log_session("run", LogInput(val=6.0))
    mcp_payload = rs.tracing_overview()
    with TestClient(create_app()) as c:
        rest_payload = c.get("/tracing").json()["data"]
    assert json.dumps(mcp_payload, sort_keys=True) == json.dumps(rest_payload, sort_keys=True)


# --------------------------------------------------------------------------- #
# write-through — tracing_log (direct, no proposal gate)                         #
# --------------------------------------------------------------------------- #
def test_tracing_log_write_through_returns_updated_view(trc_db):
    _mk("run", goal=10.0)
    out = trc.tracing_log("run", 6.0, dur_min=30, note="am")
    assert out["logged"] is True and out["activityId"] == "run"
    assert out["activity"]["today"]["val"] == 6.0 and out["activity"]["today"]["pct"] == 60


def test_tracing_log_accumulates_same_day_round_trip(trc_db):
    """log twice same day → the returned view + a fresh overview both show the ACCUMULATED val
    (not overwrite) — the MCP write-through round-trip."""
    _mk("run", goal=10.0)
    trc.tracing_log("run", 4.0)
    out2 = trc.tracing_log("run", 7.0)
    assert out2["activity"]["today"]["val"] == 11.0  # 4+7 accumulated
    assert out2["activity"]["today"]["done"] is True
    # and a fresh overview reflects it (the round-trip an agent would read back)
    ov = rs.tracing_overview()
    a = [x for x in ov["activities"] if x["id"] == "run"][0]
    assert a["today"]["val"] == 11.0


def test_tracing_log_unknown_activity_found_false(trc_db):
    """Unknown activity_id → {found:False, activityId} (honest existence-contract, not a crash)."""
    assert trc.tracing_log("ghost", 5.0) == {"found": False, "activityId": "ghost"}


def test_tracing_log_negative_val_raises(trc_db):
    """val<0 → the LogInput validator raises (the agent sees the validation error, no row stored)."""
    from pydantic import ValidationError
    _mk("run", goal=10.0)
    with pytest.raises(ValidationError):
        trc.tracing_log("run", -1.0)
    # nothing stored — today still 0
    assert rs.tracing_overview()["activities"][0]["today"]["val"] == 0


# --------------------------------------------------------------------------- #
# build + registration                                                           #
# --------------------------------------------------------------------------- #
def test_build_server_registers_three_tools():
    srv = trc.build_server()
    assert srv is not None and type(srv).__name__ == "FastMCP"
    # #109: +tracing_templates (was 2: overview + log)
    assert len(srv._tool_manager.list_tools()) == 3
    assert set(trc.TOOLS.keys()) == {"tracing_overview", "tracing_templates", "tracing_log"}


def test_tracing_templates_is_identity_across_servers():
    """#109: lifeos-tracing's tracing_templates IS read_server's own fn (the per-domain anti-dup
    spine — reference-imported, same fn object, can't drift)."""
    assert trc.TOOLS["tracing_templates"] is rs.tracing_templates


def test_read_server_has_tracing_overview():
    """tracing_overview is registered on the main read-server (so any read agent sees the board)."""
    assert "tracing_overview" in rs.TOOLS


def test_no_future_annotations_in_tracing_server():
    """FastMCP needs REAL annotations — tracing_server must NOT add `from __future__ import
    annotations` (same AST check as the other servers)."""
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(trc))
    future = [n for n in ast.walk(tree)
              if isinstance(n, ast.ImportFrom) and n.module == "__future__"
              and any(a.name == "annotations" for a in n.names)]
    assert not future


# --------------------------------------------------------------------------- #
# THE GATE-MIRROR — write-server CANNOT mutate; lifeos-tracing CAN               #
# --------------------------------------------------------------------------- #
def test_whole_app_write_server_no_mutate_gate_still_green():
    """The whole-app write-server is STRUCTURALLY enqueue-ONLY — DAILY-TRACING-P2 did NOT touch it
    (tracing writes go to lifeos-tracing, NOT here) → its no-mutate gate STILL holds."""
    import mcp_servers.write_server as ws
    forbidden = ("create_note", "update_note", "delete_note", "merge_notes",
                 "log_session", "create_activity", "accept_proposal")
    leaked = [s for s in forbidden if s in vars(ws)]
    assert leaked == [], f"the whole-app write-server leaked a mutation symbol: {leaked}"


def test_read_server_no_tracing_write_symbol_leak():
    """The read-server must NOT bind a tracing WRITE symbol (only the read fn tracing_overview).
    The read no-write gate holds for the new tool."""
    ns = vars(rs)
    for w in ("log_session", "insert_log", "create_activity", "archive_activity", "update_activity"):
        assert w not in ns, f"read-server leaked a tracing write symbol: {w}"


def test_lifeos_tracing_server_CAN_mutate():
    """The INVERSE of the write-server gate: lifeos-tracing IS allowed to mutate (the capability
    decision — tracing is reversible single-user append, no trust boundary). tracing_log is defined
    HERE and reaches service.log_session (the mutation path)."""
    import inspect
    assert trc.tracing_log.__module__ == "mcp_servers.tracing_server"
    src = inspect.getsource(trc)
    assert "service.log_session" in src or "_tracing_service.log_session" in src
