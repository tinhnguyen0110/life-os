"""modules/dev_activity/schema.py — dev-activity shapes (DEV-TRACING-P1, #63).

The dev_activity contract (FROZEN once announced — P2/FE mirror this). A *scan* reads local git repos
→ per (date-VN × repo × source) aggregates. ``source`` = "you" (author-email ∈ the identity-map) or
"other" (a teammate / AI-commit on a shared repo) — both STORED + counted-in-totals-but-TAGGED, never
merged or silently dropped. LOC is INFORMATIONAL (Goodhart — surfaced secondary, never ranked/scored).
All dates are VN-day (UTC+7). NEUTRAL — no AI, no auth, no score.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Source tag: a commit is "you" (your git email) or "other" (teammate / shared-repo AI commit).
# Both are real dev-activity on the user's machine; the tag keeps team-context honest, not dropped.
Source = str  # Literal["you", "other"] kept open-str for forward-compat (P2 may add "ai"/remotes)


class RepoDay(BaseModel):
    """One (date × repo × source) aggregate row — the stored + surfaced unit."""

    date: str = Field(..., description="VN calendar day YYYY-MM-DD")
    repo: str = Field(..., description="repo name (basename of the git dir)")
    source: Source = Field(..., description="'you' (your email) | 'other' (teammate/shared)")
    commits: int = Field(..., ge=0, description="non-merge commits on this day in this repo")
    locAdded: int = Field(..., ge=0, description="lines added (LOC_SKIP-filtered; INFORMATIONAL, not a score)")
    locDeleted: int = Field(..., ge=0, description="lines deleted (LOC_SKIP-filtered; informational)")
    firstTs: str | None = Field(default=None, description="earliest commit time today HH:MM (VN), or None")
    lastTs: str | None = Field(default=None, description="latest commit time today HH:MM (VN), or None")
    activeSpan: str = Field(default="", description="lastTs−firstTs formatted 'Hh Mm' (or '' if single/none)")


class DayView(BaseModel):
    """All repos active on one VN day + the day roll-up (the 'you' totals; 'other' shown per-repo)."""

    date: str
    repos: list[RepoDay] = Field(default_factory=list)
    totalCommits: int = Field(..., ge=0, description="your (source=you) commits across all repos this day")
    activeRepos: int = Field(..., ge=0, description="distinct repos you committed to this day")


class RepoSummary(BaseModel):
    """Per-repo roll-up over the scan range (your activity)."""

    repo: str
    commits: int = Field(..., ge=0)
    locAdded: int = Field(..., ge=0)
    locDeleted: int = Field(..., ge=0)
    activeDays: int = Field(..., ge=0, description="distinct VN days you committed to this repo")
    lastActive: str | None = Field(default=None, description="most-recent VN day you committed, or None")


class DevActivitySummary(BaseModel):
    """The whole-scan roll-up (your activity; LOC informational)."""

    totalCommits: int = Field(..., ge=0, description="your commits across the range")
    activeDays: int = Field(..., ge=0, description="distinct VN days you committed (any repo)")
    activeRepos: int = Field(..., ge=0, description="distinct repos you committed to")
    locAdded: int = Field(..., ge=0, description="informational — never a score")
    locDeleted: int = Field(..., ge=0, description="informational")
    topRepos: list[str] = Field(default_factory=list, description="your repos by commit count, desc (top 5)")


class DevActivityOverview(BaseModel):
    """GET /dev_activity — the scan result. honest-mirror: no repos/commits → []+0; roots unreachable
    → warnings names them (NOT silent-zero). ``source`` always present so team-context is honest."""

    rangeDays: int = Field(..., ge=1, description="the backfill window scanned (days)")
    byDay: list[DayView] = Field(default_factory=list, description="per VN day, newest-first")
    byRepo: list[RepoSummary] = Field(default_factory=list, description="per repo, by commits desc")
    otherRepos: list[RepoDay] = Field(default_factory=list,
                                      description="'other'-source rows (team context), tagged, not in your totals")
    summary: DevActivitySummary
    scannedRepos: int = Field(..., ge=0, description="git repos found + scanned")
    lastScanned: str | None = Field(default=None,
                                    description="ISO ts of the most-recent scan, or None if never scanned (#77 honest freshness)")
    warnings: list[str] = Field(default_factory=list,
                                description="honest non-fatal issues: roots unreachable / repo skipped / identity unset / no-scan-yet")


class ScanResult(BaseModel):
    """POST /dev_activity/scan — what one re-scan did (idempotent upsert)."""

    scannedRepos: int = Field(..., ge=0)
    days: int = Field(..., ge=1, description="the backfill window scanned")
    rowsUpserted: int = Field(..., ge=0, description="(date,repo,source) aggregate rows written")
    yourCommits: int = Field(..., ge=0, description="your commits found in the window")
    warnings: list[str] = Field(default_factory=list)
