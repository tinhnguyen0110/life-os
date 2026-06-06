"""modules/market/schema.py — Market data shapes (Sprint 3, SPEC §S8).

Simple in implementation, full in features: quotes, alerts (+history), macro
signals, price history. assetClass drives the reader branch (crypto→CoinGecko,
else mock). changePct is derived server-side (price_history), nullable when the
series is too short.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AssetClass = Literal["crypto", "etf", "vn"]
AlertOp = Literal["above", "below"]
AlertState = Literal["hit", "near", "far"]


class AssetQuote(BaseModel):
    """A single asset's current quote. price/changePct derived; source tags origin."""

    symbol: str = Field(..., min_length=1, description="ticker, e.g. BTC")
    name: str = Field(..., min_length=1, description="display name")
    assetClass: AssetClass
    price: float = Field(..., ge=0)
    changePct: float | None = Field(None, description="server-derived % change, None if no series")
    currency: str = Field("USD")
    ts: str = Field(..., description="ISO-8601 UTC of this quote")
    source: str = Field(..., description="coingecko | mock | last-known")


class AlertRule(BaseModel):
    """A user price-alert rule. above: price≥threshold; below: price≤threshold.

    ``id`` is server-assigned (slug(symbol)+counter) on create; clients DELETE by id.
    """

    id: str = Field(..., min_length=1, description="server-assigned rule id")
    symbol: str = Field(..., min_length=1)
    op: AlertOp
    threshold: float = Field(..., gt=0)
    enabled: bool = Field(True)


class AlertRuleInput(BaseModel):
    """POST /market/alerts body — id is assigned server-side, not supplied."""

    symbol: str = Field(..., min_length=1)
    op: AlertOp
    threshold: float = Field(..., gt=0)
    enabled: bool = Field(True)


class AlertTrigger(BaseModel):
    """An evaluated alert rule against the current quote — what the user sees live."""

    symbol: str
    op: AlertOp
    threshold: float
    price: float
    state: AlertState = Field(..., description="hit | near (|distancePct|≤5) | far")
    distancePct: float = Field(..., description="(threshold-price)/price*100 — signed proximity %")


class AlertEvent(BaseModel):
    """A fired alert recorded to history (run_log) — user-visible alert history."""

    symbol: str
    op: AlertOp
    threshold: float
    price: float
    ts: str = Field(..., description="ISO-8601 UTC when it fired")


class MacroSignal(BaseModel):
    """A macro indicator (Fear&Greed/BTC Dominance/Brent) — stub mock this build.

    value is a STRING ("38", "54%", "$72") — display-ready, mixed units.
    """

    name: str = Field(..., min_length=1)
    value: str
    status: str = Field(..., description="e.g. fear | greed | neutral")
    note: str = Field("", description="short human note")


class PricePoint(BaseModel):
    """One price_history point (history endpoint)."""

    asset: str
    price: float
    ts: str
