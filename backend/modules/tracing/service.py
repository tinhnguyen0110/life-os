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
from typing import Any

from . import store
from .schema import (
    Activity,
    ActivityInput,
    ActivityUpdate,
    ActivityView,
    LogInput,
    Note,
    NoteInput,
    NoteUpdate,
    Template,
    TemplateInput,
    TodayStat,
    TracingOverview,
    TracingScore,
    VN_TZ,
    vn_day_of,
    vn_now_iso,
    vn_today,
)

# #121: the link source for a day-note's reminder (distinct from an activity's "tracing").
_NOTE_SOURCE = "tracing-note"

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
        remindChannel=row["remind_channel"] if "remind_channel" in keys else "in_app",  # #111
        time=row["time"] if "time" in keys else None,  # #136: _ACT_COLS aliases sched_time AS time
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
        remindChannel=act.remindChannel,  # #117: the GET /tracing read-back was dropping this → in_app default masked the stored channel
        time=act.time,  # #136 G3-(ii): surface the scheduled time (the FE timeline rails by it) — same thread-through lesson as #117
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
                channel=act.remindChannel,  # #111: the linked reminder fires on the activity's channel
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
        remind_channel=inp.remindChannel,  # #111
        sched_time=inp.time,  # #136 G3-(ii): per-activity scheduled time (independent of the reminder)
    )
    created = store.get_activity(inp.id)
    assert created is not None  # just inserted
    act = _row_to_activity(created)
    _sync_reminder(act)  # #75: materialize/clear the linked reminder (NOTE: time does NOT touch this)
    return act


# 75-TWEAK: the camel wire field → snake store column (only the remind fields + #136 time differ;
# the rest share the same name in both field + column).
_FIELD_TO_COL = {"remindAt": "remind_at", "remindRepeat": "remind_repeat",
                 "remindChannel": "remind_channel",  # #111
                 "time": "sched_time"}  # #136 G3-(ii): API field `time` → DB col `sched_time`


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


# --------------------------------------------------------------------------- #
# TRACING-UX T1 (#109): task templates — prefill suggestions for the "new        #
# activity" form. The list = SEED (immutable code) ⊕ USER OVERRIDE (the store).   #
# Templates are PREFILL ONLY — they never create activities (the FE prefills the  #
# form → the existing create_activity does the create). decide-and-log: ~8 seeds. #
# --------------------------------------------------------------------------- #
# The immutable SEED templates (in code, NOT editable). A user who "edits a seed"
# creates an override row with the SAME id (override wins); deleting a seed writes
# a tombstone (hidden=1). Goals/units are sensible Vietnamese-habit prefills.
_SEED_TEMPLATES: list[dict[str, Any]] = [
    {"id": "uong-nuoc",   "name": "Uống nước",      "emoji": "💧", "icon": "droplet",  "unit": "ly",    "goal": 8.0,  "color": "#38bdf8"},
    {"id": "tap-the-duc", "name": "Tập thể dục",    "emoji": "🏃", "icon": "run",      "unit": "phút",  "goal": 30.0, "color": "#f97316"},
    {"id": "doc-sach",    "name": "Đọc sách",       "emoji": "📖", "icon": "book",     "unit": "trang", "goal": 20.0, "color": "#a78bfa"},
    {"id": "ngu",         "name": "Ngủ đủ giấc",    "emoji": "😴", "icon": "moon",     "unit": "giờ",   "goal": 8.0,  "color": "#818cf8"},
    {"id": "thien",       "name": "Thiền",          "emoji": "🧘", "icon": "lotus",    "unit": "phút",  "goal": 10.0, "color": "#34d399"},
    {"id": "di-bo",       "name": "Đi bộ",          "emoji": "🚶", "icon": "walk",     "unit": "bước",  "goal": 6000.0, "color": "#fbbf24"},
    {"id": "hoc",         "name": "Học",            "emoji": "📚", "icon": "study",    "unit": "phút",  "goal": 60.0, "color": "#60a5fa"},
    {"id": "viet",        "name": "Viết nhật ký",   "emoji": "✍️", "icon": "pen",      "unit": "phút",  "goal": 15.0, "color": "#f472b6"},
]


