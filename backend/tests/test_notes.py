"""tests/test_notes.py — Sprint 6 T4: Notes module verification (tester scaffold).

Sections:
  A. Service unit tests — CRUD behavior-tests + git-commit-landed (Sprint-13 lesson)
  B. Filter tests — search (q=), tag filter, attached filter
  C. Edge cases — empty store, malformed front-matter skip, attachment validation
  D. API endpoint tests — all 5 endpoints via TestClient (skip-guarded until T2)

Frozen service API (verified against modules/notes/service.py):
  create_note(NoteInput) -> Note
  get_note(id) -> Note | None         # None if absent (router raises 404)
  update_note(id, NoteInput) -> Note | None  # None if absent
  delete_note(id) -> bool             # True if deleted, False if absent
  list_notes(q?, tag?, attached?) -> tuple[list[Note], list[str]]  # (notes, warnings)

Frozen schema (modules/notes/schema.py):
  Note {id, title, body, tags, attachedType, attachedId, createdAt, updatedAt}
  NoteInput {title (min_length=1), body="", tags=[], attachedType="none", attachedId=None}
  attachedType != "none" → attachedId required (model_validator)

Storage: notes/<id>.md — YAML front-matter + body. Every write = 1 md_store git commit.
"""

from __future__ import annotations

import importlib as _importlib
import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import guard — A/B/C skip until T1 (service) lands.
# ---------------------------------------------------------------------------

pytest.importorskip(
    "modules.notes.service",
    reason="modules/notes/service not yet implemented — pre-scaffold",
)

from modules.notes.schema import Attach, Note, NoteInput  # noqa: E402
from modules.notes import service  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _git_commit_count(repo: Path) -> int:
    res = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "--count", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    return 0 if res.returncode != 0 else int(res.stdout.strip())


def _git_log_messages(repo: Path, n: int = 5) -> list[str]:
    res = subprocess.run(
        ["git", "-C", str(repo), "log", f"-{n}", "--pretty=%s"],
        capture_output=True, text=True, check=False,
    )
    return res.stdout.strip().splitlines() if res.returncode == 0 else []


def _list(*, q=None, tag=None, attached=None) -> list[Note]:
    """Unwrap list_notes() tuple → just the notes list."""
    notes, _ = service.list_notes(q=q, tag=tag, attached=attached)
    return notes


# ---------------------------------------------------------------------------
# A. Service CRUD — behavior tests (create → read-back, update, delete)
# ---------------------------------------------------------------------------

class TestNotesCreate:
    def test_create_returns_note_with_id_and_timestamps(self, isolated_paths):
        note = service.create_note(NoteInput(title="Hello", body="World"))
        assert isinstance(note, Note)
        assert note.id, "id must be non-empty"
        assert note.title == "Hello"
        assert note.body == "World"
        assert note.createdAt
        assert note.updatedAt

    def test_create_id_derived_from_title(self, isolated_paths):
        note = service.create_note(NoteInput(title="My Great Note", body=""))
        # id should be slug-based — starts with slug of title
        assert note.id.startswith("my-great-note-"), f"Expected slug-based id, got {note.id!r}"

    def test_create_empty_title_rejected(self, isolated_paths):
        """title min_length=1 → NoteInput(title='') must raise validation error."""
        with pytest.raises(Exception):
            NoteInput(title="", body="some body")

    def test_create_note_with_tags(self, isolated_paths):
        note = service.create_note(NoteInput(title="Tagged", body="body", tags=["work", "idea"]))
        assert "work" in note.tags
        assert "idea" in note.tags

    def test_create_note_attached_to_project(self, isolated_paths):
        note = service.create_note(NoteInput(
            title="Proj note", body="body",
            attach=Attach(type="project", ref="life-os"),
        ))
        assert note.attach.type == "project"
        assert note.attach.ref == "life-os"

    def test_create_note_attached_to_channel(self, isolated_paths):
        note = service.create_note(NoteInput(
            title="Chan note", body="body",
            attach=Attach(type="channel", ref="crypto"),
        ))
        assert note.attach.type == "channel"
        assert note.attach.ref == "crypto"

    def test_create_note_standalone_default(self, isolated_paths):
        note = service.create_note(NoteInput(title="Standalone", body=""))
        assert note.attach.type == "none"
        assert note.attach.ref is None


