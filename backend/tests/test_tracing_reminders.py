"""tests/test_tracing_reminders.py — TRACING-REMINDERS-BE (#75): the tracing→reminder wire.

ONE-WAY: an activity with remind_at + remind_repeat≠off materializes a reminder (source=tracing)
that the existing #29 engine fires; clearing the remind / archiving the activity deletes it. The
activity is source-of-truth (deleting the reminder doesn't touch the activity).

EXERCISE the wire (behavior-test-not-field-read) — set remind → assert a reminder APPEARS; update →
SAME reminder updates (no dup); clear/archive → GONE; a manual POST can't forge source=tracing
(forge-guard); reminders_list + the linked fields survive (consumer-recheck).
"""

from __future__ import annotations

import pytest

from modules.reminders import service as rem
from modules.reminders import store as rem_store
from modules.tracing import service as trc
from modules.tracing import store as trc_store
from modules.tracing.schema import ActivityInput, ActivityUpdate


@pytest.fixture
def db(isolated_paths):
    trc_store.init_tracing_tables()
    rem_store.init_reminders_tables()
    return isolated_paths


def _tracing_reminders():
    """All source=tracing reminders currently stored (the wire's output)."""
    view, _ = rem.list_reminders("all")
    return [r for r in view.reminders if r.source == "tracing"]


# --- set remind → a tracing reminder APPEARS --------------------------------- #
def test_create_with_remind_materializes_reminder(db):
    trc.create_activity(ActivityInput(id="run", name="Run", emoji="🏃", goal=5.0,
                                      remindAt="07:00", remindRepeat="daily"))
    rems = _tracing_reminders()
    assert len(rems) == 1
    r = rems[0]
    assert r.source == "tracing" and r.activity_id == "run" and r.repeat == "daily"
    assert "Run" in r.title  # title from emoji+name
    assert r.due_at.endswith("Z") or "+00:00" in r.due_at  # due_at is UTC-normalized


def test_create_without_remind_no_reminder(db):
    trc.create_activity(ActivityInput(id="read", name="Read", goal=1.0))  # no remind_at
    assert _tracing_reminders() == []


def test_remind_repeat_off_no_reminder(db):
    """remind_at set but remindRepeat=off → NO reminder (off wins)."""
    trc.create_activity(ActivityInput(id="x", name="X", goal=1.0, remindAt="07:00", remindRepeat="off"))
    assert _tracing_reminders() == []


# --- update → the SAME reminder updates (no duplicate) ----------------------- #
def test_update_remind_updates_same_reminder_no_dup(db):
    trc.create_activity(ActivityInput(id="run", name="Run", goal=5.0,
                                      remindAt="07:00", remindRepeat="daily"))
    first = _tracing_reminders()
    assert len(first) == 1
    first_id = first[0].id
    trc.update_activity("run", ActivityUpdate(remindAt="08:30"))
    after = _tracing_reminders()
    assert len(after) == 1, "update must NOT create a duplicate reminder"
    assert after[0].id == first_id  # SAME reminder row (find-by-activity upsert)
    assert "08:30" in after[0].due_at or after[0].due_at != first[0].due_at  # time changed


def test_rename_activity_updates_reminder_title(db):
    trc.create_activity(ActivityInput(id="run", name="Run", goal=5.0,
                                      remindAt="07:00", remindRepeat="daily"))
    trc.update_activity("run", ActivityUpdate(name="Morning Run"))
    rems = _tracing_reminders()
    assert len(rems) == 1 and "Morning Run" in rems[0].title


# --- clear / archive → the reminder is GONE --------------------------------- #
def test_clear_remind_via_off_deletes_reminder(db):
    trc.create_activity(ActivityInput(id="run", name="Run", goal=5.0,
                                      remindAt="07:00", remindRepeat="daily"))
    assert len(_tracing_reminders()) == 1
    trc.update_activity("run", ActivityUpdate(remindRepeat="off"))  # the clear path
    assert _tracing_reminders() == [], "remindRepeat=off must delete the linked reminder"


def test_archive_activity_deletes_reminder(db):
    trc.create_activity(ActivityInput(id="run", name="Run", goal=5.0,
                                      remindAt="07:00", remindRepeat="daily"))
    assert len(_tracing_reminders()) == 1
    trc.archive_activity("run")
    assert _tracing_reminders() == [], "archiving the activity must delete its reminder (one-way)"
    # one-way: the activity still exists (archived), the reminder is gone
    act = trc.get_activity("run")
    assert act is not None and act.archived is True


