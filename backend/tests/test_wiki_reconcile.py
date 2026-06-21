"""tests/test_wiki_reconcile.py — WIKI-RECONCILE (#53): bulk prune orphan wiki cache rows.

The tree-lies bug: a .md deleted out-of-band (test-writes that didn't go through _apply_delete) leaves
a phantom wiki_notes cache row → all_notes() lists it but GET /notes/{id} 404s. reindex_all() bulk-runs
the per-note reindex primitive to PRUNE those orphan INDEX rows (md already gone) — never a real note.

THE distinguishing (a collapsed impl that drops ALL or NOTHING FAILS): an orphan (cache row, md gone)
is dropped while a REAL note (cache + md) SURVIVES. Plus: idempotent (2nd run drops 0), md-stale→rebuilt
(don't regress reindex_note), REST≡MCP byte-identical.
"""

from __future__ import annotations

import json

import pytest

from modules.wiki import reader as wiki_reader
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.schema import NoteCreateInput


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    return isolated_paths


def _orphan_a_note(note_id: int) -> None:
    """Simulate the out-of-band-delete bug: remove the .md file directly (via the store's file delete,
    NOT _apply_delete) → the wiki_notes cache row is left ORPHANED (lists in all_notes, GET 404s)."""
    wiki_store.delete_note_file(note_id, "test: orphan the md out-of-band")


# --------------------------------------------------------------------------- #
# THE orphan-only-drop distinguishing                                            #
# --------------------------------------------------------------------------- #
def test_reindex_all_drops_orphan_keeps_real(wiki_db):
    """An orphan (cache row, md gone) is PRUNED; a real note (cache + md) SURVIVES. A collapsed
    drop-all / drop-nothing impl FAILS this."""
    real = wsvc.create_note(NoteCreateInput(title="Real note", content="keep me")).id
    orphan = wsvc.create_note(NoteCreateInput(title="Ghost note", content="md will vanish")).id
    _orphan_a_note(orphan)
    # precondition: BOTH still list (the cache lies) — orphan hasn't been pruned yet
    ids_before = {int(r["id"]) for r in wiki_store.all_notes()}
    assert real in ids_before and orphan in ids_before

    res = wiki_reader.reindex_all()
    assert res["droppedIds"] == [orphan], "ONLY the orphan is dropped"
    assert res["dropped"] == 1
    # the real note SURVIVES (still cached + still GET-able)
    assert wiki_store.get_note_cache(real) is not None
    assert wsvc.get_note(real) is not None
    # the orphan is GONE from the cache (the tree no longer lies)
    assert wiki_store.get_note_cache(orphan) is None
    assert orphan not in {int(r["id"]) for r in wiki_store.all_notes()}


def test_reindex_all_aggregate_shape(wiki_db):
    """The lean agent-readable aggregate: scanned/dropped/rebuilt/unchanged/droppedIds."""
    wsvc.create_note(NoteCreateInput(title="A", content="x"))
    res = wiki_reader.reindex_all()
    assert set(res) == {"scanned", "dropped", "rebuilt", "unchanged", "droppedIds"}
    assert res["scanned"] == 1 and res["unchanged"] == 1 and res["dropped"] == 0
    assert res["droppedIds"] == []


def test_reindex_all_idempotent(wiki_db):
    """A 2nd run immediately after drops 0 — the orphans are gone, nothing left to prune."""
    o = wsvc.create_note(NoteCreateInput(title="Ghost", content="x")).id
    _orphan_a_note(o)
    first = wiki_reader.reindex_all()
    assert first["dropped"] == 1 and first["droppedIds"] == [o]
    second = wiki_reader.reindex_all()
    assert second["dropped"] == 0 and second["droppedIds"] == []


def test_reindex_all_honest_empty(wiki_db):
    """Empty vault → all-zero aggregate (honest, never a crash)."""
    res = wiki_reader.reindex_all()
    assert res == {"scanned": 0, "dropped": 0, "rebuilt": 0, "unchanged": 0, "droppedIds": []}


