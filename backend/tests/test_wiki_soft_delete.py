"""tests/test_wiki_soft_delete.py — #94 wiki SOFT-delete + restore + bulk + MCP.

User CHỐT "a" (soft-delete) + pain "xoá nhầm" (delete-by-mistake → want rollback). DELETE is now
SOFT (recoverable): a deletedAt tombstone, the .md KEPT (reconcile-safe — reindex won't prune it),
hidden from live views, restorable. The load-bearing proof: after a soft-delete, reindex KEEPS the
cache row (the .md exists) — a hard-delete would have pruned it.

BEHAVIOR-TESTED: soft-delete → read the views + reindex + restore round-trip (not field-reads).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.wiki import reader as wreader
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.schema import NoteCreateInput


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    # the MCP delete/restore go through create_proposal → need the proposals table.
    from modules.wiki import proposals_store
    proposals_store.init_proposal_tables()
    return isolated_paths


@pytest.fixture
def client(wiki_db):
    from main import create_app
    return TestClient(create_app())


def _note(title="N", body="body", tags=None):
    return wsvc.create_note(NoteCreateInput(title=title, content=body, tags=tags or []))


# --------------------------------------------------------------------------- #
# soft-delete — hidden from live, but .md + cache KEPT (NOT a hard delete)       #
# --------------------------------------------------------------------------- #
def test_soft_delete_hides_but_keeps_md_and_cache(wiki_db):
    n = _note("Will Delete", "[[Other]] body")
    _note("Other", "x")
    before = len(wiki_store.all_notes())
    wsvc.soft_delete_note(n.id)
    # gone from live views
    assert len(wiki_store.all_notes()) == before - 1
    assert wreader.search("Will") == []                  # dropped from fts
    titles = {r["title"] for r in wiki_store.all_notes()}
    assert "Will Delete" not in titles
    # but KEPT (recoverable): .md exists + cache row exists w/ deleted_at
    assert wiki_store.read_note_file(n.id) is not None    # the .md SURVIVES (reconcile-safe)
    row = wiki_store.get_note_cache(n.id)
    assert row is not None and row["deleted_at"] is not None
    assert wsvc.get_note(n.id).deletedAt is not None      # the note model carries the tombstone


def test_soft_delete_excluded_from_counts(wiki_db):
    a = _note("A"); _note("B")
    before_count = wiki_store.count_notes()
    before_status = wiki_store.count_by_status()
    wsvc.soft_delete_note(a.id)
    assert wiki_store.count_notes() == before_count - 1
    assert wiki_store.count_by_status().get("fleeting", 0) == before_status.get("fleeting", 0) - 1


# --------------------------------------------------------------------------- #
# 🔴 reconcile-safe (the #61 teeth) — reindex KEEPS the soft-deleted row          #
# --------------------------------------------------------------------------- #
def test_reconcile_safe_reindex_keeps_soft_deleted_row(wiki_db):
    """After a soft-delete, reindex/reconcile does NOT prune the cache row (the .md exists) — the
    note is recoverable. THIS is the load-bearing constraint: a hard-delete (.md gone) would prune."""
    n = _note("Reconcile Me")
    wsvc.soft_delete_note(n.id)
    result = wreader.reindex_note(n.id)
    assert result["action"] != "missing_dropped", "soft-deleted note must NOT be pruned (md kept)"
    assert wiki_store.get_note_cache(n.id) is not None, "the cache row survives reindex"
    # contrast: a HARD-delete removes the .md → reindex WOULD prune (the behavior we avoid)
    m = _note("Hard Me")
    wsvc.delete_note(m.id)  # hard delete (the .md is gone)
    assert wiki_store.read_note_file(m.id) is None  # md gone → reindex would prune (proves the contrast)


# --------------------------------------------------------------------------- #
# restore — the note comes fully BACK (links/aliases/content intact)             #
# --------------------------------------------------------------------------- #
def test_restore_brings_note_back_value_by_value(wiki_db):
    other = _note("Other", "x")
    n = _note("Restore Me", "links [[Other]]", tags=["keep"])
    wsvc.soft_delete_note(n.id)
    assert n.id not in {r["id"] for r in wiki_store.all_notes()}  # gone
    restored = wsvc.restore_note(n.id)
    assert restored.deletedAt is None
    assert restored.title == "Restore Me" and restored.tags == ["keep"]
    assert "[[Other]]" in restored.content
    assert n.id in {r["id"] for r in wiki_store.all_notes()}     # back in live
    assert wreader.search("Restore") != []                       # back in fts
    # the [[Other]] link is back resolved
    bl = wreader.backlinks(other.id)
    linked = bl["linked"] if isinstance(bl, dict) else bl
    assert any(b["id"] == n.id for b in linked)


def test_soft_delete_then_restore_idempotent(wiki_db):
    n = _note("Idem")
    wsvc.soft_delete_note(n.id)
    wsvc.soft_delete_note(n.id)   # second soft-delete = no-op
    assert wsvc.get_note(n.id).deletedAt is not None
    wsvc.restore_note(n.id)
    again = wsvc.restore_note(n.id)  # second restore = no-op
    assert again.deletedAt is None


# --------------------------------------------------------------------------- #
# teeth (the user's pain) — soft-delete is RECOVERABLE where hard-delete is not   #
# --------------------------------------------------------------------------- #
def test_teeth_soft_delete_recoverable_hard_delete_not(wiki_db):
    """The user's 'xoá nhầm' fix: a soft-deleted note can be brought back; a hard-deleted one is
    gone forever (get_note → None)."""
    soft = _note("Soft", "recover me")
    wsvc.soft_delete_note(soft.id)
    assert wsvc.restore_note(soft.id).content == "recover me"  # RECOVERED

    hard = _note("Hard", "lost forever")
    wsvc.delete_note(hard.id)                                  # hard delete
    assert wsvc.get_note(hard.id) is None                     # GONE — no restore possible


# --------------------------------------------------------------------------- #
# bulk soft-delete — per-id results, fail-soft                                   #
# --------------------------------------------------------------------------- #
def test_bulk_soft_delete(client):
    ids = [_note(f"B{i}").id for i in range(3)]
    r = client.post("/wiki/notes/bulk-delete", json={"ids": ids})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["deletedCount"] == 3
    assert all(row["ok"] for row in data["results"])
    # all 3 gone from live, all restorable
    live = {row["id"] for row in client.get("/wiki/trash").json()["data"]["trash"]}
    assert set(ids) <= live


def test_bulk_one_bad_id_fail_soft(client):
    good = _note("Good").id
    r = client.post("/wiki/notes/bulk-delete", json={"ids": [good, 999999]})
    data = r.json()["data"]
    assert data["deletedCount"] == 1
    by_id = {row["id"]: row for row in data["results"]}
    assert by_id[good]["ok"] is True
    assert by_id[999999]["ok"] is False and by_id[999999]["error"]["code"] == "NOT_FOUND"


# --------------------------------------------------------------------------- #
# REST API — DELETE is soft, restore, trash list, 404                            #
# --------------------------------------------------------------------------- #
def test_rest_delete_is_soft_then_restore(client):
    nid = _note("RestDel", "body").id
    d = client.delete(f"/wiki/notes/{nid}")
    assert d.status_code == 200 and d.json()["data"]["deletedAt"]
    # gone from the tree/list but in trash
    trash_ids = {t["id"] for t in client.get("/wiki/trash").json()["data"]["trash"]}
    assert nid in trash_ids
    # restore
    r = client.post(f"/wiki/notes/{nid}/restore")
    assert r.status_code == 200 and r.json()["data"]["deletedAt"] is None
    assert nid not in {t["id"] for t in client.get("/wiki/trash").json()["data"]["trash"]}


def test_rest_restore_unknown_is_404(client):
    r = client.post("/wiki/notes/999999/restore")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_rest_trash_honest_empty(client):
    data = client.get("/wiki/trash").json()["data"]
    assert data == {"trash": [], "count": 0}


# --------------------------------------------------------------------------- #
# MCP delete + restore (subsumes #90-GAP2) — go through the proposal chokepoint    #
# --------------------------------------------------------------------------- #
def test_mcp_delete_and_restore(wiki_db):
    from modules.wiki.mcp import write_server as ws
    n = _note("MCP Target", "body")
    res = ws.wiki_delete_note(n.id)
    assert res["applied"] is True and res["noteId"] == n.id
    assert wsvc.get_note(n.id).deletedAt is not None       # soft-deleted via MCP
    res2 = ws.wiki_restore_note(n.id)
    assert res2["applied"] is True
    assert wsvc.get_note(n.id).deletedAt is None           # restored via MCP


def test_mcp_tools_registered(wiki_db):
    from modules.wiki.mcp import write_server as ws
    assert "wiki_delete_note" in ws.TOOLS and "wiki_restore_note" in ws.TOOLS
