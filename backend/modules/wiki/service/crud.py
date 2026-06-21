"""modules/wiki/service/crud.py — public CRUD (the router + other modules call these).

Each mutation builds an ``Op`` and blocks on ``enqueue`` (the single-writer queue);
reads go straight to the read path (no queue). This is the module's public surface."""

from __future__ import annotations

from ..schema import Note, NoteCreateInput, NoteUpdateInput
from ._queue import Op, enqueue
from .read import _read_note


def create_note(inp: NoteCreateInput, actor: str = "human") -> Note:
    """Create a fleeting note through the queue. Returns the created Note."""
    op = Op(kind="create", note_id=None, payload={"input": inp}, actor=actor)
    note = enqueue(op)
    assert note is not None
    return note


def get_note(note_id: int) -> Note | None:
    """Read one note (no queue). None if absent/malformed → router maps to 404."""
    return _read_note(note_id)


def update_note(note_id: int, inp: NoteUpdateInput, actor: str = "human",
                feedback: dict | None = None) -> Note:
    """Partial-update a note through the queue. Raises NoteNotFound if absent.

    #35: ``feedback={reason, text}`` (optional) is the override-feedback a HUMAN gives
    when editing an AGENT-written note — captured into the op_log detail by the apply
    layer (only when this edit overrides agent work; a silent edit passes feedback=None)."""
    payload: dict = {"input": inp}
    if feedback is not None:
        payload["feedback"] = feedback
    op = Op(kind="update", note_id=note_id, payload=payload, actor=actor)
    note = enqueue(op)
    assert note is not None
    return note


def delete_note(note_id: int, actor: str = "human",
                feedback: dict | None = None) -> None:
    """HARD-delete a note through the queue (the .md + cache + aliases/links/fts gone forever).
    Raises NoteNotFound if absent. #94: the ROUTER's DELETE now calls soft_delete_note (recoverable);
    this hard path stays for merge/internal use that genuinely removes a note.

    #35: ``feedback={reason, text}`` (optional) is the override-feedback a HUMAN gives
    when deleting an AGENT-written note — captured into the op_log detail by the apply
    layer (only when this delete overrides agent work)."""
    payload: dict = {}
    if feedback is not None:
        payload["feedback"] = feedback
    op = Op(kind="delete", note_id=note_id, payload=payload, actor=actor)
    enqueue(op)


def soft_delete_note(note_id: int, actor: str = "human",
                     feedback: dict | None = None) -> Note:
    """#94 SOFT-delete (recoverable): tombstone the note (deletedAt=now), KEEP the .md (reconcile-
    safe) + cache row + aliases/links, hide from live views. Returns the tombstoned note. Raises
    NoteNotFound if absent. Idempotent (already-deleted → returned unchanged).

    #35: optional override-feedback (a human deleting an AGENT-written note) flows to the op_log,
    same as the hard-delete path."""
    payload: dict = {}
    if feedback is not None:
        payload["feedback"] = feedback
    op = Op(kind="softdelete", note_id=note_id, payload=payload, actor=actor)
    note = enqueue(op)
    assert note is not None
    return note


def restore_note(note_id: int, actor: str = "human") -> Note:
    """#94 RESTORE: clear the tombstone → the note is fully back in every view (links/aliases intact).
    Returns the restored note. Raises NoteNotFound if absent. Idempotent (already-live → unchanged)."""
    op = Op(kind="restore", note_id=note_id, payload={}, actor=actor)
    note = enqueue(op)
    assert note is not None
    return note


def merge_notes(source_id: int, target_id: int, actor: str = "human") -> Note:
    """Merge ``source`` INTO ``target`` through the queue (B5/D6). Returns the
    target note. Raises MergeError (same id → 422) / NoteNotFound (absent → 404)."""
    op = Op(kind="merge", note_id=source_id,
            payload={"sourceId": source_id, "targetId": target_id}, actor=actor)
    note = enqueue(op)
    assert note is not None
    return note


def refine_note(note_id: int, inp: NoteUpdateInput,
                actor: str = "human") -> tuple[Note, str | None]:
    """REFINE a note through the queue (C6/D9) — the ≥1-link hard gate path.
    Returns ``(note, warning)``: warning is set on the cold-start exception.
    Raises NoteNotFound (absent → 404) / RefineGateError (0-link non-cold-start → 422)."""
    op = Op(kind="refine", note_id=note_id, payload={"input": inp}, actor=actor)
    note = enqueue(op)
    assert note is not None
    return note, op.warning
