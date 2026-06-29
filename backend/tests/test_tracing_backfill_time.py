"""tests/test_tracing_backfill_time.py — TRACING-UX3A T1 (#170 follow-up): backfill timeless time.

``service.backfill_timeless_time("08:00")`` is a re-runnable maintenance helper that sets ``time``
to a default for every ACTIVE activity whose time is null/empty, via the canonical update path.
The load-bearing guarantees (the #72 scoped-write discipline on a REAL store):
  - 🔴 timeless → default_time; counts {before, after, touched};
  - an already-timed activity is SKIPPED (idempotent — a re-run touches 0);
  - reminder / streak-logs / name / goal are PRESERVED (only `time` is written);
  - archived activities are NOT touched (active-only scope).
"""

from __future__ import annotations

import pytest

from modules.reminders import service as rem
from modules.reminders import store as rem_store
from modules.tracing import service as svc
from modules.tracing import store as trc_store
from modules.tracing.schema import ActivityInput, ActivityUpdate, LogInput


@pytest.fixture
def db(isolated_paths):
    trc_store.init_tracing_tables()
    rem_store.init_reminders_tables()
    return isolated_paths


def _tracing_reminders():
    view, _ = rem.list_reminders("all")
    return [r for r in view.reminders if r.source == "tracing"]


def test_backfill_sets_timeless_to_default_and_counts(db):
    """🔴 the core: timeless activities with NO remindAt get default_time; already-timed are left;
    counts are honest."""
    svc.create_activity(ActivityInput(id="t1", name="T1", goal=1.0))               # timeless, no remind
    svc.create_activity(ActivityInput(id="t2", name="T2", goal=1.0))               # timeless, no remind
    svc.create_activity(ActivityInput(id="timed", name="Timed", goal=1.0, time="06:30"))  # already timed

    res = svc.backfill_timeless_time("08:00")
    assert res["beforeTimeless"] == 2 and res["afterTimeless"] == 0
    assert set(res["touched"]) == {"t1", "t2"}  # the timed one is NOT touched
    assert res["set"] == {"t1": "08:00", "t2": "08:00"}  # per-id chosen time (no remindAt → default)
    assert res["defaultTime"] == "08:00"

    assert svc.get_activity("t1").time == "08:00"
    assert svc.get_activity("t2").time == "08:00"
    assert svc.get_activity("timed").time == "06:30", "an already-timed activity is left UNCHANGED"


def test_backfill_uses_remindAt_when_present_no_jump(db):
    """🔴 T1 REFINEMENT (the 'Viết nhật ký' case): a timeless activity WITH a remindAt gets
    time = remindAt (matching what the FE rail already shows = ``a.time || a.remindAt``), NOT the
    hard default — so it does NOT visibly jump. The reminder field itself is untouched."""
    svc.create_activity(ActivityInput(id="viet", name="Viết nhật ký", goal=1.0,
                                      remindAt="07:00", remindRepeat="daily"))   # timeless, remind 07:00
    svc.create_activity(ActivityInput(id="plain", name="Plain", goal=1.0))       # timeless, no remind

    res = svc.backfill_timeless_time("08:00")
    assert res["set"] == {"viet": "07:00", "plain": "08:00"}, "remindAt wins for viet; default for plain"

    viet = svc.get_activity("viet")
    assert viet.time == "07:00", "time = remindAt (no jump from what's on the rail)"
    assert viet.remindAt == "07:00" and viet.remindRepeat == "daily", "the reminder is UNTOUCHED"
    assert svc.get_activity("plain").time == "08:00"


def test_backfill_is_idempotent(db):
    """A re-run touches 0 (every activity already has a time)."""
    svc.create_activity(ActivityInput(id="a", name="A", goal=1.0))
    first = svc.backfill_timeless_time("08:00")
    assert first["beforeTimeless"] == 1 and first["touched"] == ["a"]
    second = svc.backfill_timeless_time("08:00")
    assert second["beforeTimeless"] == 0 and second["afterTimeless"] == 0 and second["touched"] == []
    assert svc.get_activity("a").time == "08:00"  # unchanged by the no-op re-run


def test_backfill_preserves_reminder(db):
    """🔴 the live 'viet' case: an activity with remindAt=07:00 keeps its reminder after backfill —
    only `time` is written (= remindAt per the refinement), the reminder fires off remindAt (untouched)."""
    svc.create_activity(ActivityInput(id="viet", name="Viết nhật ký", goal=1.0,
                                      remindAt="07:00", remindRepeat="daily"))
    assert len(_tracing_reminders()) == 1
    svc.backfill_timeless_time("08:00")
    act = svc.get_activity("viet")
    assert act.time == "07:00", "time backfilled to remindAt (no UX jump)"
    assert act.remindAt == "07:00" and act.remindRepeat == "daily", "reminder UNCHANGED"
    assert len(_tracing_reminders()) == 1, "the linked reminder still exists at 07:00"


def test_backfill_preserves_name_goal_and_logs(db):
    """Only `time` changes — name/goal and today's logged sessions survive."""
    svc.create_activity(ActivityInput(id="run", name="Run", goal=5.0, unit="km"))
    svc.log_session("run", LogInput(val=3.0))  # a today session → streak/today derivation
    before = svc.get_activity("run")
    ov_before = next(a for a in svc.overview().activities if a.id == "run")
    assert ov_before.today.val == 3.0

    svc.backfill_timeless_time("08:00")

    after = svc.get_activity("run")
    assert after.time == "08:00"
    assert after.name == before.name == "Run" and after.goal == before.goal == 5.0
    ov_after = next(a for a in svc.overview().activities if a.id == "run")
    assert ov_after.today.val == 3.0, "today's logged session survives the backfill"


def test_backfill_skips_archived(db):
    """Archived activities are out of scope (store.list_activities excludes them) → not touched."""
    svc.create_activity(ActivityInput(id="arch", name="Arch", goal=1.0))
    svc.archive_activity("arch")
    res = svc.backfill_timeless_time("08:00")
    assert res["beforeTimeless"] == 0 and res["touched"] == []
    # the archived row's time stays None (get_activity includes archived)
    assert svc.get_activity("arch").time is None
