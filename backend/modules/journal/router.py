"""modules/journal/router.py — Journal REST endpoints (Sprint 9, SPEC §S7).

Mounts at ``/journal`` via the registry (``MODULE``). Locked envelope. GET serves
entries + folded-in stats (JournalStats). Write endpoints fail-CLOSED — an
md_store failure propagates as 500, never a false success. No routine.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from core.agent_errors import agent_error_response  # AGENT-ERROR-P5 (#46): flat REST error parity
from core.base import BaseModule
from core.responses import ok

from . import service
from .schema import JournalInput

logger = logging.getLogger("life-os.journal.router")

router = APIRouter(tags=["journal"])


@router.get("")
def list_journal(
    action: str | None = None,
    tag: str | None = None,
    channel: str | None = None,
    asset: str | None = None,
):
    """Entries (newest first) + folded-in stats. Filters: action/tag/channel/asset."""
    stats, warnings = service.list_entries(action=action, tag=tag, channel=channel, asset=asset)
    return ok(data=stats.model_dump(), warning="; ".join(warnings) if warnings else None)


@router.get("/{entry_id}")
def get_journal(entry_id: str):
    """One entry. 404 if absent/malformed."""
    entry = service.get_entry(entry_id)
    if entry is None:
        return agent_error_response("NOT_FOUND", f"journal entry {entry_id!r} not found",
                                    hint="GET /journal for valid ids")
    return ok(data=entry.model_dump())


@router.post("")
def create_journal(body: JournalInput):
    """Create an entry (server id + timestamps). One git commit. Fail-CLOSED on write."""
    entry = service.create_entry(body)
    return ok(data=entry.model_dump())


@router.put("/{entry_id}")
def update_journal(entry_id: str, body: JournalInput):
    """Update/close an entry (set pnl/outcome/lesson). 404 if absent. Fail-CLOSED."""
    entry = service.update_entry(entry_id, body)
    if entry is None:
        return agent_error_response("NOT_FOUND", f"journal entry {entry_id!r} not found",
                                    hint="GET /journal for valid ids")
    return ok(data=entry.model_dump())


@router.delete("/{entry_id}")
def delete_journal(entry_id: str):
    """Delete an entry (one git commit). 404 if absent."""
    if not service.delete_entry(entry_id):
        return agent_error_response("NOT_FOUND", f"journal entry {entry_id!r} not found",
                                    hint="GET /journal for valid ids")
    return ok(data={"deleted": entry_id})


MODULE = BaseModule(name="journal", router=router)
