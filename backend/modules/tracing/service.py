"""modules/tracing/service.py — tracing business logic + DERIVATIONS (DAILY-TRACING-P1, #65).

Raw-data-first: the store holds raw sessions; THIS layer derives every metric (today/streak/week/
history12w/heatmap12w/score) server-side. ALL date bucketing is VN-day (UTC+7) — the FE/agent never
re-compute. The derivations here are the architect's spec (plan_sprint_DAILY-TRACING-P1.md §🔑) —
implemented as written, not improvised.

Key rules:
  - today.val = Σ(today's sessions' val); pct = round(min(100, val/goal*100)) (goal>0 else 0);
    done = val ≥ goal (goal>0); note = the latest today session's note.
  - streak = consecutive goal-met VN-days back from today; today-incomplete does NOT break it
    (today = at-risk: walk from today if today-met, else from yesterday; a gap stops the count).
  - week[7] = Mon→Sun Σ(val)/day this week. history12w[84] = oldest→newest per-day Σ(val).
  - heatmap12w[84] = per-day COUNT of activities that met goal (a COUNT, not a boolean).
  - score = {total active, done-today, pct, timeActive 'Hh Mm', topStreak}.
"""

from __future__ import annotations

import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta

from . import store
from .schema import (
    Activity,
    ActivityInput,
    ActivityUpdate,
    ActivityView,
    LogInput,
    TodayStat,
    TracingOverview,
    TracingScore,
    VN_TZ,
    vn_day_of,
    vn_now_iso,
    vn_today,
)

logger = logging.getLogger("life-os.tracing.service")

_HISTORY_DAYS = 84  # 12 weeks


# --------------------------------------------------------------------------- #
# small helpers                                                                 #
# --------------------------------------------------------------------------- #
def _fmt_dur(total_min: int) -> str:
    """Format minutes as 'Hh Mm' (e.g. 90 → '1h 30m', 45 → '45m', 0 → ''). Honest empty for 0."""
    if total_min <= 0:
        return ""
    h, m = divmod(int(total_min), 60)
    if h and m:
        return f"{h}h {m}m"
    if h:
        return f"{h}h"
    return f"{m}m"


def _pct(val: float, goal: float) -> int:
    """round(min(100, val/goal*100)); 0 when goal<=0 (no divide-by-zero, never 'done')."""
    if goal <= 0:
        return 0
    return round(min(100.0, val / goal * 100.0))


def _row_to_activity(row: sqlite3.Row) -> Activity:
    keys = row.keys()  # tolerate a pre-#75 row missing remind_* (migration adds them)
    return Activity(
        id=row["id"], name=row["name"], emoji=row["emoji"], icon=row["icon"],
        unit=row["unit"], goal=row["goal"], color=row["color"], created=row["created"],
        archived=bool(row["archived"]),
        remindAt=row["remind_at"] if "remind_at" in keys else None,  # camel field ← snake DB col
        remindRepeat=row["remind_repeat"] if "remind_repeat" in keys else "off",
    )


def _last_n_vn_days(n: int, *, end: str | None = None) -> list[str]:
    """The n VN calendar days ending at ``end`` (default today-VN), oldest→newest, as YYYY-MM-DD."""
    end_day = datetime.strptime(end or vn_today(), "%Y-%m-%d").date()
    return [(end_day - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n - 1, -1, -1)]


def _week_days() -> list[str]:
    """The current VN week Mon→Sun as YYYY-MM-DD (Mon = weekday 0)."""
    today = datetime.strptime(vn_today(), "%Y-%m-%d").date()
    monday = today - timedelta(days=today.weekday())
    return [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]


def _daily_sums(rows: list[sqlite3.Row]) -> dict[str, float]:
    """Σ(val) per VN-day for a set of one activity's session rows."""
    out: dict[str, float] = defaultdict(float)
    for r in rows:
        out[r["date"]] += float(r["val"])
    return dict(out)


# --------------------------------------------------------------------------- #
# DERIVATIONS                                                                   #
# --------------------------------------------------------------------------- #
def _derive_today(rows_today: list[sqlite3.Row], goal: float) -> TodayStat:
    """today rollup from one activity's TODAY sessions (already date-filtered to today-VN)."""
    val = sum(float(r["val"]) for r in rows_today)
    dur_min = sum(int(r["dur_min"]) for r in rows_today if r["dur_min"] is not None)
    # latest session's note: rows arrive oldest→newest (ts ASC) → the last non-None note wins.
    note: str | None = None
    for r in rows_today:
        if r["note"]:
            note = r["note"]
    # but "latest session's note" = the note of the chronologically last session (even if None
    # overwrites) — honour the LAST session that HAS a note as the shown one (a no-note later
    # session shouldn't blank a meaningful earlier note). Above loop already does that.
    return TodayStat(
        done=(goal > 0 and val >= goal),
        val=val,
        dur=_fmt_dur(dur_min),
        durMin=dur_min,
        note=note,
        pct=_pct(val, goal),
        sessions=len(rows_today),
    )


