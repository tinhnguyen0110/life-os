"""modules/wiki/sync.py — M3 multi-device sync merge (Sprint W6 A1a, option B).

The op-log + single-writer already exist (M1, store.py/service.py). M3 adds the
cross-device MERGE layer on top: many device op-streams over the same notes →
block-level Last-Writer-Wins convergence, with TRUE conflicts DETECTED + surfaced
(never silently overwritten). 0 data loss: every block from every stream is either
in the merged doc OR recoverable from a conflict record.

OPTION B (team-lead locked): ship the MECHANISM + a provable convergence/conflict
gate. DEFERRED (see end_sprint §Assumptions): device-id-prefix id migration, the FE
conflict-resolution UI, real device-to-device transport. The merge fn takes
op-streams as INPUT — how they arrive over a wire is out of scope (single device today).

This module is PURE (no HTTP, no DB) so the convergence property is unit-testable:
merge is COMMUTATIVE (merge(A,B) == merge(B,A)) and order-independent.

BLOCK MODEL (deterministic, documented): a note body splits into ordered blocks on
blank-line runs (``\\n\\n+``). A block's identity = its INDEX in that ordered list.
LWW + conflict detection operate per (noteId, blockIndex). Simple + deterministic
for single-user; index identity is fine because edits are localized per block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Blank-line run = block separator. Splitting on this gives ordered body blocks.
_BLOCK_SPLIT = re.compile(r"\n\s*\n")


def split_blocks(body: str) -> list[str]:
    """Split a note body into ordered blocks on blank-line runs. Each block is
    stripped of surrounding blank lines but keeps internal single newlines. An empty
    body → []. Deterministic — the block at index i is always the i-th paragraph."""
    if not body or not body.strip():
        return []
    parts = _BLOCK_SPLIT.split(body.strip())
    return [p.strip() for p in parts if p.strip()]


def join_blocks(blocks: list[str]) -> str:
    """Rejoin merged blocks into a body (blank-line separated) — the inverse of
    split_blocks for the converged document."""
    return "\n\n".join(blocks)


# A whole-note DELETE is a BlockEdit with this sentinel content at block_index -1.
# delete-on-A vs edit-on-B is then a divergence at note scope → a CONFLICT (ASK),
# never a silent delete or silent resurrect (spec M3 defensive case).
TOMBSTONE = "\x00__WIKI_TOMBSTONE__\x00"
_DELETE_BLOCK = -1


@dataclass(frozen=True)
class BlockEdit:
    """One device's edit to one block of one note. ``ts`` is an ISO-8601 string
    (lexically comparable for LWW); ``device`` is the originating device id. A
    whole-note delete is ``block_index=-1, content=TOMBSTONE``."""

    note_id: int
    block_index: int
    content: str
    ts: str
    device: str


def delete_edit(note_id: int, ts: str, device: str) -> "BlockEdit":
    """A device's whole-note DELETE op (M3 defensive case). Modeled as a tombstone
    BlockEdit so the merge treats delete-vs-edit on the same note as a conflict."""
    return BlockEdit(note_id=note_id, block_index=_DELETE_BLOCK, content=TOMBSTONE,
                     ts=ts, device=device)


@dataclass
class Conflict:
    """A TRUE conflict: the SAME (note, block) edited to DIFFERENT content by two
    streams, neither an ancestor of the other. The LWW winner is in the merged doc;
    BOTH versions are kept here so the loser is recoverable (0 data loss)."""

    note_id: int
    block_index: int
    versions: list[dict[str, Any]] = field(default_factory=list)  # [{device, content, ts}]


def _lww_key(edit: BlockEdit) -> tuple[str, str]:
    """LWW ordering key: latest ts wins; tie broken by max device id (deterministic,
    handles clock skew / equal ts without a crash)."""
    return (edit.ts, edit.device)


def merge_streams(streams: list[list[BlockEdit]]) -> dict[str, Any]:
    """Merge N device op-streams (each a list of BlockEdit) → converged state +
    detected conflicts. PURE + COMMUTATIVE (the result does not depend on the order
    of ``streams`` or of edits within them — sorting is by the LWW key).

    Per (note_id, block_index):
      - touched by one content only → take it (no conflict).
      - touched to the SAME content by multiple → take it (no conflict — idempotent
        / mid-sync-resume replay is a no-op).
      - touched to DIFFERENT content by ≥2 → CONFLICT: the LWW winner (max key) goes
        into the merged block, AND a Conflict record keeps every distinct version
        (the loser is recoverable). 0 data loss.

    Returns ``{notes: {note_id: [block,...]}, conflicts: [Conflict,...]}`` —
    ``notes`` maps each touched note to its converged ordered block list; conflicts
    are the surfaced true conflicts. Deterministic ordering throughout.
    """
    # group all edits by (note_id, block_index)
    by_cell: dict[tuple[int, int], list[BlockEdit]] = {}
    for stream in streams:
        for edit in stream:
            by_cell.setdefault((edit.note_id, edit.block_index), []).append(edit)

    notes: dict[int, dict[int, str]] = {}  # note_id -> {block_index -> winning content}
    conflicts: list[Conflict] = []

    for (note_id, block_index), edits in by_cell.items():
        distinct_contents = {e.content for e in edits}
        # LWW winner = max by (ts, device) — deterministic tie-break.
        winner = max(edits, key=_lww_key)
        notes.setdefault(note_id, {})[block_index] = winner.content

        if len(distinct_contents) > 1:
            # true conflict — keep every distinct version (latest per device+content),
            # sorted deterministically so the record is stable/commutative.
            seen: dict[tuple[str, str], BlockEdit] = {}
            for e in edits:
                k = (e.device, e.content)
                if k not in seen or _lww_key(e) > _lww_key(seen[k]):
                    seen[k] = e
            versions = sorted(
                ({"device": e.device, "content": e.content, "ts": e.ts}
                 for e in seen.values()),
                key=lambda v: (v["ts"], v["device"]),
            )
            conflicts.append(Conflict(note_id=note_id, block_index=block_index,
                                      versions=versions))

    # delete-vs-edit (M3 defensive case): a note tombstoned by one stream AND given a
    # real block edit by another → a note-scope CONFLICT (ASK), not a silent delete
    # or resurrect. Detected at block_index -1 vs any real block on the same note.
    already_conflicted = {(c.note_id, c.block_index) for c in conflicts}
    for note_id, blocks in notes.items():
        has_tombstone = _DELETE_BLOCK in blocks
        has_real_edit = any(idx >= 0 for idx in blocks)
        if has_tombstone and has_real_edit and (note_id, _DELETE_BLOCK) not in already_conflicted:
            # gather the delete op + a representative edit so the human sees both sides
            del_edits = by_cell.get((note_id, _DELETE_BLOCK), [])
            versions = [{"device": e.device, "content": "<deleted>", "ts": e.ts}
                        for e in del_edits]
            for idx in sorted(i for i in blocks if i >= 0):
                for e in by_cell.get((note_id, idx), []):
                    versions.append({"device": e.device, "content": e.content, "ts": e.ts})
            versions.sort(key=lambda v: (v["ts"], v["device"]))
            conflicts.append(Conflict(note_id=note_id, block_index=_DELETE_BLOCK,
                                      versions=versions))

    # materialize each note's ordered block list — EXCLUDE the tombstone sentinel
    # block (-1); it's a delete marker, not body content.
    materialized: dict[int, list[str]] = {}
    for note_id, blocks in notes.items():
        materialized[note_id] = [blocks[i] for i in sorted(blocks) if i >= 0]

    conflicts.sort(key=lambda c: (c.note_id, c.block_index))
    return {"notes": materialized, "conflicts": conflicts}


def edits_from_note(note_id: int, body: str, ts: str, device: str) -> list[BlockEdit]:
    """Helper: turn a note body into a per-block BlockEdit list for a given device/ts
    (so a whole-note edit becomes the stream of block edits the merge consumes).
    Block index = position in split_blocks(body)."""
    return [
        BlockEdit(note_id=note_id, block_index=i, content=block, ts=ts, device=device)
        for i, block in enumerate(split_blocks(body))
    ]


# --------------------------------------------------------------------------- #
# Impure bridge — run the pure merge + PERSIST detected conflicts so the        #
# surfacing endpoint (GET /wiki/sync/conflicts) can show them. Kept separate    #
# from merge_streams so the convergence property stays purely unit-testable.    #
# --------------------------------------------------------------------------- #
def merge_and_record(streams: list[list[BlockEdit]], detected_at: str) -> dict[str, Any]:
    """Merge device op-streams (pure merge_streams) THEN persist each detected
    conflict via sync_store (status open) so a human can resolve it. Returns
    ``{notes, conflicts:[{noteId, blockIndex, versions}], conflictIds:[...]}``.
    The converged ``notes`` block-sets are returned for the caller to apply through
    the single-writer (this fn itself never writes note files)."""
    from . import sync_store

    result = merge_streams(streams)
    conflict_ids = []
    for c in result["conflicts"]:
        cid = sync_store.record_conflict(
            note_id=c.note_id, block_index=c.block_index,
            versions=c.versions, detected=detected_at,
        )
        conflict_ids.append(cid)
    return {
        "notes": result["notes"],
        "conflicts": [
            {"noteId": c.note_id, "blockIndex": c.block_index, "versions": c.versions}
            for c in result["conflicts"]
        ],
        "conflictIds": conflict_ids,
    }
