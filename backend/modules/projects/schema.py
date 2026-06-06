"""modules/projects/schema.py — the FROZEN common ProjectStatus shape (Tier-S).

SPEC §0 line 207. Every one of the 14 screens + every later reader
(finance/market/journal) inherits this shape, so it is LOCKED on commit. Field
names + types here are the contract; frontend/lib/types.ts mirrors this exactly.

health buckets, the None-vs-default policy for human fields, and the metrics
sub-shape are all decided by the architect's Logic block — see reader.py for the
derivation. This file only declares the shape + validates the boundary.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# The four health buckets, derived from days-since-last-commit (see reader).
Health = Literal["act", "slow", "stall", "dead"]


class ProjectMetrics(BaseModel):
    """Per-project metrics sub-shape. git-derived where possible; stars/testPass
    are honest None this build (no GitHub API, no test-artifact parser)."""

    commits: int = Field(0, ge=0, description="git rev-list --count HEAD")
    branch: str = Field("", description="current branch (git rev-parse --abbrev-ref HEAD)")
    lang: str | None = Field(None, description="dominant tracked-file language, else None")
    testPass: int | None = Field(None, description="test pass %, None — no parser this sprint")
    stars: int | None = Field(None, description="repo stars, None — no GitHub API this build")


class ProjectStatus(BaseModel):
    """The common project status shape — FROZEN. Read by all 14 screens.

    Human-authored fields (progress/next/users) come from status.md front-matter
    and default to None/0 when absent — never fabricated. git-derived fields
    (health/last/lastDays/metrics) come from read-only local git.
    """

    id: str = Field(..., min_length=1, description="slug = repo folder name, lowercased, non-alnum→'-'")
    name: str = Field(..., min_length=1, description="status.md name: else repo folder name")
    desc: str | None = Field(None, description="status.md desc:/goal: else None")
    health: Health = Field(..., description="act|slow|stall|dead from lastDays")
    progress: int | None = Field(
        None, ge=0, le=100, description="status.md progress 0-100, else None"
    )
    users: int = Field(0, ge=0, description="status.md users, else 0")
    last: str | None = Field(None, description="ISO-8601 UTC of last commit, None if unknown")
    lastDays: int | None = Field(
        None, ge=0, description="whole UTC days since last commit, None if unknown"
    )
    next: str | None = Field(None, description="status.md next action, else None")
    repo: str = Field(..., description="absolute path of the source repo")
    metrics: ProjectMetrics = Field(default_factory=ProjectMetrics)  # type: ignore[arg-type]
    routines: list[str] = Field(default_factory=list, description="routine ids touching this project")
    lastAuto: str | None = Field(None, description="ISO-8601 UTC of last automation touch, else None")


class ProjectRegisterInput(BaseModel):
    """Body of POST /projects (register). id is derived = slug(name); the body's
    human fields are written into the new project's status.md front-matter."""

    name: str = Field(..., min_length=1, max_length=200, description="display name")
    repo: str = Field(..., min_length=1, description="absolute path of the source git repo")
    goal: str | None = Field(None, max_length=2000, description="one-line goal → status.md desc")
    progress: int | None = Field(None, ge=0, le=100, description="initial progress 0-100")
    next: str | None = Field(None, max_length=2000, description="initial next action")
    users: int | None = Field(None, ge=0, description="initial users count")


class ProjectAbandonInput(BaseModel):
    """Body of POST /projects/{id}/abandon. Sets the graveyard flag in status.md;
    orthogonal to commit-age health (abandon is an explicit human decision)."""

    reason: str = Field(..., min_length=1, max_length=2000, description="why abandoned")
    atProgress: int | None = Field(
        None, ge=0, le=100, description="progress % at abandon, else current"
    )
