"""tests/test_tracing_archive_legacy.py — TRACING-DEFAULT T1 (#173): archive the 7 legacy habits.

``service.archive_legacy_habits()`` soft-deletes (RECOVERABLE) exactly the 7 old habit activities so
/tracing defaults to the 3 check-ins. The guarantees:
  - 🔴 SCOPED: only the 7 legacy ids; the 3 check-ins (and any other id) are NEVER touched;
  - RECOVERABLE: archive = soft-delete (the row + logs survive; restore by un-archiving);
  - the linked reminder is removed (a retired habit shouldn't nag);
  - IDEMPOTENT: an absent/already-archived id is skipped → a re-run archives 0;
  - count before/after honest.
"""

from __future__ import annotations

import pytest

from modules.reminders import store as rem_store
from modules.tracing import service as svc
from modules.tracing import store as trc_store
from modules.tracing.schema import ActivityInput, LogInput

LEGACY = ["tap-the-duc", "doc-sach", "ngu", "thien", "di-bo", "hoc", "viet"]
CHECKINS = ["check-in-sang", "check-in-trua", "bao-cao-toi"]


@pytest.fixture
def db(isolated_paths):
    trc_store.init_tracing_tables()
    rem_store.init_reminders_tables()
    return isolated_paths


def _seed_full_board() -> None:
    """The 7 legacy habits + the 3 check-ins (the live shape: 10 active)."""
    for aid in LEGACY:
        svc.create_activity(ActivityInput(id=aid, name=aid.title(), goal=1.0))
    svc.seed_checkin_activities()


def test_archives_exactly_the_seven_keeps_checkins(db):
    _seed_full_board()
    assert len(trc_store.list_activities()) == 10  # active

    res = svc.archive_legacy_habits()
    assert res["archivedCount"] == 7
    assert set(res["archived"]) == set(LEGACY)
    assert res["activeBefore"] == 10 and res["activeAfter"] == 3

    active_ids = {r["id"] for r in trc_store.list_activities()}
    assert active_ids == set(CHECKINS), "only the 3 check-ins remain active"
    # the 7 are archived (not deleted — still in the DB)
    for aid in LEGACY:
        assert svc.get_activity(aid).archived is True


def test_recoverable_row_and_logs_survive(db):
    """archive = soft-delete: the row + its logs survive (restore by un-archiving)."""
    svc.create_activity(ActivityInput(id="viet", name="Viết", goal=1.0))
    svc.log_session("viet", LogInput(val=1.0))
    svc.archive_legacy_habits()
    # the row still exists (archived) + its log row survives
    assert svc.get_activity("viet").archived is True
    assert len(trc_store.logs_for_activity("viet")) == 1, "archive must NOT wipe logs (recoverable)"


def test_archive_removes_linked_reminder(db):
    """viet with a reminder → archive drops the linked reminder (a retired habit shouldn't nag)."""
    svc.create_activity(ActivityInput(id="viet", name="Viết", goal=1.0,
                                      remindAt="07:00", remindRepeat="daily"))
    assert rem_store.find_by_activity("viet", source="tracing") is not None
    svc.archive_legacy_habits()
    assert rem_store.find_by_activity("viet", source="tracing") is None, "reminder removed on archive"


def test_scoped_never_touches_checkins(db):
    """🔴 SCOPED: the 3 check-ins are NEVER archived, even on repeated runs."""
    _seed_full_board()
    svc.archive_legacy_habits()
    for aid in CHECKINS:
        assert svc.get_activity(aid).archived is False, f"{aid} must stay active"


def test_idempotent_rerun_archives_zero(db):
    _seed_full_board()
    first = svc.archive_legacy_habits()
    assert first["archivedCount"] == 7 and first["activeAfter"] == 3
    second = svc.archive_legacy_habits()
    assert second["archivedCount"] == 0, "re-run archives nothing (all already archived/absent)"
    assert set(second["skipped"]) == set(LEGACY)
    assert second["activeAfter"] == 3  # still 3


def test_absent_legacy_id_is_skipped_not_error(db):
    """Only the 3 check-ins exist (no legacy) → archive 0, no error."""
    svc.seed_checkin_activities()
    res = svc.archive_legacy_habits()
    assert res["archivedCount"] == 0 and set(res["skipped"]) == set(LEGACY)
    assert res["activeAfter"] == 3
