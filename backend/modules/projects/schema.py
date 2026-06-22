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

# PROJECTS-UNIFY T2 (#113): where a project's repo entry came from.
#   config     = a settings.project_repos built-in
#   registered = a projects/<id>/status.md with a repo: pointer (manual register)
#   auto       = auto-discovered under DEV_TRACING_ROOTS (a .git repo, no manual register)
# Precedence on id collision: registered > config > auto (human/config truth wins).
ProjectSource = Literal["config", "registered", "auto"]


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
    source: ProjectSource = Field(
        "config",
        description="repo origin: config|registered|auto (#113). read_one always sets it explicitly; "
        "the 'config' default only applies to direct construction.",
    )
    hidden: bool = Field(
        False,
        description="not-interested flag (#113), set via /hide. INDEPENDENT of abandoned (a dead "
        "project w/ a lesson) and of health=='dead' (git-derived). list_projects excludes hidden.",
    )


class RepoDevStat(BaseModel):
    """PROJECTS-UNIFY T1 (#112): the dev-activity aggregate for ONE matched repo (slug == project_id).
    Carries ``repo`` (the raw basename, to distinguish a slug-collision) so two different-path repos
    that slug to the same id are both returned, each identified by its basename."""

    repo: str = Field(..., description="the dev_activity repo basename (raw-case) this stat is for")
    commits: int = Field(0, ge=0, description="Σ commits over the window (all sources)")
    locNet: int = Field(0, description="Σ(loc_added - loc_deleted) — net LOC, can be negative")
    lastActiveDay: str | None = Field(None, description="most recent VN-day with activity, or None")
    activeDays: int = Field(0, ge=0, description="count of distinct VN-days with activity in the window")


class ProjectDevStat(BaseModel):
    """PROJECTS-UNIFY T1 (#112): a project's dev-activity, JOINED by slug(dev_activity.repo)==project_id.

    ``found`` = whether the project's repo appears in the dev_activity scan (DEV_TRACING_ROOTS). A
    registered project NOT in the scan → ``found: false`` + ``commits: 0`` + ``reason`` (HONEST — never
    a fabricated 0-as-if-real). A slug-COLLISION (≥2 repos same basename→same slug) → ``found: true``,
    the aggregate summed across matches, AND ``matches`` listing each repo + a ``warning`` (honest, not
    silently merged). REST + MCP byte-identical (#24)."""

    projectId: str = Field(..., description="the project slug this dev-stat is for")
    found: bool = Field(..., description="true if the repo is in the dev_activity scan; false = not scanned")
    commits: int = Field(0, ge=0, description="Σ commits across matched repos over the window")
    locNet: int = Field(0, description="Σ net LOC (added-deleted) across matched repos")
    lastActiveDay: str | None = Field(None, description="most recent active VN-day across matches, or None")
    days: int = Field(..., ge=1, description="the window in VN-days this stat covers")
    activeDays: int = Field(0, ge=0, description="distinct active VN-days in the window (across matches)")
    matches: list[RepoDevStat] = Field(default_factory=list,
                                       description="per-repo breakdown (>1 only on a slug-collision)")
    reason: str | None = Field(None, description="why found=false (e.g. not in DEV_TRACING_ROOTS), else None")
    warning: str | None = Field(None, description="honest note, e.g. a slug-collision across repos")


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
    lesson: str | None = Field(
        None, max_length=2000, description="what was learned (Graveyard lesson); never fabricated"
    )
