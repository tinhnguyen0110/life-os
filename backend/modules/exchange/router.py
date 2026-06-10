"""modules/exchange/router.py — OKX exchange endpoints.

Mounts at /exchange via registry. All responses: {success, data, warning?}.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from core.base import BaseModule, Routine
from core.responses import ok

from . import service

logger = logging.getLogger("life-os.exchange.router")

router = APIRouter(tags=["exchange"])


@router.get("")
def get_exchange():
    """OKX account overview: total USD, top balances, open positions."""
    overview, warning = service.get_overview()
    return ok(data=overview.model_dump(), warning=warning)


@router.get("/balances")
def get_balances():
    """OKX asset balances (sorted by USD value)."""
    overview, warning = service.get_overview()
    return ok(
        data=[b.model_dump() for b in overview.balances],
        warning=warning,
    )


@router.get("/positions")
def get_positions():
    """Open positions (margin/futures)."""
    overview, warning = service.get_overview()
    return ok(
        data=[p.model_dump() for p in overview.positions],
        warning=warning,
    )


@router.patch("/sync")
def force_sync():
    """Force a fresh pull from OKX API (ignores cache)."""
    overview, warning = service.sync()
    return ok(data=overview.model_dump(), warning=warning)


def _bg_sync() -> None:
    """Background sync — swallows all errors (scheduler routine)."""
    try:
        service.sync()
    except Exception as exc:
        logger.warning("background OKX sync failed: %s", exc)


MODULE = BaseModule(
    name="exchange",
    router=router,
    routines=[
        Routine(
            id="okx-sync",
            name="OKX account sync",
            func=_bg_sync,
            trigger="interval",
            trigger_args={"minutes": 15},
        )
    ],
)