class TestNotesGitCommit:
    """Sprint-13 lesson: verify the git commit LANDED — not just the return value."""

    def test_create_produces_exactly_one_git_commit(self, isolated_paths):
        from core.config import settings
        repo = settings.data_dir
        service.create_note(NoteInput(title="Commit test", body="body"))
        assert _git_commit_count(repo) == 1, "create_note must produce exactly 1 git commit"

    def test_create_sha_is_40_chars(self, isolated_paths):
        from core.config import settings
        service.create_note(NoteInput(title="Sha test", body=""))
        res = subprocess.run(
            ["git", "-C", str(settings.data_dir), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=False,
        )
        assert res.returncode == 0, "git repo must exist after create"
        assert len(res.stdout.strip()) == 40

    def test_each_write_produces_one_commit(self, isolated_paths):
        """create + update = 2 commits (not 1, not 3)."""
        from core.config import settings
        repo = settings.data_dir
        note = service.create_note(NoteInput(title="Multi", body="v1"))
        assert _git_commit_count(repo) == 1
        service.update_note(note.id, NoteInput(title="Multi", body="v2"))
        assert _git_commit_count(repo) == 2, "update_note must add exactly 1 more commit"

    def test_delete_produces_commit(self, isolated_paths):
        from core.config import settings
        repo = settings.data_dir
        note = service.create_note(NoteInput(title="Delete me", body=""))
        service.delete_note(note.id)
        assert _git_commit_count(repo) == 2, "delete_note must produce a git commit"

    def test_commit_message_references_note_id(self, isolated_paths):
        from core.config import settings
        note = service.create_note(NoteInput(title="Msg check", body=""))
        msgs = _git_log_messages(settings.data_dir, 1)
        assert msgs, "No git commit messages found"
        assert note.id in msgs[0], (
            f"Commit message should contain note id {note.id!r}, got: {msgs[0]!r}"
        )


class TestNotesReadBack:
    """Verify create→read-back round-trip: markdown file + front-matter on disk."""

    def test_get_note_returns_created_note(self, isolated_paths):
        note = service.create_note(NoteInput(title="Read back", body="The body"))
        fetched = service.get_note(note.id)
        assert fetched is not None, "get_note must return the note after create"
        assert fetched.id == note.id
        assert fetched.title == "Read back"
        assert fetched.body == "The body"

    def test_note_file_exists_on_disk(self, isolated_paths):
        from core.config import settings
        note = service.create_note(NoteInput(title="Disk check", body="content"))
        note_file = settings.data_dir / "notes" / f"{note.id}.md"
        assert note_file.exists(), f"Note file must exist at {note_file}"

    def test_note_file_has_front_matter(self, isolated_paths):
        from core.config import settings
        note = service.create_note(NoteInput(title="Front matter", body="body text"))
        note_file = settings.data_dir / "notes" / f"{note.id}.md"
        content = note_file.read_text()
        assert content.startswith("---"), "Note file must start with YAML front-matter"
        assert "title" in content
        assert note.id in content

    def test_note_file_contains_body(self, isolated_paths):
        from core.config import settings
        note = service.create_note(NoteInput(title="Body check", body="**bold body**"))
        note_file = settings.data_dir / "notes" / f"{note.id}.md"
        content = note_file.read_text()
        assert "**bold body**" in content, "Note file must contain the raw markdown body"

    def test_list_notes_returns_created_note(self, isolated_paths):
        service.create_note(NoteInput(title="Listed", body=""))
        notes = _list()
        assert len(notes) == 1
        assert notes[0].title == "Listed"

    def test_list_notes_returns_all_created(self, isolated_paths):
        service.create_note(NoteInput(title="Note A", body=""))
        service.create_note(NoteInput(title="Note B", body=""))
        service.create_note(NoteInput(title="Note C", body=""))
        notes = _list()
        assert len(notes) == 3
        titles = {n.title for n in notes}
        assert {"Note A", "Note B", "Note C"} == titles


class TestNotesUpdate:
    def test_update_changes_title_and_body(self, isolated_paths):
        note = service.create_note(NoteInput(title="Old title", body="old body"))
        updated = service.update_note(note.id, NoteInput(title="New title", body="new body"))
        assert updated is not None
        assert updated.title == "New title"
        assert updated.body == "new body"

    def test_update_preserves_created_at(self, isolated_paths):
        note = service.create_note(NoteInput(title="Preserve ts", body=""))
        updated = service.update_note(note.id, NoteInput(title="Preserve ts", body="changed"))
        assert updated is not None
        assert updated.createdAt == note.createdAt, "createdAt must not change on update"

    def test_update_bumps_updated_at(self, isolated_paths):
        import time
        note = service.create_note(NoteInput(title="Bump ts", body=""))
        time.sleep(0.01)  # ensure clock advances
        updated = service.update_note(note.id, NoteInput(title="Bump ts", body="changed"))
        assert updated is not None
        assert updated.updatedAt >= note.updatedAt, "updatedAt must be ≥ createdAt after update"

    def test_update_unknown_id_returns_none(self, isolated_paths):
        """Service returns None for absent id — router translates to 404."""
        result = service.update_note("does-not-exist", NoteInput(title="x", body=""))
        assert result is None

    def test_update_reflected_in_list(self, isolated_paths):
        note = service.create_note(NoteInput(title="Before", body=""))
        service.update_note(note.id, NoteInput(title="After", body=""))
        notes = _list()
        assert any(n.title == "After" for n in notes)
        assert not any(n.title == "Before" for n in notes)


class TestNotesDelete:
    def test_delete_returns_true_for_existing(self, isolated_paths):
        note = service.create_note(NoteInput(title="Bye", body=""))
        result = service.delete_note(note.id)
        assert result is True

    def test_delete_removes_note_from_list(self, isolated_paths):
        note = service.create_note(NoteInput(title="Gone", body=""))
        service.delete_note(note.id)
        assert _list() == []

    def test_delete_removes_file_from_disk(self, isolated_paths):
        from core.config import settings
        note = service.create_note(NoteInput(title="File gone", body=""))
        note_file = settings.data_dir / "notes" / f"{note.id}.md"
        assert note_file.exists()
        service.delete_note(note.id)
        assert not note_file.exists(), "Note file must be removed after delete"

    def test_delete_absent_returns_false(self, isolated_paths):
        """Service returns False for absent id — router translates to 404."""
        result = service.delete_note("does-not-exist")
        assert result is False

    def test_get_note_returns_none_after_delete(self, isolated_paths):
        note = service.create_note(NoteInput(title="Ephemeral", body=""))
        service.delete_note(note.id)
        assert service.get_note(note.id) is None

    def test_delete_then_create_new_note_still_works(self, isolated_paths):
        note = service.create_note(NoteInput(title="Temp", body=""))
        service.delete_note(note.id)
        new_note = service.create_note(NoteInput(title="Fresh", body=""))
        assert new_note.title == "Fresh"
        notes = _list()
        assert len(notes) == 1
        assert notes[0].title == "Fresh"


# ---------------------------------------------------------------------------
# B. Filter tests
# ---------------------------------------------------------------------------

class TestNotesSearch:
    def test_search_by_title_substring(self, isolated_paths):
        service.create_note(NoteInput(title="FastAPI tricks", body=""))
        service.create_note(NoteInput(title="React patterns", body=""))
        results = _list(q="fastapi")
        assert len(results) == 1
        assert results[0].title == "FastAPI tricks"

    def test_search_case_insensitive(self, isolated_paths):
        service.create_note(NoteInput(title="Python Tips", body=""))
        results = _list(q="PYTHON")
        assert len(results) == 1

    def test_search_by_body_substring(self, isolated_paths):
        service.create_note(NoteInput(title="Note", body="The secret phrase here"))
        service.create_note(NoteInput(title="Other", body="nothing special"))
        results = _list(q="secret phrase")
        assert len(results) == 1
        assert results[0].title == "Note"

    def test_search_by_tag_content(self, isolated_paths):
        service.create_note(NoteInput(title="Tagged", body="", tags=["retrospective"]))
        service.create_note(NoteInput(title="Other", body="", tags=["planning"]))
        results = _list(q="retrospective")
        assert len(results) == 1

    def test_search_no_match_returns_empty(self, isolated_paths):
        service.create_note(NoteInput(title="Something", body=""))
        results = _list(q="zzznomatch")
        assert results == []

    def test_search_empty_q_returns_all(self, isolated_paths):
        service.create_note(NoteInput(title="A", body=""))
        service.create_note(NoteInput(title="B", body=""))
        results = _list(q="")
        assert len(results) == 2

    def test_search_empty_store_returns_empty(self, isolated_paths):
        results = _list(q="anything")
        assert results == []


class TestNotesTagFilter:
    def test_filter_by_exact_tag(self, isolated_paths):
        service.create_note(NoteInput(title="Work note", body="", tags=["work"]))
        service.create_note(NoteInput(title="Personal note", body="", tags=["personal"]))
        results = _list(tag="work")
        assert len(results) == 1
        assert results[0].title == "Work note"

    def test_filter_tag_no_match_returns_empty(self, isolated_paths):
        service.create_note(NoteInput(title="Note", body="", tags=["work"]))
        results = _list(tag="nonexistent")
        assert results == []

    def test_filter_tag_is_exact_not_substring(self, isolated_paths):
        """tag='wor' must NOT match tag='work' — exact match."""
        service.create_note(NoteInput(title="Work note", body="", tags=["work"]))
        results = _list(tag="wor")
        assert results == [], "tag filter must be exact, not substring"

    def test_note_with_multiple_tags_matches_any(self, isolated_paths):
        service.create_note(NoteInput(title="Multi", body="", tags=["work", "idea"]))
        results = _list(tag="idea")
        assert len(results) == 1


class TestNotesAttachedFilter:
    def test_filter_by_attached_type(self, isolated_paths):
        service.create_note(NoteInput(title="Proj note", body="", attach=Attach(type="project", ref="life-os")))
        service.create_note(NoteInput(title="Chan note", body="", attach=Attach(type="channel", ref="crypto")))
        service.create_note(NoteInput(title="Standalone", body=""))
        results = _list(attached="project")
        assert len(results) == 1
        assert results[0].title == "Proj note"

    def test_filter_by_attached_ref(self, isolated_paths):
        service.create_note(NoteInput(title="life-os note", body="", attach=Attach(type="project", ref="life-os")))
        service.create_note(NoteInput(title="other note", body="", attach=Attach(type="project", ref="outboundos")))
        results = _list(attached="project:life-os")
        assert len(results) == 1
        assert results[0].title == "life-os note"

    def test_filter_standalone_only(self, isolated_paths):
        service.create_note(NoteInput(title="Attached", body="", attach=Attach(type="project", ref="p1")))
        service.create_note(NoteInput(title="Standalone", body=""))
        results = _list(attached="none")
        assert len(results) == 1
        assert results[0].title == "Standalone"


# ---------------------------------------------------------------------------
# C. Edge cases + defensive
# ---------------------------------------------------------------------------

class TestNotesEdgeCases:
    def test_empty_notes_dir_returns_empty_list(self, isolated_paths):
        """No notes created → list returns ([], []) without crashing."""
        notes, warnings = service.list_notes()
        assert notes == []

    def test_malformed_front_matter_file_skipped(self, isolated_paths):
        """A corrupted note file must NOT crash list_notes — fail-open (stale-store lesson)."""
        from core.config import settings
        notes_dir = settings.data_dir / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        (notes_dir / "bad-note.md").write_text("---\nthis: : : bad yaml: [\n---\nbody\n")
        # A valid note alongside a bad one
        service.create_note(NoteInput(title="Good note", body="good"))
        notes, warnings = service.list_notes()
        # Must not crash; good note still returned; bad note skipped with warning
        assert any(n.title == "Good note" for n in notes), "Good note must survive malformed neighbor"
        assert any("malformed" in w or "bad-note" in w for w in warnings), (
            f"Expected a skip-warning for bad-note.md, got: {warnings}"
        )

    def test_get_note_unknown_id_returns_none(self, isolated_paths):
        """get_note('bogus') → None (not a crash); router translates to 404."""
        result = service.get_note("does-not-exist")
        assert result is None

    def test_attach_type_not_none_requires_ref(self, isolated_paths):
        """attach.type='project' without attach.ref → pydantic validation error."""
        with pytest.raises(Exception):
            NoteInput(title="Missing ref", body="", attach=Attach(type="project", ref=None))

    def test_body_is_optional(self, isolated_paths):
        """Body can be empty string — only title is required."""
        note = service.create_note(NoteInput(title="No body", body=""))
        assert note.body == ""

    def test_tags_default_to_empty_list(self, isolated_paths):
        note = service.create_note(NoteInput(title="No tags"))
        assert note.tags == []

    def test_two_notes_with_similar_titles_get_unique_ids(self, isolated_paths):
        n1 = service.create_note(NoteInput(title="My Note", body="first"))
        n2 = service.create_note(NoteInput(title="My Note", body="second"))
        assert n1.id != n2.id, "Duplicate titles must still get unique ids"

    def test_list_warnings_returned_alongside_notes(self, isolated_paths):
        """list_notes() returns a 2-tuple (notes, warnings) — callers must unpack."""
        result = service.list_notes()
        assert isinstance(result, tuple) and len(result) == 2, (
            "list_notes must return (notes, warnings) tuple"
        )
        notes, warnings = result
        assert isinstance(notes, list)
        assert isinstance(warnings, list)


# ---------------------------------------------------------------------------
# D. API endpoint tests (skip-guarded until T2 router lands)
# ---------------------------------------------------------------------------

_router_available = _importlib.util.find_spec("modules.notes.router") is not None
_skip_router = pytest.mark.skipif(
    not _router_available,
    reason="modules/notes/router not yet implemented — skip D section",
)

try:
    import importlib as _importlib2  # noqa: E402
    import main as _main_mod  # noqa: E402
    from fastapi.testclient import TestClient  # noqa: E402
    from store import db as _db  # noqa: E402
    _app_importable = True
except ImportError:
    _app_importable = False


@pytest.fixture
def client(isolated_paths):
    if not _app_importable or not _router_available:
        pytest.skip("router/app not available")
    _importlib2.reload(_main_mod)
    app = _main_mod.create_app()
    with TestClient(app) as c:
        yield c
    _db.close_db()


@_skip_router
class TestNotesApiEndpoints:
    def test_post_notes_creates_note(self, client):
        resp = client.post("/notes", json={"title": "API note", "body": "body text"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["title"] == "API note"
        assert data["data"]["id"]

    def test_get_notes_list(self, client):
        client.post("/notes", json={"title": "Listed A", "body": ""})
        client.post("/notes", json={"title": "Listed B", "body": ""})
        resp = client.get("/notes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 2

    def test_get_notes_with_q_filter(self, client):
        client.post("/notes", json={"title": "Search me", "body": ""})
        client.post("/notes", json={"title": "Ignore me", "body": ""})
        resp = client.get("/notes?q=search")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["title"] == "Search me"

    def test_get_notes_with_tag_filter(self, client):
        client.post("/notes", json={"title": "Tagged", "body": "", "tags": ["api"]})
        client.post("/notes", json={"title": "Untagged", "body": "", "tags": []})
        resp = client.get("/notes?tag=api")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1

    def test_get_note_by_id(self, client):
        create_resp = client.post("/notes", json={"title": "Fetchable", "body": "hello"})
        note_id = create_resp.json()["data"]["id"]
        resp = client.get(f"/notes/{note_id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["body"] == "hello"

    def test_get_note_unknown_id_returns_404(self, client):
        resp = client.get("/notes/does-not-exist")
        assert resp.status_code == 404

    def test_put_note_updates_note(self, client):
        create_resp = client.post("/notes", json={"title": "Old", "body": "old"})
        note_id = create_resp.json()["data"]["id"]
        resp = client.put(f"/notes/{note_id}", json={"title": "New", "body": "new"})
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "New"
        assert resp.json()["data"]["body"] == "new"

    def test_put_note_unknown_id_returns_404(self, client):
        resp = client.put("/notes/ghost", json={"title": "x", "body": ""})
        assert resp.status_code == 404

    def test_delete_note_removes_it(self, client):
        create_resp = client.post("/notes", json={"title": "Delete me", "body": ""})
        note_id = create_resp.json()["data"]["id"]
        del_resp = client.delete(f"/notes/{note_id}")
        assert del_resp.status_code == 200
        get_resp = client.get(f"/notes/{note_id}")
        assert get_resp.status_code == 404

    def test_delete_note_unknown_id_returns_404(self, client):
        resp = client.delete("/notes/ghost")
        assert resp.status_code == 404

    def test_post_notes_missing_title_returns_422(self, client):
        resp = client.post("/notes", json={"body": "no title"})
        assert resp.status_code == 422

    def test_post_notes_empty_title_returns_422(self, client):
        resp = client.post("/notes", json={"title": "", "body": "empty title"})
        assert resp.status_code == 422

    def test_post_notes_attach_type_without_ref_returns_422(self, client):
        resp = client.post("/notes", json={
            "title": "Bad attach", "body": "",
            "attach": {"type": "project", "ref": None},
        })
        assert resp.status_code == 422

    def test_response_envelope_shape(self, client):
        """All responses use {success: bool, data: ..., warning?: str} envelope."""
        resp = client.get("/notes")
        body = resp.json()
        assert "success" in body
        assert "data" in body

    def test_git_commit_landed_after_api_create(self, client, isolated_paths):
        """Sprint-13 lesson: git commit must be in git log, not just return value correct."""
        from core.config import settings
        client.post("/notes", json={"title": "Git verify", "body": "content"})
        count = _git_commit_count(settings.data_dir)
        assert count >= 1, f"Expected ≥1 git commit after POST /notes, got {count}"

    def test_health_includes_notes_module(self, client):
        """After router registers, /health must list 'notes' as a known module."""
        resp = client.get("/health")
        assert resp.status_code == 200
        modules = resp.json()["data"]["modules"]
        assert "notes" in modules, f"/health modules must include 'notes', got {modules}"

    def test_get_notes_attached_filter(self, client):
        client.post("/notes", json={
            "title": "Proj note", "body": "",
            "attach": {"type": "project", "ref": "life-os"},
        })
        client.post("/notes", json={"title": "Standalone", "body": ""})
        resp = client.get("/notes?attached=project")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["title"] == "Proj note"
