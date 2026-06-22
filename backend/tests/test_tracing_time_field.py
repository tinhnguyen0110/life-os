"""tests/test_tracing_time_field.py — TRACING-UX2 #136-BE-2: per-activity `time` (INDEPENDENT of remind).

G3-(ii): an activity has a scheduled TIME even without a reminder. ``time`` (HH:MM VN) is a dedicated
field, NOT overloaded onto remindAt. The load-bearing cases:
  - 🔴 set time → ActivityView.time == it, and NO reminder is created (time is reminder-independent);
  - set time WITHOUT remindAt/repeat → still no reminder;
  - existing remindAt behavior UNCHANGED (regression — time doesn't touch _sync_reminder);
  - bad HH:MM → 422; PUT sets time; round-trips through the store (sched_time col, aliased AS time).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.reminders import service as rem
from modules.reminders import store as rem_store
from modules.tracing import service as svc
from modules.tracing import store as trc_store
from modules.tracing.schema import ActivityInput, ActivityUpdate


@pytest.fixture
def db(isolated_paths):
    trc_store.init_tracing_tables()
    rem_store.init_reminders_tables()
    return isolated_paths


@pytest.fixture
def api(db):
    from main import create_app
    return TestClient(create_app())


def _tracing_reminders():
    view, _ = rem.list_reminders("all")
    return [r for r in view.reminders if r.source == "tracing"]


# --- 🔴 set time → surfaced + NO reminder (the independence) ----------------- #
def test_set_time_no_reminder_created(db):
    svc.create_activity(ActivityInput(id="meet", name="Standup", goal=1.0, time="08:30"))
    act = svc.get_activity("meet")
    assert act.time == "08:30"
    # the view surfaces it (the FE timeline rails by time)
    ov_act = next(a for a in svc.overview().activities if a.id == "meet")
    assert ov_act.time == "08:30"
    # 🔴 NO reminder — time is INDEPENDENT of the reminder (the whole point of G3-(ii))
    assert _tracing_reminders() == []


def test_time_without_remind_still_no_reminder(db):
    """time set, remindAt/repeat at defaults → no reminder (independent)."""
    svc.create_activity(ActivityInput(id="x", name="X", goal=1.0, time="09:00"))
    assert _tracing_reminders() == []
    assert svc.get_activity("x").time == "09:00"


def test_time_and_remind_coexist(db):
    """An activity can have BOTH a time AND a reminder — distinct fields, both surface; the reminder
    fires off remindAt (not time)."""
    svc.create_activity(ActivityInput(id="run", name="Run", goal=5.0, time="06:00",
                                      remindAt="07:00", remindRepeat="daily"))
    act = svc.get_activity("run")
    assert act.time == "06:00" and act.remindAt == "07:00"
    rems = _tracing_reminders()
    # the reminder fires at remindAt 07:00 VN = 00:00 UTC (NOT at time 06:00 VN = 23:00 UTC prior day);
    # due_at is UTC-normalized so assert the UTC instant, not the raw VN string.
    assert len(rems) == 1
    assert rems[0].due_at.endswith("T00:00:00+00:00"), f"reminder at remindAt 07:00VN=00:00UTC, got {rems[0].due_at}"


# --- PUT sets time (the existing update path) -------------------------------- #
def test_put_sets_time(db):
    svc.create_activity(ActivityInput(id="a", name="A", goal=1.0))
    assert svc.get_activity("a").time is None
    svc.update_activity("a", ActivityUpdate(time="14:15"))
    assert svc.get_activity("a").time == "14:15"
    assert _tracing_reminders() == []  # setting time via PUT still creates no reminder


def test_put_time_does_not_disturb_remind(db):
    """Setting time on an activity that HAS a reminder leaves the reminder intact (regression)."""
    svc.create_activity(ActivityInput(id="r", name="R", goal=1.0, remindAt="07:00", remindRepeat="daily"))
    assert len(_tracing_reminders()) == 1
    svc.update_activity("r", ActivityUpdate(time="08:00"))
    assert len(_tracing_reminders()) == 1, "setting time must not touch the reminder"
    assert svc.get_activity("r").time == "08:00" and svc.get_activity("r").remindAt == "07:00"


# --- regression: remindAt unchanged ----------------------------------------- #
def test_remind_unchanged_no_time(db):
    """An activity with a reminder + NO time → reminder still fires, time is None (no regression)."""
    svc.create_activity(ActivityInput(id="z", name="Z", goal=1.0, remindAt="07:00", remindRepeat="daily"))
    assert len(_tracing_reminders()) == 1
    assert svc.get_activity("z").time is None


# --- REST surface ----------------------------------------------------------- #
def test_rest_create_with_time(api):
    r = api.post("/tracing/activities", json={"id": "m", "name": "M", "goal": 1, "time": "08:30"})
    assert r.status_code == 201, r.text
    assert r.json()["data"]["time"] == "08:30"
    # view surfaces it
    ov = api.get("/tracing").json()["data"]
    a = next(x for x in ov["activities"] if x["id"] == "m")
    assert a["time"] == "08:30"


def test_rest_put_time(api):
    api.post("/tracing/activities", json={"id": "a", "name": "A", "goal": 1})
    r = api.put("/tracing/activities/a", json={"time": "14:15"})
    assert r.status_code == 200 and r.json()["data"]["time"] == "14:15"


def test_rest_bad_time_is_422(api):
    r = api.post("/tracing/activities", json={"id": "bad", "name": "Bad", "goal": 1, "time": "25:99"})
    assert r.status_code == 422


def test_rest_no_time_is_null(api):
    r = api.post("/tracing/activities", json={"id": "n", "name": "N", "goal": 1})
    assert r.status_code == 201 and r.json()["data"]["time"] is None  # honest null, not ""


# --- #136-BE-3: explicit {time: null} CLEARS (exclude_none drop fix) --------- #
def test_clear_time_via_explicit_null(db):
    """🔴 set a time, then PUT {time: null} → CLEARS sched_time back to None. The bug: exclude_none
    dropped {time:null} so the clear never wrote. Fixed via model_fields_set special-case."""
    svc.create_activity(ActivityInput(id="c", name="C", goal=1.0, time="07:15"))
    assert svc.get_activity("c").time == "07:15"
    svc.update_activity("c", ActivityUpdate(time=None))  # explicit clear
    assert svc.get_activity("c").time is None, "explicit time=null must CLEAR sched_time"


def test_omitted_time_leaves_unchanged(db):
    """OMITTING time (not in the update at all) leaves it unchanged — the omit-vs-set-null distinction."""
    svc.create_activity(ActivityInput(id="k", name="K", goal=1.0, time="09:00"))
    svc.update_activity("k", ActivityUpdate(name="K renamed"))  # time NOT supplied
    act = svc.get_activity("k")
    assert act.time == "09:00" and act.name == "K renamed"  # time survived the unrelated edit


def test_reset_time_after_clear(db):
    """Control: after a clear, time can be SET again (no sticky-null)."""
    svc.create_activity(ActivityInput(id="r", name="R", goal=1.0, time="07:15"))
    svc.update_activity("r", ActivityUpdate(time=None))
    svc.update_activity("r", ActivityUpdate(time="08:00"))
    assert svc.get_activity("r").time == "08:00"


def test_remindAt_null_still_unchanged_not_cleared(db):
    """🔴 the regression control: remindAt keeps its 'None = unchanged' semantics (NOT cleared by
    null — it clears via remindRepeat='off'). The #136-BE-3 fix is scoped to `time` ONLY."""
    svc.create_activity(ActivityInput(id="z", name="Z", goal=1.0, remindAt="07:00", remindRepeat="daily"))
    # PUT remindAt=None (the partial-update convention: None = leave unchanged, NOT clear)
    svc.update_activity("z", ActivityUpdate(name="Z2"))  # remindAt omitted/None
    act = svc.get_activity("z")
    assert act.remindAt == "07:00" and act.remindRepeat == "daily", "remindAt unchanged (not cleared)"


def test_rest_clear_time_round_trip(api):
    api.post("/tracing/activities", json={"id": "c", "name": "C", "goal": 1, "time": "07:15"})
    r = api.put("/tracing/activities/c", json={"time": None})  # FE "Xóa giờ"
    assert r.status_code == 200 and r.json()["data"]["time"] is None
    # GET confirms persisted
    ov = api.get("/tracing").json()["data"]
    a = next(x for x in ov["activities"] if x["id"] == "c")
    assert a["time"] is None
