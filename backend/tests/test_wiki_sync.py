"""tests/test_wiki_sync.py — M3 multi-device sync merge (Sprint W6 A1a, option B).

THE GATE (team-lead non-negotiable, provable NOW without a real 2nd device):
simulate two device op-streams →
  (a) non-conflicting edits CONVERGE, 0 data loss, merge(A,B) == merge(B,A);
  (b) a TRUE conflict (same block edited divergently) is DETECTED + surfaced via the
      endpoint, NOT silently overwritten — the LWW loser is recoverable from the
      conflict record.
A collapsed "take latest everywhere" impl passes (a) but FAILS (b)'s
loser-recoverable — that divergence is the teeth (behavior-test-not-field-read:
the test RUNS the merge over two streams, it doesn't read a model).

Tests in their own module (test-where-the-reader-greps). merge_streams is pure.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.wiki import store as wiki_store
from modules.wiki import proposals_store as pstore
from modules.wiki import sync_store
from modules.wiki import service as wsvc
from modules.wiki.schema import NoteCreateInput
from modules.wiki.sync import (
    BlockEdit,
    delete_edit,
    join_blocks,
    merge_streams,
    split_blocks,
)


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    pstore.init_proposal_tables()
    sync_store.init_sync_tables()
    return isolated_paths


def _e(note_id, block, content, ts, device) -> BlockEdit:
    return BlockEdit(note_id=note_id, block_index=block, content=content, ts=ts, device=device)


# --------------------------------------------------------------------------- #
# block split (the LWW unit)                                                    #
# --------------------------------------------------------------------------- #
def test_split_blocks_on_blank_lines():
    assert split_blocks("a\n\nb\n\nc") == ["a", "b", "c"]
    assert split_blocks("") == []
    assert split_blocks("   ") == []
    assert split_blocks("single") == ["single"]


def test_join_is_inverse_of_split():
    blocks = ["one", "two", "three"]
    assert split_blocks(join_blocks(blocks)) == blocks


# --------------------------------------------------------------------------- #
# THE GATE (a): convergence + 0 data loss + commutative                         #
# --------------------------------------------------------------------------- #
def test_nonconflicting_edits_converge_zero_data_loss():
    # device A edits block 0, device B edits block 2 of note 1 — non-overlapping.
    A = [_e(1, 0, "A-block0", "2026-06-14T10:00:00Z", "deskA")]
    B = [_e(1, 2, "B-block2", "2026-06-14T10:01:00Z", "phoneB")]
    merged = merge_streams([A, B])
    blocks = merged["notes"][1]
    # BOTH edits present → 0 data loss; NO conflict (different blocks)
    assert "A-block0" in blocks and "B-block2" in blocks
    assert merged["conflicts"] == []


def test_merge_is_commutative():
    A = [_e(1, 0, "fromA", "2026-06-14T10:00:00Z", "deskA")]
    B = [_e(1, 1, "fromB", "2026-06-14T10:01:00Z", "phoneB")]
    assert merge_streams([A, B]) == merge_streams([B, A])


def test_same_content_both_streams_no_conflict():
    # idempotent / mid-sync resume: both streams carry the SAME block content → no conflict.
    A = [_e(1, 0, "identical", "2026-06-14T10:00:00Z", "deskA")]
    B = [_e(1, 0, "identical", "2026-06-14T10:05:00Z", "phoneB")]
    merged = merge_streams([A, B])
    assert merged["conflicts"] == []
    assert merged["notes"][1] == ["identical"]


# --------------------------------------------------------------------------- #
# THE GATE (b): true conflict DETECTED + LWW winner + loser RECOVERABLE          #
# --------------------------------------------------------------------------- #
def test_divergent_same_block_is_conflict_loser_recoverable():
    # device A and B both edit block 0 to DIFFERENT content → conflict.
    A = [_e(1, 0, "A-version", "2026-06-14T10:00:00Z", "deskA")]
    B = [_e(1, 0, "B-version", "2026-06-14T10:05:00Z", "phoneB")]  # later ts → LWW winner
    merged = merge_streams([A, B])
    assert len(merged["conflicts"]) == 1
    c = merged["conflicts"][0]
    assert c.note_id == 1 and c.block_index == 0
    # LWW winner (later ts) is in the converged doc
    assert merged["notes"][1] == ["B-version"]
    # BOTH versions kept → the loser (A-version) is RECOVERABLE (0 data loss)
    contents = {v["content"] for v in c.versions}
    assert contents == {"A-version", "B-version"}


def test_clock_skew_tiebreak_deterministic():
    # equal ts → tie broken by max device id, deterministically, no crash.
    A = [_e(1, 0, "A-content", "2026-06-14T10:00:00Z", "aaa")]
    B = [_e(1, 0, "B-content", "2026-06-14T10:00:00Z", "zzz")]  # same ts, zzz > aaa
    merged = merge_streams([A, B])
    assert merged["notes"][1] == ["B-content"]  # zzz wins the tie
    assert len(merged["conflicts"]) == 1  # still a conflict (divergent content)


def test_rename_and_edit_concurrent_both_preserved():
    # rename touches block 0 (title-ish first line), edit touches block 1 — different
    # blocks → both preserved, no conflict.
    A = [_e(1, 0, "# Renamed", "2026-06-14T10:00:00Z", "deskA")]
    B = [_e(1, 1, "edited body", "2026-06-14T10:01:00Z", "phoneB")]
    merged = merge_streams([A, B])
    assert merged["notes"][1] == ["# Renamed", "edited body"]
    assert merged["conflicts"] == []


def test_delete_vs_edit_is_conflict_not_silent():
    # device A deletes note 1; device B edits a block of note 1 → CONFLICT (ASK),
    # not a silent delete or silent resurrect.
    A = [delete_edit(1, "2026-06-14T10:00:00Z", "deskA")]
    B = [_e(1, 0, "B still editing", "2026-06-14T10:05:00Z", "phoneB")]
    merged = merge_streams([A, B])
    # a conflict is surfaced for the note
    assert any(c.note_id == 1 for c in merged["conflicts"])
    # both the delete and the edit are represented (neither silently won)
    dc = next(c for c in merged["conflicts"] if c.block_index == -1)
    contents = {v["content"] for v in dc.versions}
    assert "<deleted>" in contents and "B still editing" in contents
    # the tombstone sentinel is NOT materialized as body content
    assert "\x00__WIKI_TOMBSTONE__\x00" not in merged["notes"].get(1, [])


def test_idempotent_resume_replay_is_noop():
    # mid-sync disconnect → replaying the SAME op (same content) is a no-op, not a conflict.
    op = _e(1, 0, "content X", "2026-06-14T10:00:00Z", "deskA")
    once = merge_streams([[op]])
    twice = merge_streams([[op], [op]])  # replayed
    assert once["notes"] == twice["notes"] and twice["conflicts"] == []


# --------------------------------------------------------------------------- #
# device registry + sync cursor (offline resume)                                #
# --------------------------------------------------------------------------- #
def test_device_register_and_list(wiki_db):
    sync_store.register_device("dev1", "Desktop", "2026-06-14T10:00:00Z")
    sync_store.register_device("dev2", "Phone", "2026-06-14T11:00:00Z")
    devices = sync_store.list_devices()
    assert {d["deviceId"] for d in devices} == {"dev1", "dev2"}
    assert devices[0]["deviceId"] == "dev2"  # most-recently-seen first


def test_sync_cursor_resume_point(wiki_db):
    assert sync_store.get_cursor("dev1") == 0  # never synced
    sync_store.set_cursor("dev1", 42)
    assert sync_store.get_cursor("dev1") == 42
    sync_store.set_cursor("dev1", 99)  # advance
    assert sync_store.get_cursor("dev1") == 99


# --------------------------------------------------------------------------- #
# conflict persistence + surfacing endpoint                                     #
# --------------------------------------------------------------------------- #
def test_merge_and_record_persists_conflicts(wiki_db):
    from modules.wiki import sync
    A = [_e(1, 0, "A-version", "2026-06-14T10:00:00Z", "deskA")]
    B = [_e(1, 0, "B-version", "2026-06-14T10:05:00Z", "phoneB")]
    out = sync.merge_and_record([A, B], detected_at="2026-06-14T12:00:00Z")
    assert len(out["conflictIds"]) == 1
    open_conflicts = sync_store.list_conflicts("open")
    assert len(open_conflicts) == 1
    v = {x["content"] for x in open_conflicts[0]["versions"]}
    assert v == {"A-version", "B-version"}  # loser recoverable from the record


@pytest.fixture
def client(wiki_db):
    from main import app
    return TestClient(app)


def test_api_device_register_and_list(client):
    r = client.post("/wiki/sync/devices", json={"deviceId": "d1", "name": "Desk"})
    assert r.status_code == 200
    assert any(d["deviceId"] == "d1" for d in r.json()["data"]["devices"])
    assert any(d["deviceId"] == "d1" for d in client.get("/wiki/sync/devices").json()["data"]["devices"])


def test_api_conflicts_empty_honest(client):
    assert client.get("/wiki/sync/conflicts").json()["data"] == {"conflicts": []}


def test_api_full_conflict_surface_and_resolve(client):
    # seed a note, simulate a divergent 2-device edit → record conflict → surface → resolve.
    from modules.wiki import sync
    nid = wsvc.create_note(NoteCreateInput(title="N", content="orig block")).id
    A = [sync.BlockEdit(note_id=nid, block_index=0, content="deskA edit",
                        ts="2026-06-14T10:00:00Z", device="deskA")]
    B = [sync.BlockEdit(note_id=nid, block_index=0, content="phoneB edit",
                        ts="2026-06-14T10:05:00Z", device="phoneB")]
    sync.merge_and_record([A, B], detected_at="2026-06-14T12:00:00Z")
    # surfaced via the endpoint, both versions present (loser recoverable)
    conflicts = client.get("/wiki/sync/conflicts").json()["data"]["conflicts"]
    assert len(conflicts) == 1
    cid = conflicts[0]["id"]
    assert {v["content"] for v in conflicts[0]["versions"]} == {"deskA edit", "phoneB edit"}
    # human resolves → writes the chosen content THROUGH the single-writer + closes it
    r = client.post(f"/wiki/sync/conflicts/{cid}/resolve",
                    json={"noteId": nid, "content": "human-chosen final"})
    assert r.status_code == 200
    # note reflects the chosen content; conflict no longer open
    assert "human-chosen final" in wsvc.get_note(nid).content
    assert client.get("/wiki/sync/conflicts").json()["data"]["conflicts"] == []


def test_api_resolve_missing_conflict_404(client):
    nid = wsvc.create_note(NoteCreateInput(title="N", content="x")).id
    r = client.post("/wiki/sync/conflicts/99999/resolve", json={"noteId": nid, "content": "y"})
    assert r.status_code == 404


def test_F2_M3_resolve_invalid_conflict_does_not_write_note(client):
    # F2-M3: resolving an ABSENT conflict must 404 WITHOUT mutating the note (the old
    # order wrote the note first, then 404'd — a stray write). Gate the write on the
    # conflict being open.
    nid = wsvc.create_note(NoteCreateInput(title="N", content="original body")).id
    r = client.post("/wiki/sync/conflicts/99999/resolve",
                    json={"noteId": nid, "content": "SHOULD NOT BE WRITTEN"})
    assert r.status_code == 404
    # the note is UNCHANGED — the stray write didn't happen.
    assert wsvc.get_note(nid).content == "original body"
