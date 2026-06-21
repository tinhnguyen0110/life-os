"""tests/test_reminders.py — Reminders module (REMINDERS-1, #27): storage core + REST.

Coverage:
  - CRUD: create → stored → get returns it; delete removes it.
  - tick: sets done_at; IDEMPOTENT re-tick = no-op (done_at unchanged), not an error.
  - filter boundaries (UTC, <= inclusive): today INCLUDES due-today-undone, EXCLUDES due-today-
    DONE (respects BOTH due AND done — the distinguishing) + EXCLUDES due-next-week; week; undone.
  - unknown filter → lenient all.
  - fail-open: a malformed row → skipped + warned, never crashes the list.
  - REST: 201 create / 200 list+get / 200 idempotent tick / 200 delete / 404 absent / 422 bad input.
  - module auto-discovered (/health modules has "reminders") — NOT a core/main.py edit.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from modules.reminders import service, store
from modules.reminders.schema import ReminderInput


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def rem_db(isolated_paths):
    store.init_reminders_tables()
    return isolated_paths


# --------------------------------------------------------------------------- #
# CRUD + tick (service/store layer)                                            #
# --------------------------------------------------------------------------- #
def test_create_get_roundtrip(rem_db):
    r = service.create(ReminderInput(title="Pay rent", due_at=_now().isoformat()))
    assert r.id >= 1 and r.title == "Pay rent" and r.done_at is None and r.created
    got = service.get(r.id)
    assert got is not None and got.id == r.id and got.title == "Pay rent"


def test_create_strips_title_and_note(rem_db):
    r = service.create(ReminderInput(title="  spaced  ", note="  detail  ",
                                     due_at=_now().isoformat()))
    assert r.title == "spaced" and r.note == "detail"


def test_get_absent_is_none(rem_db):
    assert service.get(99999) is None


def test_tick_sets_done_at(rem_db):
    r = service.create(ReminderInput(title="t", due_at=_now().isoformat()))
    ticked = service.tick(r.id)
    assert ticked is not None and ticked.done_at is not None


def test_tick_is_idempotent_no_op(rem_db):
    """Re-ticking a done reminder keeps the FIRST done_at (no-op), returns the reminder, NOT
    an error."""
    r = service.create(ReminderInput(title="t", due_at=_now().isoformat()))
    first = service.tick(r.id).done_at
    second = service.tick(r.id)
    assert second is not None and second.done_at == first, "re-tick must not change done_at"


def test_tick_absent_is_none(rem_db):
    assert service.tick(99999) is None


def test_delete_existing_and_absent(rem_db):
    r = service.create(ReminderInput(title="t", due_at=_now().isoformat()))
    assert service.delete(r.id) is True
    assert service.get(r.id) is None
    assert service.delete(r.id) is False  # already gone → 404 at the router


# --------------------------------------------------------------------------- #
# Filter boundaries — the DISTINGUISHING (respects BOTH due AND done)           #
# --------------------------------------------------------------------------- #
def test_today_includes_undone_excludes_done_and_nextweek(rem_db):
    now = _now()
    a = service.create(ReminderInput(title="today-undone", due_at=now.isoformat()))
    b = service.create(ReminderInput(title="today-done", due_at=now.isoformat()))
    service.tick(b.id)
    c = service.create(ReminderInput(title="next-week", due_at=(now + timedelta(days=8)).isoformat()))
    today, _ = service.list_reminders("today")
    ids = {r.id for r in today.reminders}
    assert a.id in ids, "today must INCLUDE a due-today-undone"
    assert b.id not in ids, "today must EXCLUDE a due-today-DONE (respects done, not just due)"
    assert c.id not in ids, "today must EXCLUDE a due-next-week"
    # counts: all in 'today' are undone by construction
    assert today.count == today.undoneCount


# --------------------------------------------------------------------------- #
# REMINDERS-1A — UTC-normalize due_at: the non-UTC-offset / naive filter bug    #
# (the aligned-fixture trap — all #27 tests used UTC/Z so it never fired). The  #
# store's lexicographic compare is only correct once due_at is stored UTC.      #
# --------------------------------------------------------------------------- #
def test_1A_offset_due_at_today_in_utc_included(rem_db):
    """THE REPRO: a +07:00-offset due_at that IS today-in-UTC (now, expressed in +07) must be in
    filter=today. Stored RAW it sorted as tomorrow (lexicographic) → wrongly EXCLUDED; UTC-
    normalized at the validator → correctly INCLUDED."""
    now = _now()
    plus7 = now.astimezone(timezone(timedelta(hours=7)))
    r = service.create(ReminderInput(title="offset-today", due_at=plus7.isoformat()))
    # stored due_at is UTC-normalized (ends in +00:00, not the +07:00 input)
    assert r.due_at.endswith("+00:00"), f"due_at must be UTC-normalized, got {r.due_at}"
    today, _ = service.list_reminders("today")
    assert r.id in {x.id for x in today.reminders}, "offset-today (UTC) must be IN today"


def test_1A_offset_due_at_not_today_in_utc_excluded(rem_db):
    """An offset due_at that is NOT today-in-UTC (8 days out, in +07) → EXCLUDED from today (the
    other direction — normalize doesn't over-include)."""
    now = _now()
    far = (now + timedelta(days=8)).astimezone(timezone(timedelta(hours=7)))
    r = service.create(ReminderInput(title="offset-far", due_at=far.isoformat()))
    today, _ = service.list_reminders("today")
    assert r.id not in {x.id for x in today.reminders}, "offset-far must be EXCLUDED from today"


def test_1A_naive_due_at_assumed_utc(rem_db):
    """A NAIVE due_at (no tz, e.g. '2026-06-21T02:00:00') → ASSUMED UTC (decide-and-log: single-
    user simplest rule), normalized to +00:00, filters correctly. NOT system-local-converted
    (which would be ambiguous)."""
    now = _now()
    naive = now.replace(tzinfo=None).isoformat()  # strip tz → naive
    r = service.create(ReminderInput(title="naive", due_at=naive))
    assert r.due_at.endswith("+00:00"), "naive due_at → assumed UTC (+00:00)"
    today, _ = service.list_reminders("today")
    assert r.id in {x.id for x in today.reminders}, "naive-today (assumed UTC) must be IN today"


def test_1A_utc_z_input_still_works_no_regression(rem_db):
    """A UTC/Z input (the #27 fixtures' shape) still normalizes + filters correctly — no
    regression from the 1A change."""
    now = _now()
    r = service.create(ReminderInput(title="utc-z", due_at=now.isoformat().replace("+00:00", "Z")))
    assert r.due_at.endswith("+00:00")
    today, _ = service.list_reminders("today")
    assert r.id in {x.id for x in today.reminders}


def test_week_includes_within_7d_excludes_beyond(rem_db):
    now = _now()
    inside = service.create(ReminderInput(title="in-6d", due_at=(now + timedelta(days=6)).isoformat()))
    outside = service.create(ReminderInput(title="in-8d", due_at=(now + timedelta(days=8)).isoformat()))
    week, _ = service.list_reminders("week")
    ids = {r.id for r in week.reminders}
    assert inside.id in ids and outside.id not in ids


def test_undone_excludes_ticked(rem_db):
    now = _now()
    a = service.create(ReminderInput(title="a", due_at=now.isoformat()))
    b = service.create(ReminderInput(title="b", due_at=now.isoformat()))
    service.tick(b.id)
    undone, _ = service.list_reminders("undone")
    ids = {r.id for r in undone.reminders}
    assert a.id in ids and b.id not in ids


def test_all_returns_everything_unknown_filter_lenient(rem_db):
    now = _now()
    a = service.create(ReminderInput(title="a", due_at=now.isoformat()))
    b = service.create(ReminderInput(title="b", due_at=now.isoformat()))
    service.tick(b.id)
    allv, _ = service.list_reminders("all")
    assert allv.count == 2 and allv.filter == "all"
    # unknown filter → lenient all (not an error, not empty)
    unk, _ = service.list_reminders("zzz-not-a-filter")
    assert unk.count == 2 and unk.filter == "all"


def test_empty_list_is_honest_empty(rem_db):
    view, warnings = service.list_reminders("all")
    assert view.reminders == [] and view.count == 0 and view.undoneCount == 0


def test_list_newest_due_first(rem_db):
    now = _now()
    older = service.create(ReminderInput(title="older", due_at=(now - timedelta(days=2)).isoformat()))
    newer = service.create(ReminderInput(title="newer", due_at=now.isoformat()))
    allv, _ = service.list_reminders("all")
    assert [r.id for r in allv.reminders] == [newer.id, older.id]  # newest-due first


# --------------------------------------------------------------------------- #
# fail-open — a malformed row is skipped + warned, never crashes the list       #
# --------------------------------------------------------------------------- #
def test_malformed_row_skipped_warned(rem_db):
    """A row with a non-null-violating but model-invalid value (e.g. a blank title that bypassed
    the input validator via a direct DB write) is skipped + a warning recorded — the list never
    crashes. We inject a bad row directly into the table."""
    good = service.create(ReminderInput(title="good", due_at=_now().isoformat()))
    conn = store.db.get_conn()
    # a title of "" violates the Reminder model's min_length=1 → row_to_reminder raises → skipped
    conn.execute(
        "INSERT INTO reminders(title, note, due_at, repeat, notified_count, created) "
        "VALUES ('', NULL, ?, 'once', 0, ?)",
        (_now().isoformat(), _now().isoformat()),
    )
    conn.commit()
    view, warnings = service.list_reminders("all")
    ids = {r.id for r in view.reminders}
    assert good.id in ids, "the good row survives"
    assert len(warnings) == 1 and "skipped malformed" in warnings[0], "the bad row is skipped + warned"


# --------------------------------------------------------------------------- #
# Input validation — bad input never stores a row (422 at the router)           #
# --------------------------------------------------------------------------- #
def test_blank_title_rejected(rem_db):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ReminderInput(title="   ", due_at=_now().isoformat())


def test_bad_due_at_rejected(rem_db):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ReminderInput(title="t", due_at="not-a-date")


# =========================================================================== #
# REST + auto-discovery (real app via TestClient)                              #
# =========================================================================== #
@pytest.fixture
def app_client(tmp_path, monkeypatch):
    from core.config import settings
    from store import db

    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "db_path", tmp_path / "store" / "test.db")
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    monkeypatch.setattr(db, "DB_PATH", None)
    db.close_db()
    import main as main_mod
    app = main_mod.create_app()
    with TestClient(app) as c:
        yield c
    db.close_db()


