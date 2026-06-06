"""tests/test_notes_backend.py — backend's own notes schema + service tests.

(Separate from tester's T4 scaffold `test_notes.py`.) CRUD behavior-tested:
create → read back markdown+front-matter, and CONFIRM the git commit landed
(Sprint-13 lesson). Filters + fail-open on malformed.
"""

from __future__ import annotations

import subprocess

import pytest

from modules.notes import service
from modules.notes.schema import Note, NoteInput


def _git_log(data_dir) -> list[str]:
    r = subprocess.run(["git", "-C", str(data_dir), "log", "--oneline"],
                       capture_output=True, text=True)
    return r.stdout.strip().splitlines()


# --- id / slug ---
def test_id_is_slug_plus_6hex():
    nid = service._new_id("My Cool Note!!")
    assert nid.startswith("my-cool-note-")
    suffix = nid.rsplit("-", 1)[1]
    assert len(suffix) == 6 and all(c in "0123456789abcdef" for c in suffix)


def test_id_fallback_for_punct_only_title():
    assert service._new_id("!!!").startswith("note-")


# --- create + git-commit-landed proof ---
def test_create_persists_and_commits(isolated_paths):
    note = service.create_note(NoteInput(title="First Note", body="hello world", tags=["a", "b"]))
    assert isinstance(note, Note)
    assert note.id.startswith("first-note-")
    assert note.createdAt == note.updatedAt

    from store import md_store
    raw = md_store.read(f"notes/{note.id}.md")
    assert raw is not None and raw.startswith("---")
    assert "title: First Note" in raw and "hello world" in raw

    log = _git_log(isolated_paths / "data")
    assert any(f"create note {note.id}" in line for line in log), f"commit not in log: {log}"


def test_create_read_back_roundtrip(isolated_paths):
    note = service.create_note(NoteInput(
        title="Trip", body="body text", tags=["x"], attach={"type": "project", "ref": "devcrew"}))
    got = service.get_note(note.id)
    assert got is not None
    assert got.title == "Trip" and got.body == "body text" and got.tags == ["x"]
    assert got.attach.type == "project" and got.attach.ref == "devcrew"


# --- update ---
def test_update_preserves_created_bumps_updated(isolated_paths):
    note = service.create_note(NoteInput(title="Editable", body="v1"))
    updated = service.update_note(note.id, NoteInput(title="Editable", body="v2"))
    assert updated is not None and updated.id == note.id
    assert updated.createdAt == note.createdAt and updated.body == "v2"
    assert service.get_note(note.id).body == "v2"


def test_update_absent_returns_none(isolated_paths):
    assert service.update_note("nope-000000", NoteInput(title="X")) is None


# --- delete ---
def test_delete_removes_and_commits(isolated_paths):
    note = service.create_note(NoteInput(title="Doomed", body="bye"))
    assert service.delete_note(note.id) is True
    assert service.get_note(note.id) is None
    log = _git_log(isolated_paths / "data")
    assert any(f"delete note {note.id}" in line for line in log), f"delete commit not in log: {log}"


def test_delete_absent_returns_false(isolated_paths):
    assert service.delete_note("ghost-000000") is False


# --- list + filters ---
def test_list_empty(isolated_paths):
    notes, warnings = service.list_notes()
    assert notes == [] and warnings == []


def test_list_sorted_newest_first(isolated_paths):
    service.create_note(NoteInput(title="A"))
    b = service.create_note(NoteInput(title="B"))
    service.update_note(b.id, NoteInput(title="B", body="touched"))
    notes, _ = service.list_notes()
    assert notes[0].id == b.id


def test_search_q_over_title_body_tags(isolated_paths):
    service.create_note(NoteInput(title="Alpha", body="the QUICK fox", tags=["zebra"]))
    service.create_note(NoteInput(title="Beta", body="nothing", tags=["other"]))
    assert {n.title for n in service.list_notes(q="quick")[0]} == {"Alpha"}   # body
    assert {n.title for n in service.list_notes(q="ALPHA")[0]} == {"Alpha"}   # title, ci
    assert {n.title for n in service.list_notes(q="zebra")[0]} == {"Alpha"}   # tag
    assert service.list_notes(q="nomatch")[0] == []


def test_filter_by_tag_exact(isolated_paths):
    service.create_note(NoteInput(title="T1", tags=["urgent", "work"]))
    service.create_note(NoteInput(title="T2", tags=["work"]))
    assert {n.title for n in service.list_notes(tag="urgent")[0]} == {"T1"}
    assert {n.title for n in service.list_notes(tag="work")[0]} == {"T1", "T2"}


def test_filter_by_attached(isolated_paths):
    service.create_note(NoteInput(title="P", attach={"type": "project", "ref": "devcrew"}))
    service.create_note(NoteInput(title="C", attach={"type": "channel", "ref": "crypto"}))
    service.create_note(NoteInput(title="N"))
    assert {n.title for n in service.list_notes(attached="project")[0]} == {"P"}
    assert {n.title for n in service.list_notes(attached="channel:crypto")[0]} == {"C"}
    assert service.list_notes(attached="project:nonexistent")[0] == []


# --- fail-open on malformed ---
def test_malformed_note_skipped_with_warning(isolated_paths):
    good = service.create_note(NoteInput(title="Good"))
    from store import md_store
    md_store.write_file("notes/broken.md", "not front-matter at all", "junk")
    md_store.write_file("notes/badyaml.md", "---\n: : : bad\n---\nbody", "bad yaml")
    notes, warnings = service.list_notes()
    ids = {n.id for n in notes}
    assert good.id in ids
    assert "broken" not in ids and "badyaml" not in ids
    assert len(warnings) >= 2


# --- validator ---
def test_attached_id_required_when_attached():
    with pytest.raises(Exception):
        NoteInput(title="X", attach={"type": "project"})
    assert NoteInput(title="X", attach={"type": "none"}).attach.ref is None
    assert NoteInput(title="X", attach={"type": "project", "ref": "devcrew"}).attach.ref == "devcrew"


def test_title_required():
    with pytest.raises(Exception):
        NoteInput(title="")


# --- pinned (sort + filter) ---
def test_pinned_sorts_first(isolated_paths):
    # create an unpinned then a pinned; pinned must top the list despite older updatedAt
    a = service.create_note(NoteInput(title="Unpinned"))
    p = service.create_note(NoteInput(title="Pinned", pinned=True))
    # touch the unpinned so it has the NEWEST updatedAt — pinned must STILL win
    service.update_note(a.id, NoteInput(title="Unpinned", body="touched"))
    notes, _ = service.list_notes()
    assert notes[0].id == p.id, "pinned note must sort first even if an unpinned one is newer"
    assert notes[0].pinned is True


def test_pinned_filter(isolated_paths):
    service.create_note(NoteInput(title="P1", pinned=True))
    service.create_note(NoteInput(title="N1", pinned=False))
    assert {n.title for n in service.list_notes(pinned=True)[0]} == {"P1"}
    assert {n.title for n in service.list_notes(pinned=False)[0]} == {"N1"}


def test_pin_toggle_via_update(isolated_paths):
    note = service.create_note(NoteInput(title="Toggle", pinned=False))
    assert note.pinned is False
    updated = service.update_note(note.id, NoteInput(title="Toggle", pinned=True))
    assert updated.pinned is True
    assert service.get_note(note.id).pinned is True
