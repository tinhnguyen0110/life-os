"""modules/macro/router.py — Macro REST endpoints + daily macro-poll routine (MACRO-1).

Mounts at ``/macro`` via the registry (``MODULE``). Locked envelope ({success, data,
warning?}). Business logic is in service.py; this is HTTP shape + status codes only.

  GET /macro/overview              latest value + descriptive trend per indicator (NEUTRAL)
  GET /macro/history?indicator&days  one indicator's time-series

Macro data updates slowly (monthly CPI, ~6-weekly Fed), so the poll routine is DAILY
(cron 06:00 UTC) — not the 5-min market cadence. Gated on the master automation switch
via the shared run-record wrapper.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from core.agent_errors import agent_error_response  # AGENT-ERROR-P6 (#46): flat REST error parity
from core.base import BaseModule, Routine
from core.responses import ok

from . import service

logger = logging.getLogger("life-os.macro.router")

router = APIRouter(tags=["macro"])

MACRO_POLL_ID = "macro-poll"


@router.get("/overview")
def macro_overview():
    """Every tracked macro indicator's latest value + DESCRIPTIVE trend (up/down/flat
    vs the prior observation). NEUTRAL — no forecast. Fail-open: no live source → honest
    mock + warning, never 500."""
    overview, warnings = service.get_overview()
    return ok(data=overview.model_dump(), warning="; ".join(warnings) if warnings else None)


@router.get("/history")
def macro_history(indicator: str, days: int = 365):
    """One indicator's time-series over the last ``days`` (oldest→newest). 404 if the
    indicator is not tracked. Empty series → honest empty points list, never 500."""
    hist = service.get_history(indicator, days=days)
    if hist is None:
        tracked = ", ".join(service.tracked_indicators())
        return agent_error_response(
            "NOT_FOUND", f"macro indicator {indicator!r} not tracked",
            hint=f"valid indicators: {tracked}")
    return ok(data=hist.model_dump())


# --------------------------------------------------------------------------- #
# Daily poll routine — fetch + persist the latest macro observations.           #
# --------------------------------------------------------------------------- #
def _macro_poll_work() -> tuple[str, str]:
    """The poll work — returns (status, detail). Raises are caught by the wrapper.
    Fail-open per indicator (service.refresh handles it). warn if any warning."""
    written, warnings = service.refresh()
    status = "warn" if warnings else "ok"
    detail = f"macro refresh: points={written}" + (
        f" warnings={len(warnings)}" if warnings else "")
    return status, detail


def macro_poll() -> None:
    """Scheduler entry point — runs the refresh via the unified run-record wrapper,
    gated on the master automation switch (no-ops when off)."""
    from modules.automation import service as auto
    auto.run_scheduled(MACRO_POLL_ID, _macro_poll_work)


_MACRO_POLL_ROUTINE = Routine(
    id=MACRO_POLL_ID,
    func=macro_poll,
    trigger="cron",
    trigger_args={"hour": 6, "minute": 0},
    name="macro-poll (fetch + persist Fed/CPI/DXY, daily 06:00 UTC)",
    enabled=True,
)


MODULE = BaseModule(name="macro", router=router, routines=[_MACRO_POLL_ROUTINE])
