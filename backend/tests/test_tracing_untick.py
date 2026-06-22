"""tests/test_tracing_untick.py — TRACING-UX2 #136-BE: the un-tick (un-complete) endpoint.

The tracing todo tick is a TOGGLE: tick a NOT-done row → POST /log {val:1} → done; tick a DONE row
→ DELETE /tracing/{id}/sessions?date=today → UN-complete (delete today's sessions → val 0 → done
false). The load-bearing cases:
  - 🔴 the toggle round-trip: log val=1 → done=True; clear today → done=FALSE, val=0, deleted≥1;
  - 🔴 SCOPED (#72): clearing activity A's today sessions does NOT touch A's OTHER days nor OTHER
    activities' logs;
  - 404 on an unknown activity; honest deletedSessions:0 when there were none; explicit ?date.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.tracing import service as svc
from modules.tracing import store as trc_store
from modules.tracing.schema import ActivityInput, LogInput, vn_today


@pytest.fixture
def db(isolated_paths):
    trc_store.init_tracing_tables()
    return isolated_paths


@pytest.fixture
def api(db):
    from main import create_app
    return TestClient(create_app())


def _done(activity_id: str) -> bool:
    ov = svc.overview()
    a = next((x for x in ov.activities if x.id == activity_id), None)
    return bool(a and a.today.done)


def _val(activity_id: str) -> float:
    ov = svc.overview()
    a = next((x for x in ov.activities if x.id == activity_id), None)
    return a.today.val if a else -1.0


# --- 🔴 the toggle round-trip (tick → done → un-tick → un-done) -------------- #
def test_untick_round_trip(db):
    svc.create_activity(ActivityInput(id="read", name="Read", goal=1.0))
    svc.log_session("read", LogInput(val=1.0))  # tick
    assert _done("read") is True and _val("read") == 1.0
    day, deleted, view = svc.clear_sessions_for_day("read")  # un-tick (default today)
    assert deleted >= 1 and day == vn_today()
    assert view.today.done is False and view.today.val == 0.0  # un-done, val back to 0
    assert _done("read") is False  # confirmed via the board overview too


def test_untick_honest_zero_when_no_sessions(db):
    """No sessions today → clear is a no-op: deletedSessions=0, done stays false (honest)."""
    svc.create_activity(ActivityInput(id="x", name="X", goal=1.0))
    day, deleted, view = svc.clear_sessions_for_day("x")
    assert deleted == 0 and view.today.done is False


def test_untick_accumulated_sessions_all_cleared(db):
    """Two same-day sessions (val 1 + 1 = 2 ≥ goal 1) → done; clear removes BOTH → val 0, done false."""
    svc.create_activity(ActivityInput(id="run", name="Run", goal=1.0))
    svc.log_session("run", LogInput(val=1.0))
    svc.log_session("run", LogInput(val=1.0))
    assert _val("run") == 2.0 and _done("run") is True
    _day, deleted, view = svc.clear_sessions_for_day("run")
    assert deleted == 2 and view.today.val == 0.0 and view.today.done is False


# --- 🔴 SCOPED (#72): clearing A's today does NOT touch A's other days / other activities --- #
def test_untick_scoped_to_one_activity_one_day(db):
    from datetime import datetime, timedelta
    from modules.tracing.schema import VN_TZ
    yesterday = (datetime.now(VN_TZ).date() - timedelta(days=1)).strftime("%Y-%m-%d")
    svc.create_activity(ActivityInput(id="A", name="A", goal=1.0))
    svc.create_activity(ActivityInput(id="B", name="B", goal=1.0))
    # A: a session today + a session YESTERDAY; B: a session today
    svc.log_session("A", LogInput(val=1.0))                 # A today
    svc.log_session("A", LogInput(val=1.0, date=yesterday)) # A yesterday
    svc.log_session("B", LogInput(val=1.0))                 # B today
    # clear A's TODAY only
    _day, deleted, _view = svc.clear_sessions_for_day("A")
    assert deleted == 1  # ONLY A's today session
    # A yesterday survives (the OTHER day) — its raw log row still exists
    a_logs = trc_store.logs_for_activity("A")
    assert any(r["date"] == yesterday for r in a_logs), "A's yesterday session must survive"
    assert not any(r["date"] == vn_today() for r in a_logs), "A's today session is gone"
    # B's today survives (the OTHER activity)
    assert _done("B") is True, "B (another activity) is untouched"


def test_untick_explicit_date(db):
    """An explicit ?date clears THAT day's sessions (not today)."""
    from datetime import datetime, timedelta
    from modules.tracing.schema import VN_TZ
    yesterday = (datetime.now(VN_TZ).date() - timedelta(days=1)).strftime("%Y-%m-%d")
    svc.create_activity(ActivityInput(id="A", name="A", goal=1.0))
    svc.log_session("A", LogInput(val=1.0, date=yesterday))
    svc.log_session("A", LogInput(val=1.0))  # today
    day, deleted, _view = svc.clear_sessions_for_day("A", date=yesterday)
    assert day == yesterday and deleted == 1
    # today's session survives
    assert _done("A") is True


# --- REST surface ----------------------------------------------------------- #
def test_rest_untick_round_trip(api):
    api.post("/tracing/activities", json={"id": "read", "name": "Read", "goal": 1})
    api.post("/tracing/read/log", json={"val": 1.0})
    # tick → done
    ov = api.get("/tracing").json()["data"]
    a = next(x for x in ov["activities"] if x["id"] == "read")
    assert a["today"]["done"] is True
    # un-tick
    r = api.delete("/tracing/read/sessions")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["activityId"] == "read" and d["deletedSessions"] >= 1
    assert d["view"]["today"]["done"] is False and d["view"]["today"]["val"] == 0.0


def test_rest_untick_unknown_activity_404(api):
    r = api.delete("/tracing/ghost/sessions")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_rest_untick_explicit_date_param(api):
    api.post("/tracing/activities", json={"id": "x", "name": "X", "goal": 1})
    api.post("/tracing/x/log", json={"val": 1.0})
    r = api.delete("/tracing/x/sessions", params={"date": vn_today()})
    assert r.status_code == 200 and r.json()["data"]["date"] == vn_today()
    assert r.json()["data"]["deletedSessions"] >= 1