def _derive_streak(daily: dict[str, float], goal: float, today: str) -> int:
    """Consecutive goal-met VN-days. today-incomplete does NOT break: start at today if today is
    met, else at yesterday; walk backwards while each day met (Σ ≥ goal); a gap (unmet day) stops.
    goal<=0 → never met → streak 0."""
    if goal <= 0:
        return 0
    today_date = datetime.strptime(today, "%Y-%m-%d").date()
    # start cursor: today if today already met, else yesterday (today = at-risk, not a break).
    if daily.get(today, 0.0) >= goal:
        cursor = today_date
    else:
        cursor = today_date - timedelta(days=1)
    streak = 0
    while True:
        key = cursor.strftime("%Y-%m-%d")
        if daily.get(key, 0.0) >= goal:
            streak += 1
            cursor -= timedelta(days=1)
        else:
            break
    return streak


def _derive_activity_view(act: Activity) -> ActivityView:
    """One activity def → its full derived card (today + streak + week + history12w)."""
    today = vn_today()
    window_start = _last_n_vn_days(_HISTORY_DAYS)[0]
    # one windowed read (last 84 days) covers today + week + history + streak (streak only walks
    # back within met-days, which can't exceed the window unless the streak is >84 — acceptable
    # for a 12-week board; the heatmap/history are the displayed 84-day surface).
    rows = store.logs_for_activity(act.id, since_date=window_start)
    daily = _daily_sums(rows)

    rows_today = [r for r in rows if r["date"] == today]
    today_stat = _derive_today(rows_today, act.goal)
    streak = _derive_streak(daily, act.goal, today)
    week = [round(daily.get(d, 0.0), 6) for d in _week_days()]
    history = [round(daily.get(d, 0.0), 6) for d in _last_n_vn_days(_HISTORY_DAYS)]

    return ActivityView(
        id=act.id, name=act.name, emoji=act.emoji, icon=act.icon, unit=act.unit,
        goal=act.goal, color=act.color,
        remindAt=act.remindAt, remindRepeat=act.remindRepeat,  # #75: surface the reminder link (camel)
        today=today_stat, streak=streak, week=week, history12w=history,
    )


def _derive_heatmap(activities: list[Activity]) -> list[int]:
    """heatmap12w[84], oldest→newest: per-day COUNT of activities that MET their goal that day
    (Σ(that activity's val that day) ≥ its goal). A COUNT 0..N, NOT a boolean. goal<=0 activities
    never contribute. One read of all logs in the window, summed per (activity, day)."""
    days = _last_n_vn_days(_HISTORY_DAYS)
    if not activities:
        return [0] * _HISTORY_DAYS
    window_start = days[0]
    rows = store.logs_since(window_start)
    # per (activity_id, day) → Σ val
    by_act_day: dict[tuple[str, str], float] = defaultdict(float)
    for r in rows:
        by_act_day[(r["activity_id"], r["date"])] += float(r["val"])
    goals = {a.id: a.goal for a in activities}
    heatmap: list[int] = []
    for d in days:
        score = 0
        for a in activities:
            if a.goal > 0 and by_act_day.get((a.id, d), 0.0) >= a.goal:
                score += 1
        heatmap.append(score)
    return heatmap


def _derive_score(views: list[ActivityView]) -> TracingScore:
    """Board roll-up from the per-activity views (no extra reads — reuse what's derived)."""
    total = len(views)
    done = sum(1 for v in views if v.today.done)
    pct = round(done / total * 100) if total else 0
    time_active = sum(v.today.durMin for v in views)
    top_streak = max((v.streak for v in views), default=0)
    return TracingScore(
        total=total, done=done, pct=pct,
        timeActive=_fmt_dur(time_active), topStreak=top_streak,
    )


# --------------------------------------------------------------------------- #
# public API (router calls these)                                              #
# --------------------------------------------------------------------------- #
def overview() -> TracingOverview:
    """The whole tracing board for today-VN. honest-mirror: no activities → [] + all-0 score +
    all-0 heatmap (never fabricated)."""
    activities = [_row_to_activity(r) for r in store.list_activities(include_archived=False)]
    views = [_derive_activity_view(a) for a in activities]
    heatmap = _derive_heatmap(activities)
    score = _derive_score(views)
    return TracingOverview(date=vn_today(), activities=views, heatmap12w=heatmap, score=score)


