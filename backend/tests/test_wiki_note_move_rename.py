"""tests/test_wiki_note_move_rename.py — WIKI-WORKDIR W2 (#133): note move + rename (thin/existing).

W2 = the FILE half. Move + rename ALREADY work via the existing PUT /wiki/notes/{id} (NoteUpdateInput
carries folder + title). This file VERIFIES that contract (no new endpoint — decided + frozen: the FE
moves/renames a note via PUT /notes/{id} {folder} / {title}, NOT a dedicated /move endpoint).

🔴 The W1 gotcha applies: a soft-delete tombstones but get_note STILL returns the row → "moved out of
folder A" is observed via the TREE / all_notes (a live view), NOT get_note. Move is NOT a delete, but
we verify folder membership via the tree (the live, authoritative view) per the same principle.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.wiki import proposals_store as pstore
from modules.wiki import reader
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.schema import NoteCreateInput, NoteUpdateInput


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    pstore.init_proposal_tables()
    return isolated_paths


@pytest.fixture
def api(wiki_db):
    from main import create_app
    return TestClient(create_app())


def _node_at(tree: dict, path: str) -> dict | None:
    if not path:
        return tree
    node = tree
    for seg in path.split("/"):
        child = next((f for f in node.get("folders", []) if f["name"] == seg), None)
        if child is None:
            return None
        node = child
    return node


def _note_ids_in(tree: dict, path: str) -> set[int]:
    node = _node_at(tree, path)
    return {n["id"] for n in node["notes"]} if node else set()


# --- move a note between folders (via the existing PUT folder field) --------- #
def test_move_note_changes_folder_field(wiki_db):
    n = wsvc.create_note(NoteCreateInput(title="movable", folder="A"))
    wsvc.update_note(n.id, NoteUpdateInput(folder="B"))
    assert wsvc.get_note(n.id).folder == "B"  # the field moved


def test_move_note_leaves_A_joins_B_in_tree(wiki_db):
    """🔴 verify membership via the TREE (the live view), per the W1 gotcha: the note leaves A's
    node + joins B's node."""
    n = wsvc.create_note(NoteCreateInput(title="x", folder="A"))
    # before: in A, not in B
    t0 = reader.folder_tree()
    assert n.id in _note_ids_in(t0, "A")
    wsvc.update_note(n.id, NoteUpdateInput(folder="B"))
    t1 = reader.folder_tree()
    assert n.id not in _note_ids_in(t1, "A"), "the note must leave A's tree node"
    assert n.id in _note_ids_in(t1, "B"), "the note must join B's tree node"


def test_move_note_to_root(wiki_db):
    n = wsvc.create_note(NoteCreateInput(title="x", folder="A/B"))
    wsvc.update_note(n.id, NoteUpdateInput(folder=""))
    t = reader.folder_tree()
    assert n.id in _note_ids_in(t, "")  # back at the root


def test_move_note_into_nested(wiki_db):
    n = wsvc.create_note(NoteCreateInput(title="x"))  # root
    wsvc.update_note(n.id, NoteUpdateInput(folder="P/Q/R"))
    assert wsvc.get_note(n.id).folder == "P/Q/R"
    assert n.id in _note_ids_in(reader.folder_tree(), "P/Q/R")  # nested node created on move


# --- rename a note (via the existing PUT title field) ------------------------ #
def test_rename_note_updates_title(wiki_db):
    n = wsvc.create_note(NoteCreateInput(title="old name"))
    wsvc.update_note(n.id, NoteUpdateInput(title="new name"))
    assert wsvc.get_note(n.id).title == "new name"


# --- REST: move + rename via PUT /wiki/notes/{id} (the frozen contract) ------ #
def test_rest_move_via_put_folder(api):
    nid = api.post("/wiki/notes", json={"title": "n", "folder": "A"}).json()["data"]["id"]
    r = api.put(f"/wiki/notes/{nid}", json={"folder": "B"})
    assert r.status_code == 200 and r.json()["data"]["folder"] == "B"
    tree = api.get("/wiki/tree").json()["data"]
    assert nid in _note_ids_in(tree, "B") and nid not in _note_ids_in(tree, "A")


def test_rest_rename_via_put_title(api):
    nid = api.post("/wiki/notes", json={"title": "before"}).json()["data"]["id"]
    r = api.put(f"/wiki/notes/{nid}", json={"title": "after"})
    assert r.status_code == 200 and r.json()["data"]["title"] == "after"


def test_rest_move_and_rename_together(api):
    """one PUT can do both (folder + title) — the FE's combined edit."""
    nid = api.post("/wiki/notes", json={"title": "x", "folder": "A"}).json()["data"]["id"]
    r = api.put(f"/wiki/notes/{nid}", json={"folder": "C", "title": "renamed"})
    d = r.json()["data"]
    assert d["folder"] == "C" and d["title"] == "renamed"


def test_rest_move_absent_note_404(api):
    r = api.put("/wiki/notes/99999", json={"folder": "X"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