def list_templates() -> list[Template]:
    """The merged template list: SEED ⊕ USER OVERRIDE, each tagged ``source``. Rules:
    - a user override with the SAME id as a seed → REPLACES it (source='user', override wins);
    - a tombstone override (hidden=1) → HIDES the matching seed (dropped from the list);
    - a user-only id (no seed) → appears (source='user');
    - an un-overridden seed → appears (source='seed').
    Order: seeds (in seed order) first, then user-only templates (by id). LEAN — prefill fields only.
    """
    overrides = {r["id"]: r for r in store.list_template_overrides()}
    out: list[Template] = []
    # 1) seeds, applying any override / tombstone keyed by the seed id
    for seed in _SEED_TEMPLATES:
        ov = overrides.pop(seed["id"], None)
        if ov is None:
            out.append(Template(source="seed", **seed))
            continue
        if ov["hidden"]:
            continue  # tombstoned seed → hidden
        out.append(Template(
            id=ov["id"], name=ov["name"], emoji=ov["emoji"], icon=ov["icon"],
            unit=ov["unit"], goal=ov["goal"], color=ov["color"], source="user"))
    # 2) remaining overrides = user-only templates (not matching any seed); skip tombstones (a
    #    tombstone for a non-seed id is meaningless → just hide it, don't surface an empty row)
    for ov in sorted((o for o in overrides.values() if not o["hidden"]), key=lambda r: r["id"]):
        out.append(Template(
            id=ov["id"], name=ov["name"], emoji=ov["emoji"], icon=ov["icon"],
            unit=ov["unit"], goal=ov["goal"], color=ov["color"], source="user"))
    return out


def _is_seed(template_id: str) -> bool:
    return any(s["id"] == template_id for s in _SEED_TEMPLATES)


def upsert_template(template_id: str, inp: TemplateInput) -> Template:
    """Upsert a user template override (create a new one OR override a seed). Returns the merged
    Template (always source='user' — it's now an override). The caller validated ``inp`` (→ 422)."""
    store.upsert_template(
        id=template_id, name=inp.name, emoji=inp.emoji, icon=inp.icon,
        unit=inp.unit, goal=inp.goal, color=inp.color)
    return Template(id=template_id, name=inp.name, emoji=inp.emoji, icon=inp.icon,
                    unit=inp.unit, goal=inp.goal, color=inp.color, source="user")


def delete_template(template_id: str) -> bool:
    """Delete a template: a USER template → remove its override row; a SEED → write a tombstone
    (hidden). Returns True if the list changed. A non-existent, non-seed id → False (idempotent-ish:
    nothing to do). SCOPED to tracing_template (never touches real activities)."""
    if _is_seed(template_id):
        store.tombstone_template(template_id)  # hide the seed
        return True
    return store.delete_template_override(template_id)  # remove the user row (False if absent)


def bulk_delete_templates(ids: list[str]) -> int:
    """Bulk-delete templates (#109 bulk-action): each id → seed-tombstone or user-row-remove (reuses
    ``delete_template``). Returns the count that changed the list. Empty ids → 0 (no-op); an absent
    non-seed id → skipped (idempotent, never errors). SCOPED to tracing_template."""
    return sum(1 for tid in ids if delete_template(tid))


def reset_templates() -> int:
    """RESET all templates to pure SEED: delete every override row. Returns the count deleted.
    SCOPED — never touches activities/logs (the #72 lesson)."""
    return store.reset_templates()


def get_template(template_id: str) -> Template | None:
    """One template by id from the merged SEED⊕USER list (None if unknown / tombstoned). #124:
    the lookup behind the add-button — uses the SAME merge as list_templates so a user-overridden
    or user-only template resolves, and a tombstoned seed reads as absent."""
    tid = (template_id or "").strip()
    if not tid:
        return None
    return next((t for t in list_templates() if t.id == tid), None)


def _template_to_activity_input(t: Template) -> ActivityInput:
    """#124 (CORRECTED): map a saved template → a BINARY TODO activity — name ONLY + goal=1.
    🔴 The #122 redesign made /tracing text+tick (a todo = goal=1, tick=done; the user REJECTED
    goals/units/emoji/progress-bars — the screen is checkboxes). A #109 template has a stored goal
    (e.g. seed 'uống nước' goal=8) but importing WITH that goal would render a measured progress-bar
    on a checkbox screen (wrong/inconsistent). So a 'template' now = a saved todo TEXT: we take
    t.name + goal=1 and DROP the stored goal/unit/emoji/color. (The #109 store keeps those columns
    for backward-compat — unchanged — only this IMPORT path ignores them.) remind* = defaults; the
    user sets a remind separately."""
    return ActivityInput(id=t.id, name=t.name, goal=1.0)  # binary todo: name-only, goal=1


