"""modules/finance/router.py — Finance REST endpoints (Sprint 4, T2).

Mounts at ``/finance`` via the registry (``MODULE``). Endpoints return the locked
envelope ``{success, data, warning?}``. Business logic is in service.py; this is
HTTP shape + status codes only. No routine this module (finance is read-on-demand;
prices come from the market module's market-poll).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from core.base import BaseModule
from core.responses import ok

from . import service
from .schema import CryptoBasisInput, GoldenPathInput, HoldingInput, SimulateInput

logger = logging.getLogger("life-os.finance.router")

router = APIRouter(tags=["finance"])


@router.get("")
def get_finance():
    """S5 overview: total value, per-channel allocations + drift, total P&L."""
    overview, warnings = service.get_overview()
    return ok(data=overview.model_dump(), warning="; ".join(warnings) if warnings else None)


@router.get("/holdings")
def list_holdings():
    """All holdings (raw positions)."""
    return ok(data=[h.model_dump() for h in service.list_holdings()])


@router.post("/holdings")
def upsert_holding(body: HoldingInput):
    """Add or replace (by channel+symbol) a holding. Returns it."""
    holding = service.upsert_holding(body)
    return ok(data=holding.model_dump())


@router.delete("/holdings/{symbol}")
def delete_holding(symbol: str):
    """Delete a holding by symbol. 404 if no such holding."""
    if not service.delete_holding(symbol):
        raise HTTPException(status_code=404, detail=f"no holding {symbol!r}")
    return ok(data={"deleted": symbol})


@router.get("/golden-path")
def get_golden_path():
    """Current golden-path: {targets, ladder}. Baseline if unset.

    Response key is ``ladder`` (the per-channel {reference,rungs} dict) — SAME key
    as the PUT body (GoldenPathInput.ladder), so get/set are symmetric.
    """
    targets, ladder, warnings = service.get_golden_path()
    return ok(data={"targets": targets, "ladder": ladder},
              warning="; ".join(warnings) if warnings else None)


@router.put("/golden-path")
def set_golden_path(body: GoldenPathInput):
    """Set the golden-path (targets + per-channel ladder). One md_store commit.

    Returns {targets, ladder} — symmetric with the body shape.
    """
    targets, ladder = service.set_golden_path(body)
    return ok(data={"targets": targets, "ladder": ladder})


@router.get("/crypto-basis")
def get_crypto_basis():
    """Current crypto cost basis: {basis, source, setAt}. basis=null if never set."""
    basis, source = service.get_crypto_basis()
    return ok(data={"basis": basis, "source": source})


@router.put("/crypto-basis")
def set_crypto_basis(body: CryptoBasisInput):
    """Manual override of crypto cost basis. source='manual'; never overwritten by auto-snapshot."""
    payload = service.set_crypto_basis(body)
    return ok(data=payload)


# NOTE: registered BEFORE the /{channel} catch-all so "/analytics" routes here,
# not into get_channel("analytics").
@router.get("/analytics")
def get_analytics():
    """Portfolio analytics: actionable rebalance amounts (per channel: buy/sell |USD|
    to hit target), risk metrics (concentration HHI + top holdings + total drift), and
    return/volatility (when a value series exists). NEUTRAL numbers — NOT advice.
    Empty portfolio → zeroed/None metrics + warning, never a 500."""
    analytics, warnings = service.get_analytics()
    return ok(data=analytics.model_dump(), warning="; ".join(warnings) if warnings else None)


# NOTE: registered BEFORE the /{channel} catch-all (POST anyway, but keep it explicit).
@router.post("/simulate")
def simulate(body: SimulateInput):
    """What-if: shape a HYPOTHETICAL allocation ({channel: weight}) and compare it to the
    CURRENT portfolio — HHI / concentration / drift-vs-golden-path / turnover, plus the
    HHI delta and per-channel delta-vs-current. Weights are normalized to 100% (pass %s
    or $s). PURE NUMBERS for the user to judge — NOT advice.

    Validation (422): empty allocation · any negative weight · any unknown channel key
    (must be one of crypto/etf/vn/dry). A zero-sum allocation is accepted but yields a
    None HHI + warning (can't normalize), never a 500."""
    alloc = body.allocation
    if not alloc:
        raise HTTPException(status_code=422, detail="allocation must have at least one channel")
    valid = {"crypto", "etf", "vn", "dry"}
    unknown = [ch for ch in alloc if ch not in valid]
    if unknown:
        raise HTTPException(status_code=422,
                            detail=f"unknown channel(s) {unknown}; valid: {sorted(valid)}")
    negative = [ch for ch, w in alloc.items() if w < 0]
    if negative:
        raise HTTPException(status_code=422,
                            detail=f"negative weight(s) for {negative} — weights must be ≥0")
    result, warnings = service.simulate(alloc)
    return ok(data=result.model_dump(), warning="; ".join(warnings) if warnings else None)


# NOTE: /snapshot + /history registered BEFORE /{channel} so they route here.
@router.post("/snapshot")
def take_snapshot():
    """Record TODAY's portfolio equity snapshot (one row per UTC day — upsert, so a
    second snapshot today updates the day's value). Captures totalValue + per-channel
    breakdown from the live overview. An empty portfolio records totalValue=0 (a $0 day
    is a real point). Returns the snapshot {day, ts, totalValue, byChannel}."""
    snap = service.take_snapshot()
    return ok(data=snap)


@router.get("/history")
def get_history(days: int = Query(90, gt=0, le=365, description="lookback window in days (1..365)")):
    """Daily equity-curve points (oldest→newest) for the last ``days`` (default 90,
    capped 365). Empty list + warning when no snapshots exist yet — never a 500.
    ``days`` ≤0 or >365 → 422 (FastAPI validates the bounds)."""
    points = service.value_history(days=days)
    warning = "no portfolio snapshots yet — POST /finance/snapshot to start the equity curve" if not points else None
    return ok(data={"points": points, "days": days}, warning=warning)


@router.get("/{channel}")
def get_channel(channel: str):
    """S6 detail for one channel: alloc + holdings (priced, P&L) + ladder. 404 if unknown."""
    detail, warnings = service.get_channel(channel)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"channel {channel!r} not found")
    return ok(data=detail, warning="; ".join(warnings) if warnings else None)


MODULE = BaseModule(name="finance", router=router)
