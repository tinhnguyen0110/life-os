"""modules/automation/router.py — Automation REST endpoints + morning-pull routine (S10A).

Mounts at ``/routines`` via the registry (``MODULE``). GET lists all routines +
run_log stats; PATCH toggles (persisted); POST runs on-demand. The automation
module OWNS the morning-pull routine (cron 08:00) — supplied via routines(),
wrapped by record_routine_run so its timer fires record a run_log row.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from core.agent_errors import agent_error_response  # AGENT-ERROR-P6 (#46): flat REST error parity
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
        return agent_error_response("NOT_FOUND", f"routine {routine_id!r} not found",
                                    hint="GET /routines for valid ids")
    return ok(data=info.model_dump())


@router.post("/{routine_id}/run")
def run_routine(routine_id: str):
    """Run a routine on-demand NOW (records a run_log row). 404 if unknown.

    A failed run is still 200 — the run HAPPENED and is logged as an error row
    (a failed-but-logged run is the correct outcome, not a 500).
    """
    run = service.run_routine(routine_id)
    if run is None:
        return agent_error_response("NOT_FOUND", f"routine {routine_id!r} not found",
                                    hint="GET /routines for valid ids")
    return ok(data=run.model_dump())


# --------------------------------------------------------------------------- #
# morning-pull routine (cron 08:00) — owned here, wrapped to record run_log.    #
# --------------------------------------------------------------------------- #
def _morning_pull_job() -> None:
    """Scheduler entry point for morning-pull. Gated on the master automation switch
    (S12); records a run_log row when on, no-ops when automation is off."""
    service.run_scheduled("morning-pull", service.morning_pull)


def _brief_hour() -> int:
    """morning-pull cron hour from settings (S12 wiring; default 8). Read at module load
    = applied at boot. Fail-open to 8 if settings unreadable. (A live briefHour change
    takes effect on next boot — single-user; documented in §Assumptions.)"""
    try:
        from modules.settings import service as cfg
        return cfg.get_config().briefHour
    except Exception:
        return 8


_MORNING_PULL_ROUTINE = Routine(
    id="morning-pull", func=_morning_pull_job, trigger="cron",
    trigger_args={"hour": _brief_hour()}, name="Morning Pull", enabled=True,
)


# --------------------------------------------------------------------------- #
# macro-snapshot routine (cron 07:30) — FINANCE-ASSISTANT P1 (#52). Owned by the #
# macro module (func resolved on demand to avoid an import cycle), wrapped here   #
# so its timer fires record a run_log row + respects the master automation gate.  #
# --------------------------------------------------------------------------- #
def _macro_snapshot_job() -> None:
    """Scheduler entry point for macro-snapshot. Gated on the master automation switch;
    records a run_log row when on, no-ops when off. Resolves the macro module's snapshot
    func on demand (import inside the fn → no import-time cycle)."""
    from modules.macro.service import macro_sentiment_snapshot
    service.run_scheduled("macro-snapshot", macro_sentiment_snapshot)


_MACRO_SNAPSHOT_ROUTINE = Routine(
    id="macro-snapshot", func=_macro_snapshot_job, trigger="cron",
    trigger_args={"hour": 7, "minute": 30}, name="Macro Snapshot", enabled=True,
)


MODULE = BaseModule(
    name="routines", router=router,
    routines=[_MORNING_PULL_ROUTINE, _MACRO_SNAPSHOT_ROUTINE],
)
