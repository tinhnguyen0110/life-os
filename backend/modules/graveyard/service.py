"""modules/graveyard/service.py — aggregate the abandoned set (Sprint 8, SPEC §S4).

Reuses `projects.service.list_abandoned()` (the abandoned set lives in the projects
store) — NO duplicate discovery. Membership = the `abandoned` flag, orthogonal to
commit-age health (abandon-orthogonal-to-health). All pattern stats per the
architect's Logic block.

Logic (verbatim):
  - graves: every abandoned project. peak=abandonedProgress (else progress, else 0).
  - avgPeak: mean of graves' peak, round 1dp; 0 if no graves.
  - commonReasons: group by reason.strip() (exact, no NLP), count, sort desc.
  - reachedUser/beforeUser: graves users>0 vs users==0.
  - lessons: distinct non-empty lesson strings, first-seen order.
"""

from __future__ import annotations

import logging

from modules.projects import service as projects_service

from .schema import GraveProject, GraveyardStats, ReasonCount

logger = logging.getLogger("life-os.graveyard.service")


def _peak(status, meta: dict) -> int:
    """peak display value: abandonedProgress → progress → 0 (for the grave card)."""
    val = meta.get("abandonedProgress")
    if isinstance(val, int) and not isinstance(val, bool) and val >= 0:
        return val
    if isinstance(status.progress, int) and status.progress >= 0:
        return status.progress
    return 0


def _abandoned_progress(meta: dict) -> int | None:
    """The SNAPSHOT abandonedProgress only (None if missing) — for avgPeak, which
    skips missing rather than treating None as 0 (would skew the mean low)."""
    val = meta.get("abandonedProgress")
    if isinstance(val, int) and not isinstance(val, bool) and val >= 0:
        return val
    return None


def _users(status, meta: dict) -> int:
    """users at abandon: SNAPSHOT abandonedUsers → live status.users → 0.
    The snapshot makes the reached/before pattern immune to later edits."""
    snap = meta.get("abandonedUsers")
    if isinstance(snap, int) and not isinstance(snap, bool) and snap >= 0:
        return snap
    return status.users if isinstance(status.users, int) and status.users >= 0 else 0


def get_graveyard() -> GraveyardStats:
    """The graveyard view: abandoned projects + pattern aggregates. Fail-open.

    Never raises — a malformed abandoned project is skipped (projects.list_abandoned
    fail-opens per-project). Empty graveyard → all-zero stats, never 500.
    """
    abandoned, _warnings = projects_service.list_abandoned()

    graves: list[GraveProject] = []
    valid_peaks: list[int] = []  # abandonedProgress present → counts toward avgPeak
    for status, meta in abandoned:
        lesson = meta.get("lesson")
        lesson_str = lesson.strip() if isinstance(lesson, str) and lesson.strip() else None
        reason = meta.get("abandonedReason")
        reason_str = reason.strip() if isinstance(reason, str) and reason.strip() else "(no reason)"
        died = meta.get("abandonedAt")
        died_str = died if isinstance(died, str) else ""
        graves.append(GraveProject(
            id=status.id, name=status.name, peak=_peak(status, meta),
            reason=reason_str, lesson=lesson_str, died=died_str,
            users=_users(status, meta), health=status.health, repo=status.repo,
        ))
        ap = _abandoned_progress(meta)
        if ap is not None:
            valid_peaks.append(ap)

    count = len(graves)
    # avgPeak: mean over graves WITH a valid abandonedProgress (skip missing — don't
    # treat None as 0, which would skew the % low). 0.0 if none valid.
    avg_peak = round(sum(valid_peaks) / len(valid_peaks), 1) if valid_peaks else 0.0

    # commonReasons: group by NORMALIZED reason (strip+lower), count desc; DISPLAY the
    # original-case reason of the FIRST occurrence (stable on count ties by display text).
    norm_count: dict[str, int] = {}
    norm_display: dict[str, str] = {}
    for g in graves:
        key = g.reason.strip().lower()
        norm_count[key] = norm_count.get(key, 0) + 1
        norm_display.setdefault(key, g.reason)
    common = [ReasonCount(reason=norm_display[k], count=c) for k, c in norm_count.items()]
    common.sort(key=lambda rc: (-rc.count, rc.reason))

    reached_user = sum(1 for g in graves if g.users > 0)
    before_user = sum(1 for g in graves if g.users == 0)

    # lessons: distinct non-empty, first-seen order.
    lessons: list[str] = []
    seen: set[str] = set()
    for g in graves:
        if g.lesson and g.lesson not in seen:
            seen.add(g.lesson)
            lessons.append(g.lesson)

    return GraveyardStats(
        graves=graves, count=count, avgPeak=avg_peak, commonReasons=common,
        reachedUser=reached_user, beforeUser=before_user, lessons=lessons,
    )
