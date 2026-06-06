"""modules/notes/router.py — Notes REST endpoints (Sprint 6, T2).

Mounts at ``/notes`` via the registry (``MODULE``). Locked envelope
``{success, data, warning?}``. Business logic is in service.py; this is HTTP shape
+ status codes only. No routine (notes are user-driven CRUD).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from core.base import BaseModule
from core.responses import ok

from . import service
from .schema import NoteInput

logger = logging.getLogger("life-os.notes.router")

router = APIRouter(tags=["notes"])


@router.get("")
def list_notes(
    q: str | None = None,
    tag: str | None = None,
    attached: str | None = None,
    pinned: bool | None = None,
):
    """Notes matching filters (q substring / tag exact / attached type[:ref] / pinned),
    pinned-first then newest updatedAt."""
    notes, warnings = service.list_notes(q=q, tag=tag, attached=attached, pinned=pinned)
    return ok(data=[n.model_dump() for n in notes], warning="; ".join(warnings) if warnings else None)


@router.get("/{note_id}")
def get_note(note_id: str):
    """One note. 404 if absent/malformed."""
    note = service.get_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail=f"note {note_id!r} not found")
    return ok(data=note.model_dump())


@router.post("")
def create_note(body: NoteInput):
    """Create a note (server-set id + timestamps). One git commit."""
    note = service.create_note(body)
    return ok(data=note.model_dump())


@router.put("/{note_id}")
def update_note(note_id: str, body: NoteInput):
    """Update a note in place (preserve createdAt). 404 if absent."""
    note = service.update_note(note_id, body)
    if note is None:
        raise HTTPException(status_code=404, detail=f"note {note_id!r} not found")
    return ok(data=note.model_dump())


@router.delete("/{note_id}")
def delete_note(note_id: str):
    """Delete a note (one git commit). 404 if absent."""
    if not service.delete_note(note_id):
        raise HTTPException(status_code=404, detail=f"note {note_id!r} not found")
    return ok(data={"deleted": note_id})


MODULE = BaseModule(name="notes", router=router)
