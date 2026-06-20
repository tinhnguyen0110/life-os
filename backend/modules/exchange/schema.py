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
    # FINANCE-ASSISTANT P1 (#52) — OKX's per-coin cost-basis + its own unrealized P&L, all
    # ADDITIVE + NULLABLE. accAvgPx is the single source of truth for per-coin pnl (wired into
    # Holding.avgCost → the shipped _pnl() lights up). spotUpl/spotUplRatio are OKX's OWN P&L,
    # carried ONLY as a cross-check (NOT displayed as a 2nd pnl). None when OKX has no basis
    # (stablecoins, or coins held before OKX history — honest-null, never a fabricated 0).
    accAvgPx: float | None = Field(
        None, description="OKX accumulated avg cost price per unit (the per-coin basis); "
                          "None when OKX exposes none (stablecoin / pre-history coin)")
    spotUpl: float | None = Field(
        None, description="OKX's own unrealized P&L in USD (cross-check only, not a 2nd pnl)")
    spotUplRatio: float | None = Field(
        None, description="OKX's own unrealized P&L as a FRACTION (×100 = pct; cross-check)")
    # DUST-FOLD (#17) — ADDITIVE/NULLABLE (no break). When ``isDust`` is True this row is the
    # ONE ·dust summary (symbol="·dust", usdValue=Σ of folded sub-$1 balances, count=how many);
    # mirrors finance Holding.isDust/count so the FE/agent renders the summary the same way.
    isDust: bool = Field(
        False, description="True only on the synthetic ·dust summary row (folded sub-$1 balances)")
    count: int | None = Field(
        None, description="how many balances this ·dust summary folds (None on normal rows)")


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
