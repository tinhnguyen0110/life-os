"""tests/test_wiki_folder_lifecycle.py — WIKI-WORKDIR W1 (#127): folder lifecycle + empty-folder anchor.

The empty-folder model (design §3, option B): a folder EXISTS if it has notes (prefix) OR a
wiki_folder_meta row. The load-bearing distinguishing cases (the dispatch pass-bar):
  - 🔴 create NESTED "A/B/C" (no notes) → appears NESTED in /tree (counts:0 at each level) — headline;
  - create a sub-folder of an existing folder → child node appears;
  - 🔴 DELETE a folder → subtree notes #94-tombstoned (recoverable) + folder_meta rows gone + OTHER
    folders UNTOUCHED (SCOPED);
  - move/rename "A"→"X" → notes re-prefixed (A/B/n → X/B/n) + meta keys moved;
  - backward-compat: a folder WITH notes still works (prefix path unchanged);
  - empty meta-only folder → honest node (counts:0, meta); 409 on duplicate-create; 422 on bad path.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

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


@pytest.fixture
def api(wiki_db):
    from main import create_app
    return TestClient(create_app())


def _node_at(tree: dict, path: str) -> dict | None:
    """Descend the tree to the node at ``path`` (or None). path '' = the root node."""
    if not path:
        return tree
    node = tree
    for seg in path.split("/"):
        child = next((f for f in node.get("folders", []) if f["name"] == seg), None)
        if child is None:
            return None
        node = child
    return node


# --- 🔴 the headline: create a NESTED empty folder → appears in /tree -------- #
def test_create_nested_empty_folder_appears_in_tree(wiki_db):
    out = wsvc.create_folder("A/B/C")
    assert out["path"] == "A/B/C" and out["created"] is True
    t = reader.folder_tree()
    # nested A → B → C, each an honest node with counts:0 (no notes)
    a = _node_at(t, "A"); b = _node_at(t, "A/B"); c = _node_at(t, "A/B/C")
    assert a is not None and a["counts"]["notes"] == 0
    assert b is not None and b["counts"]["notes"] == 0
    assert c is not None and c["counts"]["notes"] == 0 and c["path"] == "A/B/C"


def test_create_folder_with_desc(wiki_db):
    out = wsvc.create_folder("Docs", desc="design docs")
    assert out["desc"] == "design docs"
    c = _node_at(reader.folder_tree(), "Docs")
    assert c is not None and c["meta"] == {"desc": "design docs"}


def test_create_subfolder_of_existing(wiki_db):
    wsvc.create_folder("A")
    wsvc.create_folder("A/sub")
    a = _node_at(reader.folder_tree(), "A")
    assert any(f["name"] == "sub" for f in a["folders"])


def test_create_normalizes_path(wiki_db):
    out = wsvc.create_folder("  /X//Y/ ")
    assert out["path"] == "X/Y"


def test_create_empty_path_is_invalid(wiki_db):
    from modules.wiki.service import FolderError
    with pytest.raises(FolderError) as ei:
        wsvc.create_folder("   ")
    assert ei.value.code == "INVALID_INPUT"


def test_create_duplicate_is_conflict(wiki_db):
    wsvc.create_folder("Dup")
    from modules.wiki.service import FolderError
    with pytest.raises(FolderError) as ei:
        wsvc.create_folder("Dup")
    assert ei.value.code == "CONFLICT"


def test_create_over_existing_note_prefix_is_conflict(wiki_db):
    """A folder that already exists via a NOTE's prefix → create is a 409 (already present)."""
    wsvc.create_note(NoteCreateInput(title="n", folder="Has/Notes"))
    from modules.wiki.service import FolderError
    with pytest.raises(FolderError) as ei:
        wsvc.create_folder("Has/Notes")
    assert ei.value.code == "CONFLICT"


# --- 🔴 DELETE folder → subtree soft-deleted + meta gone + SCOPED ------------ #
def test_delete_folder_soft_deletes_subtree_notes_scoped(wiki_db):
    keep = wsvc.create_note(NoteCreateInput(title="keep", folder="Other")).id
    n1 = wsvc.create_note(NoteCreateInput(title="del1", folder="Trash")).id
    n2 = wsvc.create_note(NoteCreateInput(title="del2", folder="Trash/sub")).id
    wsvc.create_folder("Trash/empty")  # an empty meta-only sub-folder in the subtree
    out = wsvc.delete_folder("Trash")
    assert set(out["deletedNotes"]) == {n1, n2}
    assert "Trash/empty" in out["removedMeta"]
    # the deleted notes are SOFT (recoverable) — TOMBSTONED (deletedAt set), excluded from live views.
    # (get_note still returns the row WITH deletedAt — the live-exclusion is at all_notes/tree.)
    assert wsvc.get_note(n1).deletedAt is not None
    assert wsvc.get_note(n2).deletedAt is not None
    # 🔴 SCOPED: the OTHER folder's note is untouched (still live, no tombstone)
    assert wsvc.get_note(keep).deletedAt is None
    # the Trash subtree is gone from the LIVE tree (built from all_notes which excludes tombstoned);
    # Other remains.
    t = reader.folder_tree()
    assert _node_at(t, "Trash") is None
    assert _node_at(t, "Other") is not None


