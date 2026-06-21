"""tests/test_wiki_folder_meta.py — WIKI-RETRIEVAL-1 (#20): wiki_tree enrichment.

The tree gains, additively (ls-style navigation WITHOUT reading bodies):
  - per-folder ``meta:{desc}|null`` (from wiki_folder_meta; null when no row — honest, never
    fabricated) + ``counts:{notes:N}`` (notes directly in the folder).
  - per-note ``kind`` (note_type) + ``status`` — so a MOC (kind="moc") is the spottable index.
  - ``wiki_tree(folder?, depth?)`` — scoped subtree + depth-limited nesting.
The #24 invariant is PRESERVED: REST /wiki/tree data == MCP wiki_tree byte-identical WITH the new
fields (no wrapper / no drift).
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from modules.wiki import reader
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.schema import NoteCreateInput
from modules.wiki.mcp import read_server as wrs


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    return isolated_paths


# --------------------------------------------------------------------------- #
# note-stub gains kind + status (a MOC is spottable)                            #
# --------------------------------------------------------------------------- #
def test_note_stub_has_kind_and_status(wiki_db):
    moc = wsvc.create_note(NoteCreateInput(title="Index", content="x", noteType="moc")).id
    plain = wsvc.create_note(NoteCreateInput(title="Plain", content="y")).id
    notes = {n["id"]: n for n in reader.folder_tree()["notes"]}
    assert set(notes[moc]) == {"id", "title", "kind", "status"}
    assert notes[moc]["kind"] == "moc", "a MOC must be spottable by kind"
    assert notes[plain]["kind"] == "concept"
    assert notes[moc]["status"] in ("fleeting", "developing", "evergreen")


# --------------------------------------------------------------------------- #
# folder meta — null when no row (honest), {desc} when set, null again cleared  #
# --------------------------------------------------------------------------- #
def test_folder_meta_null_when_absent(wiki_db):
    wsvc.create_note(NoteCreateInput(title="n", content="x", folder="Area"))
    area = reader.folder_tree()["folders"][0]
    assert area["path"] == "Area"
    assert area["meta"] is None, "a folder with no folder_meta row → meta:null (never fabricated)"


def test_folder_meta_set_surfaces_desc(wiki_db):
    wsvc.create_note(NoteCreateInput(title="n", content="x", folder="Area"))
    wiki_store.set_folder_meta("Area", "research notes on X")
    area = reader.folder_tree()["folders"][0]
    assert area["meta"] == {"desc": "research notes on X"}


def test_folder_meta_blank_clears_to_null(wiki_db):
    wsvc.create_note(NoteCreateInput(title="n", content="x", folder="Area"))
    wiki_store.set_folder_meta("Area", "something")
    assert reader.folder_tree()["folders"][0]["meta"] == {"desc": "something"}
    wiki_store.set_folder_meta("Area", "   ")  # blank → clear (honest-null, not "")
    assert reader.folder_tree()["folders"][0]["meta"] is None


# --------------------------------------------------------------------------- #
# counts — notes directly in a folder (no body, token-cheap)                     #
# --------------------------------------------------------------------------- #
def test_counts_notes_directly_in_folder(wiki_db):
    wsvc.create_note(NoteCreateInput(title="a", content="x", folder="A"))
    wsvc.create_note(NoteCreateInput(title="b", content="x", folder="A"))
    wsvc.create_note(NoteCreateInput(title="c", content="x", folder="A/B"))
    t = reader.folder_tree()
    A = t["folders"][0]
    assert A["counts"] == {"notes": 2}, "counts = notes DIRECTLY in A (not its subtree)"
    assert A["folders"][0]["counts"] == {"notes": 1}  # A/B has 1
    # no body anywhere in the tree (token-cheap)
    assert "content" not in A["notes"][0] and "body" not in A["notes"][0]


# --------------------------------------------------------------------------- #
# folder + depth params                                                          #
# --------------------------------------------------------------------------- #
def test_folder_param_scopes_subtree(wiki_db):
    wsvc.create_note(NoteCreateInput(title="root", content="x"))
    wsvc.create_note(NoteCreateInput(title="deep", content="x", folder="A/B"))
    sub = reader.folder_tree(folder="A/B")
    assert sub["path"] == "A/B"
    assert [n["title"] for n in sub["notes"]] == ["deep"]


def test_folder_param_unknown_is_honest_empty(wiki_db):
    sub = reader.folder_tree(folder="Nonexistent/Path")
    assert sub["path"] == "Nonexistent/Path" and sub["notes"] == [] and sub["folders"] == []
    assert sub["meta"] is None and sub["counts"] == {"notes": 0}


def test_depth_limits_nesting(wiki_db):
    wsvc.create_note(NoteCreateInput(title="deep", content="x", folder="A/B/C"))
    # depth=0 → A is listed (name + counts) but NOT descended (its folders/notes empty)
    d0 = reader.folder_tree(depth=0)
    A = d0["folders"][0]
    assert A["name"] == "A" and A["folders"] == [] and A["notes"] == []
    # unlimited → A/B/C fully nested
    full = reader.folder_tree()
    assert full["folders"][0]["folders"][0]["folders"][0]["path"] == "A/B/C"


# --------------------------------------------------------------------------- #
# THE #24 INVARIANT — REST == MCP byte-identical WITH the new fields             #
# --------------------------------------------------------------------------- #
def test_rest_mcp_byte_identical_with_new_fields(wiki_db):
    wsvc.create_note(NoteCreateInput(title="n", content="x", folder="A", noteType="moc"))
    wiki_store.set_folder_meta("A", "desc A")
    rest = reader.folder_tree()       # == REST /wiki/tree data
    mcp = wrs.wiki_tree()             # the MCP tool
    assert json.dumps(rest, sort_keys=True) == json.dumps(mcp, sort_keys=True), \
        "REST == MCP byte-identical incl meta/kind/status/counts (the #24 invariant)"
    assert "tree" not in mcp  # no wrapper drift re-introduced
    # the params also match across surfaces
    assert json.dumps(reader.folder_tree(folder="A", depth=0), sort_keys=True) == \
        json.dumps(wrs.wiki_tree(folder="A", depth=0), sort_keys=True)


# --------------------------------------------------------------------------- #
# REST set-folder-meta endpoint (the optional setter)                            #
# --------------------------------------------------------------------------- #
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
    # the wiki store's import-time init_wiki_tables ran against the PRE-rebind db; re-init the
    # wiki tables on the now-rebound tmp connection so the REST wiki routes have their tables.
    wiki_store.init_wiki_tables()
    with TestClient(app) as c:
        yield c
    db.close_db()


def test_rest_set_folder_meta_round_trip(app_client):
    # create a note in folder A so the folder exists in the tree
    app_client.post("/wiki/notes", json={"title": "n", "content": "x", "folder": "A"})
    # set the meta via the PUT endpoint
    r = app_client.put("/wiki/folders/A/meta", json={"desc": "the A area"})
    assert r.status_code == 200 and r.json()["data"]["meta"] == {"desc": "the A area"}
    # it shows in the tree
    tree = app_client.get("/wiki/tree").json()["data"]
    assert tree["folders"][0]["meta"] == {"desc": "the A area"}
    # blank clears it
    app_client.put("/wiki/folders/A/meta", json={"desc": ""})
    assert app_client.get("/wiki/tree").json()["data"]["folders"][0]["meta"] is None
