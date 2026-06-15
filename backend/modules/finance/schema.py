"""modules/finance/schema.py — Finance shapes (Sprint 4, SPEC §S5/§S6). FROZEN.

Self-describing-raw convention: every DERIVED field carries its inputs so an
external agent can verify the number without reading code. RAW fields (price,
qty, avgCost) are untagged.
  - PnL carries {cost, current} → abs/pct checkable.
  - ChannelAlloc carries {target, actual=pct} + driftAlert (5% rule lives in
    BACKEND, not FE) → drift + alert checkable.
  - LadderState carries {referencePrice, currentPrice, triggerPrice} → checkable.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Channel = Literal["crypto", "etf", "vn", "dry"]  # dry = "Dry powder" (SPEC §S5)


class Holding(BaseModel):
    """One position. RAW inputs (qty, avgCost) + provenance (source, asOf)."""

    channel: Channel
    symbol: str = Field(..., min_length=1)
    qty: float = Field(..., ge=0)
    avgCost: float = Field(..., ge=0, description="average cost per unit")
    source: str = Field("manual", description="provenance: manual | import | ...")
    asOf: str | None = Field(None, description="ISO-8601 UTC last edited")


class PnL(BaseModel):
    """Profit/loss — carries cost+current so abs/pct are self-verifiable."""

    cost: float = Field(..., description="cost basis (input)")
    current: float = Field(..., description="current market value (input)")
    abs: float = Field(..., description="current - cost")
    pct: float | None = Field(None, description="abs/cost*100; null when cost==0 (no div-0)")


class ChannelAlloc(BaseModel):
    """A channel's allocation slice. Carries {target, actual=pct} + driftAlert.

    driftAlert is the BACKEND's verdict on the 5% business rule (single source of
    truth) — FE renders the flag, never recomputes the threshold.
    """

    channel: Channel
    value: float = Field(..., description="current market value of this channel")
    pct: float = Field(..., description="actual % of total portfolio")
    target: float = Field(..., description="target % (golden-path)")
    drift: float = Field(..., description="pct - target (signed)")
    driftAlert: bool = Field(..., description="|drift| > 5 (5% rule decided server-side)")
    pnl: PnL


class LadderState(BaseModel):
    """Buy-ladder state for a channel. Carries referencePrice+currentPrice+triggers."""

    channel: Channel
    referencePrice: float = Field(..., description="anchor price (golden-path ladder.reference)")
    currentPrice: float = Field(..., description="current price (input)")
    rungsIn: int = Field(..., ge=0, description="# rungs where currentPrice ≤ triggerPrice")
    nextRung: dict | None = Field(
        None, description="{pct, triggerPrice} of the next rung not yet entered, or None"
    )
    distancePct: float | None = Field(
        None, description="(currentPrice - nextTrigger)/currentPrice*100; None if no nextRung"
    )


class Change(BaseModel):
    """Portfolio value change — abs + pct (self-describing)."""

    abs: float
    pct: float | None = None


class FinanceOverview(BaseModel):
    """S5 overview composite."""

    totalValue: float = Field(..., description="sum of all holding market values")
    change: Change | None = Field(None, description="portfolio change; None if no series")
    holdings: list[Holding] = Field(default_factory=list)
    allocations: list[ChannelAlloc] = Field(default_factory=list)
    pnlTotal: PnL
    dryPowder: float = Field(0.0, description="value of the 'dry' channel (dry powder)")
    series: list[float] = Field(default_factory=list, description="portfolio value over time ([] if none)")


# --------------------------------------------------------------------------- #
# Portfolio analytics (rebalance / risk / return) — NEUTRAL numbers, no advice   #
# --------------------------------------------------------------------------- #
class RebalanceAction(BaseModel):
    """Per-channel: where it is vs target + the actionable amount to get back.

    ``action`` ∈ buy | sell | hold. ``amount`` is the |USD| to move to reach the
    target weight (0 when on-target). NEUTRAL math — NOT investment advice."""

    channel: Channel
    currentValue: float
    currentPct: float
    targetPct: float
    targetValue: float = Field(..., description="targetPct% of totalValue")
    drift: float = Field(..., description="currentPct - targetPct (signed)")
    action: Literal["buy", "sell", "hold"]
    amount: float = Field(..., ge=0, description="|USD| to move toward target (0 if on-target)")


class ConcentrationItem(BaseModel):
    """One holding's weight in the portfolio (for the concentration view)."""

    symbol: str
    channel: Channel
    value: float
    pct: float = Field(..., description="% of total portfolio value")


class RiskMetrics(BaseModel):
    """Neutral portfolio-risk numbers (NO advice). All derived, self-describing."""

    topHoldingPct: float | None = Field(None, description="largest single holding as % of total")
    topHoldingSymbol: str | None = None
    top3Pct: float | None = Field(None, description="sum of the 3 largest holdings as % of total")
    hhi: float | None = Field(None, description="Herfindahl index of holding weights (0..1; 1=one asset)")
    holdingCount: int = Field(0, description="number of distinct holdings")
    totalAbsDrift: float = Field(0.0, description="Σ|channel drift| across channels (pp)")
    rebalanceDistance: float = Field(0.0, description="½·Σ|drift| = min turnover % to hit targets")


class ReturnMetrics(BaseModel):
    """Period return + volatility from the portfolio value series. None when there is
    no series yet (no snapshot routine this build — honest, not fabricated)."""

    points: int = Field(0, description="# series points used")
    totalReturnPct: float | None = Field(None, description="(last-first)/first*100")
    volatilityPct: float | None = Field(None, description="stddev of period-over-period % returns")
    available: bool = Field(False, description="True only when a real series exists")


class PortfolioAnalytics(BaseModel):
    """GET /finance/analytics — rebalance + risk + return. Pure numbers, no advice."""

    totalValue: float
    rebalance: list[RebalanceAction] = Field(default_factory=list)
    risk: RiskMetrics
    returns: ReturnMetrics
    asOf: str


class GoldenPathInput(BaseModel):
    """Body to set the golden-path: target % per channel + per-channel ladder."""

    targets: dict[str, float] = Field(..., description="channel -> target %")
    ladder: dict[str, dict] = Field(
        default_factory=dict,
        description="channel -> {reference: float, rungs: [float]} buy-ladder config",
    )


class HoldingInput(BaseModel):
    """Body to add/update a holding (upsert by symbol)."""

    channel: Channel
    symbol: str = Field(..., min_length=1)
    qty: float = Field(..., ge=0)
    avgCost: float = Field(..., ge=0)
    source: str = Field("manual")


class CryptoBasisInput(BaseModel):
    """Body to manually override the crypto cost basis (USD total)."""

    basis: float = Field(..., ge=0, description="total cost basis in USD")