def test_delete_empty_meta_only_folder(wiki_db):
    wsvc.create_folder("Empty")
    out = wsvc.delete_folder("Empty")
    assert out["deletedNotes"] == [] and out["removedMeta"] == ["Empty"]
    assert _node_at(reader.folder_tree(), "Empty") is None


def test_delete_root_is_invalid(wiki_db):
    from modules.wiki.service import FolderError
    with pytest.raises(FolderError) as ei:
        wsvc.delete_folder("")
    assert ei.value.code == "INVALID_INPUT"


def test_deleted_notes_are_restorable(wiki_db):
    """#94: a folder-delete is recoverable — the tombstoned note restores to live."""
    nid = wsvc.create_note(NoteCreateInput(title="x", folder="Tmp")).id
    wsvc.delete_folder("Tmp")
    assert wsvc.get_note(nid).deletedAt is not None  # tombstoned
    assert _node_at(reader.folder_tree(), "Tmp") is None  # gone from the live tree
    wsvc.restore_note(nid)
    assert wsvc.get_note(nid).deletedAt is None  # tombstone cleared
    assert _node_at(reader.folder_tree(), "Tmp") is not None  # back in the live tree


# --- move/rename → re-prefix notes + move meta ------------------------------ #
def test_move_folder_reprefixes_notes_and_meta(wiki_db):
    n1 = wsvc.create_note(NoteCreateInput(title="a", folder="A")).id
    n2 = wsvc.create_note(NoteCreateInput(title="b", folder="A/B")).id
    wsvc.create_folder("A/empty", desc="keep me")  # meta-only sub
    out = wsvc.move_folder("A", "X")
    assert set(out["movedNotes"]) == {n1, n2}
    # notes re-prefixed A → X (A/B/n → X/B/n)
    assert wsvc.get_note(n1).folder == "X"
    assert wsvc.get_note(n2).folder == "X/B"
    # meta moved (A/empty → X/empty, desc preserved)
    assert wiki_store.get_folder_meta("X/empty") == {"desc": "keep me"}
    assert wiki_store.get_folder_meta("A/empty") is None
    # the old path is gone, the new path present
    t = reader.folder_tree()
    assert _node_at(t, "A") is None and _node_at(t, "X") is not None


def test_move_into_own_subtree_is_invalid(wiki_db):
    wsvc.create_folder("A")
    from modules.wiki.service import FolderError
    with pytest.raises(FolderError) as ei:
        wsvc.move_folder("A", "A/B")  # into its own subtree
    assert ei.value.code == "INVALID_INPUT"


def test_move_to_existing_target_is_conflict(wiki_db):
    wsvc.create_note(NoteCreateInput(title="a", folder="A"))
    wsvc.create_note(NoteCreateInput(title="x", folder="X"))  # X already exists
    from modules.wiki.service import FolderError
    with pytest.raises(FolderError) as ei:
        wsvc.move_folder("A", "X")
    assert ei.value.code == "CONFLICT"


# --- backward-compat: a folder WITH notes still works (prefix path) ---------- #
def test_folder_with_notes_unchanged(wiki_db):
    """A note-anchored folder (no meta row) still appears — the prefix path, pre-#127 behavior."""
    wsvc.create_note(NoteCreateInput(title="n", folder="Proj/sub"))
    t = reader.folder_tree()
    node = _node_at(t, "Proj/sub")
    assert node is not None and node["counts"]["notes"] == 1


# --- REST surface ----------------------------------------------------------- #
def test_rest_create_delete_move(api):
    # create nested
    r = api.post("/wiki/folders", json={"path": "R/S/T", "desc": "rst"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["path"] == "R/S/T"
    # in the tree
    tree = api.get("/wiki/tree").json()["data"]
    assert _node_at(tree, "R/S/T") is not None
    # duplicate → 409
    assert api.post("/wiki/folders", json={"path": "R/S/T"}).status_code == 409
    # bad path → 422
    assert api.post("/wiki/folders", json={"path": "   "}).status_code == 422
    # move R → Q
    mv = api.put("/wiki/folders/R/move", json={"to": "Q"})
    assert mv.status_code == 200 and mv.json()["data"]["to"] == "Q"
    assert _node_at(api.get("/wiki/tree").json()["data"], "Q/S/T") is not None
    # delete Q
    dl = api.delete("/wiki/folders/Q")
    assert dl.status_code == 200 and dl.json()["data"]["folder"] == "Q"
    assert _node_at(api.get("/wiki/tree").json()["data"], "Q") is None


def test_rest_delete_root_422(api):
    # DELETE /wiki/folders/ (empty path) — the path converter needs a segment; a normalize-to-empty
    # path is rejected. We assert via the service-level empty check (the router maps it to 422).
    assert api.post("/wiki/folders", json={"path": "/"}).status_code == 422  # normalizes to empty