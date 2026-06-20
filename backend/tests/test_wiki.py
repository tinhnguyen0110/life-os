"""tests/test_wiki.py — Wiki module unit + API tests (Sprint W1a).

Coverage (T1 + T2 + T3):
  - T1 schema: defaults, Literal validation, title strip + max_length, partial update.
  - T1 store: wiki table init idempotent, next_note_id MAX+1 monotonic, cache
    upsert/get/delete, op_log append + recent_ops ordering.
  - T1 registry: wiki module auto-discovered + mounted at /wiki (no core edit).
  - T2 queue/CRUD: create→get→update→delete through the single-writer queue,
    id-gen monotonic + concurrent-unique, op_log faithful order, content-hash
    dirty-check no-op touch, fail-closed on md write error, API curl round-trip.
  - T3 reader: recent_ops shape/order, reindex_note seam (unchanged/rebuilt/
    missing_dropped).

Uses the shared ``isolated_paths`` fixture (tmp DATA_DIR + DB). Because that
fixture rebinds + closes the db connection, ``wiki_store.init_wiki_tables()`` must
run AFTER it to register wiki tables on the fresh per-test connection — the
``wiki_db`` fixture below does that.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from modules.wiki import schema as wiki_schema
from modules.wiki import store as wiki_store


@pytest.fixture
def wiki_db(isolated_paths):
    """isolated_paths + wiki tables registered on the fresh connection."""
    wiki_store.init_wiki_tables()
    return isolated_paths


# --------------------------------------------------------------------------- #
# schema                                                                       #
# --------------------------------------------------------------------------- #
def test_note_create_input_defaults():
    inp = wiki_schema.NoteCreateInput()
    assert inp.content == ""
    assert inp.title == ""
    assert inp.status == "fleeting"
    assert inp.noteType == "concept"
    assert inp.tags == []
    assert inp.author == "human"


def test_note_create_input_strips_title():
    inp = wiki_schema.NoteCreateInput(title="  Knowledge work accretes  ")
    assert inp.title == "Knowledge work accretes"


def test_note_create_input_title_max_length():
    with pytest.raises(ValidationError):
        wiki_schema.NoteCreateInput(title="x" * 201)


def test_note_create_input_rejects_bad_status():
    with pytest.raises(ValidationError):
        wiki_schema.NoteCreateInput(status="archived")  # not in Literal


def test_note_create_input_rejects_bad_note_type():
    with pytest.raises(ValidationError):
        wiki_schema.NoteCreateInput(noteType="diary")


def test_note_update_input_all_optional():
    inp = wiki_schema.NoteUpdateInput()
    assert inp.title is None
    assert inp.content is None
    assert inp.status is None
    assert inp.aliases is None


def test_note_update_input_strips_title_when_present():
    inp = wiki_schema.NoteUpdateInput(title="  refined  ")
    assert inp.title == "refined"


def test_note_update_input_rejects_bad_trust_tier():
    with pytest.raises(ValidationError):
        wiki_schema.NoteUpdateInput(trustTier="unknown")


def test_note_response_model_roundtrip():
    n = wiki_schema.Note(
        id=47, title="t", created="2026-06-13T00:00:00Z",
        updated="2026-06-13T00:00:00Z", contentHash="abc",
    )
    d = n.model_dump()
    assert d["id"] == 47
    assert d["status"] == "fleeting"
    assert d["trustTier"] == "verified"
    assert d["author"] == "human"
    assert d["aliases"] == []


# --------------------------------------------------------------------------- #
# store — id generation                                                        #
# --------------------------------------------------------------------------- #
def test_init_wiki_tables_idempotent(wiki_db):
    # Calling twice must not raise (CREATE TABLE IF NOT EXISTS).
    wiki_store.init_wiki_tables()
    wiki_store.init_wiki_tables()


def test_resolver_seam_tables_exist(wiki_db):
    # Addendum (c): the title→id + alias→id resolver SEAM must be stood up in W1a
    # so W1b's ghost-resolver plugs in without a schema change. Verify the table +
    # indexes exist (empty in W1a; W1b populates).
    from store import db

    conn = db.get_conn()
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "wiki_aliases" in tables
    indexes = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    ).fetchall()}
    assert "idx_wiki_notes_title" in indexes      # title→id path
    assert "idx_wiki_aliases_alias" in indexes    # alias→id path
    # Empty in W1a (no resolver logic yet — that's W1b).
    n = conn.execute("SELECT COUNT(*) AS c FROM wiki_aliases").fetchone()["c"]
    assert n == 0


def test_next_note_id_starts_at_one(wiki_db):
    assert wiki_store.next_note_id() == 1


def test_next_note_id_monotonic_after_inserts(wiki_db):
    assert wiki_store.next_note_id() == 1
    _insert_cache(1)
    assert wiki_store.next_note_id() == 2
    _insert_cache(2)
    assert wiki_store.next_note_id() == 3


def test_next_note_id_uses_max_not_count(wiki_db):
    # id 5 present but not 1-4 → next must be 6 (MAX+1), not 2 (COUNT+1).
    _insert_cache(5)
    assert wiki_store.next_note_id() == 6


# --------------------------------------------------------------------------- #
# store — cache CRUD                                                           #
# --------------------------------------------------------------------------- #
def _insert_cache(note_id: int, *, title: str = "t", content_hash: str = "h"):
    wiki_store.upsert_note_cache(
        note_id=note_id, title=title, aliases_json="[]", status="fleeting",
        note_type="concept", trust_tier="verified", author="human", tags_json="[]",
        content_hash=content_hash, created="2026-06-13T00:00:00Z",
        updated="2026-06-13T00:00:00Z",
    )


def test_upsert_then_get_cache(wiki_db):
    _insert_cache(1, title="hello")
    row = wiki_store.get_note_cache(1)
    assert row is not None
    assert row["id"] == 1
    assert row["title"] == "hello"
    assert row["status"] == "fleeting"


def test_get_cache_missing_returns_none(wiki_db):
    assert wiki_store.get_note_cache(999) is None


def test_upsert_updates_existing_row(wiki_db):
    _insert_cache(1, title="old", content_hash="h1")
    wiki_store.upsert_note_cache(
        note_id=1, title="new", aliases_json="[]", status="developing",
        note_type="concept", trust_tier="verified", author="human", tags_json="[]",
        content_hash="h2", created="2026-06-13T00:00:00Z",
        updated="2026-06-13T01:00:00Z",
    )
    row = wiki_store.get_note_cache(1)
    assert row["title"] == "new"
    assert row["status"] == "developing"
    assert row["content_hash"] == "h2"
    # MAX(id) still 1 → no duplicate row created.
    assert wiki_store.next_note_id() == 2


def test_delete_cache_removes_row(wiki_db):
    _insert_cache(1)
    assert wiki_store.note_cache_exists(1)
    assert wiki_store.delete_note_cache(1) is True
    assert not wiki_store.note_cache_exists(1)


def test_delete_missing_cache_returns_false(wiki_db):
    assert wiki_store.delete_note_cache(404) is False


# --------------------------------------------------------------------------- #
# store — op_log (append-only, ordered)                                        #
# --------------------------------------------------------------------------- #
def test_append_op_and_recent_ops_ordered(wiki_db):
    wiki_store.append_op(op_id="op1", kind="create", note_id=1, actor="human",
                         ts="2026-06-13T00:00:00Z", commit_sha="sha1")
    wiki_store.append_op(op_id="op2", kind="edit", note_id=1, actor="human",
                         ts="2026-06-13T00:01:00Z", commit_sha="sha2")
    wiki_store.append_op(op_id="op3", kind="delete", note_id=1, actor="human",
                         ts="2026-06-13T00:02:00Z", commit_sha="sha3")
    ops = wiki_store.recent_ops(limit=10)
    # newest-first
    assert [o["kind"] for o in ops] == ["delete", "edit", "create"]
    # seq strictly increasing in insert order
    seqs = [o["seq"] for o in ops]
    assert seqs == sorted(seqs, reverse=True)
    assert ops[-1]["op_id"] == "op1"
    assert ops[0]["commit_sha"] == "sha3"


def test_recent_ops_respects_limit(wiki_db):
    for i in range(5):
        wiki_store.append_op(op_id=f"op{i}", kind="create", note_id=i,
                             actor="human", ts=f"2026-06-13T00:0{i}:00Z")
    ops = wiki_store.recent_ops(limit=3)
    assert len(ops) == 3


def test_recent_ops_empty(wiki_db):
    assert wiki_store.recent_ops() == []


# --------------------------------------------------------------------------- #
# store — path helpers                                                         #
# --------------------------------------------------------------------------- #
def test_note_rel_path():
    assert wiki_store.note_rel_path(47) == "wiki/notes/47.md"


# --------------------------------------------------------------------------- #
# registry — module auto-discovered + mounted (no core edit)                  #
# --------------------------------------------------------------------------- #
def test_wiki_module_mounted(wiki_db):
    from main import create_app

    app = create_app()
    client = TestClient(app)
    # /health lists the wiki module among discovered modules.
    health = client.get("/health").json()
    assert "wiki" in health["data"]["modules"]
    # GET /wiki is reachable (the T1 info endpoint).
    r = client.get("/wiki")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["module"] == "wiki"


# =========================================================================== #
# T2 — changes-queue / single-writer + CRUD                                    #
# =========================================================================== #
from modules.wiki import service as wiki_service  # noqa: E402
from modules.wiki.schema import NoteCreateInput, NoteUpdateInput  # noqa: E402


# --- service: create / get round-trip through the queue --------------------- #
def test_create_note_returns_note_with_id(wiki_db):
    note = wiki_service.create_note(NoteCreateInput(content="raw dump", title="t1"))
    assert note.id == 1
    assert note.title == "t1"
    assert note.content == "raw dump"
    assert note.status == "fleeting"
    assert note.trustTier == "verified"
    assert note.created == note.updated
    assert note.contentHash  # sha256 of body, non-empty


def test_create_then_get_reflects(wiki_db):
    created = wiki_service.create_note(NoteCreateInput(content="hello body"))
    got = wiki_service.get_note(created.id)
    assert got is not None
    assert got.id == created.id
    assert got.content == "hello body"
    assert got.contentHash == created.contentHash


def test_get_missing_returns_none(wiki_db):
    assert wiki_service.get_note(999) is None


def test_id_gen_monotonic_across_creates(wiki_db):
    ids = [wiki_service.create_note(NoteCreateInput(content=f"n{i}")).id for i in range(5)]
    assert ids == [1, 2, 3, 4, 5]


# --- service: queue applies ops IN ORDER (op_log faithful replay) ----------- #
def test_op_log_records_create_then_edit_in_order(wiki_db):
    note = wiki_service.create_note(NoteCreateInput(content="v1"))
    wiki_service.update_note(note.id, NoteUpdateInput(content="v2"))
    ops = wiki_store.recent_ops(limit=10)
    # newest-first → [edit, create]
    assert [o["kind"] for o in ops] == ["edit", "create"]
    assert all(o["note_id"] == note.id for o in ops)
    # both carry a commit sha (audit trail op → git)
    assert all(o["commit_sha"] for o in ops)


def test_concurrent_creates_get_unique_ids(wiki_db):
    # Many threads create at once; the single writer must still hand out unique,
    # contiguous ids (no race in MAX+1 because the queue serializes).
    import threading as _t

    results: list[int] = []
    rlock = _t.Lock()

    def _mk():
        n = wiki_service.create_note(NoteCreateInput(content="x"))
        with rlock:
            results.append(n.id)

    threads = [_t.Thread(target=_mk) for _ in range(10)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert sorted(results) == list(range(1, 11))  # 10 unique contiguous ids
    assert len(set(results)) == 10


# --- service: update partial + content-hash dirty-check (A5) ---------------- #
def test_update_partial_preserves_unset_fields(wiki_db):
    note = wiki_service.create_note(
        NoteCreateInput(content="body", title="orig", tags=["a"])
    )
    updated = wiki_service.update_note(note.id, NoteUpdateInput(status="developing"))
    assert updated.status == "developing"
    assert updated.title == "orig"        # unchanged
    assert updated.content == "body"      # unchanged
    assert updated.tags == ["a"]          # unchanged
    assert updated.created == note.created  # created preserved


def test_update_bumps_updated_on_real_edit(wiki_db):
    note = wiki_service.create_note(NoteCreateInput(content="v1"))
    updated = wiki_service.update_note(note.id, NoteUpdateInput(content="v2 changed"))
    assert updated.content == "v2 changed"
    assert updated.updated >= note.updated
    assert updated.contentHash != note.contentHash


def test_update_noop_touch_makes_no_new_op(wiki_db):
    note = wiki_service.create_note(NoteCreateInput(content="same", title="t"))
    ops_before = len(wiki_store.recent_ops(limit=100))
    # Same body + same frontmatter → no-op touch: no new commit, no op_log row.
    same = wiki_service.update_note(
        note.id, NoteUpdateInput(content="same", title="t")
    )
    ops_after = len(wiki_store.recent_ops(limit=100))
    assert ops_after == ops_before            # NO new op_log row
    assert same.updated == note.updated       # updated NOT bumped
    assert same.contentHash == note.contentHash


def test_update_missing_raises_not_found(wiki_db):
    with pytest.raises(wiki_service.NoteNotFound):
        wiki_service.update_note(404, NoteUpdateInput(content="x"))


# --- service: delete (A4) --------------------------------------------------- #
def test_delete_removes_note_and_cache_keeps_oplog(wiki_db):
    note = wiki_service.create_note(NoteCreateInput(content="bye"))
    wiki_service.delete_note(note.id)
    assert wiki_service.get_note(note.id) is None          # md file gone
    assert wiki_store.get_note_cache(note.id) is None       # cache row hard-deleted
    ops = wiki_store.recent_ops(limit=10)
    # op_log RETAINS the delete record (+ the original create)
    assert [o["kind"] for o in ops] == ["delete", "create"]


def test_delete_missing_raises_not_found(wiki_db):
    with pytest.raises(wiki_service.NoteNotFound):
        wiki_service.delete_note(999)


# --- service: fail-closed on md write error (A2) ---------------------------- #
def test_create_fails_closed_on_md_write_error(wiki_db, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(wiki_store, "write_note_file", _boom)
    with pytest.raises(RuntimeError, match="disk full"):
        wiki_service.create_note(NoteCreateInput(content="x"))
    # Nothing partially applied: no cache row, no op_log row for the failed op.
    assert wiki_store.get_note_cache(1) is None
    assert wiki_store.recent_ops(limit=10) == []


# --- API: CRUD round-trip through the HTTP layer ---------------------------- #
@pytest.fixture
def api(wiki_db):
    from main import create_app

    return TestClient(create_app())


def test_api_create_get_update_delete_roundtrip(api):
    # CREATE
    r = api.post("/wiki/notes", json={"content": "api body", "title": "api note"})
    assert r.status_code == 200
    data = r.json()["data"]
    nid = data["id"]
    assert data["title"] == "api note"
    assert data["status"] == "fleeting"

    # GET reflects
    g = api.get(f"/wiki/notes/{nid}")
    assert g.status_code == 200
    assert g.json()["data"]["content"] == "api body"

    # PUT edits + GET reflects the edit (write-form round-trip)
    p = api.put(f"/wiki/notes/{nid}", json={"content": "edited body", "status": "evergreen"})
    assert p.status_code == 200
    assert p.json()["data"]["status"] == "evergreen"
    g2 = api.get(f"/wiki/notes/{nid}")
    assert g2.json()["data"]["content"] == "edited body"
    assert g2.json()["data"]["status"] == "evergreen"

    # DELETE + GET 404
    d = api.delete(f"/wiki/notes/{nid}")
    assert d.status_code == 200
    assert d.json()["data"]["deleted"] == nid
    assert api.get(f"/wiki/notes/{nid}").status_code == 404


def test_api_get_missing_404(api):
    assert api.get("/wiki/notes/12345").status_code == 404


def test_api_update_missing_404(api):
    assert api.put("/wiki/notes/12345", json={"content": "x"}).status_code == 404


def test_api_delete_missing_404(api):
    assert api.delete("/wiki/notes/12345").status_code == 404


def test_api_create_rejects_bad_status_422(api):
    r = api.post("/wiki/notes", json={"content": "x", "status": "archived"})
    assert r.status_code == 422


def test_api_create_title_too_long_422(api):
    r = api.post("/wiki/notes", json={"content": "x", "title": "z" * 201})
    assert r.status_code == 422


def test_api_create_defaults_fleeting_empty_title(api):
    # Raw capture: no title, defaults to fleeting.
    r = api.post("/wiki/notes", json={"content": "just a dump"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["title"] == ""
    assert data["status"] == "fleeting"


# =========================================================================== #
# T3 — op_log read seam + reindex seam (reader.py)                              #
# =========================================================================== #
from modules.wiki import reader as wiki_reader  # noqa: E402


def test_recent_ops_shape_and_order(wiki_db):
    note = wiki_service.create_note(NoteCreateInput(content="v1"))
    wiki_service.update_note(note.id, NoteUpdateInput(content="v2"))
    ops = wiki_reader.recent_ops(limit=10)
    assert [o["kind"] for o in ops] == ["edit", "create"]  # newest-first
    # camelCase keys for the API/feed; commitSha present
    first = ops[0]
    assert set(first) == {"seq", "op_id", "kind", "noteId", "actor", "ts", "commitSha", "detail"}
    assert first["noteId"] == note.id
    assert first["actor"] == "human"
    assert first["commitSha"]


def test_reader_recent_ops_empty(wiki_db):
    assert wiki_reader.recent_ops() == []


def test_reindex_unchanged_when_cache_matches(wiki_db):
    note = wiki_service.create_note(NoteCreateInput(content="body", title="t"))
    # Cache was written by the create — reindex should find it already consistent.
    res = wiki_reader.reindex_note(note.id)
    assert res == {"noteId": note.id, "action": "unchanged"}


def test_reindex_rebuilds_dropped_cache_row(wiki_db):
    note = wiki_service.create_note(NoteCreateInput(content="body", title="t"))
    # Simulate a dropped/disposable cache row (md file remains the source of truth).
    wiki_store.delete_note_cache(note.id)
    assert wiki_store.get_note_cache(note.id) is None
    res = wiki_reader.reindex_note(note.id)
    assert res == {"noteId": note.id, "action": "rebuilt"}
    row = wiki_store.get_note_cache(note.id)
    assert row is not None
    assert row["title"] == "t"
    assert row["content_hash"] == note.contentHash


def test_reindex_drops_stale_cache_when_md_missing(wiki_db):
    note = wiki_service.create_note(NoteCreateInput(content="body"))
    # Remove the md file out-of-band but leave the cache row → reindex must drop it.
    wiki_store.delete_note_file(note.id, "out-of-band removal")
    assert wiki_store.get_note_cache(note.id) is not None  # cache row still there
    res = wiki_reader.reindex_note(note.id)
    assert res == {"noteId": note.id, "action": "missing_dropped"}
    assert wiki_store.get_note_cache(note.id) is None


def test_reindex_missing_everywhere_is_unchanged(wiki_db):
    # No md, no cache → nothing to do.
    res = wiki_reader.reindex_note(999)
    assert res == {"noteId": 999, "action": "unchanged"}


# =========================================================================== #
# W1b-T1 — wikilink parser + resolver + edge persistence                       #
# =========================================================================== #
def _links_of(source_id: int) -> list[dict]:
    return [dict(r) for r in wiki_store.links_from(source_id)]


# --- B1: parse_wikilinks (4 forms + dedup + edge cases) --------------------- #
def test_parse_id_link():
    out = wiki_service.parse_wikilinks("see [[47]] here")
    assert out == [{"target_id": 47, "target_title": None, "display": None}]


def test_parse_id_link_with_display():
    out = wiki_service.parse_wikilinks("see [[47|Knowledge work]] here")
    assert out == [{"target_id": 47, "target_title": None, "display": "Knowledge work"}]


def test_parse_title_link():
    out = wiki_service.parse_wikilinks("see [[Atomicity principle]] here")
    assert out == [{"target_id": None, "target_title": "Atomicity principle", "display": None}]


def test_parse_title_link_with_display():
    out = wiki_service.parse_wikilinks("[[Atomicity principle|atoms]]")
    assert out == [{"target_id": None, "target_title": "Atomicity principle", "display": "atoms"}]


def test_parse_multiple_and_dedup():
    out = wiki_service.parse_wikilinks("[[47]] and [[88]] and [[47|again]]")
    # 47 deduped to one (first occurrence's display=None wins); 88 separate.
    assert len(out) == 2
    ids = {o["target_id"] for o in out}
    assert ids == {47, 88}


def test_parse_empty_and_malformed_skipped():
    assert wiki_service.parse_wikilinks("no links here") == []
    assert wiki_service.parse_wikilinks("[[]] and [[ | x]]") == []
    assert wiki_service.parse_wikilinks("") == []


# --- B2: resolver (case-insensitive, collision→lowest id) ------------------- #
def test_resolve_title_hit_and_miss(wiki_db):
    n = wiki_service.create_note(NoteCreateInput(title="Atomicity principle", content="x"))
    assert wiki_store.resolve_title("Atomicity principle") == n.id
    assert wiki_store.resolve_title("Nonexistent") is None


def test_resolve_title_case_insensitive(wiki_db):
    n = wiki_service.create_note(NoteCreateInput(title="Knowledge Work", content="x"))
    assert wiki_store.resolve_title("knowledge work") == n.id
    assert wiki_store.resolve_title("KNOWLEDGE WORK") == n.id


def test_resolve_title_collision_returns_lowest_id(wiki_db):
    a = wiki_service.create_note(NoteCreateInput(title="Dup Title", content="x"))
    b = wiki_service.create_note(NoteCreateInput(title="Dup Title", content="y"))
    assert a.id < b.id
    assert wiki_store.resolve_title("Dup Title") == a.id  # lowest id
    assert wiki_store.resolve_title_count("Dup Title") == 2


def test_alias_index_populated_on_create(wiki_db):
    n = wiki_service.create_note(NoteCreateInput(title="Has Title", content="x"))
    # title indexed; empty-title note would not be.
    assert wiki_store.resolve_title("Has Title") == n.id


def test_empty_title_not_indexed(wiki_db):
    n = wiki_service.create_note(NoteCreateInput(content="raw dump, no title"))
    assert n.title == ""
    assert wiki_store.resolve_title("") is None


# --- B2: edge persistence + re-derive on write ------------------------------ #
def test_edges_derived_on_create_id_link(wiki_db):
    target = wiki_service.create_note(NoteCreateInput(title="target", content="t"))
    src = wiki_service.create_note(NoteCreateInput(content=f"link to [[{target.id}]]"))
    links = _links_of(src.id)
    assert len(links) == 1
    assert links[0]["target_id"] == target.id
    assert links[0]["is_resolved"] == 1


def test_edges_title_link_resolves(wiki_db):
    target = wiki_service.create_note(NoteCreateInput(title="Concept X", content="t"))
    src = wiki_service.create_note(NoteCreateInput(content="ref [[Concept X]]"))
    links = _links_of(src.id)
    assert len(links) == 1
    assert links[0]["target_id"] == target.id
    assert links[0]["is_resolved"] == 1


def test_edges_ghost_when_target_absent(wiki_db):
    src = wiki_service.create_note(NoteCreateInput(content="ref [[Nonexistent Note]]"))
    links = _links_of(src.id)
    assert len(links) == 1
    assert links[0]["target_id"] is None
    assert links[0]["target_title"] == "Nonexistent Note"
    assert links[0]["is_resolved"] == 0


def test_edges_default_type_relates(wiki_db):
    target = wiki_service.create_note(NoteCreateInput(title="t", content="x"))
    src = wiki_service.create_note(NoteCreateInput(content=f"[[{target.id}]]"))
    assert _links_of(src.id)[0]["type"] == "relates"


def test_edges_rederived_on_edit(wiki_db):
    a = wiki_service.create_note(NoteCreateInput(title="A", content="a"))
    b = wiki_service.create_note(NoteCreateInput(title="B", content="b"))
    src = wiki_service.create_note(NoteCreateInput(content=f"[[{a.id}]]"))
    assert {l["target_id"] for l in _links_of(src.id)} == {a.id}
    # Edit body to point at b instead → edges re-derived (old a-edge gone).
    wiki_service.update_note(src.id, NoteUpdateInput(content=f"now [[{b.id}]]"))
    assert {l["target_id"] for l in _links_of(src.id)} == {b.id}


def test_edges_cleared_when_body_loses_links(wiki_db):
    a = wiki_service.create_note(NoteCreateInput(title="A", content="a"))
    src = wiki_service.create_note(NoteCreateInput(content=f"[[{a.id}]]"))
    assert len(_links_of(src.id)) == 1
    wiki_service.update_note(src.id, NoteUpdateInput(content="no more links"))
    assert _links_of(src.id) == []


def test_self_link_no_crash(wiki_db):
    n = wiki_service.create_note(NoteCreateInput(title="self", content="x"))
    wiki_service.update_note(n.id, NoteUpdateInput(content=f"I link [[{n.id}]] myself"))
    links = _links_of(n.id)
    assert len(links) == 1
    assert links[0]["target_id"] == n.id  # self-edge persisted, no crash


def test_circular_link_no_crash(wiki_db):
    a = wiki_service.create_note(NoteCreateInput(title="A", content="start"))
    b = wiki_service.create_note(NoteCreateInput(title="B", content=f"[[{a.id}]]"))
    wiki_service.update_note(a.id, NoteUpdateInput(content=f"[[{b.id}]]"))
    # a→b and b→a both persisted, no infinite loop.
    assert {l["target_id"] for l in _links_of(a.id)} == {b.id}
    assert {l["target_id"] for l in _links_of(b.id)} == {a.id}


def test_delete_clears_own_edges_and_ghostifies_inbound(wiki_db):
    target = wiki_service.create_note(NoteCreateInput(title="Target Note", content="t"))
    src = wiki_service.create_note(NoteCreateInput(content=f"[[{target.id}]]"))
    # src→target resolved
    assert _links_of(src.id)[0]["is_resolved"] == 1
    wiki_service.delete_note(target.id)
    # target's own edges gone; src's inbound edge ghostified (keeps target title)
    link = _links_of(src.id)[0]
    assert link["target_id"] is None
    assert link["is_resolved"] == 0
    assert link["target_title"] == "Target Note"


# =========================================================================== #
# W1b-T2 — backlinks + ghost auto-resolve + rename-no-rewrite                   #
# =========================================================================== #
# --- B3: backlinks (linked + outbound + ghost) ------------------------------ #
def test_backlinks_linked_mentions(wiki_db):
    target = wiki_service.create_note(NoteCreateInput(title="Target", content="t"))
    src = wiki_service.create_note(
        NoteCreateInput(title="Source", content=f"context before [[{target.id}]] context after")
    )
    bl = wiki_reader.backlinks(target.id)
    assert len(bl["linked"]) == 1
    assert bl["linked"][0]["id"] == src.id
    assert bl["linked"][0]["title"] == "Source"
    assert str(target.id) in bl["linked"][0]["snippet"] or "context" in bl["linked"][0]["snippet"]
    assert bl["unlinked"] == []  # W1b: deferred to W1c


def test_backlinks_snippet_finds_title_form_link(wiki_db):
    # The source links by TITLE ([[Target]]), not by id — the snippet finder must
    # still locate the mention (it resolves via the target's title, not just id).
    target = wiki_service.create_note(NoteCreateInput(title="Target", content="t"))
    wiki_service.create_note(
        NoteCreateInput(content="some text [[Target]] more text")
    )
    bl = wiki_reader.backlinks(target.id)
    assert len(bl["linked"]) == 1
    assert "Target" in bl["linked"][0]["snippet"]


def test_backlinks_linked_dedup_by_source(wiki_db):
    target = wiki_service.create_note(NoteCreateInput(title="Target", content="t"))
    # one source links the target twice → ONE linked row (deduped by source).
    src = wiki_service.create_note(
        NoteCreateInput(content=f"[[{target.id}]] and again [[{target.id}|x]]")
    )
    bl = wiki_reader.backlinks(target.id)
    assert len(bl["linked"]) == 1
    assert bl["linked"][0]["id"] == src.id


def test_backlinks_outbound_resolved_and_ghost(wiki_db):
    target = wiki_service.create_note(NoteCreateInput(title="Exists", content="t"))
    src = wiki_service.create_note(
        NoteCreateInput(content=f"[[{target.id}]] and [[Does Not Exist]]")
    )
    bl = wiki_reader.backlinks(src.id)
    out = bl["outbound"]
    resolved = [o for o in out if o.get("isResolved")]
    ghosts = [o for o in out if not o.get("isResolved")]
    assert len(resolved) == 1 and resolved[0]["id"] == target.id and resolved[0]["title"] == "Exists"
    assert len(ghosts) == 1 and ghosts[0]["ghost"] == "Does Not Exist"


def test_backlinks_empty_for_unlinked_note(wiki_db):
    n = wiki_service.create_note(NoteCreateInput(title="Lonely", content="no links"))
    bl = wiki_reader.backlinks(n.id)
    assert bl == {"linked": [], "unlinked": [], "outbound": []}


# --- B4: ghost auto-resolve on create + on rename --------------------------- #
def test_ghost_auto_resolves_on_target_create(wiki_db):
    # src links a title that doesn't exist yet → ghost.
    src = wiki_service.create_note(NoteCreateInput(content="ref [[Atomicity principle]]"))
    assert _links_of(src.id)[0]["is_resolved"] == 0
    # create the note with that title → the ghost flips to resolved.
    target = wiki_service.create_note(NoteCreateInput(title="Atomicity principle", content="x"))
    link = _links_of(src.id)[0]
    assert link["is_resolved"] == 1
    assert link["target_id"] == target.id
    assert link["target_title"] is None


def test_ghost_auto_resolves_case_insensitive(wiki_db):
    src = wiki_service.create_note(NoteCreateInput(content="[[knowledge WORK]]"))
    assert _links_of(src.id)[0]["is_resolved"] == 0
    target = wiki_service.create_note(NoteCreateInput(title="Knowledge Work", content="x"))
    assert _links_of(src.id)[0]["target_id"] == target.id


def test_ghost_auto_resolves_on_rename(wiki_db):
    src = wiki_service.create_note(NoteCreateInput(content="[[Final Title]]"))
    other = wiki_service.create_note(NoteCreateInput(title="Old Title", content="x"))
    assert _links_of(src.id)[0]["is_resolved"] == 0  # still ghost
    # rename other → "Final Title" → ghost auto-resolves to it.
    wiki_service.update_note(other.id, NoteUpdateInput(title="Final Title"))
    link = _links_of(src.id)[0]
    assert link["is_resolved"] == 1
    assert link["target_id"] == other.id


def test_ghost_auto_resolves_via_alias(wiki_db):
    src = wiki_service.create_note(NoteCreateInput(content="[[the accretion model]]"))
    assert _links_of(src.id)[0]["is_resolved"] == 0
    target = wiki_service.create_note(NoteCreateInput(title="Knowledge work", content="x"))
    # add the alias via update → ghost resolves on the alias match.
    wiki_service.update_note(target.id, NoteUpdateInput(aliases=["the accretion model"]))
    link = _links_of(src.id)[0]
    assert link["is_resolved"] == 1
    assert link["target_id"] == target.id


# --- D1: rename-no-rewrite teeth (THE invariant) ---------------------------- #
def test_rename_does_not_rewrite_inbound_links(wiki_db):
    target = wiki_service.create_note(NoteCreateInput(title="Original", content="t"))
    src = wiki_service.create_note(NoteCreateInput(content=f"link [[{target.id}]] here"))
    before = _links_of(src.id)
    assert before[0]["target_id"] == target.id and before[0]["is_resolved"] == 1
    src_body_before = wiki_store.read_note_file(src.id)

    # Rename target's title 3×. Inbound links point at the ID → must NOT change.
    for new_title in ("Renamed Once", "Renamed Twice", "Final Name"):
        wiki_service.update_note(target.id, NoteUpdateInput(title=new_title))

    after = _links_of(src.id)
    assert after[0]["target_id"] == target.id  # still points at the id
    assert after[0]["is_resolved"] == 1        # still resolved
    assert len(after) == len(before)           # 0 extra/rewritten link rows
    # The SOURCE note's body+links were never touched by the rename (id-stable).
    assert wiki_store.read_note_file(src.id) == src_body_before


# --- API: backlinks endpoint ------------------------------------------------ #
def test_api_backlinks_endpoint(api):
    t = api.post("/wiki/notes", json={"title": "T", "content": "x"}).json()["data"]["id"]
    s = api.post("/wiki/notes", json={"content": f"[[{t}]] and [[Ghosty]]"}).json()["data"]["id"]
    r = api.get(f"/wiki/notes/{t}/backlinks")
    assert r.status_code == 200
    data = r.json()["data"]
    assert {"linked", "unlinked", "outbound"} == set(data)
    assert data["linked"][0]["id"] == s

    r2 = api.get(f"/wiki/notes/{s}/backlinks")
    out = r2.json()["data"]["outbound"]
    assert any(o.get("ghost") == "Ghosty" for o in out)


def test_api_backlinks_404_missing(api):
    assert api.get("/wiki/notes/9999/backlinks").status_code == 404


# --- API: context endpoint (WIKI-RETRIEVAL-3 #23) --------------------------- #
def test_api_context_endpoint(api):
    """GET /wiki/notes/{id}/context → the composed {found, note_id, graph, backlinks} in one call."""
    t = api.post("/wiki/notes", json={"title": "Ctx target", "content": "x"}).json()["data"]["id"]
    s = api.post("/wiki/notes", json={"content": f"see [[{t}]]"}).json()["data"]["id"]
    r = api.get(f"/wiki/notes/{t}/context")
    assert r.status_code == 200
    data = r.json()["data"]
    assert set(data) == {"found", "note_id", "graph", "backlinks"}
    assert data["found"] is True and data["note_id"] == t
    assert set(data["graph"]) == {"center", "nodes", "edges", "clusters"}
    assert set(data["backlinks"]) == {"linked", "unlinked", "outbound"}
    # the linked backlink resolves to the source note (real composed data, not a stub)
    assert data["backlinks"]["linked"][0]["id"] == s


def test_api_context_404_missing(api):
    assert api.get("/wiki/notes/9999/context").status_code == 404


def test_api_context_byte_identical_to_mcp(api):
    """THE #24 invariant: REST /wiki/notes/{id}/context ``data`` is BYTE-IDENTICAL to the MCP
    wiki_context(id) present payload — both call the SAME reader.context, so consolidation keeps
    REST≡MCP parity (no drift between the two surfaces)."""
    import json
    from modules.wiki.mcp import read_server as wiki_mcp  # noqa: E402

    t = api.post("/wiki/notes", json={"title": "Parity", "content": "x"}).json()["data"]["id"]
    api.post("/wiki/notes", json={"content": f"[[{t}]]"})
    rest_data = api.get(f"/wiki/notes/{t}/context").json()["data"]
    mcp_data = wiki_mcp.wiki_context(t)
    assert json.dumps(rest_data, sort_keys=True) == json.dumps(mcp_data, sort_keys=True)


# =========================================================================== #
# W1b-T3 — D6 merge tombstone + D10 archive-never-orphans                      #
# =========================================================================== #
# --- B5: merge → source gone + redirect + inbound repointed ----------------- #
def test_merge_deletes_source_writes_redirect(wiki_db):
    src = wiki_service.create_note(NoteCreateInput(title="Dupe A", content="a"))
    tgt = wiki_service.create_note(NoteCreateInput(title="Canonical", content="b"))
    result = wiki_service.merge_notes(src.id, tgt.id)
    assert result.id == tgt.id                          # returns the target
    assert wiki_service.get_note(src.id) is None         # source md gone
    assert wiki_store.get_note_cache(src.id) is None     # source cache gone
    assert wiki_store.get_redirect(src.id) == tgt.id     # redirect tombstone written


def test_merge_repoints_inbound_links(wiki_db):
    src = wiki_service.create_note(NoteCreateInput(title="Old", content="o"))
    tgt = wiki_service.create_note(NoteCreateInput(title="New", content="n"))
    linker = wiki_service.create_note(NoteCreateInput(content=f"cites [[{src.id}]]"))
    assert _links_of(linker.id)[0]["target_id"] == src.id
    wiki_service.merge_notes(src.id, tgt.id)
    # the inbound link now points at the target (citation survives, not ghosted)
    link = _links_of(linker.id)[0]
    assert link["target_id"] == tgt.id
    assert link["is_resolved"] == 1


def test_merge_records_op_log(wiki_db):
    src = wiki_service.create_note(NoteCreateInput(title="A", content="a"))
    tgt = wiki_service.create_note(NoteCreateInput(title="B", content="b"))
    wiki_service.merge_notes(src.id, tgt.id)
    ops = wiki_store.recent_ops(limit=5)
    assert ops[0]["kind"] == "merge"
    assert f"#{src.id}" in ops[0]["detail"] and f"#{tgt.id}" in ops[0]["detail"]


# --- B5: GET on tombstone → target + warning (NOT 404) ---------------------- #
def test_resolve_note_follows_redirect(wiki_db):
    src = wiki_service.create_note(NoteCreateInput(title="Source", content="s"))
    tgt = wiki_service.create_note(NoteCreateInput(title="Target", content="t"))
    wiki_service.merge_notes(src.id, tgt.id)
    note, warning = wiki_service.resolve_note(src.id)
    assert note is not None and note.id == tgt.id          # returns target
    assert warning is not None and str(tgt.id) in warning  # with a warning


def test_resolve_note_chained_redirect(wiki_db):
    a = wiki_service.create_note(NoteCreateInput(title="A", content="a"))
    b = wiki_service.create_note(NoteCreateInput(title="B", content="b"))
    c = wiki_service.create_note(NoteCreateInput(title="C", content="c"))
    wiki_service.merge_notes(a.id, b.id)   # a → b
    wiki_service.merge_notes(b.id, c.id)   # b → c  (so a → b → c)
    note, warning = wiki_service.resolve_note(a.id)
    assert note is not None and note.id == c.id            # followed the chain to c
    assert warning is not None


def test_resolve_note_absent_returns_none(wiki_db):
    note, warning = wiki_service.resolve_note(9999)
    assert note is None and warning is None


def test_follow_redirect_cycle_capped(wiki_db):
    # Construct a redirect cycle directly in the store (shouldn't happen via merge,
    # but the follower must not hang) — a→b, b→a.
    wiki_store.add_redirect(1, 2, "2026-06-13T00:00:00Z")
    wiki_store.add_redirect(2, 1, "2026-06-13T00:00:00Z")
    final, redirected = wiki_store.follow_redirect(1, max_depth=10)
    assert redirected is True
    assert final in (1, 2)  # terminates (cycle guard), does not hang


# --- B5: merge validation --------------------------------------------------- #
def test_merge_same_id_raises(wiki_db):
    n = wiki_service.create_note(NoteCreateInput(title="X", content="x"))
    with pytest.raises(wiki_service.MergeError):
        wiki_service.merge_notes(n.id, n.id)


def test_merge_missing_source_raises(wiki_db):
    tgt = wiki_service.create_note(NoteCreateInput(title="T", content="t"))
    with pytest.raises(wiki_service.NoteNotFound):
        wiki_service.merge_notes(999, tgt.id)


def test_merge_missing_target_raises(wiki_db):
    src = wiki_service.create_note(NoteCreateInput(title="S", content="s"))
    with pytest.raises(wiki_service.NoteNotFound):
        wiki_service.merge_notes(src.id, 999)


# --- D10: archive (status/facet change) NEVER orphans concept edges --------- #
def test_status_change_never_touches_links(wiki_db):
    """D10 invariant: changing a note's status/facet must NOT delete or orphan its
    concept edges. Tested via a status change (the only facet mutation in W1b) —
    there is NO code path from status → wiki_links deletion."""
    target = wiki_service.create_note(NoteCreateInput(title="Target", content="t"))
    src = wiki_service.create_note(NoteCreateInput(content=f"links [[{target.id}]]"))
    inbound_before = wiki_store.links_to(target.id)
    outbound_before = _links_of(src.id)
    assert len(inbound_before) == 1 and len(outbound_before) == 1

    # "Archive" the target by graduating its status (fleeting→evergreen). The body
    # is unchanged, so its own edges are unchanged; inbound edges must survive too.
    wiki_service.update_note(target.id, NoteUpdateInput(status="evergreen"))

    inbound_after = wiki_store.links_to(target.id)
    assert len(inbound_after) == 1                       # inbound edge survives
    assert inbound_after[0]["source_id"] == src.id
    assert inbound_after[0]["is_resolved"] == 1          # still resolved
    assert len(_links_of(src.id)) == 1                   # source's edge intact


def test_status_change_keeps_source_outbound_edges(wiki_db):
    """A note whose OWN status changes keeps its outbound edges (body unchanged →
    edges re-derived identically; status is orthogonal to the concept graph)."""
    target = wiki_service.create_note(NoteCreateInput(title="T", content="t"))
    src = wiki_service.create_note(NoteCreateInput(content=f"[[{target.id}]]"))
    wiki_service.update_note(src.id, NoteUpdateInput(status="developing"))
    links = _links_of(src.id)
    assert len(links) == 1 and links[0]["target_id"] == target.id and links[0]["is_resolved"] == 1


# --- API: merge endpoint ---------------------------------------------------- #
def test_api_merge_and_redirect(api):
    s = api.post("/wiki/notes", json={"title": "Src", "content": "s"}).json()["data"]["id"]
    t = api.post("/wiki/notes", json={"title": "Tgt", "content": "t"}).json()["data"]["id"]
    r = api.post("/wiki/notes/merge", json={"sourceId": s, "targetId": t})
    assert r.status_code == 200
    assert r.json()["data"]["id"] == t
    # GET old id → target + warning, NOT 404
    g = api.get(f"/wiki/notes/{s}")
    assert g.status_code == 200
    assert g.json()["data"]["id"] == t
    assert "merged" in (g.json().get("warning") or "")


def test_api_merge_same_id_422(api):
    n = api.post("/wiki/notes", json={"title": "X", "content": "x"}).json()["data"]["id"]
    assert api.post("/wiki/notes/merge", json={"sourceId": n, "targetId": n}).status_code == 422


def test_api_merge_missing_404(api):
    t = api.post("/wiki/notes", json={"title": "T", "content": "t"}).json()["data"]["id"]
    assert api.post("/wiki/notes/merge", json={"sourceId": 9999, "targetId": t}).status_code == 404


# =========================================================================== #
# W1c-T1 — FTS5 + search + unlinked-mentions                                    #
# =========================================================================== #
# --- C1: FTS index sync on write/delete ------------------------------------- #
def test_fts_indexed_on_create(wiki_db):
    wiki_service.create_note(
        NoteCreateInput(title="Knowledge work", content="the quick brown fox accretes")
    )
    rows = wiki_store.fts_search("accretes")
    assert len(rows) == 1
    assert rows[0]["title"] == "Knowledge work"


def test_fts_reindexed_on_edit(wiki_db):
    n = wiki_service.create_note(NoteCreateInput(title="T", content="original term alpha"))
    assert len(wiki_store.fts_search("alpha")) == 1
    wiki_service.update_note(n.id, NoteUpdateInput(content="replaced term beta"))
    # old term no longer matches; new term does (FTS row re-synced).
    assert wiki_store.fts_search("alpha") == []
    assert len(wiki_store.fts_search("beta")) == 1


def test_fts_row_removed_on_delete(wiki_db):
    n = wiki_service.create_note(NoteCreateInput(title="Gone", content="ephemeral content"))
    assert len(wiki_store.fts_search("ephemeral")) == 1
    wiki_service.delete_note(n.id)
    assert wiki_store.fts_search("ephemeral") == []


def test_fts_row_removed_on_merge(wiki_db):
    src = wiki_service.create_note(NoteCreateInput(title="Src", content="uniqueword zeta"))
    tgt = wiki_service.create_note(NoteCreateInput(title="Tgt", content="other"))
    wiki_service.merge_notes(src.id, tgt.id)
    assert wiki_store.fts_search("zeta") == []  # merged-away note's FTS row gone


# --- C1: search rank + snippet + sanitization ------------------------------- #
def test_search_returns_ranked_with_snippet(wiki_db):
    wiki_service.create_note(NoteCreateInput(title="Alpha note", content="mango mango mango"))
    wiki_service.create_note(NoteCreateInput(title="Beta note", content="mango once only"))
    results = wiki_reader.search("mango")
    assert len(results) == 2
    # WIKI-RETRIEVAL-2 (#22): the result shape is now {id,title,folder,snippet,score} — dropped
    # the unused `status`, added `folder` + the FTS `score` (agent sees WHY it ranked). Top-5 default.
    for r in results:
        assert set(r) == {"id", "title", "folder", "snippet", "score"}
    assert any("<b>mango</b>" in r["snippet"] for r in results)


def test_search_empty_query_returns_empty(wiki_db):
    wiki_service.create_note(NoteCreateInput(title="X", content="content"))
    assert wiki_reader.search("") == []
    assert wiki_reader.search("   ") == []


def test_search_bad_query_no_crash(wiki_db):
    wiki_service.create_note(NoteCreateInput(title="X", content="hello world"))
    # FTS5 syntax-breaking inputs must NOT raise — sanitized to safe tokens or [].
    bad_queries = ['"', "AND OR NOT", "((", "*", "a:b", '" OR 1=1 --', "NEAR(x"]
    for bad in bad_queries:
        out = wiki_reader.search(bad)
        assert isinstance(out, list)  # never raises


def test_search_matches_title_and_body(wiki_db):
    wiki_service.create_note(NoteCreateInput(title="Photosynthesis", content="plants"))
    wiki_service.create_note(NoteCreateInput(title="Other", content="about photosynthesis too"))
    # term in title (note 1) + in body (note 2) both match.
    assert len(wiki_reader.search("photosynthesis")) == 2


# --- C2: unlinked-mentions (excludes self + already-linked) ------------------ #
def test_unlinked_mention_found(wiki_db):
    target = wiki_service.create_note(NoteCreateInput(title="Emergence", content="t"))
    # another note mentions "Emergence" as plain text but does NOT link it.
    mentioner = wiki_service.create_note(
        NoteCreateInput(title="Essay", content="I discuss Emergence at length here")
    )
    um = wiki_reader.unlinked_mentions(target.id)
    assert any(u["id"] == mentioner.id for u in um)


def test_unlinked_excludes_self(wiki_db):
    n = wiki_service.create_note(
        NoteCreateInput(title="Recursion", content="Recursion mentions Recursion itself")
    )
    um = wiki_reader.unlinked_mentions(n.id)
    assert all(u["id"] != n.id for u in um)  # never lists itself


def test_unlinked_excludes_already_linked(wiki_db):
    target = wiki_service.create_note(NoteCreateInput(title="Linked Topic", content="t"))
    # this note LINKS the target (so it's a LINKED mention, not unlinked).
    linker = wiki_service.create_note(
        NoteCreateInput(content=f"see [[{target.id}]] about Linked Topic")
    )
    um = wiki_reader.unlinked_mentions(target.id)
    assert all(u["id"] != linker.id for u in um)  # already-linked excluded


def test_backlinks_unlinked_now_populated(wiki_db):
    target = wiki_service.create_note(NoteCreateInput(title="Populated Topic", content="t"))
    wiki_service.create_note(
        NoteCreateInput(title="Mentioner", content="a note about Populated Topic, unlinked")
    )
    bl = wiki_reader.backlinks(target.id)
    assert len(bl["unlinked"]) >= 1
    assert any("Populated Topic" in (u["snippet"] or "") or u["title"] == "Mentioner"
               for u in bl["unlinked"])


def test_unlinked_empty_for_titleless_note(wiki_db):
    n = wiki_service.create_note(NoteCreateInput(content="raw dump no title"))
    assert wiki_reader.unlinked_mentions(n.id) == []


# --- API: search endpoint --------------------------------------------------- #
def test_api_search_endpoint(api):
    api.post("/wiki/notes", json={"title": "Searchable", "content": "findme keyword"})
    r = api.get("/wiki/search", params={"q": "findme"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1 and data[0]["title"] == "Searchable"


def test_api_search_bad_query_200_not_500(api):
    api.post("/wiki/notes", json={"title": "X", "content": "y"})
    r = api.get("/wiki/search", params={"q": '" OR ((('})
    assert r.status_code == 200  # sanitized, never 500
    assert r.json()["data"] == [] or isinstance(r.json()["data"], list)


def test_api_search_empty_query(api):
    api.post("/wiki/notes", json={"title": "X", "content": "y"})
    assert api.get("/wiki/search", params={"q": ""}).json()["data"] == []


# =========================================================================== #
# W1c-T2 — ego-graph + overview + inbox readers                                #
# =========================================================================== #
def _link(src_id: int, tgt_id: int):
    """Helper: make src link tgt by id (through the queue)."""
    existing = wiki_service.get_note(src_id)
    body = (existing.content + f" [[{tgt_id}]]") if existing else f"[[{tgt_id}]]"
    wiki_service.update_note(src_id, NoteUpdateInput(content=body))


# --- C3: ego-graph BFS ------------------------------------------------------ #
def test_ego_graph_center_absent_returns_none(wiki_db):
    assert wiki_reader.ego_graph(999) is None


def test_ego_graph_depth1(wiki_db):
    center = wiki_service.create_note(NoteCreateInput(title="C", content="c"))
    a = wiki_service.create_note(NoteCreateInput(title="A", content="a"))
    b = wiki_service.create_note(NoteCreateInput(title="B", content="b"))
    _link(center.id, a.id)   # center → a
    _link(b.id, center.id)   # b → center
    g = wiki_reader.ego_graph(center.id, depth=1)
    ids = {n["id"] for n in g["nodes"]}
    assert ids == {center.id, a.id, b.id}   # 1-hop neighbors both directions
    assert g["center"] == center.id
    # W5a: clusters is now POPULATED (was [] in W1c). C-A + B-C = 2 edges among 3
    # nodes (density 0.667 ≥ threshold) → one detected cluster over these members.
    assert len(g["clusters"]) == 1
    assert {m["id"] for m in g["clusters"][0]["members"]} == {center.id, a.id, b.id}


def test_ego_graph_depth2_reaches_2hops(wiki_db):
    c = wiki_service.create_note(NoteCreateInput(title="C", content="c"))
    a = wiki_service.create_note(NoteCreateInput(title="A", content="a"))
    far = wiki_service.create_note(NoteCreateInput(title="Far", content="f"))
    _link(c.id, a.id)     # c → a
    _link(a.id, far.id)   # a → far  (far is 2 hops from c)
    g1 = wiki_reader.ego_graph(c.id, depth=1)
    assert far.id not in {n["id"] for n in g1["nodes"]}  # depth1 excludes far
    g2 = wiki_reader.ego_graph(c.id, depth=2)
    assert far.id in {n["id"] for n in g2["nodes"]}       # depth2 includes far


def test_ego_graph_degree_counted(wiki_db):
    c = wiki_service.create_note(NoteCreateInput(title="Hub", content="c"))
    a = wiki_service.create_note(NoteCreateInput(title="A", content="a"))
    b = wiki_service.create_note(NoteCreateInput(title="B", content="b"))
    _link(c.id, a.id)
    _link(c.id, b.id)
    g = wiki_reader.ego_graph(c.id, depth=1)
    hub = next(n for n in g["nodes"] if n["id"] == c.id)
    assert hub["degree"] == 2   # two outbound resolved edges


def test_ego_graph_ghost_not_a_node(wiki_db):
    c = wiki_service.create_note(NoteCreateInput(title="C", content="ref [[Nonexistent]]"))
    g = wiki_reader.ego_graph(c.id, depth=2)
    # ghost target is NOT materialized as a node; only the real center node exists.
    assert {n["id"] for n in g["nodes"]} == {c.id}
    # and the ghost edge is NOT in edges (edges are resolved-only between real nodes)
    assert g["edges"] == []


def test_ego_graph_edges_have_type_and_resolved(wiki_db):
    c = wiki_service.create_note(NoteCreateInput(title="C", content="c"))
    a = wiki_service.create_note(NoteCreateInput(title="A", content="a"))
    _link(c.id, a.id)
    g = wiki_reader.ego_graph(c.id, depth=1)
    assert len(g["edges"]) == 1
    e = g["edges"][0]
    assert e["source"] == c.id and e["target"] == a.id
    assert e["type"] == "relates" and e["isResolved"] is True


def test_ego_graph_200_notes_under_1s(wiki_db):
    import time
    # Build a star: 1 hub + 200 spokes each linking the hub.
    hub = wiki_service.create_note(NoteCreateInput(title="Hub", content="h"))
    for i in range(200):
        s = wiki_service.create_note(NoteCreateInput(title=f"S{i}", content=f"node {i}"))
        _link(s.id, hub.id)
    t0 = time.perf_counter()
    g = wiki_reader.ego_graph(hub.id, depth=2)
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0, f"200-note ego-graph took {elapsed:.3f}s (gate <1s)"
    assert len(g["nodes"]) == 201  # hub + 200 spokes


# --- C4: overview stats ----------------------------------------------------- #
def test_overview_empty_vault_pct_none_with_warning(wiki_db):
    data, warning = wiki_reader.overview()
    assert data["stats"]["totalNotes"] == 0
    assert data["stats"]["pctWithLink"] is None   # NOT 0, NOT div-by-zero
    assert warning is not None and "empty" in warning.lower()
    assert data["proposalCount"] == 0


def test_overview_stats_counts(wiki_db):
    a = wiki_service.create_note(NoteCreateInput(title="A", status="evergreen", content="a"))
    b = wiki_service.create_note(NoteCreateInput(title="B", status="developing", content="b"))
    wiki_service.create_note(NoteCreateInput(title="C", content="lonely"))  # fleeting, orphan
    _link(a.id, b.id)  # a↔b linked
    data, warning = wiki_reader.overview()
    s = data["stats"]
    assert s["totalNotes"] == 3
    assert s["byStatus"]["evergreen"] == 1
    assert s["byStatus"]["developing"] == 1
    assert s["byStatus"]["fleeting"] == 1
    assert s["totalLinks"] == 1          # one resolved edge a→b
    assert s["orphanCount"] == 1         # C has no links
    assert s["pctWithLink"] == round(2 / 3 * 100, 1)  # a,b linked / 3
    assert warning is None


def test_overview_orphans_and_activity(wiki_db):
    n = wiki_service.create_note(NoteCreateInput(title="Orphan", content="alone"))
    data, _ = wiki_reader.overview()
    assert any(o["id"] == n.id for o in data["orphans"])
    # recentActivity reflects the op_log (the create op)
    assert any(act["op"] == "create" and act["noteId"] == n.id
               for act in data["recentActivity"])


def test_overview_ghost_link_count(wiki_db):
    wiki_service.create_note(NoteCreateInput(title="C", content="ref [[Ghosttown]]"))
    data, _ = wiki_reader.overview()
    assert data["stats"]["ghostLinkCount"] == 1


# --- C5: inbox -------------------------------------------------------------- #
def test_inbox_fleeting_only(wiki_db):
    f = wiki_service.create_note(NoteCreateInput(title="Fleeting one", content="raw"))
    ev = wiki_service.create_note(NoteCreateInput(title="Evergreen one", content="x"))
    wiki_service.update_note(ev.id, NoteUpdateInput(status="evergreen"))
    items = wiki_reader.inbox()["items"]
    ids = {i["id"] for i in items}
    assert f.id in ids
    assert ev.id not in ids  # not fleeting → not in inbox


def test_inbox_item_shape(wiki_db):
    n = wiki_service.create_note(NoteCreateInput(title="Cap", content="some raw content"))
    item = wiki_reader.inbox()["items"][0]
    assert item["id"] == n.id
    assert item["status"] == "fleeting"
    assert item["aiSuggest"] is None
    assert "some raw content" in item["rawContent"]
    assert item["captureSource"]  # default present
    assert item["linkCount"] == 0


# --- API: graph / overview / inbox ------------------------------------------ #
def test_api_overview_endpoint(api):
    api.post("/wiki/notes", json={"title": "A", "content": "a"})
    r = api.get("/wiki/overview")
    assert r.status_code == 200
    data = r.json()["data"]
    assert set(data) == {"stats", "inbox", "orphans", "recentActivity", "proposalCount"}
    assert data["stats"]["totalNotes"] == 1


def test_api_overview_empty_vault_warning(api):
    r = api.get("/wiki/overview")
    assert r.status_code == 200
    assert r.json()["data"]["stats"]["pctWithLink"] is None
    assert r.json().get("warning")


def test_api_graph_endpoint(api):
    c = api.post("/wiki/notes", json={"title": "C", "content": "c"}).json()["data"]["id"]
    a = api.post("/wiki/notes", json={"title": "A", "content": f"[[{c}]]"}).json()["data"]["id"]
    r = api.get("/wiki/graph", params={"note": c, "depth": 2})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["center"] == c
    assert {n["id"] for n in data["nodes"]} == {c, a}


def test_api_graph_404_missing(api):
    assert api.get("/wiki/graph", params={"note": 9999}).status_code == 404


def test_api_inbox_endpoint(api):
    api.post("/wiki/notes", json={"title": "Fleet", "content": "raw"})
    r = api.get("/wiki/inbox")
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert len(items) == 1 and items[0]["status"] == "fleeting"


# =========================================================================== #
# W1c-T3 — refine ≥1-link gate + captureSource + config                        #
# =========================================================================== #
from core.config import settings as _settings  # noqa: E402


# --- C6: refine gate — 3 DIVERGENT cases (verify-with-distinguishing-case) --- #
def test_refine_with_link_ok_and_flips_status(wiki_db, monkeypatch):
    # Set a LOW threshold so the vault is NOT in cold-start (the gate is live).
    monkeypatch.setattr(_settings, "wiki_cold_start_min_notes", 1)
    target = wiki_service.create_note(NoteCreateInput(title="Target", content="t"))
    note = wiki_service.create_note(NoteCreateInput(content="draft"))
    # refine with a link → allowed, status flips, NO warning.
    refined, warning = wiki_service.refine_note(
        note.id, NoteUpdateInput(content=f"refined [[{target.id}]]", status="developing")
    )
    assert refined.status == "developing"
    assert warning is None


def test_refine_zero_link_non_coldstart_422(wiki_db, monkeypatch):
    # vault has 2 notes, threshold 1 → NOT cold-start → 0-link refine is BLOCKED.
    monkeypatch.setattr(_settings, "wiki_cold_start_min_notes", 1)
    wiki_service.create_note(NoteCreateInput(title="Other", content="x"))
    note = wiki_service.create_note(NoteCreateInput(content="draft, no links"))
    with pytest.raises(wiki_service.RefineGateError):
        wiki_service.refine_note(note.id, NoteUpdateInput(content="still no links", status="developing"))


def test_refine_zero_link_coldstart_ok_with_warning(wiki_db, monkeypatch):
    # vault below threshold → cold-start → 0-link refine ALLOWED + warning.
    monkeypatch.setattr(_settings, "wiki_cold_start_min_notes", 5)
    note = wiki_service.create_note(NoteCreateInput(content="first note ever"))
    refined, warning = wiki_service.refine_note(
        note.id, NoteUpdateInput(content="refined but no link yet", status="developing")
    )
    assert refined.status == "developing"
    assert warning is not None and "cold-start" in warning.lower()


def test_refine_gate_counts_inbound_link(wiki_db, monkeypatch):
    # A note with an INBOUND link (someone links it) but no outbound → linkCount≥1.
    monkeypatch.setattr(_settings, "wiki_cold_start_min_notes", 1)
    target = wiki_service.create_note(NoteCreateInput(title="Popular", content="t"))
    wiki_service.create_note(NoteCreateInput(content=f"[[{target.id}]]"))  # inbound to target
    # refine the TARGET with a no-link body → still ok (inbound counts).
    refined, warning = wiki_service.refine_note(
        target.id, NoteUpdateInput(content="refined, no outbound", status="evergreen")
    )
    assert refined.status == "evergreen"
    assert warning is None


def test_refine_missing_note_raises(wiki_db):
    with pytest.raises(wiki_service.NoteNotFound):
        wiki_service.refine_note(999, NoteUpdateInput(content="x"))


def test_refine_records_refine_op_kind(wiki_db, monkeypatch):
    monkeypatch.setattr(_settings, "wiki_cold_start_min_notes", 1)
    target = wiki_service.create_note(NoteCreateInput(title="T", content="t"))
    note = wiki_service.create_note(NoteCreateInput(content="d"))
    wiki_service.refine_note(note.id, NoteUpdateInput(content=f"[[{target.id}]]", status="developing"))
    ops = wiki_store.recent_ops(limit=5)
    assert ops[0]["kind"] == "refine"


# --- C5: captureSource ------------------------------------------------------ #
def test_capture_source_stored_and_in_inbox(wiki_db):
    wiki_service.create_note(NoteCreateInput(content="from the bar", captureSource="command_bar"))
    item = wiki_reader.inbox()["items"][0]
    assert item["captureSource"] == "command_bar"


def test_capture_source_defaults_quick_add(wiki_db):
    wiki_service.create_note(NoteCreateInput(content="no source given"))
    item = wiki_reader.inbox()["items"][0]
    assert item["captureSource"] == "quick_add"


def test_capture_source_preserved_across_edit(wiki_db):
    n = wiki_service.create_note(NoteCreateInput(content="x", captureSource="mcp_agent"))
    wiki_service.update_note(n.id, NoteUpdateInput(content="edited"))
    row = wiki_store.get_note_cache(n.id)
    assert row["capture_source"] == "mcp_agent"  # edit preserves provenance


# --- config threshold toggle (without seeding N notes) ---------------------- #
def test_config_threshold_toggle_waives_at_4(wiki_db, monkeypatch):
    # threshold 5, vault will have <5 → cold-start waives the gate (no seeding needed).
    monkeypatch.setattr(_settings, "wiki_cold_start_min_notes", 5)
    note = wiki_service.create_note(NoteCreateInput(content="solo note"))
    _, warning = wiki_service.refine_note(note.id, NoteUpdateInput(status="developing"))
    assert warning is not None  # waived (cold-start)


def test_config_threshold_toggle_gates_at_low_threshold(wiki_db, monkeypatch):
    # threshold 1, vault has 1 → NOT cold-start → gate is LIVE (without seeding 5).
    monkeypatch.setattr(_settings, "wiki_cold_start_min_notes", 1)
    note = wiki_service.create_note(NoteCreateInput(content="solo note"))
    with pytest.raises(wiki_service.RefineGateError):
        wiki_service.refine_note(note.id, NoteUpdateInput(status="developing"))


# --- API: refine endpoint (the 3 cases) ------------------------------------- #
def test_api_refine_with_link_200(api, monkeypatch):
    monkeypatch.setattr(_settings, "wiki_cold_start_min_notes", 1)
    t = api.post("/wiki/notes", json={"title": "T", "content": "t"}).json()["data"]["id"]
    n = api.post("/wiki/notes", json={"content": "draft"}).json()["data"]["id"]
    r = api.post(f"/wiki/notes/{n}/refine", json={"content": f"[[{t}]]", "status": "developing"})
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "developing"


def test_api_refine_zero_link_non_coldstart_422(api, monkeypatch):
    monkeypatch.setattr(_settings, "wiki_cold_start_min_notes", 1)
    api.post("/wiki/notes", json={"title": "Other", "content": "x"})
    n = api.post("/wiki/notes", json={"content": "draft"}).json()["data"]["id"]
    r = api.post(f"/wiki/notes/{n}/refine", json={"content": "no link", "status": "developing"})
    assert r.status_code == 422


def test_api_refine_coldstart_200_with_warning(api, monkeypatch):
    monkeypatch.setattr(_settings, "wiki_cold_start_min_notes", 5)
    n = api.post("/wiki/notes", json={"content": "first"}).json()["data"]["id"]
    r = api.post(f"/wiki/notes/{n}/refine", json={"content": "no link yet", "status": "developing"})
    assert r.status_code == 200
    assert "cold-start" in (r.json().get("warning") or "").lower()


def test_api_refine_missing_404(api):
    assert api.post("/wiki/notes/9999/refine", json={"content": "x"}).status_code == 404


def test_api_create_with_capture_source(api):
    api.post("/wiki/notes", json={"content": "x", "captureSource": "daily_note"})
    item = api.get("/wiki/inbox").json()["data"]["items"][0]
    assert item["captureSource"] == "daily_note"
