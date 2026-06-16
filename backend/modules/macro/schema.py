"""modules/macro/schema.py — Macro economic data shapes (MACRO-1).

Captures real-time macro context (Fed funds rate / US CPI / DXY dollar index) so an
agent reading the user's portfolio understands the BACKGROUND, not just coin prices.
NEUTRAL by contract: the overview describes the latest value + the trend vs the prior
observation (up/down/flat) — it NEVER forecasts ("Fed will cut"). The agent reasons;
this module only reports observed data.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# The macro indicators tracked. Keys are stable API identifiers (the FRED series id
# lives in config, not here, so the API stays source-agnostic).
# FINANCE-ASSISTANT P1 (#52): + the macro-cycle substrate indicators.
MacroIndicator = Literal[
    "fed_funds_rate", "cpi", "dxy",
    "yield_curve_10y2y", "unemployment", "m2_liquidity", "industrial_production",
]

# Direction of the latest move vs the prior observation — DESCRIPTIVE, not predictive.
Trend = Literal["up", "down", "flat"]


class MacroPoint(BaseModel):
    """One observation of one macro indicator at a point in time."""

    indicator: str = Field(..., description="indicator key (fed_funds_rate|cpi|dxy)")
    value: float = Field(..., description="observed value (rate %, index level)")
    ts: str = Field(..., description="ISO-8601 UTC observation date")
    source: str = Field(..., description="'fred' | 'mock'")


class MacroIndicatorView(BaseModel):
    """Latest reading of one indicator + its descriptive trend vs the prior point."""

    indicator: str
    label: str = Field(..., description="human label, e.g. 'Fed Funds Rate'")
    unit: str = Field(..., description="'%' | 'index'")
    latest: float | None = Field(default=None, description="most recent value, None if no data")
    asOf: str | None = Field(default=None, description="ISO-8601 of the latest point, None if none")
    previous: float | None = Field(default=None, description="prior observation's value, None if <2 points")
    change: float | None = Field(default=None, description="latest - previous (signed), None if <2 points")
    trend: Trend = Field(default="flat", description="descriptive direction vs prior (NOT a forecast)")
    source: str = Field(default="mock", description="'fred' | 'mock' of the latest point")
    points: int = Field(default=0, ge=0, description="how many observations are stored")
    # FINANCE-ASSISTANT P1 (#52): a SIMPLE source-based confidence seam (Phase-1 stub).
    # source='fred' (real CSV) → 0.9; 'mock' (fail-open placeholder) → 0.2. Phase-2 replaces
    # this with compute_q() (freshness × coverage × agreement) WITHOUT touching call-sites.
    confidence: float = Field(
        default=0.2, ge=0.0, le=1.0,
        description="Phase-1 source-based confidence (fred 0.9 / mock 0.2); Phase-2 → compute_q()")


class MacroOverview(BaseModel):
    """The macro view: every tracked indicator's latest value + descriptive trend.
    NEUTRAL — no prediction. ``asOf`` is the freshest point across all indicators."""

    indicators: list[MacroIndicatorView] = Field(default_factory=list)
    asOf: str | None = Field(default=None, description="freshest observation across indicators")
    source: str = Field(default="mock", description="'fred' if any live data, else 'mock'")


class MacroHistory(BaseModel):
    """A single indicator's time-series over a window (oldest→newest)."""

    indicator: str
    points: list[MacroPoint] = Field(default_factory=list)
