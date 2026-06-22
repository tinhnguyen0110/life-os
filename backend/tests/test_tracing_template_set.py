"""tests/test_tracing_template_set.py — TRACING-TEMPLATE #137 T1: template-SETS.

A "mẫu" = a saved NAMED LIST of rich activities (a reusable routine), NOT 1-word chips. 1-click
import → all members become today's activities (goal=1 binary todos, time + reminder preset). The
load-bearing cases:
  - CRUD round-trip (create/list/get/replace/delete) — model B JSON activities;
  - 🔴 import → each member is a goal=1 activity WITH its time + remind carried (a timed+reminded
    member emits a reminder; a bare member doesn't);
  - reset → discard all + exactly the ONE default set remains;
  - blank name / blank member content / bad member time → 422;
  - 🔴 SCOPED (#72): reset/delete touch ONLY tracing_template_set, never real activities/logs.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.reminders import service as rem
from modules.reminders import store as rem_store
from modules.tracing import service as svc
from modules.tracing import store as trc_store
from modules.tracing.schema import ActivityInput, TemplateMember, TemplateSetInput


@pytest.fixture
def db(isolated_paths):
    trc_store.init_tracing_tables()
    rem_store.init_reminders_tables()
    return isolated_paths


@pytest.fixture
def api(db):
    from main import create_app
    return TestClient(create_app())


def _M(content, time=None, repeat="off", channel="in_app"):
    return TemplateMember(content=content, time=time, remindRepeat=repeat, remindChannel=channel)


# --- CRUD round-trip --------------------------------------------------------- #
def test_create_and_get_set(db):
    s = svc.create_template_set(TemplateSetInput(name="Buổi sáng", activities=[
        _M("Uống nước", time="07:00", repeat="daily"), _M("Đọc sách")]))
    assert s.id == "buoi-sang" and s.name == "Buổi sáng" and len(s.activities) == 2
    got = svc.get_template_set(s.id)
    assert got is not None and got.activities[0].content == "Uống nước" and got.activities[0].time == "07:00"
    assert got.activities[1].content == "Đọc sách" and got.activities[1].remindRepeat == "off"


def test_list_sets_honest_empty(db):
    assert svc.list_template_sets() == []


def test_id_suffix_on_name_collision(db):
    a = svc.create_template_set(TemplateSetInput(name="Routine", activities=[]))
    b = svc.create_template_set(TemplateSetInput(name="Routine", activities=[]))
    assert a.id == "routine" and b.id == "routine-2"  # no collision


def test_replace_set_whole(db):
    s = svc.create_template_set(TemplateSetInput(name="X", activities=[_M("a")]))
    out = svc.replace_template_set(s.id, TemplateSetInput(name="X2", activities=[_M("b"), _M("c")]))
    assert out is not None and out.name == "X2" and [m.content for m in out.activities] == ["b", "c"]


def test_replace_absent_is_none(db):
    assert svc.replace_template_set("ghost", TemplateSetInput(name="X", activities=[])) is None


def test_delete_set(db):
    s = svc.create_template_set(TemplateSetInput(name="X", activities=[]))
    assert svc.delete_template_set(s.id) is True
    assert svc.get_template_set(s.id) is None
    assert svc.delete_template_set(s.id) is False  # idempotent-ish: absent → False


# --- 🔴 import → goal=1 activities WITH time/remind carried ------------------ #
def _tracing_reminders():
    view, _ = rem.list_reminders("all")
    return [r for r in view.reminders if r.source == "tracing"]


def test_import_creates_goal1_activities_with_presets(db):
    s = svc.create_template_set(TemplateSetInput(name="Morning", activities=[
        _M("Uống nước", time="07:00", repeat="daily", channel="discord"),  # timed + reminded
        _M("Đọc sách"),  # bare (no time, no remind)
    ]))
    result = svc.import_template_set(s.id)
    assert result is not None
    created, skipped = result
    assert skipped == [] and len(created) == 2
    # both are goal=1 binary todos
    assert all(v.goal == 1.0 for v in created)
    water = next(v for v in created if v.name == "Uống nước")
    read = next(v for v in created if v.name == "Đọc sách")
    # the timed+reminded member carries time + remind
    assert water.time == "07:00" and water.remindRepeat == "daily" and water.remindChannel == "discord"
    # the bare member: no time, no remind
    assert read.time is None and read.remindRepeat == "off"
    # 🔴 the reminded member emitted a reminder; the bare one did NOT
    rems = _tracing_reminders()
    assert len(rems) == 1 and "Uống nước" in rems[0].title and rems[0].channel == "discord"


def test_import_reminder_at_member_time(db):
    s = svc.create_template_set(TemplateSetInput(name="M", activities=[
        _M("x", time="06:00", repeat="daily")]))
    svc.import_template_set(s.id)
    rems = _tracing_reminders()
    # reminder fires at 06:00 VN = 23:00 UTC prior day (UTC-normalized due_at)
    assert len(rems) == 1 and rems[0].due_at.endswith("T23:00:00+00:00")


def test_import_member_with_time_but_no_remind_no_reminder(db):
    """A member with a time but remindRepeat=off → the activity has the time, but NO reminder."""
    s = svc.create_template_set(TemplateSetInput(name="M", activities=[
        _M("x", time="09:00", repeat="off")]))
    created, _ = svc.import_template_set(s.id)
    assert created[0].time == "09:00"
    assert _tracing_reminders() == []  # time independent of reminder (#136)


def test_import_unknown_set_is_none(db):
    assert svc.import_template_set("ghost") is None


def test_import_unique_ids_no_409_on_reimport(db):
    """Re-importing the same set → unique activity ids (slug+suffix) → no 409, both imports succeed."""
    s = svc.create_template_set(TemplateSetInput(name="M", activities=[_M("task")]))
    c1, _ = svc.import_template_set(s.id)
    c2, _ = svc.import_template_set(s.id)
    assert len(c1) == 1 and len(c2) == 1
    assert c1[0].id != c2[0].id  # second import got a suffixed id (task, task-2)


# --- reset → discard + one default ------------------------------------------ #
def test_reset_reseeds_one_default(db):
    svc.create_template_set(TemplateSetInput(name="Mine", activities=[_M("a")]))
    svc.create_template_set(TemplateSetInput(name="Other", activities=[_M("b")]))
    out = svc.reset_template_sets()
    assert len(out) == 1 and out[0].id == "buoi-sang" and out[0].name == "Buổi sáng"
    assert len(out[0].activities) == 3  # the default morning routine
    # the user's sets are gone
    assert {s.name for s in svc.list_template_sets()} == {"Buổi sáng"}


# --- 🔴 SCOPED (#72): reset/delete never touch real activities/logs ---------- #
def test_reset_does_not_touch_activities(db):
    svc.create_activity(ActivityInput(id="real", name="Real habit", goal=5.0))  # a real activity
    svc.create_template_set(TemplateSetInput(name="S", activities=[_M("a")]))
    svc.reset_template_sets()
    assert svc.get_activity("real") is not None, "reset must NOT wipe real activities (#72)"


# --- validation -------------------------------------------------------------- #
def test_blank_name_422(db):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        TemplateSetInput(name="   ", activities=[])


def test_blank_member_content_422(db):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        TemplateMember(content="  ")


def test_bad_member_time_422(db):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        TemplateMember(content="x", time="25:99")


# --- REST surface ------------------------------------------------------------ #
def test_rest_crud_import_reset(api):
    # create
    r = api.post("/tracing/template-sets", json={"name": "Morning", "activities": [
        {"content": "Uống nước", "time": "07:00", "remindRepeat": "daily", "remindChannel": "discord"},
        {"content": "Đọc sách"}]})
    assert r.status_code == 201, r.text
    sid = r.json()["data"]["id"]
    # list
    assert any(s["id"] == sid for s in api.get("/tracing/template-sets").json()["data"]["sets"])
    # import → 2 activities WITH goal=1
    imp = api.post(f"/tracing/template-sets/{sid}/import")
    assert imp.status_code == 200
    created = imp.json()["data"]["created"]
    assert len(created) == 2 and all(v["goal"] == 1.0 for v in created)
    water = next(v for v in created if v["name"] == "Uống nước")
    assert water["time"] == "07:00" and water["remindRepeat"] == "daily"
    # reset → one default
    rs = api.post("/tracing/template-sets/reset")
    assert rs.status_code == 200
    sets = rs.json()["data"]["sets"]
    assert len(sets) == 1 and sets[0]["name"] == "Buổi sáng"


def test_rest_import_unknown_404(api):
    r = api.post("/tracing/template-sets/ghost/import")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_rest_blank_name_422(api):
    r = api.post("/tracing/template-sets", json={"name": "  ", "activities": []})
    assert r.status_code == 422


def test_rest_delete_404(api):
    assert api.delete("/tracing/template-sets/ghost").status_code == 404
