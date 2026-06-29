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
    created, skipped, archived = result
    assert skipped == [] and len(created) == 2 and archived == 0  # empty board → nothing to archive
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
    created, _, _ = svc.import_template_set(s.id)
    assert created[0].time == "09:00"
    assert _tracing_reminders() == []  # time independent of reminder (#136)


def test_import_unknown_set_is_none(db):
    assert svc.import_template_set("ghost") is None


def test_reimport_idempotent_by_id_no_suffix_no_trash_growth(db):
    """🔴 TRACING-TEMPLATE-UX (#173): re-importing the same set REUSES the same canonical id (NO -N
    suffix) → the board is the same id both times AND /trash does NOT grow (re-import archives 0)."""
    s = svc.create_template_set(TemplateSetInput(name="M", activities=[_M("task")]))
    c1, _, arch1 = svc.import_template_set(s.id)
    assert len(c1) == 1 and c1[0].id == "task" and arch1 == 0  # stable slug id, empty board
    trash_before = len(trc_store.trash_activities()) if hasattr(trc_store, "trash_activities") else \
        sum(1 for r in trc_store.list_activities(include_archived=True) if r["archived"])

    c2, _, arch2 = svc.import_template_set(s.id)
    assert len(c2) == 1 and c2[0].id == "task"  # 🔴 SAME id (no task-2 suffix)
    assert arch2 == 0, "re-import of the same set archives 0 (idempotent — no trash growth)"
    # the board is EXACTLY {task} (1 active, no doubling)
    assert {r["id"] for r in trc_store.list_activities()} == {"task"}
    # /trash did NOT grow
    trash_after = len(trc_store.trash_activities()) if hasattr(trc_store, "trash_activities") else \
        sum(1 for r in trc_store.list_activities(include_archived=True) if r["archived"])
    assert trash_after == trash_before, "re-import must NOT bloat /trash"


def test_reimport_updates_member_fields(db):
    """Re-importing a set whose member fields CHANGED → the same id is UPDATED (not duplicated)."""
    s = svc.create_template_set(TemplateSetInput(name="M", activities=[_M("task", time="07:00", repeat="daily")]))
    svc.import_template_set(s.id)
    assert svc.get_activity("task").time == "07:00" and svc.get_activity("task").remindRepeat == "daily"
    # change the member, re-import → same id, updated fields
    svc.replace_template_set(s.id, TemplateSetInput(name="M", activities=[_M("task", time="09:30", repeat="off")]))
    views, _, arch = svc.import_template_set(s.id)
    assert views[0].id == "task" and arch == 0
    assert svc.get_activity("task").time == "09:30" and svc.get_activity("task").remindRepeat == "off"


def test_import_different_set_archives_non_shared(db):
    """Import set A then set B → B's members active (canonical ids), A's NON-shared members archived."""
    a = svc.create_template_set(TemplateSetInput(name="A", activities=[_M("alpha"), _M("shared")]))
    b = svc.create_template_set(TemplateSetInput(name="B", activities=[_M("beta"), _M("shared")]))
    svc.import_template_set(a.id)
    assert {r["id"] for r in trc_store.list_activities()} == {"alpha", "shared"}
    _, _, arch = svc.import_template_set(b.id)
    # B's members active; "alpha" (A-only) archived; "shared" reused (not archived, not dup)
    assert {r["id"] for r in trc_store.list_activities()} == {"beta", "shared"}
    assert arch == 1 and svc.get_activity("alpha").archived is True


def test_import_atomic_no_empty_board_on_failure(db, monkeypatch):
    """🔴 the ATOMIC guard (preserved from T1): if every member upsert throws, the OLD board is INTACT
    (not archived/emptied) — upsert-first means no old activity is archived until ≥1 member lands."""
    s = svc.create_template_set(TemplateSetInput(name="M", activities=[_M("a"), _M("b")]))
    svc.import_template_set(s.id)  # board now has a, b
    before = {r["id"] for r in trc_store.list_activities()}
    assert before == {"a", "b"}

    # force EVERY member upsert to fail (re-import goes through update_activity for existing ids)
    monkeypatch.setattr(svc, "update_activity",
                        lambda aid, upd: (_ for _ in ()).throw(RuntimeError("boom")))
    views, skipped, archived = svc.import_template_set(s.id)
    assert views == [] and len(skipped) == 2 and archived == 0, "all upserts failed → archive NOTHING"
    after = {r["id"] for r in trc_store.list_activities()}
    assert after == before, "a failed import must NOT archive/empty the old board"


