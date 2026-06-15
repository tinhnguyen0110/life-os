"""modules/market/router.py — Market REST endpoints + market-poll routine (S3).

Mounts at ``/market`` via the registry (``MODULE``). Endpoints return the locked
envelope ``{success, data, warning?}``. Business logic is in service.py; this is
HTTP shape + status codes only.

T3 lives here too: ``MODULE.routines()`` hands the scheduler the ``market-poll``
routine (every 5 min: fetch → persist → eval alerts → record fired alerts).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from core.base import BaseModule, Routine
from core.responses import ok
from store import db

from . import service
from .schema import AlertRuleInput

logger = logging.getLogger("life-os.market.router")

router = APIRouter(tags=["market"])

MARKET_POLL_ID = service.MARKET_POLL_ID


@router.get("")
def get_market():
    """Live market view: quotes + alert triggers + macro + alert history."""
    data, warnings = service.get_market()
    return ok(data=data, warning="; ".join(warnings) if warnings else None)


@router.get("/history/{symbol}")
def get_history(symbol: str, hours: int = 24):
    """price_history points for a TRACKED asset over the last ``hours`` (default 24).

    A tracked asset with no series yet → 200 + {points: []} (empty is a valid
    state — raw-data-first, like /projects:[] or /market triggers:[]). Only a
    symbol NOT in the tracked universe is a true 404.
    """
    tracked = {a.get("symbol") for a in service.tracked_assets()}
    if symbol not in tracked:
        raise HTTPException(status_code=404, detail=f"asset {symbol!r} is not tracked")
    points = service.history(symbol, hours=hours)
    return ok(data={"points": [p.model_dump() for p in points]})


@router.get("/indicators/{symbol}")
def get_indicators(symbol: str, indicators: str = "summary", hours: int = 720,
                   full: bool = False):
    """Technical indicators over a TRACKED asset's close series (price_history).

    ``indicators`` = comma-separated ∈ {sma,ema,rsi,macd,bollinger,atr,summary}
    (default ``summary``). ``hours`` windows the series (default 720h ≈ 30d so the
    longer indicators have enough points); ``full=true`` attaches the aligned series
    (default = latest values only). Output is NEUTRAL technical data — no buy/sell
    advice. A short/empty series → per-indicator warning, never a 500. 404 only if
    the symbol is not in the tracked universe.
    """
    tracked = {a.get("symbol") for a in service.tracked_assets()}
    if symbol not in tracked:
        raise HTTPException(status_code=404, detail=f"asset {symbol!r} is not tracked")
    names = indicators.split(",")
    data, warnings = service.compute_indicators(symbol, names, hours=hours, full=full)
    return ok(data=data, warning="; ".join(warnings) if warnings else None)


@router.get("/alerts")
def list_alerts():
    """All configured alert rules."""
    return ok(data=[r.model_dump() for r in service.list_rules()])


@router.post("/alerts")
def set_alert(body: AlertRuleInput):
    """Create an alert rule (id assigned server-side). Returns the created rule."""
    rule = service.add_rule(body.symbol, body.op, body.threshold, body.enabled)
    return ok(data=rule.model_dump())


@router.delete("/alerts/{rule_id}")
def delete_alert(rule_id: str):
    """Delete the alert rule by id. 404 if no such rule."""
    if not service.delete_rule(rule_id):
        raise HTTPException(status_code=404, detail=f"no alert rule {rule_id!r}")
    return ok(data={"deleted": rule_id})


# --------------------------------------------------------------------------- #
# T3 — the market-poll routine (rule-based, no AI; fetch+persist+alert detect)  #
# --------------------------------------------------------------------------- #
def _market_poll_work() -> tuple[str, str]:
    """The poll work — returns (status, detail). Raises are caught by the wrapper.

    Fail-open per asset (service.poll_once handles it). warn if any per-asset warning.
    """
    summary = service.poll_once()
    status = "warn" if summary.get("warnings") else "ok"
    detail = (f"polled: persisted={summary['persisted']} fired={summary['fired']}"
              + (f" warnings={len(summary['warnings'])}" if summary.get("warnings") else ""))
    return status, detail


def market_poll() -> None:
    """Scheduler entry point — runs the poll via the unified run-record wrapper, gated on
    the master automation switch (S12; no-ops when off). S10A: all routines share the
    wrapper instead of hand-rolling record_run + try/except."""
    from modules.automation import service as auto
    auto.run_scheduled(MARKET_POLL_ID, _market_poll_work)


_MARKET_POLL_ROUTINE = Routine(
    id=MARKET_POLL_ID,
    func=market_poll,
    trigger="interval",
    trigger_args={"minutes": 5},
    name="market-poll (fetch + persist + alert detect, 5min)",
    enabled=True,
)


MODULE = BaseModule(name="market", router=router, routines=[_MARKET_POLL_ROUTINE])
