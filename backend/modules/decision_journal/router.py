"""modules/decision_journal/router.py — Decision Journal REST endpoints (W7 A2).

Mounts at ``/decision-journal`` via the registry (``MODULE``) — auto-discovered, no
edit to core/main.py. Locked envelope. GET serves entries + folded-in calibration
stats (DecisionStats). Write endpoints fail-CLOSED (an md_store failure → 500, never
a false success). No routine.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from core.base import BaseModule
from core.responses import ok

from . import service
from .schema import DecisionInput, DecisionUpdate

logger = logging.getLogger("life-os.decision_journal.router")

router = APIRouter(tags=["decision-journal"])


@router.get("")
def list_decisions(domain: str | None = None, status: str | None = None):
    """Decisions (newest first) + folded-in calibration stats (brier, bands,
    biasFlags). Filters: domain, status. Empty → honest zero stats."""
    stats, warnings = service.list_entries(domain=domain, status=status)
    return ok(data=stats.model_dump(), warning="; ".join(warnings) if warnings else None)


@router.get("/{entry_id}")
def get_decision(entry_id: str):
    """One decision. 404 if absent; 422 if the entry FILE exists but is malformed
    (F2-M5: a corrupt entry is a different failure than a missing id — surface it as
    unprocessable, not not-found, so the corruption is visible)."""
    entry = service.get_entry(entry_id)
    if entry is None:
        if service.entry_file_exists(entry_id):
            raise HTTPException(status_code=422,
                                detail=f"decision {entry_id!r} is malformed (corrupt entry file)")
        raise HTTPException(status_code=404, detail=f"decision {entry_id!r} not found")
    return ok(data=entry.model_dump())


@router.post("")
def create_decision(body: DecisionInput):
    """Create a decision (server id + timestamps). One git commit. Fail-CLOSED on write."""
    entry = service.create_entry(body)
    return ok(data=entry.model_dump())


@router.put("/{entry_id}")
def update_decision(entry_id: str, body: DecisionUpdate):
    """PARTIAL update / resolve (W7-A2-fix): all fields optional. The natural resolve
    ``PUT {status:"resolved", outcome:"right"}`` works without resending the core
    fields. 404 if absent. Fail-CLOSED."""
    entry = service.update_entry(entry_id, body)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"decision {entry_id!r} not found")
    return ok(data=entry.model_dump())


@router.delete("/{entry_id}")
def delete_decision(entry_id: str):
    """Delete a decision (one git commit). 404 if absent."""
    if not service.delete_entry(entry_id):
        raise HTTPException(status_code=404, detail=f"decision {entry_id!r} not found")
    return ok(data={"deleted": entry_id})


MODULE = BaseModule(name="decision-journal", router=router)