def add_template_to_today(template_id: str) -> tuple[Activity | None, bool]:
    """#124/#130: 1-click "add from my template" → put today's activity on the board from the saved
    template. Returns (activity, added):
      - new id → create → (activity, added=True).
      - an ARCHIVED matched id (#130) → UN-ARCHIVE + re-surface → (activity, added=True). Clicking
        "add" means "I want this today"; a silently-archived id used to do nothing (the FE-found gap).
        The row's logs/history are preserved (same row, archived=0).
      - a LIVE (non-archived) id → already on the board → (existing, added=False), NO dup (idempotent).
    (None, False) when the template id is unknown (router → 404). SCOPED: reads tracing_template +
    writes only that id's tracing_activities row (never the rejected auto-seed)."""
    t = get_template(template_id)
    if t is None:
        return None, False
    existing = get_activity(t.id)  # incl. archived (the PK would collide on re-create)
    if existing is not None:
        if existing.archived:
            # #130: re-adding an archived id → un-archive it back onto the board (added=True).
            store.unarchive_activity(t.id)
            refreshed = get_activity(t.id)
            return (refreshed if refreshed is not None else existing), True
        return existing, False  # already LIVE on the board → return existing, no dup
    return create_activity(_template_to_activity_input(t)), True


def add_all_templates() -> tuple[list[Activity], list[str]]:
    """#124/#130: add ALL non-hidden templates → today's board in one call. Returns
    (created, skipped_ids): a new OR archived id → created (#130: an archived member is un-archived
    + re-surfaced, counted as created — DELEGATES to add_template_to_today so the archived semantics
    are identical); a LIVE already-present id → skipped (honest, no dup). honest-empty ([],[]) when
    there are no templates. list_templates() already excludes tombstoned/hidden (#109 model)."""
    created: list[Activity] = []
    skipped: list[str] = []
    for t in list_templates():
        activity, added = add_template_to_today(t.id)
        if added and activity is not None:
            created.append(activity)
        else:
            skipped.append(t.id)
    return created, skipped


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


def clear_sessions_for_day(activity_id: str, date: str | None = None) -> tuple[str, int, ActivityView]:
    """#136 UN-TICK: delete an activity's session logs for ``date`` (default today-VN) → its today
    derived val drops to 0 → today.done flips false. Returns (resolvedDate, deletedCount, the
    freshly-derived view) so the caller sees the un-done state + the date actually cleared (no need
    to re-derive today-VN at the router). The activity MUST exist (router checks → 404). SCOPED to
    (activity_id, date) only (#72). honest: deletedCount=0 if there were no sessions."""
    day = date or vn_today()
    deleted = store.delete_sessions_for_day(activity_id, day)
    act = get_activity(activity_id)
    assert act is not None  # router verified existence before calling
    return day, deleted, _derive_activity_view(act)


# --------------------------------------------------------------------------- #
# TRACING-UX2 T1 (#121): day-notes — text + optional remind.                     #
# A note's remind reuses the #75 wire via source="tracing-note" (the note id is   #
# the linked-entity id in reminders.activity_id). create/update sync; delete unlinks.#
# --------------------------------------------------------------------------- #
def _row_to_note(row: sqlite3.Row) -> Note:
    keys = row.keys()
    return Note(
        id=str(row["id"]),  # autoincrement PK → string id
        text=row["text"],
        remindAt=row["remind_at"] if "remind_at" in keys else None,
        remindDate=row["remind_date"] if "remind_date" in keys else None,  # #125 one-shot future date
        remindRepeat=row["remind_repeat"] if "remind_repeat" in keys else "off",
        remindChannel=row["remind_channel"] if "remind_channel" in keys else "in_app",
        created=row["created"],
    )


def _sync_note_reminder(note: Note) -> None:
    """ONE-WAY note→reminder (#121 + #125). TWO remind KINDS for a note:
      - #125 ONE-SHOT (remindDate set + remindAt): a `repeat="once"` reminder at the FUTURE
        remindDate@remindAt (VN→UTC). Fires once, never recurs.
      - #121 RECURRING (remindRepeat≠off, no remindDate): the today@remindAt daily/weekdays path.
    Neither applicable → DELETE the linked reminder. source='tracing-note', linked id = note id.
    Fail-soft: a reminders hiccup logs but never breaks the note write (the note is source-of-truth).
    NOTE: past-date validation is the agent-facing surface's job (router → 422); this builds the
    due_at as given (it's already validated future by the time we sync)."""
    from modules.reminders import service as rem
    from modules.reminders.schema import _to_utc_iso
    try:
        title = note.text.strip()[:120]  # the reminder title = the note text (capped for the alarm)
        if note.remindDate and note.remindAt:
            # #125 ONE-SHOT future-date: repeat="once" at remindDate@remindAt (VN-offset → UTC).
            due_at = _to_utc_iso(f"{note.remindDate}T{note.remindAt}:00+07:00")
            rem.upsert_for_activity(
                activity_id=note.id, title=title, due_at=due_at,
                repeat="once", channel=note.remindChannel, source=_NOTE_SOURCE,
            )
        elif note.remindAt and note.remindRepeat != "off":
            # #121 RECURRING: today-VN @ remindAt, daily/weekdays.
            due_at = _to_utc_iso(f"{vn_today()}T{note.remindAt}:00+07:00")
            rem.upsert_for_activity(
                activity_id=note.id, title=title, due_at=due_at,
                repeat=_REPEAT_MAP.get(note.remindRepeat, "daily"),
                channel=note.remindChannel, source=_NOTE_SOURCE,
            )
        else:
            rem.delete_for_activity(note.id, source=_NOTE_SOURCE)
    except Exception as exc:  # noqa: BLE001 — reminder sync is an add-on; never break the note write
        logger.error("dev: note-reminder sync failed for note %s: %s", note.id, exc)


