"""modules/dev_activity/reader.py — dev-activity READ/derive surface (DEV-TRACING-P1, #63).

Derives the agent-readable overview from the stored (date,repo,source) aggregates: byDay + byRepo +
summary, with the 'other'-source rows surfaced SEPARATELY (team context, tagged, NOT in your totals).
LOC is INFORMATIONAL (never ranked). honest-empty: no rows → []+0; the scan's warnings (roots
unreachable / identity unset) ride on the overview so an agent never misreads "no data" as "no work".
NO writes here (reads only); the scan lives in service.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta

from . import service, store
from .schema import (
    DayView,
    DevActivityOverview,
    DevActivitySummary,
    RepoDay,
    RepoSummary,
)

logger = logging.getLogger("life-os.dev_activity.reader")

_DEFAULT_DAYS = 90


def _row_to_repoday(r: sqlite3.Row) -> RepoDay:
    return RepoDay(
        date=r["date"], repo=r["repo"], source=r["source"], commits=int(r["commits"]),
        locAdded=int(r["loc_added"]), locDeleted=int(r["loc_deleted"]),
        firstTs=r["first_ts"], lastTs=r["last_ts"],
        activeSpan=service._span(r["first_ts"], r["last_ts"]),
    )


def get_overview(days: int = _DEFAULT_DAYS, *, run_scan_warnings: bool = True) -> DevActivityOverview:
    """The dev-activity board over the last ``days`` (VN). Reads STORED aggregates (does NOT scan —
    the scan is the routine / POST /dev_activity/scan). honest-empty + warnings for unconfigured
    roots/identity so the agent can distinguish 'no data' from 'not set up'."""
    days = max(1, days)
    since = (service._now() - timedelta(days=days)).strftime("%Y-%m-%d")
    warnings: list[str] = []
    try:
        rows = [_row_to_repoday(r) for r in store.rows_since(since)]
    except Exception as exc:  # store unavailable → honest-empty, never crash
        logger.warning("dev_activity read failed: %s", exc)
        rows = []
        warnings.append(f"dev_activity store read failed ({type(exc).__name__})")

    # surface config warnings (roots unreachable / identity unset) so honest-empty isn't misread.
    if run_scan_warnings:
        if not service.scan_roots():
            warnings.append("DEV_TRACING_ROOTS not set — nothing scanned")
        if not service.your_emails():
            warnings.append("DEV_TRACING_EMAILS not set — your commits tag 'other' (totals 0 until set)")

    you_rows = [r for r in rows if r.source == "you"]
    other_rows = [r for r in rows if r.source != "you"]

    # byDay (newest-first; your rows drive the day roll-up, other rows shown within the day too).
    by_day_map: dict[str, list[RepoDay]] = {}
    for r in rows:
        by_day_map.setdefault(r.date, []).append(r)
    by_day: list[DayView] = []
    for date in sorted(by_day_map, reverse=True):
        day_rows = by_day_map[date]
        you_day = [r for r in day_rows if r.source == "you"]
        by_day.append(DayView(
            date=date, repos=day_rows,
            totalCommits=sum(r.commits for r in you_day),
            activeRepos=len({r.repo for r in you_day}),
        ))

    # byRepo (your activity, by commits desc).
    repo_map: dict[str, list[RepoDay]] = {}
    for r in you_rows:
        repo_map.setdefault(r.repo, []).append(r)
    by_repo: list[RepoSummary] = []
    for repo, rr in repo_map.items():
        by_repo.append(RepoSummary(
            repo=repo, commits=sum(x.commits for x in rr),
            locAdded=sum(x.locAdded for x in rr), locDeleted=sum(x.locDeleted for x in rr),
            activeDays=len({x.date for x in rr}),
            lastActive=max((x.date for x in rr), default=None),
        ))
    by_repo.sort(key=lambda s: -s.commits)

    summary = DevActivitySummary(
        totalCommits=sum(r.commits for r in you_rows),
        activeDays=len({r.date for r in you_rows}),
        activeRepos=len({r.repo for r in you_rows}),
        locAdded=sum(r.locAdded for r in you_rows),
        locDeleted=sum(r.locDeleted for r in you_rows),
        topRepos=[s.repo for s in by_repo[:5]],
    )

    return DevActivityOverview(
        rangeDays=days, byDay=by_day, byRepo=by_repo, otherRepos=other_rows,
        summary=summary, scannedRepos=len({r.repo for r in rows}), warnings=warnings,
    )
