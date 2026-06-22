"""tests/test_reminders_mcp_server.py — REMINDERS-2 (#28): the lifeos-reminders MCP server +
the reminders_list read tool on the main read-server.

The capability decision (A): reminders are single-user REVERSIBLE CRUD with NO trust boundary →
DIRECT write-through (no proposal gate). So the per-domain lifeos-reminders server CAN mutate
(imports service.create/tick), the INVERSE of the whole-app write-server which is structurally
enqueue-ONLY (no-mutate AST gate). Both gates are asserted here (the gate-mirror).

Coverage:
  - reminders_list on read-server AND lifeos-reminders → same result (is-identity: same fn object).
  - reminder_create → write-through, returns real id, GET finds it (MCP≡REST). reminder_tick →
    done_at set, idempotent, absent→found:False.
  - the whole-app write-server's no-mutate AST gate STILL green (untouched).
  - lifeos-reminders CAN mutate (imports service.create/tick — the inverse of the write-server).
  - build_server registers 3; read_server count delta = +1 (reminders_list).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

import mcp_servers.read_server as rs
import mcp_servers.reminders_server as rem
from modules.reminders import service, store
from modules.reminders.schema import ReminderInput


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def rem_db(isolated_paths):
    store.init_reminders_tables()
    return isolated_paths


# --------------------------------------------------------------------------- #
# is-identity — reminders_list is the SAME fn on both servers                    #
# --------------------------------------------------------------------------- #
def test_reminders_list_is_identity_across_servers():
    """The per-domain anti-dup spine: lifeos-reminders' reminders_list IS read_server's own fn
    object (reference-imported, not a copy) → a read agent sees the agenda on lifeos-read OR
    lifeos-reminders, one fn, can't drift."""
    assert rem.TOOLS["reminders_list"] is rs.reminders_list
    assert rem.TOOLS["reminders_list"].__module__ == "mcp_servers.read_server"


def test_reminders_list_same_result_both_servers(rem_db):
    service.create(ReminderInput(title="a", due_at=_now()))
    via_read = rs.reminders_list("all")
    via_rem = rem.TOOLS["reminders_list"]("all")
    assert via_read == via_rem and via_read["count"] == 1


def test_reminders_list_filter_and_lean_shape(rem_db):
    from modules.reminders.schema import ReminderInput
    service.create(ReminderInput(title="today", due_at=_now()))
    out = rs.reminders_list("today")
    assert set(out) >= {"reminders", "count", "undoneCount", "filter"}
    assert out["filter"] == "today" and out["count"] == 1
    # lean per-reminder shape (not a full dump) — id/title/due_at/repeat/done_at + channel (#111)
    r0 = out["reminders"][0]
    assert set(r0) == {"id", "title", "due_at", "repeat", "done_at", "channel"}


# --------------------------------------------------------------------------- #
# write-through — reminder_create / reminder_tick (direct, no proposal gate)     #
# --------------------------------------------------------------------------- #
def test_reminder_create_write_through_returns_id(rem_db):
    r = rem.reminder_create("Buy milk", _now())
    assert r["created"] is True and r["id"] >= 1
    # MCP≡REST: the same service.create the REST POST uses → GET finds it
    got = service.get(r["id"])
    assert got is not None and got.title == "Buy milk"


def test_reminder_create_validates(rem_db):
    """A blank title / unparseable due_at raises (the frozen #27 validator) — no row stored."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        rem.reminder_create("   ", _now())
    with pytest.raises(ValidationError):
        rem.reminder_create("t", "not-a-date")
    assert rs.reminders_list("all")["count"] == 0  # nothing stored


def test_reminder_tick_write_through_and_idempotent(rem_db):
    rid = rem.reminder_create("t", _now())["id"]
    t1 = rem.reminder_tick(rid)
    assert t1["found"] is True and t1["reminder"]["done_at"] is not None
    first = t1["reminder"]["done_at"]
    t2 = rem.reminder_tick(rid)  # idempotent
    assert t2["reminder"]["done_at"] == first


def test_reminder_tick_absent_is_found_false(rem_db):
    assert rem.reminder_tick(99999) == {"found": False, "id": 99999}


# --------------------------------------------------------------------------- #
# build + count                                                                  #
# --------------------------------------------------------------------------- #
def test_build_server_registers_four_tools():
    srv = rem.build_server()
    assert srv is not None and type(srv).__name__ == "FastMCP"
    # #111: +reminders_channels (was 3: reminders_list + reminder_create + reminder_tick)
    assert len(srv._tool_manager.list_tools()) == 4
    assert set(rem.TOOLS.keys()) == {"reminders_list", "reminders_channels",
                                     "reminder_create", "reminder_tick"}


def test_reminders_channels_is_identity_across_servers():
    """#111: lifeos-reminders' reminders_channels IS read_server's own fn (per-domain anti-dup spine)."""
    assert rem.TOOLS["reminders_channels"] is rs.reminders_channels


def test_read_server_has_reminders_list():
    """reminders_list is registered on the main read-server (so a read agent sees the agenda)."""
    assert "reminders_list" in rs.TOOLS


def test_no_future_annotations_in_reminders_server():
    """FastMCP needs REAL annotations — reminders_server must NOT add `from __future__ import
    annotations` (same AST check as the other servers)."""
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(rem))
    future = [n for n in ast.walk(tree)
              if isinstance(n, ast.ImportFrom) and n.module == "__future__"
              and any(a.name == "annotations" for a in n.names)]
    assert not future


# --------------------------------------------------------------------------- #
# THE GATE-MIRROR — write-server CANNOT mutate; lifeos-reminders CAN             #
# --------------------------------------------------------------------------- #
def test_whole_app_write_server_no_mutate_gate_still_green():
    """The whole-app write-server is STRUCTURALLY enqueue-ONLY — it must NOT import any
    note/data-mutation fn. REMINDERS-2 did NOT touch it (reminder writes go to lifeos-reminders,
    NOT here) → its no-mutate gate STILL holds. (Asserts the same forbidden-symbol namespace check
    the write-server's own test does — pinned here too as the gate-mirror.)"""
    import mcp_servers.write_server as ws
    forbidden = ("create_note", "update_note", "delete_note", "merge_notes",
                 "create_reminder", "tick_reminder", "accept_proposal")
    ns = vars(ws)
    leaked = [s for s in forbidden if s in ns]
    assert leaked == [], f"the whole-app write-server leaked a mutation symbol: {leaked}"


def test_lifeos_reminders_server_CAN_mutate():
    """The INVERSE of the write-server gate: lifeos-reminders IS allowed to mutate (the capability
    decision A — reminders are reversible single-user CRUD, no trust boundary). It imports the
    reminders service (create/tick) → reminder_create/reminder_tick are real write fns living in
    THIS module. This is what makes reminder writes direct (not enqueued)."""
    import mcp_servers.reminders_server as rmod
    # the write tools are defined HERE (not reference-imported read fns) → they mutate
    assert rmod.reminder_create.__module__ == "mcp_servers.reminders_server"
    assert rmod.reminder_tick.__module__ == "mcp_servers.reminders_server"
    # and they reach the reminders service (the mutation path)
    import inspect
    src = inspect.getsource(rmod)
    assert "service.create" in src or "_reminders_service.create" in src
    assert "service.tick" in src or "_reminders_service.tick" in src
