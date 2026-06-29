"""tests/test_tracing_alarm_weekday_mask.py — TRACING-ALARM #172: custom-weekday reminder mask.

The engine gains a VN-weekday MASK (the `days` column, CSV "0,1,2,3,4" Mon0..Sun6). A reminder with
a mask fires ONLY on its days; days=NULL fires every day (the pre-#172 behavior — old reminders
unaffected). The tracing side adds remindRepeat="custom" + remindDays, AND fixes the #75 "weekdays"
lie (it used to fire daily — now it genuinely skips Sat/Sun).

🔴 The distinguishing-case discipline (memory verify-with-the-distinguishing-case): the mask is
verified with an EXCLUDED day (Sat) that must NOT fire AND an INCLUDED day (Mon) that MUST fire — a
test that only checks an included day is a false-green (it can't tell a working mask from no mask).

🔴 The VN-tz discipline (memory reminders-tz-filter-bug): the weekday is computed in VN time. A
21:00-VN reminder near a UTC date boundary is a DIFFERENT UTC weekday — masking on the UTC day would
fire/skip on the wrong day. Tested with a near-midnight-UTC instant whose VN weekday differs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from modules.reminders import service as rem
from modules.reminders import store as rem_store
from modules.tracing import service as svc
from modules.tracing import store as trc_store
from modules.tracing.schema import ActivityInput, ActivityUpdate

VN = timezone(timedelta(hours=7))


@pytest.fixture
def db(isolated_paths):
    trc_store.init_tracing_tables()
    rem_store.init_reminders_tables()
    return isolated_paths


@pytest.fixture
def api(db):
    from main import create_app
    return TestClient(create_app())


def _tracing_reminder(activity_id: str):
    return rem_store.find_by_activity(activity_id, source="tracing")


def _backdate_due(activity_id: str) -> None:
    """Force the tracing-linked reminder's due_at far into the past so the ONLY gate left under test
    is the weekday mask (a freshly-synced reminder's due_at = today@remindAt, which can be in the
    future relative to a test's chosen scan-day)."""
    row = _tracing_reminder(activity_id)
    conn = rem_store.db.get_conn()
    conn.execute("UPDATE reminders SET due_at = ? WHERE id = ?",
                 ("2026-01-01T00:00:00+00:00", int(row["id"])))
    conn.commit()


def _vn_noon(year: int, month: int, day: int) -> datetime:
    """A VN-noon instant on a given date (well clear of any UTC date boundary) → UTC for the scan."""
    return datetime(year, month, day, 12, 0, tzinfo=VN).astimezone(timezone.utc)


# Known VN weekdays (Mon0..Sun6): 2026-06-29 = Monday(0); 2026-06-27 = Saturday(5); 2026-06-28 = Sunday(6);
#                                 2026-06-30 = Tuesday(1); 2026-07-02 = Thursday(3).
MON = _vn_noon(2026, 6, 29)
SAT = _vn_noon(2026, 6, 27)
SUN = _vn_noon(2026, 6, 28)
TUE = _vn_noon(2026, 6, 30)
THU = _vn_noon(2026, 7, 2)


def _fires(reminder_row, now: datetime) -> bool:
    now_iso = now.astimezone(timezone.utc).isoformat()
    return rem._should_fire(reminder_row, now_iso, now)


def _seed_masked_reminder(days_csv: str | None, due_at: str) -> None:
    """A bare reminder with an explicit days mask + a due_at in the past (so the only gate under test
    is the weekday mask, not the due-time)."""
    rem_store.create_reminder(
        title="masked", note=None, due_at=due_at, repeat="daily",
        re_notify_every=None, max_times=None, created="2026-01-01T00:00:00+00:00",
        source="manual", activity_id=None, channel="in_app", days=days_csv,
    )


# --------------------------------------------------------------------------- #
# 🔴 the day-mask distinguishing case: Mon0..Fri4 fires Mon, NOT Sat/Sun        #
# --------------------------------------------------------------------------- #
def test_mask_weekdays_skips_sat_and_sun_fires_mon(db):
    past_due = _vn_noon(2026, 6, 1).astimezone(timezone.utc).isoformat()  # long past-due
    _seed_masked_reminder("0,1,2,3,4", past_due)  # Mon–Fri
    row = rem_store.undone_reminders()[0]

    # 🔴 the DISTINGUISHING assertions — an excluded day must NOT fire, an included day MUST
    assert _fires(row, SAT) is False, "Sat(5) is excluded → must NOT fire"
    assert _fires(row, SUN) is False, "Sun(6) is excluded → must NOT fire"
    assert _fires(row, MON) is True, "Mon(0) is included → MUST fire"


def test_mask_custom_tue_thu_only(db):
    past_due = _vn_noon(2026, 6, 1).astimezone(timezone.utc).isoformat()
    _seed_masked_reminder("1,3", past_due)  # Tue + Thu only
    row = rem_store.undone_reminders()[0]
    assert _fires(row, TUE) is True, "Tue(1) included → fire"
    assert _fires(row, THU) is True, "Thu(3) included → fire"
    assert _fires(row, MON) is False, "Mon(0) NOT in [1,3] → skip"
    assert _fires(row, SAT) is False, "Sat(5) NOT in [1,3] → skip"


def test_no_mask_fires_every_day_old_reminder_unaffected(db):
    """days=NULL → no mask → fires every day (the pre-#172 behavior; old reminders unaffected)."""
    past_due = _vn_noon(2026, 6, 1).astimezone(timezone.utc).isoformat()
    _seed_masked_reminder(None, past_due)  # NO mask
    row = rem_store.undone_reminders()[0]
    for label, now in [("Mon", MON), ("Sat", SAT), ("Sun", SUN), ("Thu", THU)]:
        assert _fires(row, now) is True, f"no mask → fires on {label}"


def test_mask_vn_weekday_not_utc(db):
    """🔴 the tz lesson: the weekday is computed in VN, not UTC. Pick an instant that is Monday in VN
    but Sunday in UTC: 2026-06-29 06:00 VN = 2026-06-28 23:00 UTC (Sun). A Mon–Fri mask MUST fire
    (it's Monday in VN), proving the mask reads the VN weekday, not the UTC one."""
    mon_vn_but_sun_utc = datetime(2026, 6, 29, 6, 0, tzinfo=VN).astimezone(timezone.utc)
    assert mon_vn_but_sun_utc.weekday() == 6, "fixture sanity: this instant is Sunday in UTC"
    past_due = _vn_noon(2026, 6, 1).astimezone(timezone.utc).isoformat()
    _seed_masked_reminder("0,1,2,3,4", past_due)  # Mon–Fri
    row = rem_store.undone_reminders()[0]
    assert _fires(row, mon_vn_but_sun_utc) is True, "Monday-in-VN → fires (UTC-Sunday would wrongly skip)"


# --------------------------------------------------------------------------- #
# weekdays-lie FIX: a tracing activity remindRepeat="weekdays" → days=[0..4]     #
# --------------------------------------------------------------------------- #
def test_weekdays_now_honest_no_weekend_fire(db):
    svc.create_activity(ActivityInput(id="gym", name="Gym", goal=1.0,
                                      remindAt="07:00", remindRepeat="weekdays"))
    assert _tracing_reminder("gym")["days"] == "0,1,2,3,4", "weekdays → genuine Mon–Fri mask (the #75 lie is fixed)"
    _backdate_due("gym")  # isolate the mask from the due-time gate
    linked = _tracing_reminder("gym")
    # behavior: fires Mon, NOT Sat/Sun
    assert _fires(linked, MON) is True
    assert _fires(linked, SAT) is False and _fires(linked, SUN) is False


def test_daily_has_no_mask(db):
    """daily → days=NULL (fires every day — unchanged)."""
    svc.create_activity(ActivityInput(id="water", name="Water", goal=1.0,
                                      remindAt="09:00", remindRepeat="daily"))
    assert _tracing_reminder("water")["days"] is None, "daily has no weekday mask"
    _backdate_due("water")  # isolate the mask from the due-time gate
    assert _fires(_tracing_reminder("water"), SAT) is True, "daily fires on Sat too"


# --------------------------------------------------------------------------- #
# custom round-trip through the tracing API + the linked reminder mask           #
# --------------------------------------------------------------------------- #
def test_custom_round_trip_and_fires_only_masked_days(api):
    r = api.post("/tracing/activities", json={
        "id": "study", "name": "Study", "goal": 1,
        "remindAt": "20:00", "remindRepeat": "custom", "remindDays": [1, 3]})
    assert r.status_code == 201, r.text
    assert r.json()["data"]["remindRepeat"] == "custom"
    assert r.json()["data"]["remindDays"] == [1, 3]

    # GET /tracing reads back remindDays (the FE renders the chips off this)
    ov = api.get("/tracing").json()["data"]
    a = next(x for x in ov["activities"] if x["id"] == "study")
    assert a["remindRepeat"] == "custom" and a["remindDays"] == [1, 3]

    # the linked reminder fires only Tue/Thu
    assert _tracing_reminder("study")["days"] == "1,3"
    _backdate_due("study")  # isolate the mask from the due-time gate
    linked = _tracing_reminder("study")
    assert _fires(linked, TUE) is True and _fires(linked, THU) is True
    assert _fires(linked, MON) is False and _fires(linked, SAT) is False


def test_custom_to_daily_clears_mask(db):
    """Switching repeat custom → daily drops the mask (fires every day again)."""
    svc.create_activity(ActivityInput(id="c", name="C", goal=1.0,
                                      remindAt="08:00", remindRepeat="custom", remindDays=[0]))
    assert _tracing_reminder("c")["days"] == "0"
    svc.update_activity("c", ActivityUpdate(remindRepeat="daily"))
    act = svc.get_activity("c")
    assert act.remindRepeat == "daily" and act.remindDays is None
    assert _tracing_reminder("c")["days"] is None, "leaving custom clears the linked reminder mask"


# --------------------------------------------------------------------------- #
# validation                                                                   #
# --------------------------------------------------------------------------- #
def test_custom_empty_days_is_422(api):
    r = api.post("/tracing/activities", json={
        "id": "bad", "name": "Bad", "goal": 1, "remindRepeat": "custom", "remindDays": []})
    assert r.status_code == 422


def test_custom_no_days_is_422(api):
    r = api.post("/tracing/activities", json={
        "id": "bad2", "name": "Bad2", "goal": 1, "remindRepeat": "custom"})
    assert r.status_code == 422


def test_day_out_of_range_is_422(api):
    r = api.post("/tracing/activities", json={
        "id": "bad3", "name": "Bad3", "goal": 1, "remindRepeat": "custom", "remindDays": [7]})
    assert r.status_code == 422


def test_off_no_reminder(db):
    """remindRepeat='off' → no linked reminder (regression: the mask plumbing didn't break off)."""
    svc.create_activity(ActivityInput(id="o", name="O", goal=1.0))  # off by default
    assert _tracing_reminder("o") is None
