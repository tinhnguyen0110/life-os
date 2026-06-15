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


class ProjectBurn(BaseModel):
    """Per-project token + derived-cost breakdown (from transcript cwd attribution)."""

    project: str = Field(..., description="project name (cwd basename)")
    inputTokens: int = Field(..., ge=0)
    outputTokens: int = Field(..., ge=0)
    cacheReadTokens: int = Field(..., ge=0)
    cacheCreateTokens: int = Field(..., ge=0)
    total: int = Field(..., ge=0, description="inputTokens + outputTokens")
    costUSD: float = Field(..., ge=0, description="derived from pricing table")
    msgs: int = Field(..., ge=0, description="assistant-message count")


class ClaudeUsage(BaseModel):
    """GET /claude-usage .data — composite usage view."""

    model: str = Field(..., description="most-used model label (highest total)")
    used: int = Field(..., ge=0, description="tokens in active window (default = today's total)")
    cap: int = Field(..., ge=0, description="configured cap (default 200_000; manual-override) — NOT from disk")
    pct: float | None = Field(None, description="QUOTA-window used % (pct5h else weekly); 0-100 or None — NOT used/cap (NG1)")
    remaining: int | None = Field(None, ge=0, description="cap - used; None when used>cap (token quota unknown — NG1)")
    resetIn: str | None = Field(None, description="5h-window reset countdown (live quota snapshot) or manual override")
    weekly: int | None = Field(None, description="7-day used % (live quota snapshot) or manual override")
    pct5h: float | None = Field(None, description="LIVE: 5h rate-limit used % (quota snapshot) — None if snapshot absent")
    resetWeek: str | None = Field(None, description="LIVE: 7-day reset countdown (quota snapshot)")
    ctxPct: float | None = Field(None, description="LIVE: current SESSION context-window used % (quota snapshot)")
    ctxUsed: int | None = Field(None, description="LIVE: current session context tokens used (raw)")
    ctxMax: int | None = Field(None, description="LIVE: current session context window size (model-dependent: opus 1M, sonnet 200k)")
    ctxModel: str | None = Field(None, description="LIVE: model of the current session (from statusline)")
    quotaSource: str = Field("stub", description="'snapshot' (live statusline tee) | 'manual' | 'stub'")
    series: list[DayBurn] = Field(default_factory=list, description="last 7 days (chart)")
    today: int = Field(..., ge=0, description="today's (or lastComputedDate's) tokens")
    avgPerDay: int = Field(..., ge=0, description="7-day mean tokens (round int)")
    peak: DayBurn = Field(..., description="highest-burn day in series")
    byModel: list[ModelBurn] = Field(default_factory=list, description="per model, total desc")
    costUSD: float = Field(..., ge=0, description="derived: sum of per-model cost — NOT stats-cache costUSD")
    byProject: list[ProjectBurn] = Field(default_factory=list, description="per project (transcript cwd), total desc — LIVE")
    tokenSource: str = Field("stats-cache", description="'transcripts' (live .jsonl) | 'stats-cache' | 'none'")
    asOf: str = Field(..., description="freshness date — newest transcript day, or stats lastComputedDate")
    stale: bool = Field(..., description="asOf < yesterday")
    source: str = Field(..., description="'stats-cache' | 'manual'")


class ManualOverride(BaseModel):
    """Body for T2's PUT — user-set values for data not on disk."""

    cap: int | None = Field(default=None, ge=0)
    resetIn: str | None = Field(default=None)
    weekly: int | None = Field(default=None, ge=0)
