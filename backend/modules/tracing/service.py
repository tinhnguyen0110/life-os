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

import json
import logging
import re
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
    TemplateMember,
    TemplateSet,
    TemplateSetInput,
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
        remindDays=_csv_to_days(row["remind_days"]) if "remind_days" in keys else None,  # #172: CSV → list[int]
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
        remindDays=act.remindDays,  # #172: surface the custom weekday mask so the FE renders the day-chips (same #117 thread-through)
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


# TRACING-REMINDERS (#75): map remind_repeat → the reminders engine's repeat. The engine cadence is
# always "daily"; the WEEKDAY MASK (#172, the `days` column) decides which days actually fire. This
# map is now used ONLY by the day-NOTE sync path (#121, below); the ACTIVITY path (_sync_reminder)
# computes its own mask. "off" → no reminder.
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
            # TRACING-ALARM (#172): map the repeat → a weekday-mask CSV the engine gates on (the
            # engine repeat stays "daily" — it fires daily, the MASK decides which days actually fire):
            #   daily    → None (every day, no mask — unchanged behavior)
            #   weekdays → "0,1,2,3,4" (Mon–Fri) — FIXES the #75 lie (it used to fire daily)
            #   custom   → the activity's remindDays CSV
            if act.remindRepeat == "weekdays":
                days_csv: str | None = "0,1,2,3,4"
            elif act.remindRepeat == "custom":
                days_csv = _days_to_csv(act.remindDays)
            else:  # daily
                days_csv = None
            rem.upsert_for_activity(
                activity_id=act.id, title=title, due_at=due_at,
                repeat="daily",  # the engine cadence; the day-mask (days_csv) gates which days fire
                channel=act.remindChannel,  # #111: the linked reminder fires on the activity's channel
                days=days_csv,  # #172: the weekday mask (None = every day)
            )
        else:
            rem.delete_for_activity(act.id)
    except Exception as exc:  # noqa: BLE001 — reminder sync is an add-on; never break the activity write
        logger.error("dev: reminder sync failed for activity %s: %s", act.id, exc)


# TRACING-ALARM (#172): the weekday-mask CSV <-> list[int] codec (Mon0..Sun6). The DB stores a CSV
# ("0,1,2,3,4"); the model carries list[int]. NULL/"" ⇄ None (no mask). Kept tiny + in one place.
def _days_to_csv(days: list[int] | None) -> str | None:
    """list[int] → "0,1,2,3,4" CSV (sorted, deduped), or None for None/[]."""
    if not days:
        return None
    return ",".join(str(d) for d in sorted(set(days)))


def _csv_to_days(csv: str | None) -> list[int] | None:
    """"0,1,2,3,4" CSV → sorted list[int], or None for NULL/empty. Tolerates stray spaces; a bad
    token is skipped (fail-soft read — a malformed stored mask never crashes the read-back)."""
    if not csv or not csv.strip():
        return None
    out: list[int] = []
    for tok in csv.split(","):
        tok = tok.strip()
        if tok.isdigit() and 0 <= int(tok) <= 6:
            out.append(int(tok))
    return sorted(set(out)) or None


def create_activity(inp: ActivityInput) -> Activity:
    """Create an activity def. Raises sqlite3.IntegrityError on a duplicate id (router → 409).
    #75: syncs the linked reminder if remind_at + remind_repeat≠off. #172: persists the custom
    weekday mask (remind_days CSV) so a 'custom' activity round-trips + drives the masked reminder."""
    store.create_activity(
        id=inp.id, name=inp.name, emoji=inp.emoji, icon=inp.icon, unit=inp.unit,
        goal=inp.goal, color=inp.color, created=vn_now_iso(),
        remind_at=inp.remindAt, remind_repeat=inp.remindRepeat,  # store col snake ← camel field
        remind_channel=inp.remindChannel,  # #111
        sched_time=inp.time,  # #136 G3-(ii): per-activity scheduled time (independent of the reminder)
        remind_days=_days_to_csv(inp.remindDays),  # #172: CSV weekday mask (None for non-custom)
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
                 "remindDays": "remind_days",  # #172: API field `remindDays` (list[int]) → DB col `remind_days` (CSV)
                 "time": "sched_time"}  # #136 G3-(ii): API field `time` → DB col `sched_time`


