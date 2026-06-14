"""tests/test_wiki_folder.py — W-Explorer folder field + tree + move (Sprint W-Explorer).

THE 3 INVARIANTS (architect/team-lead non-negotiable):
  1. MIGRATION-SAFE: a pre-folder note (no `folder` in frontmatter) reads as folder=""
     (root) + round-trips IDENTICALLY — 0 regression.
  2. TREE CORRECT: nested folders from "A/B/C"; ""→root; empty vault→honest empty;
     deterministic order.
  3. MOVE = NO .md REWRITE (the citation-survival invariant): setting folder via PUT
     changes ONLY the frontmatter folder — the body + integer id + links + citations
     all survive (a move never breaks grounding).

Tests in their own module (test-where-the-reader-greps). folder is additive — no
existing wiki test should need editing.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.wiki import citations as wiki_citations
from modules.wiki import proposals_store as pstore
from modules.wiki import reader
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.schema import NoteCreateInput, NoteUpdateInput, normalize_folder


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    pstore.init_proposal_tables()
    return isolated_paths


# --------------------------------------------------------------------------- #
# folder path normalization                                                     #
# --------------------------------------------------------------------------- #
def test_normalize_folder():
    assert normalize_folder("") == ""
    assert normalize_folder("/") == ""
    assert normalize_folder("   ") == ""
    assert normalize_folder("Projects") == "Projects"
    assert normalize_folder("/Projects/life-os/") == "Projects/life-os"
    assert normalize_folder("A//B///C") == "A/B/C"
    assert normalize_folder("  A / B ") == "A/B"


def test_folder_defaults_root(wiki_db):
    n = wsvc.create_note(NoteCreateInput(title="rootnote"))
    assert n.folder == ""  # default = root


def test_create_with_folder_normalized(wiki_db):
    n = wsvc.create_note(NoteCreateInput(title="x", folder="/Projects/life-os/"))
    assert n.folder == "Projects/life-os"  # normalized


# --------------------------------------------------------------------------- #
# INVARIANT 1 — migration-safe                                                  #
# --------------------------------------------------------------------------- #
def test_INV1_pre_folder_note_reads_as_root_and_roundtrips(wiki_db):
    # simulate a PRE-folder note: an md doc with NO folder line in frontmatter.
    from store import md_store
    pre_folder_md = (
        "---\n"
        "id: 1\ntitle: Legacy\naliases: []\nstatus: fleeting\n"
        "noteType: concept\ntrustTier: verified\nauthor: human\ntags: []\n"
        "captureSource: quick_add\ncreated: '2026-01-01T00:00:00+00:00'\n"
        "updated: '2026-01-01T00:00:00+00:00'\n"
        "---\nlegacy body content"
    )
    md_store.write_file("wiki/notes/1.md", pre_folder_md, "seed pre-folder note")
    note = wsvc.get_note(1)
    assert note is not None
    assert note.folder == ""              # absent folder → root (migration-safe)
    assert note.content == "legacy body content"  # body unchanged
    assert note.title == "Legacy"


# --------------------------------------------------------------------------- #
# INVARIANT 2 — tree correct                                                    #
# --------------------------------------------------------------------------- #
def test_INV2_empty_vault_honest_tree(wiki_db):
    t = reader.folder_tree()
    assert t == {"name": "", "path": "", "folders": [], "notes": []}


def test_INV2_root_notes_at_top(wiki_db):
    a = wsvc.create_note(NoteCreateInput(title="root A")).id
    t = reader.folder_tree()
    assert [n["id"] for n in t["notes"]] == [a]
    assert t["folders"] == []


def test_INV2_nested_folders(wiki_db):
    wsvc.create_note(NoteCreateInput(title="deep", folder="A/B/C"))
    wsvc.create_note(NoteCreateInput(title="mid", folder="A/B"))
    wsvc.create_note(NoteCreateInput(title="top-root"))  # root
    t = reader.folder_tree()
    # root has the root note + folder A
    assert any(n["title"] == "top-root" for n in t["notes"])
    a = next(f for f in t["folders"] if f["name"] == "A")
    assert a["path"] == "A"
    b = next(f for f in a["folders"] if f["name"] == "B")
    assert b["path"] == "A/B"
    assert any(n["title"] == "mid" for n in b["notes"])      # note in A/B
    c = next(f for f in b["folders"] if f["name"] == "C")
    assert c["path"] == "A/B/C"
    assert any(n["title"] == "deep" for n in c["notes"])     # note in A/B/C


def test_INV2_intermediate_folder_implied(wiki_db):
    # a note in "X/Y" with NO note directly in "X" → "X" still exists as a node.
    wsvc.create_note(NoteCreateInput(title="leaf", folder="X/Y"))
    t = reader.folder_tree()
    x = next(f for f in t["folders"] if f["name"] == "X")
    assert x["notes"] == []  # no note directly in X
    assert any(f["name"] == "Y" for f in x["folders"])


def test_INV2_deterministic_order(wiki_db):
    wsvc.create_note(NoteCreateInput(title="z", folder="Zeta"))
    wsvc.create_note(NoteCreateInput(title="a", folder="Alpha"))
    t = reader.folder_tree()
    assert [f["name"] for f in t["folders"]] == ["Alpha", "Zeta"]  # sorted


# --------------------------------------------------------------------------- #
# INVARIANT 3 — MOVE = no .md rewrite, citation/links survive                    #
# --------------------------------------------------------------------------- #
def test_INV3_move_changes_only_folder_body_and_links_survive(wiki_db):
    target = wsvc.create_note(NoteCreateInput(title="Target", content="the cited passage here")).id
    # a note that links to the target
    src = wsvc.create_note(NoteCreateInput(title="Source", content=f"see [[{target}]]")).id
    body_before = wsvc.get_note(target).content
    hash_before = wsvc.get_note(target).contentHash

    # MOVE the target into a folder (folder-only update)
    moved = wsvc.update_note(target, NoteUpdateInput(folder="Archive/2026"))
    assert moved.folder == "Archive/2026"

    # (a) body + id + contentHash UNCHANGED (no rewrite of content)
    after = wsvc.get_note(target)
    assert after.id == target and after.content == body_before
    assert after.contentHash == hash_before

    # (b) the inbound link from src STILL resolves (move didn't break the graph)
    resolved = [r for r in wiki_store.links_to(target, resolved_only=True)]
    assert any(r["source_id"] == src for r in resolved), "link broke on move"

    # (c) a citation to the moved note still VERIFIES (grounding survives the move)
    out = wiki_citations.verify_citations([{"noteId": target, "span": "the cited passage here"}])
    assert out["results"][0]["status"] == "verified"


def test_INV3_move_to_root(wiki_db):
    n = wsvc.create_note(NoteCreateInput(title="x", folder="A/B")).id
    wsvc.update_note(n, NoteUpdateInput(folder=""))  # move back to root
    assert wsvc.get_note(n).folder == ""


def test_move_is_not_a_noop_touch(wiki_db):
    # a folder-only change must actually persist (not be swallowed by the A5 no-op-touch).
    n = wsvc.create_note(NoteCreateInput(title="x", content="body")).id
    wsvc.update_note(n, NoteUpdateInput(folder="Moved"))
    assert wsvc.get_note(n).folder == "Moved"


# --------------------------------------------------------------------------- #
# API                                                                          #
# --------------------------------------------------------------------------- #
@pytest.fixture
def client(wiki_db):
    from main import app
    return TestClient(app)


def test_api_tree_and_move(client):
    a = client.post("/wiki/notes", json={"title": "A", "folder": "Proj"}).json()["data"]["id"]
    # tree reflects the folder
    t = client.get("/wiki/tree").json()["data"]
    assert any(f["name"] == "Proj" for f in t["folders"])
    # move via PUT
    r = client.put(f"/wiki/notes/{a}", json={"folder": "Archive"})
    assert r.status_code == 200 and r.json()["data"]["folder"] == "Archive"
    t2 = client.get("/wiki/tree").json()["data"]
    assert any(f["name"] == "Archive" for f in t2["folders"])
    assert not any(f["name"] == "Proj" for f in t2["folders"])  # moved out of Proj


def test_api_tree_empty_honest(client):
    assert client.get("/wiki/tree").json()["data"] == {
        "name": "", "path": "", "folders": [], "notes": []}
