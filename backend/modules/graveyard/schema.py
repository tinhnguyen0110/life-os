"""modules/graveyard/schema.py — Graveyard shapes (Sprint 8, SPEC §S4). FROZEN.

GET /graveyard → GraveyardStats. A grave = an abandoned project (the `abandoned`
flag, orthogonal to commit-age health). Derived pattern stats carry their inputs
(avgPeak carries {sum, count}). lesson is null when not recorded — never fabricated.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GraveProject(BaseModel):
    """One abandoned project in the graveyard."""

    id: str = Field(..., description="project id (for restore)")
    name: str
    peak: int = Field(..., ge=0, description="abandonedProgress; fallback progress; else 0")
    reason: str = Field(..., description="abandonedReason")
    lesson: str | None = Field(None, description="status.md lesson, else None (never fabricated)")
    died: str = Field(..., description="abandonedAt (ISO-8601 UTC; FE formats MM/YYYY)")
    users: int = Field(..., ge=0, description="users at abandon (for reached/before)")
    health: str = Field(..., description="commit-age health — DISPLAY ONLY (abandoned ≠ dead)")
    repo: str


class ReasonCount(BaseModel):
    """A grouped abandon-reason + its frequency."""

    reason: str
    count: int = Field(..., ge=0)


class GraveyardStats(BaseModel):
    """GET /graveyard .data — the abandoned set + pattern aggregates."""

    graves: list[GraveProject] = Field(default_factory=list)
    count: int = Field(..., ge=0, description="number abandoned")
    avgPeak: float = Field(..., ge=0, description="mean graves' peak, 1dp — carries {sum,count}; 0 if empty")
    commonReasons: list[ReasonCount] = Field(default_factory=list, description="grouped, count desc")
    reachedUser: int = Field(..., ge=0, description="graves with users>0 at abandon")
    beforeUser: int = Field(..., ge=0, description="graves with users==0 (build-to-90/0-user pattern)")
    lessons: list[str] = Field(default_factory=list, description="distinct non-empty lessons (first-seen order)")
