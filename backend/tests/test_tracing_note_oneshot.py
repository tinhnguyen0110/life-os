"""tests/test_tracing_note_oneshot.py — TRACING-UX2 #125: note one-shot future-DATE remind.

Two remind KINDS now:
  - activity remind = daily-recurring (#75/#111, source='tracing') — UNCHANGED;
  - 🔴 note remind = a ONE-SHOT future date+time (#125, source='tracing-note', repeat='once').

Distinguishing cases (the dispatch pass-bar):
  - note with remindDate(future)+remindAt → a repeat='once' reminder at that future due_at;
  - 🔴 the reminder reads back repeat=='once' (the closed-set-coercion check — like #121's source);
  - 🔴 past remindDate → 422 + hint (no row stored);
  - note without remindDate but remindRepeat≠off → the #121 recurring path (repeat='daily') — kept;
  - clear (remindRepeat='off') → the one-shot reminder deleted;
  - delete note → the one-shot reminder gone (#121 lifecycle);
  - activity remind STILL daily (regression — unchanged); both kinds coexist.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from modules.reminders import service as rem
from modules.reminders import store as rem_store
from modules.tracing import service as trc
from modules.tracing import store as trc_store
from modules.tracing.schema import VN_TZ, ActivityInput, NoteInput, NoteUpdate


@pytest.fixture
def db(isolated_paths):
    trc_store.init_tracing_tables()
    rem_store.init_reminders_tables()
    return isolated_paths


@pytest.fixture
def api(db):
    from main import create_app
    return TestClient(create_app())


def _future_date(days: int = 7) -> str:
    return (datetime.now(VN_TZ).date() + timedelta(days=days)).strftime("%Y-%m-%d")


def _past_date(days: int = 7) -> str:
    return (datetime.now(VN_TZ).date() - timedelta(days=days)).strftime("%Y-%m-%d")


def _note_reminders():
    view, _ = rem.list_reminders("all")
    return [r for r in view.reminders if r.source == "tracing-note"]


# --- one-shot future-date → repeat='once' reminder -------------------------- #
def test_note_oneshot_emits_repeat_once(db):
    fut = _future_date(7)
    n = trc.create_note(NoteInput(text="dentist", remindAt="09:00", remindDate=fut,
                                  remindChannel="discord"))
    assert n.remindDate == fut
    rems = _note_reminders()
    assert len(rems) == 1
    r = rems[0]
    assert r.source == "tracing-note" and r.activity_id == n.id
    assert r.repeat == "once", "a one-shot note remind must be repeat='once' (not daily)"
    assert r.channel == "discord"
    # due_at is the FUTURE remindDate@remindAt (UTC), NOT today
    assert r.due_at.startswith(fut) or fut in r.due_at or r.due_at > datetime.now(VN_TZ).isoformat()


def test_note_oneshot_repeat_reads_back_once(db):
    """🔴 the closed-set-coercion check (the #121 source lesson): repeat='once' survives the
    reminders read-back path (row_to_reminder), not silently coerced to daily/manual-default."""
    n = trc.create_note(NoteInput(text="x", remindAt="08:00", remindDate=_future_date(3)))
    # read it back through the full reminders read path
    view, _ = rem.list_reminders("all")
    mine = [r for r in view.reminders if r.activity_id == n.id]
    assert len(mine) == 1 and mine[0].repeat == "once", "repeat must read back 'once', not coerced"


# --- 🔴 past-date → 422 (router), no row stored ----------------------------- #
def test_rest_past_oneshot_is_422(api):
    r = api.post("/tracing/notes", json={"text": "late", "remindAt": "09:00",
                                         "remindDate": _past_date(5)})
    assert r.status_code == 422, r.text
    err = r.json()["error"]
    assert err["code"] == "INVALID_INPUT" and "past" in err["message"].lower()
    assert "future" in err["hint"].lower()
    # no note stored
    assert api.get("/tracing/notes").json()["data"]["notes"] == []


def test_rest_future_oneshot_ok(api):
    fut = _future_date(10)
    r = api.post("/tracing/notes", json={"text": "ok", "remindAt": "09:00", "remindDate": fut})
    assert r.status_code == 201, r.text
    assert r.json()["data"]["remindDate"] == fut


def test_rest_update_to_past_is_422(api):
    # create a valid future one-shot, then PUT it to a past date → 422
    fut = _future_date(5)
    rid = api.post("/tracing/notes", json={"text": "n", "remindAt": "09:00",
                                           "remindDate": fut}).json()["data"]["id"]
    r = api.put(f"/tracing/notes/{rid}", json={"remindDate": _past_date(2)})
    assert r.status_code == 422 and "past" in r.json()["error"]["message"].lower()


# --- #121 recurring path KEPT (no remindDate) ------------------------------- #
def test_note_recurring_path_still_works(db):
    """A note with remindRepeat≠off and NO remindDate → the #121 today@remindAt recurring reminder
    (repeat='daily'), unchanged by #125."""
    n = trc.create_note(NoteInput(text="daily note", remindAt="07:00", remindRepeat="daily"))
    rems = _note_reminders()
    assert len(rems) == 1 and rems[0].repeat == "daily" and rems[0].activity_id == n.id


# --- clear / delete lifecycle (#121, now also clears a one-shot) ------------- #
def test_clear_oneshot_via_off_deletes_reminder(db):
    n = trc.create_note(NoteInput(text="x", remindAt="09:00", remindDate=_future_date(4)))
    assert len(_note_reminders()) == 1
    trc.update_note(n.id, NoteUpdate(remindRepeat="off"))  # universal clear
    assert _note_reminders() == [], "remindRepeat='off' must delete the one-shot reminder too"
    # and the note's remindDate was nulled
    assert trc.get_note(n.id).remindDate is None


def test_delete_note_removes_oneshot_reminder(db):
    n = trc.create_note(NoteInput(text="x", remindAt="09:00", remindDate=_future_date(6)))
    assert len(_note_reminders()) == 1
    assert trc.delete_note(n.id) is True
    assert _note_reminders() == [], "deleting the note must delete its one-shot reminder (no orphan)"


def test_update_oneshot_moves_due_no_dup(db):
    n = trc.create_note(NoteInput(text="x", remindAt="09:00", remindDate=_future_date(3)))
    first = _note_reminders()
    assert len(first) == 1
    trc.update_note(n.id, NoteUpdate(remindDate=_future_date(9)))
    after = _note_reminders()
    assert len(after) == 1 and after[0].id == first[0].id, "moving the date UPDATES, not duplicates"
    assert after[0].repeat == "once"


# --- both kinds coexist + activity-remind regression ------------------------ #
def test_activity_daily_and_note_oneshot_coexist(db):
    """An activity (daily, source='tracing') + a note one-shot (once, source='tracing-note') live in
    the same reminders list with correct sources + repeats. Activity remind UNCHANGED (#75/#111)."""
    trc.create_activity(ActivityInput(id="run", name="Run", goal=5.0,
                                      remindAt="06:00", remindRepeat="daily"))
    trc.create_note(NoteInput(text="appt", remindAt="14:00", remindDate=_future_date(2)))
    view, _ = rem.list_reminders("all")
    by = {(r.source, r.repeat) for r in view.reminders}
    assert ("tracing", "daily") in by, "activity remind still daily (regression)"
    assert ("tracing-note", "once") in by, "note remind is a one-shot"


# --- schema format validation (bad date → 422 before the past-check) -------- #
def test_rest_bad_date_format_is_422(api):
    r = api.post("/tracing/notes", json={"text": "t", "remindAt": "09:00", "remindDate": "2026-13-99"})
    assert r.status_code == 422  # the _validate_date schema validator
