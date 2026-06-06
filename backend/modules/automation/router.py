"""modules/automation/router.py — Automation REST endpoints + morning-pull routine (S10A).

Mounts at ``/routines`` via the registry (``MODULE``). GET lists all routines +
run_log stats; PATCH toggles (persisted); POST runs on-demand. The automation
module OWNS the morning-pull routine (cron 08:00) — supplied via routines(),
wrapped by record_routine_run so its timer fires record a run_log row.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from core.base import BaseModule, Routine
from core.responses import ok

from . import service
from .schema import ToggleInput

logger = logging.getLogger("life-os.automation.router")

router = APIRouter(tags=["automation"])


@router.get("")
def list_routines():
    """All routines (registered + event) + per-id run_log stats + roll-up."""
    return ok(data=service.list_routines().model_dump())


@router.patch("/{routine_id}")
def patch_routine(routine_id: str, body: ToggleInput):
    """Toggle a routine enabled/disabled (persisted in md_store). 404 if unknown."""
    info = service.set_enabled(routine_id, body.enabled)
    if info is None:
        raise HTTPException(status_code=404, detail=f"routine {routine_id!r} not found")
    return ok(data=info.model_dump())


@router.post("/{routine_id}/run")
def run_routine(routine_id: str):
    """Run a routine on-demand NOW (records a run_log row). 404 if unknown.

    A failed run is still 200 — the run HAPPENED and is logged as an error row
    (a failed-but-logged run is the correct outcome, not a 500).
    """
    run = service.run_routine(routine_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"routine {routine_id!r} not found")
    return ok(data=run.model_dump())


# --------------------------------------------------------------------------- #
# morning-pull routine (cron 08:00) — owned here, wrapped to record run_log.    #
# --------------------------------------------------------------------------- #
def _morning_pull_job() -> None:
    """Scheduler entry point for morning-pull (records a run_log row, fail-soft)."""
    service.record_routine_run("morning-pull", service.morning_pull)


_MORNING_PULL_ROUTINE = Routine(
    id="morning-pull", func=_morning_pull_job, trigger="cron",
    trigger_args={"hour": 8}, name="Morning Pull", enabled=True,
)


MODULE = BaseModule(name="routines", router=router, routines=[_MORNING_PULL_ROUTINE])
