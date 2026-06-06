"""modules/brief/router.py — Brief REST endpoints (S11).

Mounts at ``/brief`` via the registry (``MODULE``). Read-only, template-based (NO AI).
Returns the locked envelope ``{success, data, warning?}``. No routines (morning-pull,
which assembles the brief on a timer, lives in automation — this is the on-demand read).

  GET /brief          generate + return today's brief (priorities severity-ordered)
  GET /brief/history  past persisted briefs (newest-first), [] if none
"""

from __future__ import annotations

from fastapi import APIRouter

from core.base import BaseModule
from core.responses import ok

from . import service

router = APIRouter(tags=["brief"])


@router.get("")
def get_brief():
    """Assemble today's brief from live data. Fail-soft per source — always 200 (a source
    down → warning + that rule skipped; no rule fires → priorities=[] + honest summary)."""
    brief = service.generate_brief()
    warning = "; ".join(brief.warnings) if brief.warnings else None
    return ok(data=brief.model_dump(), warning=warning)


@router.get("/history")
def get_brief_history():
    """Past persisted briefs (newest-first). [] if none persisted yet (200, not 404)."""
    briefs = service.get_history()
    return ok(data=[b.model_dump() for b in briefs])


MODULE = BaseModule(name="brief", router=router)
