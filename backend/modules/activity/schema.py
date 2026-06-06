"""modules/activity/schema.py — the activity feed shapes (S10B, FROZEN).

Read-only projection of run_log rows + roll-up stats. Self-describing-raw: each run
carries its own derived ``durationMs``; the feed carries the derived ``successRate``
(a PERCENTAGE 0-100, one decimal) + ``avgDurationMs`` + a per-routine breakdown so
the FE + AI never recompute.

Cap semantics (locked w/ tester scaffold): ``runs`` is the NEWEST-100 slice;
``count`` is the FULL filtered total (so a 110-run window shows count=110 but 100
rows — the FE can render "100 gần nhất / tổng 110").
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

RunStatus = Literal["ok", "warn", "error"]


class ActivityRun(BaseModel):
    """One run_log row, projected. ``id`` is the run_log PK (addressable via
    GET /activity/{id}). ``durationMs`` is finished-started in ms, None if the run
    has no finished_at or the timestamps are unparseable/skewed (fail-open)."""

    id: int
    routineId: str
    routineName: str            # resolved from the routine catalog, or the id if unknown
    status: RunStatus
    detail: str                 # "" when the run recorded no detail
    startedAt: str              # ISO-8601 UTC
    finishedAt: str | None
    durationMs: int | None


class RoutineBreakdown(BaseModel):
    """Per-routine roll-up inside the feed (``byRoutine``), sorted DESC by ``count``.

    Field is ``routine`` (the id) — the breakdown keys on routine id; ``routineName``
    carries the human label alongside."""

    routine: str                # routine id
    routineName: str
    count: int
    okCount: int
    warnCount: int
    errorCount: int
    lastRun: str | None         # most-recent startedAt for this routine in the window


class ActivityFeed(BaseModel):
    """The activity timeline + roll-up stats over the queried window.

    ``successRate`` = round(okCount/count*100, 1) — a PERCENTAGE, None when count==0
    (no runs to rate, NOT 0.0 which would read as "0% success"). ``avgDurationMs`` =
    mean of the runs that have a duration (None when none do). ``count`` is the FULL
    filtered total; ``runs`` is capped at the newest 100."""

    runs: list[ActivityRun]
    count: int
    runsToday: int
    okCount: int
    warnCount: int
    errorCount: int
    successRate: float | None
    avgDurationMs: int | None
    byRoutine: list[RoutineBreakdown]