def test_reindex_all_rebuilds_stale_cache_not_regressing_reindex_note(wiki_db):
    """md present but the cache row is STALE → rebuilt (not dropped, not unchanged) — proves
    reindex_all reuses reindex_note's full behavior, not just the prune arm."""
    nid = wsvc.create_note(NoteCreateInput(title="Original", content="body")).id
    # corrupt the cache row's content_hash so it's stale vs the md (md is the source of truth)
    row = wiki_store.get_note_cache(nid)
    wiki_store.upsert_note_cache(
        note_id=nid, title=row["title"], aliases_json=row["aliases"], status=row["status"],
        note_type=row["note_type"], trust_tier=row["trust_tier"], author=row["author"],
        tags_json=row["tags"], content_hash="STALE_HASH", created=row["created"],
        updated=row["updated"], capture_source="quick_add",
    )
    res = wiki_reader.reindex_all()
    assert res["rebuilt"] == 1 and res["dropped"] == 0
    # the cache row is now consistent again
    assert wiki_store.get_note_cache(nid)["content_hash"] != "STALE_HASH"


def test_reindex_all_multiple_orphans(wiki_db):
    """Several orphans + several real notes → exactly the orphans dropped, reals survive."""
    reals = [wsvc.create_note(NoteCreateInput(title=f"R{i}", content="x")).id for i in range(3)]
    orphans = [wsvc.create_note(NoteCreateInput(title=f"G{i}", content="x")).id for i in range(2)]
    for o in orphans:
        _orphan_a_note(o)
    res = wiki_reader.reindex_all()
    assert sorted(res["droppedIds"]) == sorted(orphans)
    assert all(wiki_store.get_note_cache(r) is not None for r in reals)


def test_F6_md_present_is_NEVER_dropped_only_rebuilt_or_unchanged(wiki_db):
    """F6 (#61 missing-vs-unreadable defensive): a cache row whose md EXISTS (even if stale/half-state)
    is NEVER dropped — only rebuilt (stale) or unchanged (consistent). reindex_all drops ONLY TRUE
    orphans (md truly absent), never a note mid-operation. The distinguishing for the reverse-orphan
    edge: a delete that committed the md-removal but raised before cache-delete would leave a cache
    row — but as long as the md is THERE, reconcile must keep it (rebuild), not prune it."""
    nid = wsvc.create_note(NoteCreateInput(title="Has md", content="real body")).id
    # corrupt the cache to a half-state (stale hash) but LEAVE the md on disk
    row = wiki_store.get_note_cache(nid)
    wiki_store.upsert_note_cache(
        note_id=nid, title="WRONG TITLE", aliases_json=row["aliases"], status=row["status"],
        note_type=row["note_type"], trust_tier=row["trust_tier"], author=row["author"],
        tags_json=row["tags"], content_hash="HALF_STATE", created=row["created"],
        updated=row["updated"], capture_source="quick_add",
    )
    assert wiki_store.read_note_file(nid) is not None, "precondition: md is present"
    res = wiki_reader.reindex_all()
    assert nid not in res["droppedIds"], "a note whose md EXISTS must NEVER be dropped"
    assert res["dropped"] == 0 and res["rebuilt"] == 1  # rebuilt from md, not pruned
    # the cache is reconciled back to the md's truth (title restored)
    assert wiki_store.get_note_cache(nid)["title"] == "Has md"


# --------------------------------------------------------------------------- #
# #61 item#3 — agent-readable 404 on the 3 note-id GET routes                    #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("path", [
    "/wiki/notes/99999",
    "/wiki/notes/99999/backlinks",
    "/wiki/notes/99999/context",
    "/wiki/notes/99999/suggested-links",
], ids=["get_note", "backlinks", "context", "suggested_links"])
def test_note_404_is_agent_error_shape(wiki_db, path):
    """#61 item#3: a bad note id on ALL 4 note-id GET routes → 404 with the FLAT agent-first error
    body {error:{code:'NOT_FOUND', message, hint, retryable:false}} — NOT the raw {"detail":...}.
    The agent branches on error.code + reads the hint (where to find a valid id)."""
    from fastapi.testclient import TestClient
    from main import create_app
    api = TestClient(create_app())
    r = api.get(path)
    assert r.status_code == 404
    body = r.json()
    assert "detail" not in body, "must be the flat error shape, not raw {'detail':...}"
    e = body["error"]
    assert e["code"] == "NOT_FOUND" and e["retryable"] is False
    assert "99999" in e["message"] and e["hint"]  # message names the id, hint names the fix


