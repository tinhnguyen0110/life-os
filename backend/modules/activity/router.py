"""modules/activity/router.py — Activity REST endpoints (S10B).

Mounts at ``/activity`` via the registry (``MODULE``). Two read-only endpoints
returning the locked envelope ``{success, data, warning?}``. No routines — this
module only READS run_log (the routines that write it live in automation/market/
projects).

  GET /activity            feed + stats, optional ?routine= / ?status= / ?range=
  GET /activity/{run_id}   one run by its run_log PK (404 if no such run)

Filters are LENIENT — an unknown ?status / ?range is ignored (degrades to "all"),
NOT a 422. A typo'd filter returns data, never an error (locked w/ tester scaffold).
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from core.agent_errors import agent_error_response  # AGENT-ERROR-P6 (#46): flat REST error parity
from core.base import BaseModule
from core.responses import ok

from . import service

router = APIRouter(tags=["activity"])


@router.get("")
def get_activity(
    routine: str | None = Query(None, description="filter to one routine id"),
    status: str | None = Query(None, description="filter by status: ok|warn|error (unknown ignored)"),
    range: str | None = Query(None, description="window: today|24h|week|month|all (unknown ignored)"),
):
    """The cross-routine activity feed + roll-up stats. ``count`` is the full filtered
    total; ``runs`` is the newest-100 slice. All filters optional, AND-combined, and
    LENIENT (invalid status/range ignored → behaves as 'all')."""
    feed = service.get_feed(routine=routine, status=status, range=range)
    return ok(data=feed.model_dump())


@router.get("/{run_id}")
def get_activity_run(run_id: int):
    """One run by its run_log PK. 404 if no such run. (FastAPI 422s a non-int id.)"""
    run = service.get_run(run_id)
    if run is None:
        return agent_error_response("NOT_FOUND", f"run {run_id} not found",
                                    hint="GET /activity for valid run ids")
    return ok(data=run.model_dump())


MODULE = BaseModule(name="activity", router=router)