def update_activity(activity_id: str, upd: ActivityUpdate) -> Activity | None:
    """Update the supplied fields of an activity def. Returns the updated def, or None if absent.
    #75: re-syncs the linked reminder (upsert on remind change, delete on clear/off)."""
    # map the camel wire field names to the snake store columns (#75-TWEAK).
    fields = {_FIELD_TO_COL.get(k, k): v for k, v in upd.model_dump(exclude_none=True).items()}
    # #136-BE-3: an EXPLICIT time=null CLEARS sched_time. exclude_none drops {time:null} (can't tell
    # "omitted = unchanged" from "set null = clear"), so special-case `time` ONLY via model_fields_set
    # (pydantic v2 = the fields the request actually supplied). Scoped to `time` — remindAt/repeat/
    # channel keep their "None = unchanged" semantics (remindAt clears via remindRepeat='off', not null).
    if "time" in upd.model_fields_set and upd.time is None:
        fields["sched_time"] = None
    # #172: remindDays is list[int] on the wire but CSV in the store → convert. exclude_none already
    # dropped a None remindDays (= unchanged). When the repeat is set to a NON-custom mode, CLEAR the
    # stale mask (the days only apply to 'custom'); a 'custom' update must carry days (model-validated).
    if "remind_days" in fields:
        fields["remind_days"] = _days_to_csv(fields["remind_days"])
    if upd.remindRepeat is not None and upd.remindRepeat != "custom":
        fields["remind_days"] = None  # leaving custom → drop the mask (fire per the new repeat)
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
# TRACING-DEFAULT T2 (#173): the seed templates "+ Từ mẫu" suggests = ONLY the 3 check-ins (the
# user's intent — Daily Tracing defaults to the morning/noon/evening check-ins, not the old habits).
# unit="lần" + goal=1 (a daily binary check). Distinct emojis (🌅/☀️/🌙) + hues. The merge logic
# (list_templates SEED⊕override) is UNCHANGED — only the seed CONTENTS change. (icon is a free-form
# string the FE doesn't currently render — the emoji is what shows — so the keys are advisory.)
_SEED_TEMPLATES: list[dict[str, Any]] = [
    # #173 T3b: ids = _slug(name) so the seed-path + the import-path converge on ONE id-scheme.
    {"id": "check-in-sang", "name": "Check-in sáng", "emoji": "🌅", "icon": "sunrise", "unit": "lần", "goal": 1.0, "color": "#fbbf24"},
    {"id": "check-in-trua", "name": "Check-in trưa", "emoji": "☀️", "icon": "sun",     "unit": "lần", "goal": 1.0, "color": "#f97316"},
    {"id": "bao-cao-toi",   "name": "Báo cáo tối",   "emoji": "🌙", "icon": "moon",    "unit": "lần", "goal": 1.0, "color": "#818cf8"},
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


# --------------------------------------------------------------------------- #
# TRACING-TEMPLATE #137 T1: template-SETS (a saved named LIST of rich            #
# activities). Model B — activities is a JSON blob (serialized here; the store    #
# is JSON-agnostic). import-set→today reuses create_activity per member (goal=1   #
# binary todo + time/remind preset, the #122/#124/#136 model).                    #
# --------------------------------------------------------------------------- #
def _slug(text: str) -> str:
    """A lowercase ASCII slug for a set-name / member-content → id base. ASCII-folds Vietnamese
    diacritics (đ→d, ố→o, ...) via NFKD so 'Buổi sáng' → 'buoi-sang' (clean + readable), then
    non-alnum → '-', collapsed. Empty → 'activity' (a safe fallback id base)."""
    import unicodedata
    t = (text or "").strip().lower().replace("đ", "d")  # đ has no NFKD ASCII base — handle explicitly
    folded = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")
    return s or "activity"


def _row_to_template_set(row: sqlite3.Row) -> TemplateSet:
    """Map a row → TemplateSet, json.loads the activities blob (fail-soft: a malformed blob → [])."""
    try:
        raw = json.loads(row["activities"] or "[]")
        members = [TemplateMember(**m) for m in raw] if isinstance(raw, list) else []
    except Exception as exc:  # noqa: BLE001 — a corrupt blob → honest-empty member list, never crash
        logger.warning("tracing: template-set %s has a malformed activities blob: %s", row["id"], exc)
        members = []
    return TemplateSet(id=row["id"], name=row["name"], activities=members)


def _members_json(members: list[TemplateMember]) -> str:
    """Serialize the member list → the JSON blob stored in the activities column."""
    return json.dumps([m.model_dump() for m in members])


def list_template_sets() -> list[TemplateSet]:
    """All template-sets, name-order. honest-empty [] when none."""
    return [_row_to_template_set(r) for r in store.list_template_sets()]


def get_template_set(set_id: str) -> TemplateSet | None:
    """One template-set by id, or None if absent."""
    row = store.get_template_set(set_id)
    return _row_to_template_set(row) if row is not None else None


def create_template_set(inp: TemplateSetInput) -> TemplateSet:
    """Create a template-set (server-set id = slug(name) + a numeric suffix if taken). Returns it."""
    base = _slug(inp.name)
    sid = base
    n = 2
    while store.get_template_set(sid) is not None:  # avoid an id collision across sets
        sid = f"{base}-{n}"
        n += 1
    store.upsert_template_set(id=sid, name=inp.name, activities_json=_members_json(inp.activities))
    created = store.get_template_set(sid)
    assert created is not None
    return _row_to_template_set(created)


def replace_template_set(set_id: str, inp: TemplateSetInput) -> TemplateSet | None:
    """Whole-set replace (name + members). None if the id is absent (router → 404)."""
    if store.get_template_set(set_id) is None:
        return None
    store.upsert_template_set(id=set_id, name=inp.name, activities_json=_members_json(inp.activities))
    row = store.get_template_set(set_id)
    assert row is not None
    return _row_to_template_set(row)


def delete_template_set(set_id: str) -> bool:
    """Delete one template-set. True if it existed. SCOPED (never touches activities/logs)."""
    return store.delete_template_set(set_id)


def import_template_set(set_id: str) -> tuple[list[ActivityView], list[str], int] | None:
    """#137 / TRACING-TEMPLATE-UX (#173): 1-click import = the board becomes EXACTLY this template,
    IDEMPOTENT-BY-ID. None if the set is absent (router → 404).

    Each member gets a STABLE canonical id = ``_slug(content)`` (NOT slug+suffix) → re-importing the
    same set REUSES the same ids (no ``-N`` garbage, /trash does NOT grow). Per member:
      - absent     → CREATE it (create_activity + _sync_reminder → reminder + #172 day-mask carry);
      - ARCHIVED   → UN-ARCHIVE (the #130 pattern) + UPDATE its fields to the member;
      - ACTIVE     → UPDATE its fields to the member (same content = same activity).

    Order (the ATOMIC guard, from T1): upsert/un-archive ALL members FIRST; THEN archive the old
    active ids NOT in the new member-id set. Upsert-first → a mid-import failure never empties the
    board (the old board stays until ≥1 member lands). If ALL members fail → the old board is KEPT.

    🔴 SCOPED: archive ONLY old active ids that are NOT members of this import (never a just-upserted
    member). Recoverable (soft-delete).

    Returns (memberViews, skipped, archivedCount): memberViews = the imported members (created OR
    re-activated/updated); archivedCount = old non-matching activities retired."""
    s = get_template_set(set_id)
    if s is None:
        return None
    # snapshot the OLD active ids BEFORE the upsert (the board this import replaces)
    old_ids = [r["id"] for r in store.list_activities()]  # active only (excludes archived)
    views: list[ActivityView] = []
    skipped: list[str] = []
    member_ids: set[str] = set()
    # (1) upsert every member by its STABLE canonical id (idempotent — no suffix)
    for m in s.activities:
        aid = _slug(m.content)  # STABLE id → re-import reuses it (the #173 idempotency fix)
        remind_at = m.time if m.remindRepeat != "off" else None  # reminder fires at the member's time
        try:
            existing = get_activity(aid)  # incl. archived
            act: Activity
            if existing is None:
                act = create_activity(ActivityInput(
                    id=aid, name=m.content, goal=1.0,            # #122/#124: binary todo
                    time=m.time, remindAt=remind_at, remindRepeat=m.remindRepeat,
                    remindChannel=m.remindChannel, remindDays=m.remindDays))  # #172 mask
            else:
                if existing.archived:
                    store.unarchive_activity(aid)  # #130: re-surface the same row (logs preserved)
                # UPDATE the member's fields (time/remind/remindDays/name) to match the template
                updated = update_activity(aid, ActivityUpdate(
                    name=m.content, time=m.time, remindAt=remind_at,
                    remindRepeat=m.remindRepeat, remindChannel=m.remindChannel,
                    remindDays=m.remindDays))
                assert updated is not None  # the id exists (we just read/un-archived it)
                act = updated
            views.append(_derive_activity_view(act))
            member_ids.add(aid)
        except Exception as exc:  # noqa: BLE001 — fail-soft per member; the rest still import
            logger.error("tracing: import member %r from set %s failed: %s", m.content, set_id, exc)
            skipped.append(m.content)
    # (2) archive the OLD active ids NOT in this import's member set — ONLY if ≥1 member landed (else
    #     keep the old board). SCOPED: never a just-upserted member (member_ids). A re-import of the
    #     SAME set → old_ids ⊆ member_ids → archives 0 (the idempotency: no trash growth).
    archived_count = 0
    if views:
        for aid in old_ids:
            if aid in member_ids:
                continue
            if archive_activity(aid):  # soft-delete (recoverable) + drops the linked reminder
                archived_count += 1
    logger.info("tracing import_template_set %s: members=%d skipped=%d archived=%d",
                set_id, len(views), len(skipped), archived_count)
    return views, skipped, archived_count


# #137 / TRACING-DEFAULT T3 (#173): the default template-set re-seeded by reset. Now the 3 daily
# check-ins (mirroring the seeded activities) — NOT the old "Buổi sáng" habit routine. Importing this
# set creates the 3 check-in activities with their times + reminders (checkin-* fire Mon–Fri via the
# #172 custom mask, báo-cáo-tối every day). TemplateMember carries remindRepeat="custom" + remindDays.
_DEFAULT_TEMPLATE_SET = {
    "id": "check-in",
    "name": "Check-in hàng ngày",
    "activities": [
        {"content": "Check-in sáng", "time": "07:00", "remindRepeat": "custom", "remindDays": [0, 1, 2, 3, 4], "remindChannel": "in_app"},
        {"content": "Check-in trưa", "time": "12:00", "remindRepeat": "custom", "remindDays": [0, 1, 2, 3, 4], "remindChannel": "in_app"},
        {"content": "Báo cáo tối", "time": "21:00", "remindRepeat": "daily", "remindChannel": "in_app"},
    ],
}


def reset_template_sets() -> list[TemplateSet]:
    """RESET: discard ALL template-sets + re-seed the ONE sensible default ('Check-in hàng ngày', the
    3 daily check-ins — #173). Returns the resulting list (the default). 🔴 SCOPED to
    tracing_template_set — NEVER touches activities/logs (the #72 lesson). Mirrors the #109 reset."""
    store.delete_all_template_sets()
    d = _DEFAULT_TEMPLATE_SET
    members = [TemplateMember(**m) for m in d["activities"]]  # type: ignore[arg-type]
    store.upsert_template_set(id=str(d["id"]), name=str(d["name"]), activities_json=_members_json(members))
    return list_template_sets()


# --------------------------------------------------------------------------- #
# TRACING-UX3A T1 (#170 follow-up): backfill old TIMELESS activities to a       #
# default time so they leave the "Chưa đặt giờ" bucket + go on the timeline     #
# rail. New adds now require a time; these are legacy null-time rows.           #
# --------------------------------------------------------------------------- #
def backfill_timeless_time(default_time: str = "08:00") -> dict[str, Any]:
    """Re-runnable maintenance helper (NOT a startup hook; the wiki ``supersede_pending`` pattern).

    For every ACTIVE activity whose ``time`` is null/empty, set its ``time`` via the CANONICAL update
    path (``update_activity(id, ActivityUpdate(time=...))``) — the audited write, NOT a raw SQL UPDATE.

    🔴 Per-activity rule (T1 REFINEMENT — avoid a UX jump): the FE rail falls back to ``remindAt`` when
    ``time`` is null (railTime = ``a.time || a.remindAt``), so an activity WITH a reminder already shows
    at its remindAt on the rail. To keep what's on screen:
      - time=null AND remindAt set   → time = remindAt   (e.g. "Viết nhật ký" 07:00 → no visible jump)
      - time=null AND no remindAt     → time = default_time ("08:00")
      - time already set              → SKIP (idempotent — a re-run touches 0)

    🔴 SCOPED: sets ONLY ``time`` (→ sched_time col); the reminder field itself is UNTOUCHED in all cases
    (model_dump(exclude_none=True) on a 1-field update yields ONE column). Name/goal/streak/logs/remindAt
    are preserved.

    Returns ``{"beforeTimeless": N, "afterTimeless": M, "set": {id: time}, "touched": [ids],
    "defaultTime": "08:00"}`` — ``set`` shows the per-id time chosen (the #72 before/after discipline +
    the refined per-activity audit)."""
    rows = store.list_activities()  # ACTIVE only (excludes archived), created-order
    acts = [_row_to_activity(r) for r in rows]
    timeless = [a for a in acts if not (a.time and a.time.strip())]
    before = len(timeless)
    chosen: dict[str, str] = {}
    for a in timeless:
        # prefer the activity's remindAt (matches what the FE rail already shows) else the default
        new_time = a.remindAt.strip() if (a.remindAt and a.remindAt.strip()) else default_time
        update_activity(a.id, ActivityUpdate(time=new_time))  # canonical, audited, scoped to `time`
        chosen[a.id] = new_time
    # re-read to confirm the after-count (don't trust the in-memory list)
    after = sum(1 for r in store.list_activities()
                if not ((_row_to_activity(r).time or "").strip()))
    logger.info("tracing backfill_timeless_time: before=%d after=%d set=%s default=%s",
                before, after, chosen, default_time)
    return {"beforeTimeless": before, "afterTimeless": after,
            "set": chosen, "touched": list(chosen), "defaultTime": default_time}


# --------------------------------------------------------------------------- #
# TRACING-ALARM T2 (#172): seed 3 daily check-in activities that USE the T1     #
# custom-day reminder mode, so the user has them ready on /tracing.            #
# --------------------------------------------------------------------------- #
# The seed list — each is a daily binary check (goal=1) with a reminder. checkin-* fire Mon–Fri
# (custom mask, skip weekend); report-toi fires every day (daily). Names are proper VN with diacritics.
# #173 T3b: ids = _slug(name) so seed_checkin_activities + import_template_set converge on ONE
# id-scheme (check-in-sang / check-in-trua / bao-cao-toi).
_CHECKIN_SEED: list[dict[str, Any]] = [
    {"id": "check-in-sang", "name": "Check-in sáng", "time": "07:00",
     "remindRepeat": "custom", "remindDays": [0, 1, 2, 3, 4]},
    {"id": "check-in-trua", "name": "Check-in trưa", "time": "12:00",
     "remindRepeat": "custom", "remindDays": [0, 1, 2, 3, 4]},
    {"id": "bao-cao-toi", "name": "Báo cáo tối", "time": "21:00",
     "remindRepeat": "daily", "remindDays": None},
]


def seed_checkin_activities() -> dict[str, Any]:
    """Re-runnable maintenance helper (NOT a startup hook; the #171 backfill pattern). Creates the 3
    check-in activities (Check-in sáng / Check-in trưa / Báo cáo tối) via the CANONICAL create path
    (``create_activity`` → _sync_reminder fires the linked reminder with the right day-mask).

    🔴 IDEMPOTENT + SCOPED: an id that ALREADY exists (incl. archived — get_activity covers it) is
    SKIPPED — never overwritten (a re-run must not clobber a user's edits) and never duplicated. Only
    the 3 seed ids are touched; the other activities are untouched. The reminder for each is set on
    create: ``remindAt = time`` so the linked reminder fires at that time (custom → Mon–Fri mask,
    daily → every day).

    Returns ``{"created": [ids], "skipped": [ids], "createdCount": N, "skippedCount": M}``."""
    created: list[str] = []
    skipped: list[str] = []
    for s in _CHECKIN_SEED:
        sid = str(s["id"])
        if get_activity(sid) is not None:  # already present (incl. archived) → SKIP, no overwrite
            skipped.append(sid)
            continue
        inp = ActivityInput(
            id=sid, name=str(s["name"]), goal=1.0,        # daily binary check
            time=s["time"],                               # the scheduled time (independent of reminder)
            remindAt=s["time"],                           # reminder fires AT the scheduled time
            remindRepeat=s["remindRepeat"], remindChannel="in_app",
            remindDays=s["remindDays"],                   # custom → Mon–Fri mask; daily → None
        )
        create_activity(inp)  # reuses create + _sync_reminder (the linked reminder gets the day-mask)
        created.append(sid)
    logger.info("tracing seed_checkin_activities: created=%s skipped=%s", created, skipped)
    return {"created": created, "skipped": skipped,
            "createdCount": len(created), "skippedCount": len(skipped)}


# --------------------------------------------------------------------------- #
# TRACING-TEMPLATE-UX T3b (#173): migrate the live board from the OLD non-slug   #
# check-in ids to the SLUG ids so seed-path + import-path share ONE id-scheme.   #
# --------------------------------------------------------------------------- #
# The pre-T3b ids that diverged from _slug(name) — archived on migration so the live board converges.
_OLD_CHECKIN_IDS: list[str] = ["checkin-sang", "checkin-trua", "report-toi"]


def migrate_checkin_ids_to_slug() -> dict[str, Any]:
    """Re-runnable maintenance helper (NOT a startup hook; the #171 pattern). One-shot migration of
    the LIVE board from the pre-T3b non-slug check-in ids (checkin-sang/checkin-trua/report-toi) to
    the SLUG ids (check-in-sang/check-in-trua/bao-cao-toi = `_slug(name)`), so seed + import converge.

    🔴 SCOPED + IDEMPOTENT (NOT via import — avoids the re-suffix hazard): (1) archive any ACTIVE
    old-id activity (soft-delete, recoverable); (2) seed-or-update the 3 slug ids to the canonical
    fields via `seed_checkin_activities` (which is itself idempotent: creates if absent, skips if
    present) + ensure an archived slug id is un-archived. A re-run when the board is already on the
    slug scheme → archives 0, seed skips 3 → 0 net change.

    Returns ``{"archivedOld": [ids], "slugBoard": [ids], "archivedCount": N}``."""
    archived: list[str] = []
    for oid in _OLD_CHECKIN_IDS:
        a = get_activity(oid)
        if a is not None and not a.archived:
            archive_activity(oid)  # soft-delete (recoverable) + drops the linked reminder
            archived.append(oid)
    # ensure the 3 slug ids exist + are active with the canonical fields + reminders
    for s in _CHECKIN_SEED:
        sid = str(s["id"])
        existing = get_activity(sid)  # incl. archived
        if existing is None:
            create_activity(ActivityInput(
                id=sid, name=str(s["name"]), goal=1.0, time=s["time"], remindAt=s["time"],
                remindRepeat=s["remindRepeat"], remindChannel="in_app", remindDays=s["remindDays"]))
        else:
            if existing.archived:
                store.unarchive_activity(sid)
            update_activity(sid, ActivityUpdate(
                name=str(s["name"]), time=s["time"], remindAt=s["time"],
                remindRepeat=s["remindRepeat"], remindChannel="in_app", remindDays=s["remindDays"]))
    slug_board = [str(s["id"]) for s in _CHECKIN_SEED]
    logger.info("tracing migrate_checkin_ids_to_slug: archivedOld=%s slugBoard=%s", archived, slug_board)
    return {"archivedOld": archived, "slugBoard": slug_board, "archivedCount": len(archived)}


# --------------------------------------------------------------------------- #
# TRACING-DEFAULT T1 (#173): archive the 7 legacy habit activities so /tracing  #
# defaults to ONLY the 3 check-ins (the user's original intent). RECOVERABLE.   #
# --------------------------------------------------------------------------- #
# The 7 legacy habits to retire (verified streak=0/no-log → safe). The 3 check-ins are KEPT.
_LEGACY_HABIT_IDS: list[str] = ["tap-the-duc", "doc-sach", "ngu", "thien", "di-bo", "hoc", "viet"]


def archive_legacy_habits() -> dict[str, Any]:
    """Re-runnable maintenance helper (NOT a startup hook; the #171 pattern). Archives (SOFT-deletes,
    RECOVERABLE) EXACTLY the 7 legacy habit activities so /tracing defaults to the 3 check-ins.

    🔴 SCOPED + IDEMPOTENT: only the 7 ``_LEGACY_HABIT_IDS`` are touched — NEVER the 3 check-ins. An
    id that is absent OR already archived is SKIPPED (a re-run archives 0). archive_activity also
    deletes the linked reminder (correct — a retired habit shouldn't nag). The activity row + its logs
    are KEPT (archive = soft-delete; restore by un-archiving), so this is reversible.

    Returns ``{"archived": [ids], "skipped": [ids], "archivedCount": N,
    "activeBefore": X, "activeAfter": Y}`` (the #171 before/after discipline for a real-store write)."""
    active_before = sum(1 for r in store.list_activities())  # active (excludes archived)
    archived: list[str] = []
    skipped: list[str] = []
    for aid in _LEGACY_HABIT_IDS:
        act = get_activity(aid)  # includes archived
        if act is None or act.archived:  # absent or already archived → SKIP (idempotent)
            skipped.append(aid)
            continue
        archive_activity(aid)  # soft-delete (recoverable) + drops the linked reminder
        archived.append(aid)
    active_after = sum(1 for r in store.list_activities())
    logger.info("tracing archive_legacy_habits: archived=%s skipped=%s active %d→%d",
                archived, skipped, active_before, active_after)
    return {"archived": archived, "skipped": skipped, "archivedCount": len(archived),
            "activeBefore": active_before, "activeAfter": active_after}
