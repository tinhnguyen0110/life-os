"""modules/claude_usage/schema.py — Claude Usage shapes (Sprint 7, SPEC §S9). FROZEN.

The GET /claude-usage payload. Token usage/history/per-model/cost are REAL (from
stats-cache.json, cost derived via pricing table). cap is a configurable default
+ manual override (no rate-limit ceiling on disk). resetIn/weekly/byProject are
honest STUBS (not readable from disk) — None unless a manual override sets them.
Derived fields carry their inputs (pct carries {used, cap}; cost carries tokens).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DayBurn(BaseModel):
    """One day's token burn (history chart point)."""

    date: str = Field(..., description="ISO date, e.g. 2026-06-06")
    label: str = Field(..., description="weekday short label (T2..CN)")
    tokens: int = Field(..., ge=0)


class ModelBurn(BaseModel):
    """Per-model token + derived-cost breakdown."""

    model: str
    inputTokens: int = Field(..., ge=0)
    outputTokens: int = Field(..., ge=0)
    cacheReadTokens: int = Field(..., ge=0)
    cacheCreateTokens: int = Field(..., ge=0)
    total: int = Field(..., ge=0, description="inputTokens + outputTokens")
    costUSD: float = Field(..., ge=0, description="derived from pricing table (cache unpriced)")


class ClaudeUsage(BaseModel):
    """GET /claude-usage .data — composite usage view."""

    model: str = Field(..., description="most-used model label (highest total)")
    used: int = Field(..., ge=0, description="tokens in active window (default = today's total)")
    cap: int = Field(..., ge=0, description="configured cap (default 200_000; manual-override) — NOT from disk")
    pct: float = Field(..., description="round(used/cap*100, 1) — carries {used, cap}")
    remaining: int = Field(..., ge=0, description="max(cap - used, 0)")
    resetIn: str | None = Field(None, description="STUB: None unless manual override")
    weekly: int | None = Field(None, description="STUB: None unless manual override")
    series: list[DayBurn] = Field(default_factory=list, description="last 7 days (chart)")
    today: int = Field(..., ge=0, description="today's (or lastComputedDate's) tokens")
    avgPerDay: int = Field(..., ge=0, description="7-day mean tokens (round int)")
    peak: DayBurn = Field(..., description="highest-burn day in series")
    byModel: list[ModelBurn] = Field(default_factory=list, description="per model, total desc")
    costUSD: float = Field(..., ge=0, description="derived: sum of per-model cost — NOT stats-cache costUSD")
    byProject: None = Field(None, description="STUB this sprint (per-project not in stats-cache)")
    asOf: str = Field(..., description="lastComputedDate (freshness)")
    stale: bool = Field(..., description="asOf < today")
    source: str = Field(..., description="'stats-cache' | 'manual'")


class ManualOverride(BaseModel):
    """Body for T2's PUT — user-set values for data not on disk."""

    cap: int | None = Field(default=None, ge=0)
    resetIn: str | None = Field(default=None)
    weekly: int | None = Field(default=None, ge=0)
