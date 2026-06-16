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
    """One position. RAW inputs (qty, avgCost) + provenance (source, asOf).

    FINANCE-CORRECTNESS (Task #49): additive enrichment so the agent/FE can read a
    token's worth from the payload. ``price``/``usdValue``/``changePct`` are SURFACED
    from the same per-holding numbers ``_aggregate`` already computes (NOT re-priced) —
    the per-holding usdValue sums to the channel's ``ChannelAlloc.value`` (consistency
    invariant). Sub-$1 holdings fold into ONE per-channel ``·dust`` summary entry
    (``isDust=True``, ``count`` set) so the list isn't cluttered by dust — the dust's
    usdValue still counts toward the channel + total (fold is DISPLAY-only)."""

    channel: Channel
    symbol: str = Field(..., min_length=1)
    qty: float = Field(..., ge=0)
    # OKX-FINANCE (G2): avgCost is OPTIONAL — an OKX per-coin balance is VALUE-ONLY
    # (OKX unified-account exposes no per-coin cost basis), so it carries avgCost=None
    # and its per-coin P&L is honest-null. A manual holding still sets a real avgCost.
    # None NEVER fabricates a 0-cost (which would read as +∞% gain — honest-mirror).
    avgCost: float | None = Field(None, ge=0, description="avg cost per unit; None = no per-coin basis (OKX value-only)")
    source: str = Field("manual", description="provenance: manual | import | okx | ...")
    asOf: str | None = Field(None, description="ISO-8601 UTC last edited")
    # FINANCE-CORRECTNESS (Task #49) — additive per-holding enrichment, all nullable.
    price: float | None = Field(
        None,
        description="current unit price (USD). From the live market quote; the avgCost "
                    "estimate when no quote (source=cost-fallback); None when unpriceable "
                    "(OKX value-only coin with no usdValue). NULL on a ·dust summary entry "
                    "(a sum-of-many has no single price).",
    )
    usdValue: float | None = Field(
        None,
        description="current market value (USD) = price×qty, the SAME number that sums to "
                    "this channel's ChannelAlloc.value (consistency invariant). avgCost×qty "
                    "when no quote (honest estimate). None when unpriceable (missing price ≠ "
                    "zero worth). On a ·dust entry: the SUM of the folded holdings' usdValue.",
    )
    changePct: float | None = Field(
        None,
        description="24h % change, derived via market.derive_change_pct (the same one feed "
                    "the watchlist uses). None when there is no price series for the symbol. "
                    "NULL on a ·dust summary entry.",
    )
    isDust: bool = Field(
        False,
        description="True ONLY on a per-channel ·dust summary entry (collapses the channel's "
                    "0<usdValue<$1 holdings into one line). A real holding is always False.",
    )
    count: int | None = Field(
        None,
        description="# of holdings folded into a ·dust summary entry; set ONLY on a dust "
                    "entry (None on every real holding).",
    )
    # FINANCE-ASSISTANT P1 T5 (#52) — the holding's OWN P&L (abs/pct from its OWN avgCost),
    # SURFACED from the per-holding number _aggregate already computes (NOT recomputed). This
    # is the per-holding granularity where a basis-less coin's null doesn't mask a real-basis
    # coin's pnl (the channel-level ChannelAlloc.pnl is honestly null when basisUnknown — e.g.
    # a USDT-dominated crypto channel — which would otherwise hide PEPE's real -58%). A coin
    # with a real avgCost → real pnl; a basis-less coin (avgCost None → cost 0) → abs/pct null
    # (PnL honest-null rule). NULL on a ·dust summary entry (a sum-of-many has no single pnl).
    pnl: PnL | None = Field(
        None,
        description="this holding's own P&L (abs/pct from its own avgCost vs current value); "
                    "carries {cost, current}. None on a ·dust entry; abs/pct null for a "
                    "basis-less holding (cost 0). Same number _aggregate computed (not re-derived).",
    )


class PnL(BaseModel):
    """Profit/loss — carries cost+current so abs/pct are self-verifiable."""

    cost: float = Field(..., description="cost basis (input)")
    current: float = Field(..., description="current market value (input)")
    abs: float | None = Field(
        None,
        description="current - cost; null when basisUnknown (no real cost basis → a value-"
                    "only inflow would read as a fake gain). Keep cost/current as the raw $.",
    )
    pct: float | None = Field(None, description="abs/cost*100; null when cost==0 (no div-0) or basisUnknown")


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
    # NB4 — honest framing of value-only / stablecoin-heavy data (read-path derived):
    basisUnknown: bool = Field(
        False,
        description="true when the majority (by value) of this channel's holdings lack a "
                    "cost basis (avgCost) — so pnl is computed against cost=0 and must NOT "
                    "be read as a real gain (value-only data, e.g. OKX per-coin)",
    )
    stableValue: float | None = Field(
        None,
        description="crypto channel only: USD value held in stablecoins (USDT/USDC/…) — "
                    "dry-powder-like, NOT crypto exposure. None for non-crypto channels",
    )
    stablePct: float | None = Field(
        None,
        description="crypto channel only: stableValue / channel value × 100 (None when "
                    "non-crypto or channel value is 0)",
    )


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


