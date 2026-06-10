"""modules/exchange/schema.py — OKX exchange shapes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OkxBalance(BaseModel):
    """One asset balance on OKX (unified account)."""

    symbol: str = Field(..., description="asset symbol e.g. BTC, USDT")
    available: float = Field(..., description="available balance")
    frozen: float = Field(0.0, description="frozen (in orders)")
    total: float = Field(..., description="available + frozen")
    usdValue: float | None = Field(None, description="USD equivalent if provided by OKX")


class OkxPosition(BaseModel):
    """One open position (margin / futures)."""

    instId: str = Field(..., description="instrument e.g. BTC-USDT-SWAP")
    side: str = Field(..., description="long | short")
    qty: float = Field(..., description="position size")
    avgOpenPrice: float = Field(..., description="average open price")
    unrealizedPnl: float = Field(..., description="unrealized PnL in USD")
    margin: float = Field(..., description="margin used")
    lever: str = Field(..., description="leverage")


class OkxOrder(BaseModel):
    """One completed order from history."""

    ordId: str
    instId: str
    side: str = Field(..., description="buy | sell")
    ordType: str = Field(..., description="market | limit | ...")
    sz: float = Field(..., description="quantity")
    px: float | None = Field(None, description="limit price (None for market)")
    fillPrice: float | None = Field(None, description="average fill price")
    fillSz: float = Field(0.0, description="filled quantity")
    state: str = Field(..., description="filled | partially_filled | canceled")
    ts: str = Field(..., description="ISO-8601 UTC creation time")


class ExchangeOverview(BaseModel):
    """Top-level OKX account snapshot."""

    totalUsdValue: float = Field(..., description="sum of all asset USD values")
    balances: list[OkxBalance] = Field(default_factory=list)
    positions: list[OkxPosition] = Field(default_factory=list)
    syncedAt: str | None = Field(None, description="ISO-8601 UTC last sync")
    configured: bool = Field(False, description="True if API key is set")
