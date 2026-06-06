"""modules/journal/schema.py — Journal shapes (Sprint 9, SPEC §S7). FROZEN.

A journal entry = `journal/<id>.md` (YAML front-matter + markdown body). ONE
unified entry: mock trade-log fields (date/action/asset/size/px/tag/reason/pnl)
+ SPEC decision fields OPTIONAL (thesis/negation/confidence/channel/outcome/lesson).
pnl is a free-form percent STRING ("+5.5%", null=open). Derived stats carry inputs.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Action = Literal["BUY", "SELL"]
Channel = Literal["crypto", "etf", "vn", "dry"]
Outcome = Literal["open", "right", "wrong"]


class JournalEntry(BaseModel):
    """A stored journal entry. id = slug(asset)-<6hex>; timestamps ISO-8601 UTC."""

    id: str
    date: str = Field(..., description="ISO-8601 UTC decision date")
    action: Action
    asset: str = Field(..., min_length=1)
    size: str = Field("", description="free-form display, e.g. '$2,000'")
    px: str = Field("", description="free-form display, e.g. '$68,240'")
    tag: str = Field("", description="ladder/dca/rebalance/value... free-form")
    reason: str = Field(..., min_length=1, description="decision rationale")
    channel: Channel | None = None
    thesis: str | None = None
    negationCondition: str | None = None
    confidence: int | None = Field(None, ge=0, le=100, description="0-100; 422 if out of range")
    pnl: str | None = Field(None, description="null=open; '+5.5%'/'-4.1%' when closed")
    outcome: Outcome = Field("open")
    lesson: str | None = None
    createdAt: str
    updatedAt: str


class JournalInput(BaseModel):
    """POST/PUT body — id + timestamps server-set. PUT closes a trade (set pnl/outcome/lesson)."""

    date: str | None = Field(None, description="decision date; defaults to now on create")
    action: Action
    asset: str = Field(..., min_length=1)
    size: str = ""
    px: str = ""
    tag: str = ""
    reason: str = Field(..., min_length=1)
    channel: Channel | None = None
    thesis: str | None = None
    negationCondition: str | None = None
    confidence: int | None = Field(None, ge=0, le=100)
    pnl: str | None = None
    outcome: Outcome | None = Field(None, description="default open; on close right/wrong by pnl sign")
    lesson: str | None = None


class CalibrationBand(BaseModel):
    """One confidence band vs actual win-rate (closed+confident entries only)."""

    band: str = Field(..., description="e.g. '50-60'")
    predicted: float = Field(..., description="band midpoint")
    actual: float = Field(..., description="win-rate % within the band")
    n: int = Field(..., ge=1, description="count in band (n=0 bands omitted)")


class JournalStats(BaseModel):
    """GET /journal .data — entries + derived performance/calibration stats."""

    entries: list[JournalEntry] = Field(default_factory=list)
    count: int = Field(..., ge=0)
    winRate: float | None = Field(None, description="closed pnl>0 / total closed; None if 0 closed; carries {wins,closed}")
    avgPnl: float | None = Field(None, description="mean parsed closed pnl %; None if 0 closed; carries {sum,closed}")
    ladderDiscipline: float | None = Field(None, description="count(tag=='ladder')/total; None if 0; '% ladder-tagged'")
    thisMonth: dict = Field(..., description="{total,buy,sell,ladder} for current month")
    calibration: list[CalibrationBand] = Field(default_factory=list, description="confidence buckets vs actual; [] if none")
