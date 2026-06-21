"""tests/test_wiki_recent_activity.py — #96 recentActivity dedup + exclude soft-deleted.

#94 added soft-delete hide-points to tree/search/all_notes/count_by_status but MISSED
recentActivity (the #36 brief wiki-context consumer) — so soft-deleted/empty-title/dup notes
leaked into the user's daily_brief.wikiContext. #96 fixes recentActivity (one source → fixes the
brief AND the wiki overview): exclude deletedAt-set + empty-title, dedup by noteId (keep newest).

BEHAVIOR-TESTED: seed real ops (create/edit/soft-delete) → read recentActivity + the brief → assert
0 dup / 0 empty / 0 soft-deleted (not field-reads).
"""

from __future__ import annotations

import pytest

from modules.wiki import reader as wreader
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.schema import NoteCreateInput, NoteUpdateInput


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    return isolated_paths


# --------------------------------------------------------------------------- #
# dedup by noteId — multiple ops for one note → ONE entry (newest op)            #
# --------------------------------------------------------------------------- #
def test_recent_activity_dedups_by_note_id(wiki_db):
    """A note created + edited twice (3 op_log rows) → recentActivity shows it ONCE, newest op."""
    a = wsvc.create_note(NoteCreateInput(title="Note A", content="v1")).id
    wsvc.update_note(a, NoteUpdateInput(content="v2"))
    wsvc.update_note(a, NoteUpdateInput(content="v3"))
    ra = wreader.recent_activity(20)
    ids = [e["noteId"] for e in ra]
    assert ids.count(a) == 1, "a note with multiple ops must appear ONCE (dedup)"
    entry = next(e for e in ra if e["noteId"] == a)
    assert entry["op"] == "edit"  # the NEWEST op (last edit), not the create


# --------------------------------------------------------------------------- #
# exclude soft-deleted (the #94-missed consumer) + empty-title                   #
# --------------------------------------------------------------------------- #
def test_recent_activity_excludes_soft_deleted(wiki_db):
    """A soft-deleted note (deletedAt set) is EXCLUDED from recentActivity — matches tree/search
    (the #94 hide-points it was missing). Its op_log rows still exist (append-only); the fix checks
    the note's CURRENT cache status at read time."""
    live = wsvc.create_note(NoteCreateInput(title="Live", content="x")).id
    gone = wsvc.create_note(NoteCreateInput(title="Soon Deleted", content="y")).id
    wsvc.soft_delete_note(gone)
    ids = [e["noteId"] for e in wreader.recent_activity(20)]
    assert live in ids
    assert gone not in ids, "a soft-deleted note must NOT appear in recentActivity"


def test_recent_activity_excludes_empty_title(wiki_db):
    """A note with an empty title (junk capture) is skipped (nothing to show)."""
    titled = wsvc.create_note(NoteCreateInput(title="Has Title", content="x")).id
    blank = wsvc.create_note(NoteCreateInput(title="", content="raw capture, no title")).id
    ids = [e["noteId"] for e in wreader.recent_activity(20)]
    assert titled in ids and blank not in ids


def test_recent_activity_live_note_still_appears(wiki_db):
    """The exclude is NOT over-broad — a normal live note still appears (distinguishing)."""
    n = wsvc.create_note(NoteCreateInput(title="Normal Live Note", content="x")).id
    ra = wreader.recent_activity(20)
    assert any(e["noteId"] == n and e["noteTitle"] == "Normal Live Note" for e in ra)


def test_recent_activity_limit_returns_n_live_not_n_prefilter(wiki_db):
    """The limit returns N LIVE entries (over-scan → exclude → dedup → cap), NOT N pre-filter. Seed
    2 live + 3 soft-deleted → limit=2 returns the 2 LIVE (not 2 that include deleted)."""
    a = wsvc.create_note(NoteCreateInput(title="Live1", content="x")).id
    b = wsvc.create_note(NoteCreateInput(title="Live2", content="x")).id
    for i in range(3):
        d = wsvc.create_note(NoteCreateInput(title=f"Del{i}", content="x")).id
        wsvc.soft_delete_note(d)
    ra = wreader.recent_activity(2)
    ids = {e["noteId"] for e in ra}
    assert ids == {a, b}, f"limit=2 must return the 2 LIVE notes, got {ids}"


# --------------------------------------------------------------------------- #
# the durable teeth — the user's brief is CLEAN                                  #
# --------------------------------------------------------------------------- #
def test_daily_brief_wikicontext_recentnotes_clean(wiki_db, monkeypatch):
    """The end-to-end durable fix: a vault with a dup-op note + a soft-deleted note + an empty-title
    note → daily_brief.wikiContext.recentNotes has 0 dup-noteId + 0 empty-title + 0 soft-deleted."""
    from modules.brief import reader as brief_reader, service as brief_svc
    # the dup, the deleted, the empty, the good
    a = wsvc.create_note(NoteCreateInput(title="Dup", content="v1")).id
    wsvc.update_note(a, NoteUpdateInput(content="v2"))           # 2nd op for a → dup
    gone = wsvc.create_note(NoteCreateInput(title="Trash", content="x")).id
    wsvc.soft_delete_note(gone)                                  # soft-deleted
    wsvc.create_note(NoteCreateInput(title="", content="blank")) # empty-title junk
    good = wsvc.create_note(NoteCreateInput(title="Good", content="z")).id

    # isolate the brief to ONLY the wiki source (no network finance/market)
    def _wiki_only():
        s = brief_reader.Sources()
        s.wiki = {"recentOps": wreader.recent_activity(20),
                  "clusters": wreader.detect_clusters()}
        return s
    monkeypatch.setattr(brief_reader, "pull", _wiki_only)

    rn = brief_svc.generate_brief().wikiContext.recentNotes
    ids = [n.noteId for n in rn]
    assert len(ids) == len(set(ids)), f"NO dup noteId in the brief, got {ids}"
    assert all(n.title for n in rn), "NO empty-title in the brief"
    assert gone not in ids, "the soft-deleted note must NOT be in the brief"
    assert a in ids and good in ids                              # the live notes ARE there
    assert ids.count(a) == 1                                     # the dup collapsed to one


# --------------------------------------------------------------------------- #
# regression-pin — pytest isolation holds (a wiki import doesn't write the prod vault) #
# --------------------------------------------------------------------------- #
def test_pytest_isolation_holds_import_does_not_touch_prod(wiki_db):
    """#96 regression-pin: a wiki import in a test writes ONLY the isolated tmp vault — the count is
    self-contained (isolated_paths gives a fresh tmp data_dir). Pins that pytest stays isolated so a
    future test can't accidentally write the prod vault (the junk came from LIVE curls, not pytest)."""
    before = wiki_store.count_notes()
    assert before == 0, "isolated_paths starts with an EMPTY vault (proves per-test isolation)"
    wsvc.import_files([("t.md", "---\ntitle: Imported In Test\n---\nbody")])
    after = wiki_store.count_notes()
    assert after == before + 1, "the import wrote exactly its own note into the ISOLATED vault"
    # the note is the isolated one, not leaked from/to any prod store
    titles = {r["title"] for r in wiki_store.all_notes()}
    assert titles == {"Imported In Test"}
