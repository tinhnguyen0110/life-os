"""modules/dev_activity/router.py — dev-activity REST + scan routine + registration (DEV-TRACING-P1, #63).

Mounts at ``/dev_activity`` via the registry (``MODULE``). Locked envelope {success, data, warning?}.
Business logic + git-scan in service.py, derive in reader.py — this is HTTP shape + the daily scan
routine only. No auth (single-user). No cred (P1 = local git only).

GET  /dev_activity            → the scan overview (byDay/byRepo/summary + warnings). honest-empty.
POST /dev_activity/scan       → trigger a re-scan now (idempotent upsert). Returns the ScanResult.

Daily ``dev-activity-scan`` routine (cron, owned here, wrapped to record a run_log row + respect the
master automation gate) keeps the store fresh.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from core.base import BaseModule, Routine
from core.responses import ok

from . import reader, service

logger = logging.getLogger("life-os.dev_activity.router")

router = APIRouter(tags=["dev_activity"])

SCAN_ROUTINE_ID = "dev-activity-scan"


@router.get("")
def get_dev_activity(days: int = Query(90, ge=1, le=365, description="backfill window (VN days)")):
    """The dev-activity board over the last ``days``: per VN day × repo × source (you/other)
    commits + LOC(filtered, informational) + active-span, plus byRepo + summary. honest-empty;
    warnings name unconfigured roots/identity so 'no data' isn't misread. Reads the STORED scan
    (trigger a fresh scan via POST /dev_activity/scan or the daily routine)."""
    overview = reader.get_overview(days)
    warning = "; ".join(overview.warnings) if overview.warnings else None
    return ok(data=overview.model_dump(), warning=warning)


@router.post("/scan")
def trigger_scan(days: int = Query(90, ge=1, le=365, description="backfill window to scan (VN days)")):
    """Re-scan the configured local repos NOW → idempotent upsert per (date,repo,source). Returns
    {scannedRepos, days, rowsUpserted, yourCommits, warnings}. Safe to call repeatedly (overwrites
    each day's aggregate, never double-counts)."""
    result = service.scan(days)
    warning = "; ".join(result["warnings"]) if result["warnings"] else None
    return ok(data=result, warning=warning)


# --------------------------------------------------------------------------- #
# dev-activity-scan routine (cron 05:00 UTC = 12:00 VN — after the workday's    #
# morning commits land) — owned here, wrapped to record a run_log row.          #
# --------------------------------------------------------------------------- #
def _scan_work() -> tuple[str, str]:
    """One scan run — returns (status, detail). warn if the scan surfaced warnings (roots
    unreachable / identity unset), else ok. Raises only on a true failure (caught by the wrapper)."""
    result = service.scan()
    status = "warn" if result["warnings"] else "ok"
    detail = (f"dev-activity-scan: repos={result['scannedRepos']} rows={result['rowsUpserted']} "
              f"yourCommits={result['yourCommits']}"
              + (f" warnings={len(result['warnings'])}" if result["warnings"] else ""))
    return status, detail


def dev_activity_scan() -> None:
    """Scheduler entry point — gated on the master automation switch, records a run_log row (same
    unified wrapper as the other routines)."""
    from modules.automation import service as auto
    auto.run_scheduled(SCAN_ROUTINE_ID, _scan_work)


_SCAN_ROUTINE = Routine(
    id=SCAN_ROUTINE_ID,
    func=dev_activity_scan,
    trigger="cron",
    trigger_args={"hour": 5, "minute": 0},
    name="dev-activity-scan (scan local git repos → commits/LOC/span, daily 05:00 UTC)",
    enabled=True,
)


# The registry discovers this MODULE (adding this folder is the only wiring — no core/main.py edit).
MODULE = BaseModule(name="dev_activity", router=router, routines=[_SCAN_ROUTINE])