def get_activity(activity_id: str) -> Activity | None:
    """One activity def (incl. archived), or None."""
    row = store.get_activity(activity_id)
    return _row_to_activity(row) if row is not None else None


# TRACING-REMINDERS (#75): map remind_repeat → the reminders engine's repeat. "daily"/"weekdays"
# both fire daily (the #29 engine has no weekday-mask; weekdays is surfaced for the FE but fires
# daily — documented honest limitation, refine in a later phase). "off" → no reminder.
_REPEAT_MAP = {"daily": "daily", "weekdays": "daily"}


def _sync_reminder(act: Activity) -> None:
    """ONE-WAY tracing→reminder (#75): if the activity has remind_at + remind_repeat≠off → UPSERT the
    linked reminder (source=tracing, via the reminders service — reuse the #29 engine, no new one);
    else → DELETE the linked reminder. Fail-soft: a reminders-store hiccup logs but never breaks the
    activity write (the activity is source-of-truth)."""
    from modules.reminders import service as rem
    from modules.reminders.schema import _to_utc_iso
    try:
        if act.remindAt and act.remindRepeat != "off":
            # today-VN @ remindAt → a VN-offset ISO → UTC (reminders compares due_at in UTC).
            due_local = f"{vn_today()}T{act.remindAt}:00+07:00"
            due_at = _to_utc_iso(due_local)
            title = f"{act.emoji} {act.name}".strip()
            rem.upsert_for_activity(
                activity_id=act.id, title=title, due_at=due_at,
                repeat=_REPEAT_MAP.get(act.remindRepeat, "daily"),
            )
        else:
            rem.delete_for_activity(act.id)
    except Exception as exc:  # noqa: BLE001 — reminder sync is an add-on; never break the activity write
        logger.error("dev: reminder sync failed for activity %s: %s", act.id, exc)


def create_activity(inp: ActivityInput) -> Activity:
    """Create an activity def. Raises sqlite3.IntegrityError on a duplicate id (router → 409).
    #75: syncs the linked reminder if remind_at + remind_repeat≠off."""
    store.create_activity(
        id=inp.id, name=inp.name, emoji=inp.emoji, icon=inp.icon, unit=inp.unit,
        goal=inp.goal, color=inp.color, created=vn_now_iso(),
        remind_at=inp.remindAt, remind_repeat=inp.remindRepeat,  # store col snake ← camel field
    )
    created = store.get_activity(inp.id)
    assert created is not None  # just inserted
    act = _row_to_activity(created)
    _sync_reminder(act)  # #75: materialize/clear the linked reminder
    return act


# 75-TWEAK: the camel wire field → snake store column (only the remind fields differ; the rest
# share the same name in both field + column).
_FIELD_TO_COL = {"remindAt": "remind_at", "remindRepeat": "remind_repeat"}


def update_activity(activity_id: str, upd: ActivityUpdate) -> Activity | None:
    """Update the supplied fields of an activity def. Returns the updated def, or None if absent.
    #75: re-syncs the linked reminder (upsert on remind change, delete on clear/off)."""
    # map the camel wire field names to the snake store columns (#75-TWEAK).
    fields = {_FIELD_TO_COL.get(k, k): v for k, v in upd.model_dump(exclude_none=True).items()}
    if not store.update_activity(activity_id, fields):
        return None
    row = store.get_activity(activity_id)
    if row is None:
        return None
    act = _row_to_activity(row)
    _sync_reminder(act)  # #75: re-materialize/clear the linked reminder per the new remind state
    return act


def archive_activity(activity_id: str) -> bool:
    """Archive (soft-delete) an activity def. False if absent. #75: deletes the linked reminder
    (one-way — an archived habit shouldn't keep nagging). Fail-soft on the reminder delete."""
    ok = store.archive_activity(activity_id)
    if ok:
        try:
            from modules.reminders import service as rem
            rem.delete_for_activity(activity_id)
        except Exception as exc:  # noqa: BLE001 — add-on; never break the archive
            logger.error("dev: reminder delete-on-archive failed for %s: %s", activity_id, exc)
    return ok


def log_session(activity_id: str, inp: LogInput) -> ActivityView:
    """Append one raw session against an activity, then return the activity's freshly-derived view
    (so the caller sees the accumulated today/streak immediately). The activity MUST exist + be
    non-archived (router checks existence → 404). date defaults to today-VN; same-day logs sum."""
    ts = vn_now_iso()
    date = inp.date or vn_day_of(ts)
    store.insert_log(
        activity_id=activity_id, date=date, ts=ts, val=inp.val,
        dur_min=inp.dur_min, note=inp.note,
    )
    act = get_activity(activity_id)
    assert act is not None  # router verified existence before calling
    return _derive_activity_view(act)
