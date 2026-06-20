"""modules/reminders/router.py — Reminders REST + module registration (REMINDERS-1, #27).

Mounts at ``/reminders`` via the registry (``MODULE``). Locked envelope {success, data, warning?}.
Business logic is in service.py; this is HTTP shape + status codes only. No routines in #27 (the
notify routine is #29). No auth — single-user app.

POST   /reminders            → 201, the created reminder
GET    /reminders?filter=…    → list + count/undoneCount (filter ∈ today|week|undone|all, lenient)
GET    /reminders/{id}        → the reminder, 404 if absent
PUT    /reminders/{id}/tick   → mark done (IDEMPOTENT), 404 if absent
DELETE /reminders/{id}        → {deleted}, 404 if absent

NB (decide-and-log): DELETE returns 200 + the locked {success, data:{deleted}} envelope (mirroring
every other DELETE in the app — notes/market/etc), NOT a bare 204. A 204 has no body and would
break the app-wide {success, data} contract the FE/agent rely on; the locked envelope wins. The
"204" in the dispatch is the delete-semantics intent — honoured as a successful-delete envelope.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from core.base import BaseModule
from core.responses import ok

from . import service
from .schema import ReminderInput

logger = logging.getLogger("life-os.reminders.router")

router = APIRouter(tags=["reminders"])


@router.post("", status_code=201)
def create_reminder(body: ReminderInput):
    """Create a reminder. 201 + the created reminder. A blank title or unparseable due_at is a
    422 (pydantic validation — no row stored)."""
    reminder = service.create(body)
    return ok(data=reminder.model_dump())


@router.get("")
def list_reminders(filter: str | None = None):
    """List reminders by ``filter`` (today|week|undone|all; unknown → lenient all). Returns
    {reminders, count, undoneCount, filter}. Empty → [] count 0 (raw-data-first)."""
    view, warnings = service.list_reminders(filter)
    return ok(data=view.model_dump(), warning="; ".join(warnings) if warnings else None)


@router.get("/{reminder_id}")
def get_reminder(reminder_id: int):
    """One reminder. 404 if absent."""
    reminder = service.get(reminder_id)
    if reminder is None:
        raise HTTPException(status_code=404, detail=f"reminder {reminder_id} not found")
    return ok(data=reminder.model_dump())


@router.put("/{reminder_id}/tick")
def tick_reminder(reminder_id: int):
    """Mark a reminder done. IDEMPOTENT — re-ticking a done reminder is a no-op (done_at keeps
    its first value), 200 with the reminder. 404 if the reminder doesn't exist."""
    reminder = service.tick(reminder_id)
    if reminder is None:
        raise HTTPException(status_code=404, detail=f"reminder {reminder_id} not found")
    return ok(data=reminder.model_dump())


@router.delete("/{reminder_id}")
def delete_reminder(reminder_id: int):
    """Delete a reminder. 200 + {deleted} (the locked envelope — see module docstring). 404 if
    the reminder doesn't exist."""
    if not service.delete(reminder_id):
        raise HTTPException(status_code=404, detail=f"reminder {reminder_id} not found")
    return ok(data={"deleted": reminder_id})


# The registry discovers this MODULE. No routines in #27 (notify is #29).
MODULE = BaseModule(name="reminders", router=router)