def test_import_partial_failure_keeps_what_landed(db, monkeypatch):
    """If SOME members upsert (≥1) and some fail, the ≥1 that landed are on the board; the failed are
    reported skipped; the old non-matching ids are archived."""
    a = svc.create_template_set(TemplateSetInput(name="A", activities=[_M("old-only")]))
    svc.import_template_set(a.id)  # board: old-only
    b = svc.create_template_set(TemplateSetInput(name="B", activities=[_M("ok"), _M("bad")]))

    real_create = svc.create_activity

    def flaky_create(inp):
        if inp.name == "bad":
            raise RuntimeError("boom")
        return real_create(inp)

    monkeypatch.setattr(svc, "create_activity", flaky_create)
    views, skipped, archived = svc.import_template_set(b.id)
    assert len(views) == 1 and views[0].id == "ok" and skipped == ["bad"]
    assert archived == 1  # "old-only" (not in B's landed members) archived
    assert {r["id"] for r in trc_store.list_activities()} == {"ok"}


# --- reset → discard + one default ------------------------------------------ #
def test_reset_reseeds_one_default(db):
    svc.create_template_set(TemplateSetInput(name="Mine", activities=[_M("a")]))
    svc.create_template_set(TemplateSetInput(name="Other", activities=[_M("b")]))
    out = svc.reset_template_sets()
    # TRACING-DEFAULT (#173): the default set is the 3 daily check-ins, NOT the old "Buổi sáng" habits
    assert len(out) == 1 and out[0].id == "check-in" and out[0].name == "Check-in hàng ngày"
    assert len(out[0].activities) == 3  # the 3 check-ins
    assert [m.content for m in out[0].activities] == ["Check-in sáng", "Check-in trưa", "Báo cáo tối"]
    # the morning + noon check-ins fire Mon–Fri (custom mask); báo cáo tối daily
    sang = out[0].activities[0]
    assert sang.remindRepeat == "custom" and sang.remindDays == [0, 1, 2, 3, 4] and sang.time == "07:00"
    assert out[0].activities[2].remindRepeat == "daily"
    # the user's sets are gone
    assert {s.name for s in svc.list_template_sets()} == {"Check-in hàng ngày"}


def test_import_default_set_creates_three_checkins_with_masks(db):
    """🔴 #173: importing the default 'Check-in hàng ngày' set creates the 3 check-in activities with
    the right times + reminder masks (checkin-* fire Mon–Fri via the #172 custom mask; báo cáo tối
    daily). Proves the TemplateMember remindRepeat='custom'+remindDays thread through the import."""
    svc.reset_template_sets()  # seed the default check-in set
    created, skipped, _ = svc.import_template_set("check-in")
    assert skipped == [] and len(created) == 3
    names = {v.name for v in created}
    assert names == {"Check-in sáng", "Check-in trưa", "Báo cáo tối"}

    sang = next(v for v in created if v.name == "Check-in sáng")
    assert sang.time == "07:00" and sang.remindRepeat == "custom" and sang.remindDays == [0, 1, 2, 3, 4]
    toi = next(v for v in created if v.name == "Báo cáo tối")
    assert toi.time == "21:00" and toi.remindRepeat == "daily" and toi.remindDays is None
    # the linked reminder carries the Mon–Fri mask for the morning check-in
    linked = rem_store.find_by_activity(sang.id, source="tracing")
    assert linked is not None and linked["days"] == "0,1,2,3,4"


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
    body = imp.json()["data"]
    created = body["created"]
    assert len(created) == 2 and all(v["goal"] == 1.0 for v in created)
    assert "archivedCount" in body and body["archivedCount"] == 0  # #173: empty board → 0 archived
    water = next(v for v in created if v["name"] == "Uống nước")
    assert water["time"] == "07:00" and water["remindRepeat"] == "daily"
    # reset → one default
    rs = api.post("/tracing/template-sets/reset")
    assert rs.status_code == 200
    sets = rs.json()["data"]["sets"]
    assert len(sets) == 1 and sets[0]["name"] == "Check-in hàng ngày"  # #173: default = the 3 check-ins


def test_rest_import_unknown_404(api):
    r = api.post("/tracing/template-sets/ghost/import")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_rest_blank_name_422(api):
    r = api.post("/tracing/template-sets", json={"name": "  ", "activities": []})
    assert r.status_code == 422


def test_rest_delete_404(api):
    assert api.delete("/tracing/template-sets/ghost").status_code == 404
