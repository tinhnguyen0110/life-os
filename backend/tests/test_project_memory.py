"""tests/test_project_memory.py — PROJECT-MEMORY (#42): a project's wiki notes as agent context.

Link convention (F1=a): the TAG ``project:<id>``. ``reader.project_notes(id)`` returns the notes
tagged for a project (lean, newest first, top-N); ``project_context(id)`` composes project metadata +
those notes (REST GET /projects/{id}/context + MCP project_context, byte-identical #24).

The distinguishing (tag-scoped, NOT all-notes): a note tagged ``project:other`` or untagged must NOT
appear in project X's context. Defensive: unknown project → honest (404 / found:False, never a
fabricated project); a project with zero tagged notes → ``notes: []`` (honest-empty, not omitted).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from modules.wiki import reader as wiki_reader
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.schema import NoteCreateInput


# --------------------------------------------------------------------------- #
# reader.project_notes — the tag-scoped note list (unit, isolated wiki store)    #
# --------------------------------------------------------------------------- #
@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    return isolated_paths


def test_project_notes_returns_tagged_notes(wiki_db):
    a = wsvc.create_note(NoteCreateInput(title="LifeOS arch", tags=["project:life-os"], status="evergreen")).id
    b = wsvc.create_note(NoteCreateInput(title="LifeOS todo", tags=["project:life-os", "misc"])).id
    notes = wiki_reader.project_notes("life-os")
    ids = {n["id"] for n in notes}
    assert a in ids and b in ids
    # lean shape
    for n in notes:
        assert set(n) == {"id", "title", "status", "updated", "snippet"}


def test_project_notes_is_tag_scoped_distinguishing(wiki_db):
    """THE distinguishing: notes tagged project:OTHER or UNTAGGED do NOT appear in project X's list.
    A correct tag-scoped impl excludes them; a naive all-notes impl would wrongly include them."""
    mine = wsvc.create_note(NoteCreateInput(title="Mine", tags=["project:life-os"])).id
    other = wsvc.create_note(NoteCreateInput(title="Other proj", tags=["project:cairn"])).id
    untagged = wsvc.create_note(NoteCreateInput(title="No tags")).id
    ids = {n["id"] for n in wiki_reader.project_notes("life-os")}
    assert mine in ids
    assert other not in ids, "a note tagged project:cairn must NOT appear in project:life-os"
    assert untagged not in ids, "an untagged note must NOT appear in any project's notes"


def test_project_notes_honest_empty(wiki_db):
    """A project with no tagged notes → [] (honest-empty, not fabricated)."""
    wsvc.create_note(NoteCreateInput(title="Unrelated", tags=["project:cairn"]))
    assert wiki_reader.project_notes("life-os") == []


def test_project_notes_blank_id_empty(wiki_db):
    assert wiki_reader.project_notes("") == [] and wiki_reader.project_notes("   ") == []


def test_project_notes_substring_not_matched(wiki_db):
    """Tag matching is whole-element: project:'life' must NOT match a note tagged 'project:life-os'
    (the quoted-JSON-element anchor prevents the substring false-match)."""
    wsvc.create_note(NoteCreateInput(title="LifeOS", tags=["project:life-os"]))
    assert wiki_reader.project_notes("life") == []


def test_project_notes_sorted_updated_desc_and_capped(wiki_db):
    """Newest-updated first + capped at the limit (default 10)."""
    for i in range(12):
        wsvc.create_note(NoteCreateInput(title=f"n{i}", tags=["project:big"]))
    notes = wiki_reader.project_notes("big")
    assert len(notes) == 10  # default top-10
    updated = [n["updated"] for n in notes]
    assert updated == sorted(updated, reverse=True)
    assert len(wiki_reader.project_notes("big", limit=3)) == 3


def test_project_tag_helper(wiki_db):
    assert wiki_reader.project_tag("life-os") == "project:life-os"


def test_project_notes_multi_tagged_note_appears_in_each(wiki_db):
    """A note tagged for TWO projects appears in BOTH (multi-valued, non-destructive)."""
    n = wsvc.create_note(NoteCreateInput(title="Shared", tags=["project:a", "project:b"])).id
    assert n in {x["id"] for x in wiki_reader.project_notes("a")}
    assert n in {x["id"] for x in wiki_reader.project_notes("b")}


# --------------------------------------------------------------------------- #
# project_context — metadata + notes, e2e via the real app (REST) + MCP parity   #
# --------------------------------------------------------------------------- #
def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)
    (path / "app.py").write_text("print('hi')\n")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """TestClient with an isolated DATA_DIR + one repo registered as 'demo' + wiki tables ready.

    ISOLATION (mirrors conftest.isolated_paths — critical for full-suite ordering): besides pointing
    settings at tmp_path, it RESETS db.DB_PATH (init_db() sets this module-global and never clears it
    → a prior test's DB path would otherwise win over settings.db_path → another test's project:demo
    notes leak into our store) + clears the process-global projects status cache. Without these, the
    zero-notes / tag-scoped asserts see leaked notes (a cross-FILE flake, green in isolation)."""
    from core.config import settings
    from store import db

    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "db_path", tmp_path / "store" / "test.db")
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    monkeypatch.setattr(db, "DB_PATH", None)  # else a prior init_db() path leaks (cross-test bleed)
    from modules.projects import service as _proj_service
    _proj_service._STATUS_CACHE.clear()
    repo = tmp_path / "demo"
    _init_repo(repo)
    monkeypatch.setattr(settings, "project_repos", {"demo": str(repo)})

    db.close_db()
    import main as main_mod
    app = main_mod.create_app()
    wiki_store.init_wiki_tables()
    with TestClient(app) as c:
        yield c
    db.close_db()


def test_context_composes_metadata_and_notes(app_client):
    """GET /projects/demo/context → {project, notes, noteCount}; a note tagged project:demo appears."""
    nid = app_client.post("/wiki/notes",
                          json={"title": "Demo design", "tags": ["project:demo"]}).json()["data"]["id"]
    r = app_client.get("/projects/demo/context")
    assert r.status_code == 200
    d = r.json()["data"]
    assert set(d) == {"project", "notes", "noteCount"}
    assert d["project"]["id"] == "demo"
    assert nid in {n["id"] for n in d["notes"]}
    assert d["noteCount"] == len(d["notes"]) == 1


def test_context_zero_notes_is_honest_empty(app_client):
    """A tracked project with NO tagged notes → notes: [] (honest-empty, not omitted)."""
    r = app_client.get("/projects/demo/context")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["notes"] == [] and d["noteCount"] == 0
    assert d["project"]["id"] == "demo"  # metadata still present


def test_context_unknown_project_404(app_client):
    assert app_client.get("/projects/nonexistent-xyz/context").status_code == 404


def test_context_tag_scoped_excludes_other_project(app_client):
    """e2e distinguishing: a note tagged project:OTHER does NOT appear in demo's context."""
    app_client.post("/wiki/notes", json={"title": "Other", "tags": ["project:something-else"]})
    mine = app_client.post("/wiki/notes", json={"title": "Mine", "tags": ["project:demo"]}).json()["data"]["id"]
    d = app_client.get("/projects/demo/context").json()["data"]
    titles = {n["title"] for n in d["notes"]}
    assert "Other" not in titles and "Mine" in titles
    assert d["noteCount"] == 1


def test_context_rest_mcp_byte_identical(app_client):
    """#24: REST /projects/demo/context data == MCP project_context('demo') byte-identical."""
    from mcp_servers import read_server as rs
    app_client.post("/wiki/notes", json={"title": "Parity note", "tags": ["project:demo"]})
    rest = app_client.get("/projects/demo/context").json()["data"]
    mcp_res = rs.project_context("demo")
    assert json.dumps(rest, sort_keys=True) == json.dumps(mcp_res, sort_keys=True)


def test_mcp_project_context_unknown_is_found_false(app_client):
    """MCP convention: an unknown project → {found:False, project_id} (REST 404s; the present payload
    is byte-identical, the missing arm follows each surface's convention — like project_get)."""
    from mcp_servers import read_server as rs
    assert rs.project_context("nope-xyz") == {"found": False, "project_id": "nope-xyz"}
