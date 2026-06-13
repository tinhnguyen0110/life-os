"""modules/wiki/router.py — Wiki REST endpoints (Sprint W1a).

Mounts at ``/wiki`` via the registry (``MODULE`` below). Adding this folder is the
ONLY wiring needed — no edit to ``core/`` or ``main.py`` (registry auto-discovers
``MODULE`` from this file, the projects/notes fallback path).

W1a scope = identity + store + single-writer queue + CRUD. Links/FTS/graph are
W1b/W1c. This router is HTTP shape + status codes only — all mutation logic lives
in ``service.py`` (every write goes through the single-writer changes-queue).
Envelope: ``core.responses.ok`` → ``{success, data, warning?}``. Errors via
``HTTPException`` (404 missing note; 422 validation is FastAPI/Pydantic auto).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from core.base import BaseModule
from core.responses import ok

from . import service
from .schema import NoteCreateInput, NoteUpdateInput

logger = logging.getLogger("life-os.wiki.router")

router = APIRouter(tags=["wiki"])


@router.get("")
def wiki_info():
    """Liveness/info for the wiki module. The note CRUD surface is below."""
    return ok(data={"module": "wiki", "status": "ok"})


@router.post("/notes")
def create_note(body: NoteCreateInput):
    """Create a note (capture → fleeting). Server-set id + timestamps. Goes through
    the single-writer queue → 1 git commit + 1 op_log row."""
    note = service.create_note(body)
    return ok(data=note.model_dump())


@router.get("/notes/{note_id}")
def get_note(note_id: int):
    """One note. 404 if absent/malformed."""
    note = service.get_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail=f"wiki note {note_id} not found")
    return ok(data=note.model_dump())


@router.put("/notes/{note_id}")
def update_note(note_id: int, body: NoteUpdateInput):
    """Partial-update a note in place (preserve created+id; bump updated unless a
    no-op touch). Goes through the queue. 404 if absent."""
    try:
        note = service.update_note(note_id, body)
    except service.NoteNotFound:
        raise HTTPException(status_code=404, detail=f"wiki note {note_id} not found")
    return ok(data=note.model_dump())


@router.delete("/notes/{note_id}")
def delete_note(note_id: int):
    """Delete a note (1 git commit removes the file; cache row hard-deleted; op_log
    keeps the delete record). 404 if absent."""
    try:
        service.delete_note(note_id)
    except service.NoteNotFound:
        raise HTTPException(status_code=404, detail=f"wiki note {note_id} not found")
    return ok(data={"deleted": note_id})


MODULE = BaseModule(name="wiki", router=router)
