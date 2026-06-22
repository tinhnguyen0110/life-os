"""tests/test_wiki_inbox_softdelete.py — B-T2: the inbox must EXCLUDE soft-deleted fleeting notes.

ROOT CAUSE (architect-traced): fleeting_notes() (the inbox query) was MISSING the `deleted_at IS
NULL` filter its sibling live queries (all_notes/count_notes/count_by_status) all have → the inbox
counted SOFT-DELETED fleeting notes (63) while byStatus.fleeting (count_by_status, live-only) = 34 —
irreconcilable to a user/agent. The fix: + `AND deleted_at IS NULL`.

BEHAVIOR-tested (not a field-read): create fleeting notes → soft-delete one → assert it's GONE from
the inbox AND inbox count == byStatus.fleeting (the two fleeting counts reconcile).
"""

from __future__ import annotations

import pytest

from modules.wiki import proposals_store as pstore
from modules.wiki import reader
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.schema import NoteCreateInput


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    pstore.init_proposal_tables()
    return isolated_paths


def _inbox_ids() -> set[int]:
    return {it["id"] for it in reader.inbox()["items"]}


def _by_status_fleeting() -> int:
    data, _ = reader.overview()
    return data["stats"]["byStatus"]["fleeting"]


def test_soft_deleted_fleeting_excluded_from_inbox(wiki_db):
    """🔴 the B-T2 bug: a soft-deleted fleeting note must NOT appear in the inbox."""
    keep = wsvc.create_note(NoteCreateInput(title="keep me fleeting"))  # status defaults fleeting
    gone = wsvc.create_note(NoteCreateInput(title="trash me"))
    assert {keep.id, gone.id} <= _inbox_ids()  # both in the inbox initially
    wsvc.soft_delete_note(gone.id)  # #94 tombstone
    ids = _inbox_ids()
    assert gone.id not in ids, "a soft-deleted fleeting note must be excluded from the inbox"
    assert keep.id in ids, "the live fleeting note stays"


def test_inbox_count_reconciles_with_byStatus(wiki_db):
    """🔴 the 63-vs-34 symptom: inbox length must == byStatus.fleeting (both = LIVE fleeting)."""
    a = wsvc.create_note(NoteCreateInput(title="a"))
    wsvc.create_note(NoteCreateInput(title="b"))
    wsvc.create_note(NoteCreateInput(title="c"))
    wsvc.soft_delete_note(a.id)  # one soft-deleted → must drop from BOTH counts identically
    data, _ = reader.overview()
    inbox_len = len(data["inbox"])
    fleeting = data["stats"]["byStatus"]["fleeting"]
    assert inbox_len == fleeting, f"inbox ({inbox_len}) must reconcile with byStatus.fleeting ({fleeting})"
    assert inbox_len == 2  # b + c (a was soft-deleted)


def test_fleeting_notes_store_query_excludes_soft_deleted(wiki_db):
    """The store query itself: fleeting_notes() returns only live fleeting (the 1-line fix)."""
    live = wsvc.create_note(NoteCreateInput(title="live"))
    dead = wsvc.create_note(NoteCreateInput(title="dead"))
    wsvc.soft_delete_note(dead.id)
    ids = {r["id"] for r in wiki_store.fleeting_notes()}
    assert live.id in ids and dead.id not in ids


def test_restore_returns_note_to_inbox(wiki_db):
    """Symmetry: restoring a soft-deleted fleeting note brings it BACK to the inbox (the filter is
    deleted_at, not a hard drop)."""
    n = wsvc.create_note(NoteCreateInput(title="x"))
    wsvc.soft_delete_note(n.id)
    assert n.id not in _inbox_ids()
    wsvc.restore_note(n.id)
    assert n.id in _inbox_ids(), "restore must return the note to the inbox"
    # and the counts reconcile again
    data, _ = reader.overview()
    assert len(data["inbox"]) == data["stats"]["byStatus"]["fleeting"]


def test_developing_note_not_in_inbox(wiki_db):
    """Control: a non-fleeting (developing) note is not in the inbox (status filter intact)."""
    from modules.wiki.schema import NoteUpdateInput
    n = wsvc.create_note(NoteCreateInput(title="promoted"))
    wsvc.update_note(n.id, NoteUpdateInput(status="developing"))
    assert n.id not in _inbox_ids()  # status != fleeting