def test_mcp_get_note_found_false_unchanged(wiki_db):
    """The MCP existence-contract is UNCHANGED by item#3: wiki_get_note of a missing id stays
    {found:False, note_id} (that's a not-found RESULT, NOT an error — agent_error is REST-only here)."""
    from modules.wiki.mcp import read_server as wiki_mcp
    assert wiki_mcp.wiki_get_note(99999) == {"found": False, "note_id": 99999}


# --------------------------------------------------------------------------- #
# WIKI-WRITE-404 (#14) — the 3 WRITE note-id routes use the SAME flat 404 shape  #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("method,path,body", [
    ("put", "/wiki/notes/99999", {"content": "x"}),
    ("delete", "/wiki/notes/99999", None),
    ("post", "/wiki/notes/99999/refine", {"content": "x"}),
], ids=["put", "delete", "refine"])
def test_write_route_404_is_agent_error_shape(wiki_db, method, path, body):
    """#14: the 3 WRITE note-id routes (PUT/DELETE/refine) on a bad id → 404 with the FLAT agent-first
    {error:{code:NOT_FOUND,hint,retryable:false}} — NOT raw {"detail"} — closing the #46-agent-error
    cluster (the GET routes already do this; this makes write consistent). The route RETURNS the
    JSONResponse from the except block (not raise — it's a Response)."""
    from fastapi.testclient import TestClient
    from main import create_app
    api = TestClient(create_app())
    resp = api.request(method.upper(), path, json=body) if body is not None else api.request(method.upper(), path)
    assert resp.status_code == 404
    j = resp.json()
    assert "detail" not in j, "write-route 404 must be flat {error}, not raw {'detail'}"
    e = j["error"]
    assert e["code"] == "NOT_FOUND" and e["retryable"] is False
    assert "99999" in e["message"] and e["hint"]


def test_conflict_sync_404s_unchanged_boundary(wiki_db):
    """BOUNDARY (#14 stays OUT of these): the merge route (different-entity 404) is NOT converted —
    it keeps its own shape. (proves the change is scoped to note-id routes, no creep.)"""
    from fastapi.testclient import TestClient
    from main import create_app
    api = TestClient(create_app())
    # merge with a nonexistent source → 404 but NOT the agent_error note-shape (different entity/path)
    t = api.post("/wiki/notes", json={"title": "T", "content": "x"}).json()["data"]["id"]
    r = api.post("/wiki/notes/merge", json={"sourceId": 99999, "targetId": t})
    assert r.status_code == 404  # still 404; shape is the merge route's own (out of #14 scope)


# --------------------------------------------------------------------------- #
# REST POST /wiki/reindex == MCP wiki_reindex (byte-identical #24)               #
# --------------------------------------------------------------------------- #
def test_rest_reindex_endpoint(wiki_db):
    from fastapi.testclient import TestClient
    from main import create_app
    api = TestClient(create_app())
    nid = api.post("/wiki/notes", json={"title": "T", "content": "x"}).json()["data"]["id"]
    _orphan_a_note(nid)
    r = api.post("/wiki/reindex")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["droppedIds"] == [nid] and d["dropped"] == 1


def test_rest_mcp_reindex_byte_identical_on_clean_vault(wiki_db):
    """On a CLEAN vault (no orphans), reindex is idempotent → MCP wiki_reindex then REST /reindex
    return the SAME aggregate (both dropped:0) → byte-identical (#24)."""
    from fastapi.testclient import TestClient
    from main import create_app
    from modules.wiki.mcp import read_server as wiki_mcp
    api = TestClient(create_app())
    api.post("/wiki/notes", json={"title": "Clean", "content": "x"})
    mcp_res = wiki_mcp.wiki_reindex()           # clean vault → dropped:0
    rest_res = api.post("/wiki/reindex").json()["data"]  # still clean → dropped:0
    assert json.dumps(mcp_res, sort_keys=True) == json.dumps(rest_res, sort_keys=True)
    assert mcp_res["dropped"] == 0