def test_archive_activity_without_reminder_no_crash(db):
    trc.create_activity(ActivityInput(id="read", name="Read", goal=1.0))  # no reminder
    assert trc.archive_activity("read") is True  # no-op on the reminder side, no crash


# --- forge-guard: a manual POST can't set source=tracing -------------------- #
def test_manual_reminder_cannot_forge_tracing_source(db):
    """ReminderInput has no `source` field → a manual create is always source=manual, even if the
    payload tries to smuggle source/activity_id (pydantic ignores unknown → manual)."""
    from modules.reminders.schema import ReminderInput
    from modules.reminders.schema import now_iso
    # ReminderInput doesn't accept source — a dict with source is ignored on construction.
    inp = ReminderInput(title="manual one", due_at=now_iso())
    assert not hasattr(inp, "source")  # source is NOT an input field (forge-guard by schema)
    created = rem.create(inp)
    assert created.source == "manual" and created.activity_id is None


# --- consumer-recheck: reminders_list + the new fields work ----------------- #
def test_reminders_list_includes_tracing_source_field(db):
    trc.create_activity(ActivityInput(id="run", name="Run", goal=5.0,
                                      remindAt="07:00", remindRepeat="daily"))
    view, warnings = rem.list_reminders("all")
    assert warnings == [] or all("malformed" not in w for w in warnings)  # no map failure
    tracing = [r for r in view.reminders if r.source == "tracing"]
    assert len(tracing) == 1 and tracing[0].activity_id == "run"
    # a manual reminder coexists, tagged manual
    from modules.reminders.schema import ReminderInput, now_iso
    rem.create(ReminderInput(title="manual", due_at=now_iso()))
    view2, _ = rem.list_reminders("all")
    assert {r.source for r in view2.reminders} == {"manual", "tracing"}


def test_weekdays_maps_to_daily_engine(db):
    """remindRepeat=weekdays → the reminder fires daily (the #29 engine has no weekday-mask;
    documented honest limitation — surfaced as weekdays on the activity, fires daily)."""
    trc.create_activity(ActivityInput(id="work", name="Work", goal=8.0,
                                      remindAt="09:00", remindRepeat="weekdays"))
    rems = _tracing_reminders()
    assert len(rems) == 1 and rems[0].repeat == "daily"
    # the activity surfaces the original weekdays intent
    assert trc.get_activity("work").remindRepeat == "weekdays"


def test_invalid_remind_at_rejected_422(db):
    """A bad HH:MM → ValidationError (→ 422 at the router), no activity/reminder created."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ActivityInput(id="x", name="X", goal=1.0, remindAt="25:99", remindRepeat="daily")


# --- #117: GET /tracing READ-BACK must surface the stored remindChannel ------- #
# The bug: write persisted remind_channel + _row_to_activity read it, but
# _derive_activity_view (the ActivityView built for the overview/GET /tracing
# read-back) DROPPED it → the view always defaulted to in_app, masking the
# stored discord/email. EXERCISE the read-back surface (svc.overview() →
# ActivityView), not the POST echo (which was always correct).
@pytest.mark.parametrize("channel", ["in_app", "email", "discord"])
def test_117_overview_readback_surfaces_stored_channel(db, channel):
    """create remindChannel=<channel> → the GET /tracing read-back (overview ActivityView)
    must report the SAME channel (the #117 read-path bug: it was defaulting to in_app)."""
    trc.create_activity(ActivityInput(id="run", name="Run", goal=5.0,
                                      remindAt="07:00", remindRepeat="daily",
                                      remindChannel=channel))
    ov = trc.overview()
    views = [v for v in ov.activities if v.id == "run"]
    assert len(views) == 1
    assert views[0].remindChannel == channel, (
        f"GET /tracing read-back must surface the stored channel {channel!r}, "
        f"got {views[0].remindChannel!r} (the #117 view-serializer drop)"
    )


def test_117_get_activity_readback_surfaces_channel(db):
    """The single-activity read path (get_activity → Activity) already surfaced the channel;
    pin it alongside the view fix so both read surfaces agree (discord ≠ the in_app default)."""
    trc.create_activity(ActivityInput(id="run", name="Run", goal=5.0,
                                      remindAt="07:00", remindRepeat="daily",
                                      remindChannel="discord"))
    act = trc.get_activity("run")
    assert act is not None and act.remindChannel == "discord"
