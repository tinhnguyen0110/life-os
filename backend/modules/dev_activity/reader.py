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
    Truncation,
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


# #91: past this day-window the per-day repos[] detail is OMITTED (aggregate mode) so a 1-year call
# fits an agent's token budget. 90 = the FE's max range (the FE never asks past it → FE always gets
# full detail; only the agent's large call aggregates). byRepo + summary + daily counts are KEPT.
_DETAIL_THRESHOLD = 90


def _empty_overview(days: int, warnings: list[str]) -> DevActivityOverview:
    """#91: an honest-empty overview for a non-positive ``days`` (0/negative) — NO silent coerce to 1."""
    return DevActivityOverview(
        rangeDays=max(0, days), aggregated=False, byDay=[], byRepo=[], otherRepos=[],
        summary=DevActivitySummary(totalCommits=0, activeDays=0, activeRepos=0,
                                   locAdded=0, locDeleted=0, topRepos=[]),
        scannedRepos=0, lastScanned=store.get_last_scanned() if False else None, warnings=warnings,
    )


def get_overview(days: int = _DEFAULT_DAYS, *, run_scan_warnings: bool = True) -> DevActivityOverview:
    """The dev-activity board over the last ``days`` (VN). Reads STORED aggregates (does NOT scan —
    the scan is the routine / POST /dev_activity/scan). honest-empty + warnings for unconfigured
    roots/identity so the agent can distinguish 'no data' from 'not set up'.

    #91 agent-first hardening:
      - ``days`` <= 0 → honest-empty + a message (NOT a silent coerce to 1).
      - ``days`` = N → EXACTLY N VN-days ending today VN (days=1 = today only, no yesterday off-by-one).
      - ``days`` > 90 (the FE's max) → AGGREGATE mode: byDay carries summarized days (per-day repos[]
        omitted) + otherRepos dropped → bounded output an agent can read (a 1-year call was ~186KB).
        ``aggregated=True`` + a truncate-HINT in warnings. ≤90 → full detail (the FE is unaffected)."""
    # #91 fix-3: days <= 0 → honest-empty (NOT silent days=1).
    if days <= 0:
        return _empty_overview(days, ["days must be ≥ 1 — got %d; returning empty (no window)" % days])
    # #91 fix-3: days = N = exactly N VN-days ending TODAY VN. The `date` column is the VN-day string
    # (service._vn_day); since_vn = today_vn - (N-1) so days=1 = today only (no yesterday off-by-one).
    today_vn = service._now().astimezone(service.VN_TZ).date()
    since = (today_vn - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    aggregate = days > _DETAIL_THRESHOLD
    warnings: list[str] = []
    last_scanned: str | None = None
    never_scanned = False
    try:
        rows = [_row_to_repoday(r) for r in store.rows_since(since)]
        last_scanned = store.get_last_scanned()  # #77: honest freshness
        never_scanned = last_scanned is None and store.row_count() == 0
    except Exception as exc:  # store unavailable → honest-empty, never crash (fail-soft, like _series)
        logger.warning("dev_activity read failed: %s", exc)
        rows = []
        warnings.append(f"dev_activity store read failed ({type(exc).__name__})")

    # surface config warnings (roots unreachable / identity unset) so honest-empty isn't misread.
    if run_scan_warnings:
        # #77: never-scanned (roots configured but no scan ever ran) → tell the agent to scan,
        # distinct from the not-configured case (so honest-empty isn't read as "no activity").
        if never_scanned and service.scan_roots():
            warnings.append("no scan yet — POST /dev_activity/scan or wait for the daily routine")
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
            # #91: aggregate mode (days>90) DROPS the per-day repos[] detail (the token-flood) —
            # the date + totalCommits + activeRepos counts are kept so the agent still sees the
            # daily shape; ≤90 keeps full repos[] (the FE's heatmap/peak-hours need it).
            date=date, repos=([] if aggregate else day_rows),
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

    truncated: Truncation | None = None
    if aggregate:
        # #91: STRUCTURED truncation policy-data (cairn-#295 — the agent reads the flags; each surface
        # phrases its own hint from this, NOT a transport-baked string).
        truncated = Truncation(
            daysSummarized=len(by_day), detailThresholdDays=_DETAIL_THRESHOLD,
            perDayDetailOmitted=True, otherReposOmitted=True,
        )
        # ALSO a transport-AGNOSTIC prose line in warnings for a quick read (it names no MCP tool —
        # "Use days<=N" is a param hint both surfaces share, so centralizing the prose is fine).
        warnings.append(
            f"aggregated: {len(by_day)} day(s) summarized — per-day repos[] + otherRepos omitted "
            f"past {_DETAIL_THRESHOLD}d (token budget); read byRepo + summary + per-day counts. "
            f"Use days<={_DETAIL_THRESHOLD} for full per-day detail."
        )

    return DevActivityOverview(
        rangeDays=days, aggregated=aggregate, truncated=truncated, byDay=by_day, byRepo=by_repo,
        # #91: otherRepos kept at ≤90 (the FE's you-vs-other bar reads it); DROPPED in aggregate mode
        # (>90) so the agent's large view isn't byte-doubled with the 'other' rows.
        otherRepos=([] if aggregate else other_rows),
        summary=summary, scannedRepos=len({r.repo for r in rows}),
        lastScanned=last_scanned, warnings=warnings,  # #77: honest freshness
    )
