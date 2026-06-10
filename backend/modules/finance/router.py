"""modules/finance/router.py — Finance REST endpoints (Sprint 4, T2).

Mounts at ``/finance`` via the registry (``MODULE``). Endpoints return the locked
envelope ``{success, data, warning?}``. Business logic is in service.py; this is
HTTP shape + status codes only. No routine this module (finance is read-on-demand;
prices come from the market module's market-poll).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from core.base import BaseModule
from core.responses import ok

from . import service
from .schema import CryptoBasisInput, GoldenPathInput, HoldingInput

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


@router.get("/{channel}")
def get_channel(channel: str):
    """S6 detail for one channel: alloc + holdings (priced, P&L) + ladder. 404 if unknown."""
    detail, warnings = service.get_channel(channel)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"channel {channel!r} not found")
    return ok(data=detail, warning="; ".join(warnings) if warnings else None)


MODULE = BaseModule(name="finance", router=router)