def test_reminders_module_auto_discovered(app_client):
    """The module is registry-discovered (NOT a core/main.py edit) — /health lists it."""
    assert "reminders" in app_client.get("/health").json()["data"]["modules"]


def test_health_no_skipped_modules(app_client):
    assert not app_client.get("/health").json().get("warning")


def test_rest_create_201_and_roundtrip(app_client):
    r = app_client.post("/reminders", json={"title": "Call dentist",
                                            "due_at": _now().isoformat()})
    assert r.status_code == 201 and r.json()["success"] is True
    rid = r.json()["data"]["id"]
    got = app_client.get(f"/reminders/{rid}")
    assert got.status_code == 200 and got.json()["data"]["title"] == "Call dentist"


def test_rest_list_envelope_and_counts(app_client):
    app_client.post("/reminders", json={"title": "a", "due_at": _now().isoformat()})
    body = app_client.get("/reminders?filter=all").json()
    assert body["success"] is True
    d = body["data"]
    assert set(d) >= {"reminders", "count", "undoneCount", "filter"}
    assert d["count"] == 1 and d["filter"] == "all"


def test_rest_tick_idempotent(app_client):
    rid = app_client.post("/reminders", json={"title": "t", "due_at": _now().isoformat()}).json()["data"]["id"]
    t1 = app_client.put(f"/reminders/{rid}/tick")
    assert t1.status_code == 200 and t1.json()["data"]["done_at"] is not None
    first = t1.json()["data"]["done_at"]
    t2 = app_client.put(f"/reminders/{rid}/tick")  # idempotent
    assert t2.status_code == 200 and t2.json()["data"]["done_at"] == first


