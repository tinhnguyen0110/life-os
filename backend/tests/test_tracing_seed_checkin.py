"""tests/test_tracing_seed_checkin.py — TRACING-ALARM T2 (#172): seed 3 daily check-in activities.

``service.seed_checkin_activities()`` is a re-runnable maintenance helper that creates 3 check-in
activities using the T1 custom-day reminder mode. The guarantees:
  - creates exactly Check-in sáng (07:00, custom Mon–Fri) / Check-in trưa (12:00, custom Mon–Fri) /
    Báo cáo tối (21:00, daily) — names in proper VN, goal=1;
  - 🔴 IDEMPOTENT: a re-run creates 0 (an existing id is SKIPPED, never overwritten/duplicated);
  - the linked reminder carries the right day-mask (checkin → "0,1,2,3,4"; report → NULL/every-day);
  - SCOPED: existing activities are untouched.
"""

from __future__ import annotations

import pytest

from modules.reminders import store as rem_store
from modules.tracing import service as svc
from modules.tracing import store as trc_store
from modules.tracing.schema import ActivityInput, ActivityUpdate


@pytest.fixture
def db(isolated_paths):
    trc_store.init_tracing_tables()
    rem_store.init_reminders_tables()
    return isolated_paths


def _linked(activity_id: str):
    return rem_store.find_by_activity(activity_id, source="tracing")


def test_seed_creates_the_three_with_correct_fields(db):
    res = svc.seed_checkin_activities()
    assert res["createdCount"] == 3 and res["skippedCount"] == 0
    assert set(res["created"]) == {"checkin-sang", "checkin-trua", "report-toi"}

    sang = svc.get_activity("checkin-sang")
    assert sang.name == "Check-in sáng" and sang.time == "07:00" and sang.goal == 1.0
    assert sang.remindRepeat == "custom" and sang.remindDays == [0, 1, 2, 3, 4]

    trua = svc.get_activity("checkin-trua")
    assert trua.name == "Check-in trưa" and trua.time == "12:00"
    assert trua.remindRepeat == "custom" and trua.remindDays == [0, 1, 2, 3, 4]

    toi = svc.get_activity("report-toi")
    assert toi.name == "Báo cáo tối" and toi.time == "21:00"
    assert toi.remindRepeat == "daily" and toi.remindDays is None


def test_seed_linked_reminders_have_the_mask(db):
    """🔴 the T1 plumbing: checkin → days='0,1,2,3,4' (Mon–Fri); report → days NULL (every day)."""
    svc.seed_checkin_activities()
    assert _linked("checkin-sang")["days"] == "0,1,2,3,4"
    assert _linked("checkin-trua")["days"] == "0,1,2,3,4"
    assert _linked("report-toi")["days"] is None  # daily = no mask


def test_seed_is_idempotent_rerun_creates_zero(db):
    first = svc.seed_checkin_activities()
    assert first["createdCount"] == 3
    second = svc.seed_checkin_activities()
    assert second["createdCount"] == 0 and second["skippedCount"] == 3
    assert set(second["skipped"]) == {"checkin-sang", "checkin-trua", "report-toi"}
    # still exactly one of each (no duplicate)
    assert sum(1 for r in trc_store.list_activities() if r["id"] == "checkin-sang") == 1


def test_seed_does_not_overwrite_user_edits(db):
    """🔴 idempotent SKIP = no overwrite: a user who edited a seeded activity keeps their edit on re-seed."""
    svc.seed_checkin_activities()
    svc.update_activity("checkin-sang", ActivityUpdate(name="My morning"))  # user renames it
    res = svc.seed_checkin_activities()  # re-run
    assert res["createdCount"] == 0
    assert svc.get_activity("checkin-sang").name == "My morning", "the user's edit is NOT clobbered"


def test_seed_scoped_does_not_touch_existing(db):
    """SCOPED: a pre-existing unrelated activity is untouched by the seed."""
    svc.create_activity(ActivityInput(id="run", name="Run", goal=5.0, time="06:00"))
    svc.seed_checkin_activities()
    run = svc.get_activity("run")
    assert run.name == "Run" and run.goal == 5.0 and run.time == "06:00"  # unchanged
    # total = the pre-existing one + the 3 seeds
    assert len(trc_store.list_activities()) == 4


def test_seed_skips_archived_id_no_resurrect(db):
    """An ARCHIVED seed id is still 'exists' (get_activity covers archived) → SKIP, not resurrect."""
    svc.seed_checkin_activities()
    svc.archive_activity("report-toi")  # user archives it
    res = svc.seed_checkin_activities()  # re-run
    assert "report-toi" in res["skipped"], "an archived seed id is skipped, not re-created"
    # it stays archived (not resurrected by the seed)
    assert svc.get_activity("report-toi").archived is True