def note_remind_in_past(remind_date: str | None, remind_at: str | None) -> bool:
    """#125: True if a one-shot remind (remindDate + remindAt) is in the PAST (VN now). The agent-
    facing surface (router) rejects it with a 422 (a remind in the past would never fire). Only a
    FULL one-shot (both date+time) is checked; a date without a time isn't a one-shot yet → not past.
    A bad format is NOT past here (the schema validator already 422s a malformed date/time)."""
    if not (remind_date and remind_at):
        return False
    from datetime import datetime
    try:
        when = datetime.strptime(f"{remind_date} {remind_at}", "%Y-%m-%d %H:%M").replace(tzinfo=VN_TZ)
    except ValueError:
        return False  # malformed → schema validator handles the 422; not "past"
    return when < datetime.now(VN_TZ)


def list_notes() -> list[Note]:
    """All day-notes, newest-first. honest-empty [] when none."""
    return [_row_to_note(r) for r in store.list_notes()]


def get_note(note_id: str) -> Note | None:
    """One day-note by id (str), or None if absent / non-numeric id."""
    try:
        nid = int(note_id)
    except (TypeError, ValueError):
        return None
    row = store.get_note(nid)
    return _row_to_note(row) if row is not None else None


def create_note(inp: NoteInput) -> Note:
    """Create a day-note + sync its linked reminder (#125 one-shot if remindDate+remindAt, else the
    #121 recurring path)."""
    nid = store.create_note(
        text=inp.text, remind_at=inp.remindAt, remind_date=inp.remindDate,
        remind_repeat=inp.remindRepeat, remind_channel=inp.remindChannel, created=vn_now_iso(),
    )
    row = store.get_note(nid)
    assert row is not None
    note = _row_to_note(row)
    _sync_note_reminder(note)
    return note


def update_note(note_id: str, upd: NoteUpdate) -> Note | None:
    """Partial update of a day-note + re-sync the linked reminder. None if id absent. Only supplied
    fields change. CLEAR semantics: remindRepeat='off' clears BOTH the #121 recurring AND the #125
    one-shot (we also null remind_date on an explicit 'off') → the linked reminder is deleted. To
    set/move a one-shot, pass remindDate + remindAt."""
    current = get_note(note_id)
    if current is None:
        return None
    text = upd.text if upd.text is not None else current.text
    remind_at = upd.remindAt if upd.remindAt is not None else current.remindAt
    remind_date = upd.remindDate if upd.remindDate is not None else current.remindDate
    remind_repeat = upd.remindRepeat if upd.remindRepeat is not None else current.remindRepeat
    remind_channel = upd.remindChannel if upd.remindChannel is not None else current.remindChannel
    # explicit remindRepeat='off' is the universal CLEAR — also drop a lingering one-shot date so the
    # sync's delete-branch fires (neither kind applies → reminder removed, no orphan one-shot).
    if upd.remindRepeat == "off":
        remind_date = None
    row = store.update_note(int(note_id), text=text, remind_at=remind_at, remind_date=remind_date,
                            remind_repeat=remind_repeat, remind_channel=remind_channel)
    if row is None:
        return None
    note = _row_to_note(row)
    _sync_note_reminder(note)  # re-sync: upsert (once/recurring) or delete (cleared)
    return note


def delete_note(note_id: str) -> bool:
    """Delete a day-note + its linked reminder (no orphan). True if the note existed. The reminder
    is removed FIRST (delete_for_note via source='tracing-note'), then the note row."""
    try:
        nid = int(note_id)
    except (TypeError, ValueError):
        return False
    # unlink the reminder first (fail-soft — a reminders hiccup must not block the note delete)
    try:
        from modules.reminders import service as rem
        rem.delete_for_activity(str(nid), source=_NOTE_SOURCE)
    except Exception as exc:  # noqa: BLE001
        logger.error("dev: note-reminder unlink failed for note %s: %s", nid, exc)
    return store.delete_note(nid)