def test_rest_delete_and_404s(app_client):
    rid = app_client.post("/reminders", json={"title": "t", "due_at": _now().isoformat()}).json()["data"]["id"]
    assert app_client.delete(f"/reminders/{rid}").status_code == 200
    # gone now → 404 on get/tick/delete — #46-P5: flat agent_error NOT_FOUND, not {detail}
    for resp in (app_client.get(f"/reminders/{rid}"),
                 app_client.put(f"/reminders/{rid}/tick"),
                 app_client.delete(f"/reminders/{rid}")):
        assert resp.status_code == 404
        j = resp.json()
        assert "detail" not in j and j["error"]["code"] == "NOT_FOUND" and j["error"]["hint"]


def test_rest_blank_title_422_no_row(app_client):
    r = app_client.post("/reminders", json={"title": "   ", "due_at": _now().isoformat()})
    assert r.status_code == 422
    assert app_client.get("/reminders?filter=all").json()["data"]["count"] == 0  # no row stored


def test_rest_bad_due_at_422_no_row(app_client):
    r = app_client.post("/reminders", json={"title": "t", "due_at": "nope"})
    assert r.status_code == 422
    assert app_client.get("/reminders?filter=all").json()["data"]["count"] == 0


def test_rest_today_filter_boundary(app_client):
    now = _now()
    app_client.post("/reminders", json={"title": "today", "due_at": now.isoformat()})
    nw = app_client.post("/reminders", json={"title": "nextweek",
                                             "due_at": (now + timedelta(days=8)).isoformat()})
    nw_id = nw.json()["data"]["id"]
    today = app_client.get("/reminders?filter=today").json()["data"]
    ids = {r["id"] for r in today["reminders"]}
    assert nw_id not in ids, "today must exclude a due-next-week reminder"
    assert today["count"] >= 1