class PnlScope(BaseModel):
    """FINANCE-AUDIT2 (#66): the SCOPE of ``pnlTotal`` so it can't be misread as whole-portfolio.
    pnlTotal aggregates ONLY the holdings WITH a real cost basis (accAvgPx); the no-basis
    stablecoin/dust value is EXCLUDED (you can't claim gain/loss on a no-basis position). So
    pnlTotal.pct is the return on the BASIS-KNOWN slice — ``coveragePct`` says how much of the
    book that slice is (e.g. ~2% when the book is mostly stablecoin cash), so a reader doesn't
    take a −72%-of-the-2% as a −72%-whole-portfolio."""

    basis: str = Field("known-cost-only", description="pnlTotal covers only holdings with a real cost basis")
    coveragePct: float | None = Field(
        None, description="known-basis value / totalValue × 100 — how much of the book pnlTotal covers")
    note: str = Field(..., description="plain-language scope (the basis-known % + what's excluded)")


class FinanceOverview(BaseModel):
    """S5 overview composite."""

    totalValue: float = Field(..., description="sum of all holding market values")
    change: Change | None = Field(None, description="portfolio change; None if no series")
    holdings: list[Holding] = Field(default_factory=list)
    allocations: list[ChannelAlloc] = Field(default_factory=list)
    pnlTotal: PnL = Field(
        ..., description="P&L over the BASIS-KNOWN holdings only (accAvgPx-priced) — see pnlScope "
                         "for coverage; abs/pct null when no holding has a cost basis")
    pnlScope: PnlScope | None = Field(
        None, description="FINANCE-AUDIT2 (#66): the SCOPE of pnlTotal (basis-known coverage %) "
                          "so it isn't misread as whole-portfolio")
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


# --------------------------------------------------------------------------- #
# Scenario / what-if simulate (POST /finance/simulate)                          #
# --------------------------------------------------------------------------- #
class SimulateInput(BaseModel):
    """POST /finance/simulate body. ``allocation`` = a HYPOTHETICAL channel→weight map
    ({crypto: 60, etf: 20, ...}) — the values are treated as relative WEIGHTS and
    normalized to 100% (so the user may pass percentages OR dollar amounts; either
    way the shape is what's analyzed). At least one channel required; negative weights
    rejected (422 at the route). Unknown channel keys rejected (422)."""

    allocation: dict[str, float] = Field(
        ..., description="hypothetical {channel: weight} — normalized to 100%")


class ChannelShape(BaseModel):
    """One channel's weight in a (current or hypothetical) allocation + its delta."""

    channel: Channel
    pct: float = Field(..., description="% of the allocation (normalized to 100)")
    targetPct: float = Field(0.0, description="golden-path target for this channel (0 if none)")
    drift: float = Field(..., description="pct - targetPct (signed)")
    deltaVsCurrentPct: float | None = Field(
        None, description="this allocation's pct minus the CURRENT portfolio's pct (None if no current)")


class AllocationShape(BaseModel):
    """The risk-shape of one allocation (the hypothetical OR the current), NEUTRAL."""

    hhi: float | None = Field(None, description="Σ(channel weight²); 1=all in one channel, lower=spread")
    concentrationTopPct: float | None = Field(None, description="largest channel weight %")
    concentrationTopChannel: str | None = None
    totalAbsDrift: float = Field(0.0, description="Σ|channel drift vs target| (pp)")
    rebalanceDistance: float = Field(0.0, description="½·Σ|drift| = min turnover % to hit targets")
    channels: list[ChannelShape] = Field(default_factory=list)


class SimulateResult(BaseModel):
    """POST /finance/simulate — the hypothetical allocation's shape side-by-side with the
    current portfolio's shape, plus the HHI delta. PURE NUMBERS for the user to judge —
    explicitly NOT advice (no buy/sell/recommend)."""

    hypothetical: AllocationShape
    current: AllocationShape
    hhiDelta: float | None = Field(None, description="hypothetical.hhi - current.hhi (None if either missing)")
    normalized: bool = Field(False, description="True if input weights didn't sum to 100 and were normalized")
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
