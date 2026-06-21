"""modules/market/schema.py — Market data shapes (Sprint 3, SPEC §S8).

Simple in implementation, full in features: quotes, alerts (+history), macro
signals, price history. assetClass drives the reader branch (crypto→CoinGecko,
else mock). changePct is derived server-side (price_history), nullable when the
series is too short.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AssetClass = Literal["crypto", "etf", "vn", "gold"]
AlertOp = Literal["above", "below"]
AlertState = Literal["hit", "near", "far"]

# --- indicator-based alerts (additive to the price-threshold alerts) ---------
# kind selects which TA condition the rule fires on:
#   rsi_below   — RSI(period) <= value           (e.g. oversold RSI < 30)
#   rsi_above   — RSI(period) >= value           (e.g. overbought RSI > 70)
#   price_cross_sma_above — latest close crossed ABOVE SMA(period) this step
#   price_cross_sma_below — latest close crossed BELOW SMA(period) this step
#   macd_cross_bull — MACD line crossed ABOVE its signal line this step
#   macd_cross_bear — MACD line crossed BELOW its signal line this step
IndicatorKind = Literal[
    "rsi_below", "rsi_above",
    "price_cross_sma_above", "price_cross_sma_below",
    "macd_cross_bull", "macd_cross_bear",
]


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


# --------------------------------------------------------------------------- #
# Indicator-based alert rules (TA conditions, additive to price alerts)         #
# --------------------------------------------------------------------------- #
class IndicatorAlertRule(BaseModel):
    """A technical-indicator alert. Evaluated against the asset's close series via
    ta.py (NOT a price threshold). ``value`` is the comparison level for the rsi_*
    kinds (e.g. 30 / 70) and IGNORED for the cross kinds (the cross is self-defining);
    ``period`` parameterises the indicator (RSI period / SMA period; ignored for MACD,
    which uses the standard 12/26/9)."""

    id: str = Field(..., min_length=1, description="server-assigned rule id")
    symbol: str = Field(..., min_length=1)
    kind: IndicatorKind
    value: float = Field(0.0, description="threshold for rsi_* kinds; ignored for cross kinds")
    period: int = Field(14, gt=0, description="RSI/SMA period; ignored for MACD")
    enabled: bool = Field(True)


class IndicatorAlertRuleInput(BaseModel):
    """POST /market/indicator-alerts body — id assigned server-side."""

    symbol: str = Field(..., min_length=1)
    kind: IndicatorKind
    value: float = Field(0.0)
    period: int = Field(14, gt=0)
    enabled: bool = Field(True)


class IndicatorTrigger(BaseModel):
    """An evaluated indicator rule — what the user sees live. ``fired`` = the
    condition is TRUE right now; ``detail`` carries the current indicator reading."""

    id: str
    symbol: str
    kind: IndicatorKind
    value: float
    period: int
    fired: bool
    detail: str = Field(..., description="current reading, e.g. 'RSI 28.4 ≤ 30'")


# --------------------------------------------------------------------------- #
# Watchlist — user-curated symbols with a quick view for a mini-chart screen     #
# --------------------------------------------------------------------------- #
class WatchlistInput(BaseModel):
    """POST /market/watchlist body — add a symbol to the watchlist."""

    symbol: str = Field(..., min_length=1, max_length=20)


class WatchlistItem(BaseModel):
    """One watchlist row — everything a crypto-watchlist card needs in one shot.

    ``sparkline`` is a short close-price array (oldest→newest) for a mini chart;
    ``rsi``/``trend`` are a quick TA read from ta.py. Any field that can't be
    computed (no series yet) is None — the row still renders, never a 500."""

    symbol: str
    name: str
    price: float
    changePct: float | None = Field(None, description="server-derived % change, None if unknown")
    source: str = Field(..., description="coingecko | mock | last-known")
    sparkline: list[float] = Field(default_factory=list, description="recent closes oldest→newest")
    rsi: float | None = Field(None, description="latest RSI(14), None if series too short")
    trend: str = Field("flat", description="up | down | flat — latest SMA-slope sign")
    warning: str | None = None


class MacroSignal(BaseModel):
    """A macro indicator (Fear&Greed/BTC Dominance/Brent).

    value is a STRING ("38", "54%", "$72") — display-ready, mixed units; "n/a" when the source
    has no data (honest — NEVER a fabricated number). FNG-HONEST (#44+#54): F&G + BTC.d now read the
    REAL macro store (single source of truth, byte-identical with decision/guardian); ``source``
    marks where the value came from (live | mock | n/a-ish), ``asOf`` is the data's freshness ts so
    an agent can trust + age it. Brent has no feed → value mock, source="mock".
    """

    name: str = Field(..., min_length=1)
    value: str
    status: str = Field(..., description="e.g. fear | greed | neutral")
    note: str = Field("", description="short human note")
    source: str = Field("mock", description="where the value came from: live (real feed) | mock (no feed)")  # FNG-HONEST
    asOf: str | None = Field(None, description="ISO ts of the underlying data point; None = no live data")  # FNG-HONEST


class PricePoint(BaseModel):
    """One price_history point (history endpoint)."""

    asset: str
    price: float
    ts: str
