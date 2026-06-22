"""tests/test_tracing_notes.py — TRACING-UX2 T1 (#121): day-notes + note→reminder link.

A day-note = text + optional remind. The load-bearing distinguishing cases (the dispatch pass-bar):
  - note WITHOUT remind → created, NO reminder emitted;
  - note WITH remind → created + a linked reminder (source='tracing-note', right channel + due);
  - PUT note clearing the remind (remindRepeat='off') → the linked reminder DELETED (else-branch);
  - 🔴 delete note → the linked reminder is GONE (no orphan — query reminders by source after);
  - activity-remind STILL emits a reminder (regression — #75/#111 unchanged, the generalized source);
  - honest-empty: GET /tracing/notes with none → [];
  - SCOPED writes (a note write touches only that note's row).

EXERCISE the wire (behavior-test-not-field-read): set remind → assert a reminder APPEARS by source.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.reminders import service as rem
from modules.reminders import store as rem_store
from modules.tracing import service as trc
from modules.tracing import store as trc_store
from modules.tracing.schema import ActivityInput, NoteInput, NoteUpdate


@pytest.fixture
def db(isolated_paths):
    trc_store.init_tracing_tables()
    rem_store.init_reminders_tables()
    return isolated_paths


@pytest.fixture
def api(db):
    from main import create_app
    return TestClient(create_app())


def _note_reminders():
    """All source='tracing-note' reminders currently stored (the note-wire's output)."""
    view, _ = rem.list_reminders("all")
    return [r for r in view.reminders if r.source == "tracing-note"]


# --- note WITHOUT remind → no reminder -------------------------------------- #
def test_create_note_without_remind_no_reminder(db):
    n = trc.create_note(NoteInput(text="buy milk"))
    assert n.id and n.text == "buy milk" and n.remindRepeat == "off" and n.created
    assert _note_reminders() == []  # no remind → no linked reminder


# --- note WITH remind → a linked reminder APPEARS --------------------------- #
def test_create_note_with_remind_emits_reminder(db):
    n = trc.create_note(NoteInput(text="call bank", remindAt="09:00",
                                  remindRepeat="daily", remindChannel="discord"))
    rems = _note_reminders()
    assert len(rems) == 1
    r = rems[0]
    assert r.source == "tracing-note" and r.activity_id == n.id  # linked by the note id
    assert r.repeat == "daily" and r.channel == "discord"  # #111 channel carried
    assert "call bank" in r.title
    assert r.due_at.endswith("Z") or "+00:00" in r.due_at  # UTC-normalized due


def test_note_remind_repeat_off_no_reminder(db):
    """remindAt set but remindRepeat='off' → NO reminder (off wins, mirrors the activity rule)."""
    trc.create_note(NoteInput(text="x", remindAt="09:00", remindRepeat="off"))
    assert _note_reminders() == []


# --- PUT clearing the remind → the linked reminder is DELETED ---------------- #
def test_update_note_clear_remind_deletes_reminder(db):
    n = trc.create_note(NoteInput(text="t", remindAt="09:00", remindRepeat="daily"))
    assert len(_note_reminders()) == 1
    trc.update_note(n.id, NoteUpdate(remindRepeat="off"))  # the clear path
    assert _note_reminders() == [], "remindRepeat='off' must delete the linked reminder"


def test_update_note_changes_remind_same_reminder_no_dup(db):
    n = trc.create_note(NoteInput(text="t", remindAt="09:00", remindRepeat="daily"))
    first = _note_reminders()
    assert len(first) == 1
    first_id = first[0].id
    trc.update_note(n.id, NoteUpdate(remindAt="10:30"))
    after = _note_reminders()
    assert len(after) == 1 and after[0].id == first_id, "update must UPDATE, not duplicate"


def test_update_note_text_preserves_reminder(db):
    n = trc.create_note(NoteInput(text="old", remindAt="09:00", remindRepeat="daily"))
    trc.update_note(n.id, NoteUpdate(text="new text"))
    rems = _note_reminders()
    assert len(rems) == 1 and "new text" in rems[0].title  # title re-synced to the new text


# --- 🔴 delete note → the linked reminder is GONE (no orphan) ---------------- #
def test_delete_note_removes_linked_reminder(db):
    n = trc.create_note(NoteInput(text="t", remindAt="09:00", remindRepeat="daily"))
    assert len(_note_reminders()) == 1
    assert trc.delete_note(n.id) is True
    assert _note_reminders() == [], "deleting the note must delete its linked reminder (no orphan)"
    assert trc.get_note(n.id) is None  # the note row is gone too


def test_delete_note_without_reminder_no_crash(db):
    n = trc.create_note(NoteInput(text="no remind"))
    assert trc.delete_note(n.id) is True  # no-op on the reminder side, no crash


def test_delete_absent_note_is_false(db):
    assert trc.delete_note("99999") is False
    assert trc.delete_note("not-a-number") is False  # non-numeric id → False, no crash


# --- honest-empty + list ----------------------------------------------------- #
def test_list_notes_honest_empty(db):
    assert trc.list_notes() == []


def test_list_notes_newest_first(db):
    a = trc.create_note(NoteInput(text="first"))
    b = trc.create_note(NoteInput(text="second"))
    ids = [n.id for n in trc.list_notes()]
    assert ids == [b.id, a.id]  # newest-first


# --- regression: activity-remind STILL emits (the generalized source) -------- #
def test_activity_remind_still_emits_after_note_generalization(db):
    """#121 generalized upsert_for_activity's source — confirm the ACTIVITY path (source='tracing')
    still emits its reminder unchanged (#75/#111 no regression)."""
    trc.create_activity(ActivityInput(id="run", name="Run", goal=5.0,
                                      remindAt="07:00", remindRepeat="daily", remindChannel="email"))
    view, _ = rem.list_reminders("all")
    act_rems = [r for r in view.reminders if r.source == "tracing"]
    assert len(act_rems) == 1 and act_rems[0].activity_id == "run" and act_rems[0].channel == "email"
    # and the note + activity reminders COEXIST, each tagged its own source (no cross-contamination)
    trc.create_note(NoteInput(text="note too", remindAt="08:00", remindRepeat="daily"))
    view2, _ = rem.list_reminders("all")
    by_src = {r.source for r in view2.reminders}
    assert by_src == {"tracing", "tracing-note"}


# --- SCOPED write: a note update touches only that note ---------------------- #
def test_note_update_is_scoped_to_one_id(db):
    a = trc.create_note(NoteInput(text="a-keep"))
    b = trc.create_note(NoteInput(text="b-edit"))
    trc.update_note(b.id, NoteUpdate(text="b-edited"))
    assert trc.get_note(a.id).text == "a-keep"  # untouched
    assert trc.get_note(b.id).text == "b-edited"


# --- REST surface ------------------------------------------------------------ #
def test_rest_note_crud_roundtrip(api):
    # create
    r = api.post("/tracing/notes", json={"text": "rest note", "remindAt": "09:00",
                                         "remindRepeat": "daily", "remindChannel": "discord"})
    assert r.status_code == 201, r.text
    nid = r.json()["data"]["id"]
    assert r.json()["data"]["text"] == "rest note"
    # list
    lst = api.get("/tracing/notes").json()["data"]["notes"]
    assert any(n["id"] == nid for n in lst)
    # update (clear remind)
    u = api.put(f"/tracing/notes/{nid}", json={"remindRepeat": "off"})
    assert u.status_code == 200 and u.json()["data"]["remindRepeat"] == "off"
    # delete
    d = api.delete(f"/tracing/notes/{nid}")
    assert d.status_code == 200 and d.json()["data"]["deleted"] == nid
    # gone → 404 on re-delete
    assert api.delete(f"/tracing/notes/{nid}").status_code == 404


def test_rest_empty_text_is_422(api):
    r = api.post("/tracing/notes", json={"text": "   "})  # blank after strip
    assert r.status_code == 422


def test_rest_bad_hhmm_is_422(api):
    r = api.post("/tracing/notes", json={"text": "t", "remindAt": "25:99", "remindRepeat": "daily"})
    assert r.status_code == 422


def test_rest_update_absent_note_is_404(api):
    r = api.put("/tracing/notes/99999", json={"text": "x"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_rest_list_honest_empty(api):
    assert api.get("/tracing/notes").json()["data"]["notes"] == []
