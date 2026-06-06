"""modules/activity/service.py — run_log feed reader + roll-up stats (S10B).

Read-only over store.db.run_log. Builds the cross-routine activity timeline, applies
optional routine/status/range filters, derives per-run ``durationMs`` + the feed-level
``successRate`` (percentage) / ``avgDurationMs`` / ``byRoutine``.

Cap semantics: stats (count/okCount/successRate/byRoutine) are over the FULL filtered
set; ``runs`` is the newest-100 display slice. So a 110-run window → count=110, 100 rows.

Filters are LENIENT: an unknown ?status / ?range is IGNORED (returns all) rather than
erroring — a typo'd filter degrades to "all", never a 422 (locked w/ tester scaffold).

Pure projection — NO writes, NO AI. Routine display names resolve from the automation
catalog; an unknown id falls back to the id itself (forward-compat if a routine is
renamed/removed but old runs remain).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from store import db

from .schema import ActivityFeed, ActivityRun, RoutineBreakdown

logger = logging.getLogger("life-os.activity.service")

RUNS_CAP = 100  # newest-100 display slice — count stays the full filtered total

# Supported ?range windows → lookback timedelta. "today" = calendar-day (UTC); "all"
# / None = no time filter. Unknown key → ignored (treated as all).
_RANGES: dict[str, timedelta | None] = {
    "today": None,                     # special-cased (calendar day, not a lookback)
    "24h": timedelta(hours=24),
    "week": timedelta(days=7),
    "7d": timedelta(days=7),
    "month": timedelta(days=30),
    "30d": timedelta(days=30),
    "all": None,
}
_STATUSES = {"ok", "warn", "error"}


def _routine_name(routine_id: str) -> str:
    """Display name from the automation catalog, or the id if unknown (forward-compat)."""
    try:
        from modules.automation.service import _CATALOG_BY_ID
        cat = _CATALOG_BY_ID.get(routine_id)
        return cat["name"] if cat else routine_id
    except Exception:  # automation import problem must never break the feed
        return routine_id


def _duration_ms(started: str, finished: str | None) -> int | None:
    """finished-started in ms. None if no finished_at or either is unparseable (fail-open)."""
    if not finished:
        return None
    try:
        a = datetime.fromisoformat(started)
        b = datetime.fromisoformat(finished)
    except (ValueError, TypeError):
        return None
    ms = int((b - a).total_seconds() * 1000)
    return ms if ms >= 0 else None  # clock skew / bad row → drop rather than show negative


def _to_run(row) -> ActivityRun:
    rid = row["routine_id"]
    return ActivityRun(
        id=row["id"], routineId=rid, routineName=_routine_name(rid),
        status=row["status"], detail=row["detail"] or "",
        startedAt=row["started_at"], finishedAt=row["finished_at"],
        durationMs=_duration_ms(row["started_at"], row["finished_at"]),
    )


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _cutoff_iso(range_key: str | None) -> str | None:
    """ISO cutoff for a ?range lookback window. None → no lookback filter (all / today /
    unknown-key handled by the caller)."""
    if not range_key:
        return None
    delta = _RANGES.get(range_key)
    if delta is None:
        return None
    return (datetime.now(timezone.utc) - delta).isoformat()


def get_feed(routine: str | None = None, status: str | None = None,
             range: str | None = None) -> ActivityFeed:
    """Build the activity feed. Filters AND-combined, all optional + LENIENT (unknown
    status/range ignored). Never raises (read path fail-open — a bad DB read → empty)."""
    try:
        rows = db.all_runs(limit=10000)  # generous pull; filter in Python, then cap rows
    except Exception as exc:
        logger.error("activity feed read failed: %s", exc)
        rows = []

    today = _today_str()
    # Lenient: an invalid status is ignored (no filter), never an error.
    status_filter = status if status in _STATUSES else None
    cutoff = _cutoff_iso(range)
    is_today = range == "today"

    # runsToday is ALWAYS today's total across ALL routines/statuses — independent of
    # the active filter (the dispatch: "regardless of range filter"). Compute it over
    # the raw unfiltered rows, NOT the filtered set.
    runs_today = sum(1 for row in rows
                     if isinstance(row["started_at"], str) and row["started_at"][:10] == today)

    filtered: list[ActivityRun] = []
    for row in rows:
        if routine and row["routine_id"] != routine:
            continue
        if status_filter and row["status"] != status_filter:
            continue
        started = row["started_at"]
        if is_today:
            if not (isinstance(started, str) and started[:10] == today):
                continue
        elif cutoff is not None:
            if not (isinstance(started, str) and started >= cutoff):
                continue
        filtered.append(_to_run(row))

    return _build_feed(filtered, runs_today)


def _build_feed(filtered: list[ActivityRun], runs_today: int) -> ActivityFeed:
    """Roll-up stats over the FULL filtered set; ``runs`` is the newest-100 slice.
    ``runs_today`` is the unfiltered today-count, passed in by the caller (always today).

    ``filtered`` is already newest-first (db.all_runs orders started_at DESC, id DESC)."""
    count = len(filtered)
    ok = sum(1 for r in filtered if r.status == "ok")
    warn = sum(1 for r in filtered if r.status == "warn")
    err = sum(1 for r in filtered if r.status == "error")

    # None (not 0.0) when no runs — "no runs" ≠ "0% success". Percentage, one decimal.
    success_rate = round(ok / count * 100, 1) if count else None
    durs = [r.durationMs for r in filtered if r.durationMs is not None]
    avg_dur = int(round(sum(durs) / len(durs))) if durs else None

    # Per-routine breakdown over the full filtered set, sorted DESC by count.
    by: dict[str, dict] = {}
    for r in filtered:
        b = by.get(r.routineId)
        if b is None:
            b = by[r.routineId] = {"name": r.routineName, "count": 0, "ok": 0,
                                   "warn": 0, "error": 0, "last": None}
        b["count"] += 1
        b[r.status] += 1
        if b["last"] is None:  # newest-first → first seen is the latest run
            b["last"] = r.startedAt

    breakdown = [RoutineBreakdown(
        routine=rid, routineName=v["name"], count=v["count"],
        okCount=v["ok"], warnCount=v["warn"], errorCount=v["error"], lastRun=v["last"],
    ) for rid, v in by.items()]
    breakdown.sort(key=lambda b: b.count, reverse=True)  # most runs first

    return ActivityFeed(
        runs=filtered[:RUNS_CAP], count=count, runsToday=runs_today,
        okCount=ok, warnCount=warn, errorCount=err,
        successRate=success_rate, avgDurationMs=avg_dur, byRoutine=breakdown,
    )


def get_run(run_id: int) -> ActivityRun | None:
    """One run by its run_log PK, or None (router → 404). Fail-open on read error."""
    try:
        row = db.run_by_id(run_id)
    except Exception as exc:
        logger.error("activity run %s read failed: %s", run_id, exc)
        return None
    return _to_run(row) if row is not None else None
