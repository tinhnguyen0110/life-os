"""modules/tracing/schema.py — tracing shapes (DAILY-TRACING-P1, #65).

The tracing contract (P2 MCP + P3 FE mirror THIS — schema-freeze-gate). An *activity* is a habit
definition (run/code/study), a *log* is one raw session against it. Everything else (today/streak/
week/history/heatmap/score) is DERIVED server-side from the raw logs — raw-data-first, never stored.

Input/Entity split (like reminders): ``ActivityInput`` = create/update payload (validated, → 422 on
bad input); ``Activity`` = the stored def; ``ActivityView`` = the def + its derived metrics (the
card payload); ``TracingOverview`` = the whole-board payload. NEUTRAL — no AI, no auth.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# VN day = UTC+7 — ALL date bucketing in this module uses this (a 23:30-VN session is today-VN,
# not tomorrow-UTC). Single offset, no DST in Vietnam — a fixed timedelta is correct + simplest.
VN_TZ = timezone(timedelta(hours=7))


def vn_today() -> str:
    """The current VN calendar day as YYYY-MM-DD (the bucket key for 'today')."""
    return datetime.now(VN_TZ).strftime("%Y-%m-%d")


def vn_now_iso() -> str:
    """Current instant as a VN-offset ISO-8601 string (the session ts source)."""
    return datetime.now(VN_TZ).isoformat()


def vn_day_of(ts: str) -> str:
    """The VN calendar day (YYYY-MM-DD) an ISO-8601 ts falls on. Offset-aware ts → converted to
    VN; a NAIVE ts → ASSUMED already VN (decide-and-log: single-user, the module writes VN ts).
    So a '2026-06-21T23:30:00+07:00' or naive '...T23:30:00' both bucket to 2026-06-21."""
    s = (ts or "").strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:          # naive → assume already VN (the module's own writes are VN)
        dt = dt.replace(tzinfo=VN_TZ)
    return dt.astimezone(VN_TZ).strftime("%Y-%m-%d")


# TRACING-REMINDERS (#75): an activity can drive a daily reminder. remind_at = HH:MM VN time-of-day
# (None = no reminder); remind_repeat = how it recurs (off = no reminder regardless of remind_at).
# TRACING-ALARM (#172): +"custom" — fire only on the days in remindDays (a Mon0..Sun6 weekday mask).
# "weekdays" now genuinely fires Mon–Fri only (the #75 lie — it used to fire daily — is fixed).
RemindRepeat = Literal["daily", "weekdays", "off", "custom"]


def _validate_remind_days(v: list[int] | None) -> list[int] | None:
    """TRACING-ALARM (#172): validate a weekday mask — each int in 0..6 (Mon0..Sun6, matching
    date.weekday()), deduped + sorted. None/[] → None (no mask). A value outside 0..6 → 422.
    (The 'required-non-empty when repeat=custom' rule is enforced per-model below, since it needs
    the sibling remindRepeat.)"""
    if v is None:
        return None
    cleaned = sorted({int(d) for d in v})
    for d in cleaned:
        if d < 0 or d > 6:
            raise ValueError("remindDays must be ints 0..6 (Mon=0 … Sun=6)")
    return cleaned or None


def _require_days_for_custom(repeat: str | None, days: list[int] | None) -> None:
    """TRACING-ALARM (#172): remindRepeat='custom' REQUIRES a non-empty remindDays (else 422)."""
    if repeat == "custom" and not days:
        raise ValueError("custom repeat needs remindDays (a non-empty list of weekdays 0..6)")
# TRACING-UX T3 (#111): the delivery channel the activity's linked reminder fires on (mirrors the
# reminders Channel; default in_app). Set on the linked reminder when the tracing service syncs it.
RemindChannel = Literal["in_app", "email", "discord"]


def _validate_hhmm(v: str | None) -> str | None:
    """Validate a HH:MM (24h) time-of-day string, or None. Raises ValueError (→ 422) on a bad time."""
    if v is None:
        return None
    s = v.strip()
    if not s:
        return None
    datetime.strptime(s, "%H:%M")  # raises ValueError on a malformed time → 422
    return s


def _validate_date(v: str | None) -> str | None:
    """#125: validate a YYYY-MM-DD date string, or None. Raises ValueError (→ 422) on a bad date.
    (Future-vs-past is checked at the agent-facing surface, not here — this only validates format.)"""
    if v is None:
        return None
    s = v.strip()
    if not s:
        return None
    datetime.strptime(s, "%Y-%m-%d")  # raises ValueError on a malformed date → 422
    return s


# --------------------------------------------------------------------------- #
# Inputs (create/update payloads — validated at the boundary → 422)            #
# --------------------------------------------------------------------------- #
class ActivityInput(BaseModel):
    """Create payload for an activity def. ``id`` is a stable slug the caller chooses (e.g. 'run');
    a blank name/id is a 422. ``goal`` ≥ 0 (0 = no goal → pct always 0, never done)."""

    id: str = Field(..., min_length=1, max_length=64, description="stable slug, e.g. 'run'")
    name: str = Field(..., min_length=1, max_length=120, description="display name")
    emoji: str = Field(default="", max_length=16, description="display emoji")
    icon: str = Field(default="", max_length=64, description="icon key (FE)")
    unit: str = Field(default="", max_length=32, description="unit of val, e.g. 'km', 'min', 'reps'")
    goal: float = Field(default=0.0, ge=0, description="daily goal in `unit` (0 = no goal)")
    color: str = Field(default="", max_length=32, description="display color (FE)")
    time: str | None = Field(default=None, description="HH:MM VN scheduled time, INDEPENDENT of the reminder (#136 G3-(ii); None = none)")
    remindAt: str | None = Field(default=None, description="HH:MM VN reminder time (None = none) (#75)")
    remindRepeat: RemindRepeat = Field(default="off", description="daily|weekdays|off|custom (#75/#172)")
    remindChannel: RemindChannel = Field(default="in_app", description="in_app|email|discord (#111)")
    remindDays: list[int] | None = Field(default=None, description="TRACING-ALARM (#172): weekday mask "
                                         "Mon0..Sun6 — REQUIRED non-empty when remindRepeat='custom'; "
                                         "ignored/None otherwise (e.g. [0,1,2,3,4] = Mon–Fri)")

    @field_validator("id", "name")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("must not be blank")
        return s

    @field_validator("remindAt", "time")  # #136: time mirrors remindAt's HH:MM validation
    @classmethod
    def _remind_at_hhmm(cls, v: str | None) -> str | None:
        return _validate_hhmm(v)

    @field_validator("remindDays")  # #172: each int 0..6, deduped + sorted; None/[] → None
    @classmethod
    def _remind_days_valid(cls, v: list[int] | None) -> list[int] | None:
        return _validate_remind_days(v)

    @model_validator(mode="after")
    def _custom_needs_days(self) -> "ActivityInput":  # #172: custom repeat requires non-empty days
        _require_days_for_custom(self.remindRepeat, self.remindDays)
        return self


class ActivityUpdate(BaseModel):
    """Partial update — every field optional; only the supplied ones change. ``goal`` ≥ 0."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    emoji: str | None = Field(default=None, max_length=16)
    icon: str | None = Field(default=None, max_length=64)
    unit: str | None = Field(default=None, max_length=32)
    goal: float | None = Field(default=None, ge=0)
    color: str | None = Field(default=None, max_length=32)
    # TRACING-REMINDERS (#75): None means "not supplied" (leave unchanged). To CLEAR the reminder,
    # pass remind_repeat="off" (or an explicit empty remind_at via the router's clear path).
    time: str | None = Field(default=None, description="HH:MM VN scheduled time (#136 G3-(ii); None = unchanged)")
    remindAt: str | None = Field(default=None, description="HH:MM VN reminder time (#75)")
    remindRepeat: RemindRepeat | None = Field(default=None, description="daily|weekdays|off|custom (#75/#172)")
    remindChannel: RemindChannel | None = Field(default=None, description="in_app|email|discord (#111)")
    remindDays: list[int] | None = Field(default=None, description="TRACING-ALARM (#172): weekday mask "
                                         "Mon0..Sun6 (None = unchanged); REQUIRED non-empty when this "
                                         "update sets remindRepeat='custom'")

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("name must not be blank")
        return s

    @field_validator("remindAt", "time")  # #136: time mirrors remindAt's HH:MM validation
    @classmethod
    def _remind_at_hhmm(cls, v: str | None) -> str | None:
        return _validate_hhmm(v)

    @field_validator("remindDays")  # #172: each int 0..6, deduped + sorted; None/[] → None
    @classmethod
    def _remind_days_valid(cls, v: list[int] | None) -> list[int] | None:
        return _validate_remind_days(v)

    @model_validator(mode="after")
    def _custom_needs_days(self) -> "ActivityUpdate":
        # #172: if this update SETS remindRepeat='custom', it must also carry a non-empty remindDays
        # (the FE sends both together). Other repeats ignore remindDays.
        if self.remindRepeat == "custom":
            _require_days_for_custom("custom", self.remindDays)
        return self


# --------------------------------------------------------------------------- #
# TRACING-UX T1 (#109): task templates — prefill the "new activity" form.       #
# A template is NOT an activity (it's a prefill suggestion). The list = SEED     #
# (hard-coded, immutable) ⊕ USER OVERRIDE (the tracing_template table). Each     #
# returned item carries source="seed"|"user". Templates never create activities  #
# (the FE prefills the form → the existing POST /activities creates).             #
# --------------------------------------------------------------------------- #
TemplateSource = Literal["seed", "user"]


class TemplateInput(BaseModel):
    """Upsert payload for a user template override (PUT /tracing/templates/{id}). The id is the path
    param (a stable slug); the body is the prefill fields. A blank name → 422; goal ≥ 0."""

    name: str = Field(..., min_length=1, max_length=120, description="display name")
    emoji: str = Field(default="", max_length=16, description="display emoji")
    icon: str = Field(default="", max_length=64, description="icon key (FE)")
    unit: str = Field(default="", max_length=32, description="unit of val, e.g. 'ly', 'min'")
    goal: float = Field(default=0.0, ge=0, description="suggested daily goal (0 = no goal)")
    color: str = Field(default="", max_length=32, description="display color (FE)")

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("name must not be blank")
        return s


class Template(BaseModel):
    """A merged template list item (SEED ⊕ OVERRIDE). ``source`` tells the agent/FE whether it's a
    built-in seed or a user override (a user-edited seed reports source='user'). LEAN — exactly the
    prefill fields, no derived metrics (templates are prefill suggestions, not activities)."""

    id: str
    name: str
    emoji: str = ""
    icon: str = ""
    unit: str = ""
    goal: float = Field(default=0.0, ge=0)
    color: str = ""
    source: TemplateSource = Field(..., description="'seed' (built-in) | 'user' (override)")


class LogInput(BaseModel):
    """Log one session against an activity. ``val`` ≥ 0 (a negative is a 422). ``date`` defaults to
    today-VN; multiple logs the same day ACCUMULATE (summed), they don't overwrite."""

    val: float = Field(..., ge=0, description="the session's measured value in the activity's unit")
    dur_min: int | None = Field(default=None, ge=0, description="session duration in minutes")
    note: str | None = Field(default=None, max_length=2000, description="optional session note")
    date: str | None = Field(default=None, description="YYYY-MM-DD VN-day; default today-VN")

    @field_validator("note")
    @classmethod
    def _note_strip(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s or None

    @field_validator("date")
    @classmethod
    def _date_shape(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            return None
        # validate YYYY-MM-DD (→ 422 on a bad date so a malformed bucket never stores)
        datetime.strptime(s, "%Y-%m-%d")
        return s


# --------------------------------------------------------------------------- #
# Entities + derived views (the read shapes)                                   #
# --------------------------------------------------------------------------- #
class Activity(BaseModel):
    """A stored activity def."""

    id: str
    name: str
    emoji: str = ""
    icon: str = ""
    unit: str = ""
    goal: float = Field(default=0.0, ge=0)
    color: str = ""
    created: str
    archived: bool = False
    time: str | None = Field(default=None, description="HH:MM VN scheduled time, INDEPENDENT of the reminder (#136 G3-(ii))")
    remindAt: str | None = Field(default=None, description="HH:MM VN reminder time, or None (#75)")
    remindRepeat: RemindRepeat = Field(default="off", description="daily|weekdays|off|custom (#75/#172)")
    remindChannel: RemindChannel = Field(default="in_app", description="in_app|email|discord (#111)")
    remindDays: list[int] | None = Field(default=None, description="TRACING-ALARM (#172): weekday mask Mon0..Sun6 when remindRepeat='custom', else None")


class TodayStat(BaseModel):
    """An activity's derived TODAY rollup (raw-data-first — Σ of today's sessions)."""

    done: bool = Field(..., description="val ≥ goal (goal>0)")
    val: float = Field(..., description="Σ of today's sessions' val")
    dur: str = Field(default="", description="Σ of today's dur_min, formatted 'Hh Mm' (or '')")
    durMin: int = Field(default=0, ge=0, description="Σ of today's dur_min in raw minutes")
    note: str | None = Field(default=None, description="the latest today session's note")
    pct: int = Field(..., ge=0, le=100, description="round(min(100, val/goal*100)); 0 if goal==0")
    sessions: int = Field(default=0, ge=0, description="count of today's sessions")


class ActivityView(BaseModel):
    """An activity def + its derived metrics (the S14 card payload)."""

    id: str
    name: str
    emoji: str = ""
    icon: str = ""
    unit: str = ""
    goal: float = Field(default=0.0, ge=0)
    color: str = ""
    time: str | None = Field(default=None, description="HH:MM VN scheduled time, INDEPENDENT of the reminder (#136 G3-(ii)) — the FE timeline rails by this (fallback remindAt)")
    remindAt: str | None = Field(default=None, description="HH:MM VN reminder time, or None (#75)")
    remindRepeat: RemindRepeat = Field(default="off", description="daily|weekdays|off|custom (#75/#172)")
    remindChannel: RemindChannel = Field(default="in_app", description="in_app|email|discord (#111)")
    remindDays: list[int] | None = Field(default=None, description="TRACING-ALARM (#172): weekday mask Mon0..Sun6 when remindRepeat='custom', else None — the FE renders the day-chips")
    today: TodayStat
    streak: int = Field(..., ge=0, description="consecutive goal-met VN-days (today-incomplete ≠ break)")
    week: list[float] = Field(..., description="Mon→Sun Σ(val)/day for the current week (7)")
    history12w: list[float] = Field(..., description="oldest→newest per-day Σ(val), 84 days")


class TracingScore(BaseModel):
    """The whole-board roll-up."""

    total: int = Field(..., ge=0, description="active (non-archived) activity count")
    done: int = Field(..., ge=0, description="how many met goal today")
    pct: int = Field(..., ge=0, le=100, description="round(done/total*100); 0 if total==0")
    timeActive: str = Field(default="", description="Σ today all sessions' dur_min, 'Hh Mm'")
    topStreak: int = Field(..., ge=0, description="max streak across activities")


class TracingOverview(BaseModel):
    """GET /tracing — the full board (the S14 payload). honest-mirror: no activities → [] + all-0."""

    date: str = Field(..., description="the VN day this overview is for (YYYY-MM-DD)")
    activities: list[ActivityView] = Field(default_factory=list)
    heatmap12w: list[int] = Field(..., description="per-day COUNT of activities that met goal, 84")
    score: TracingScore


# --------------------------------------------------------------------------- #
# TRACING-UX2 T1 (#121): day-notes — text + optional remind. A note WITH a       #
# remind (remindAt + remindRepeat≠off) emits a linked reminder (source=          #
# "tracing-note", the #75 wire + #111 channel); clearing/deleting removes it.    #
# --------------------------------------------------------------------------- #
class NoteInput(BaseModel):
    """POST /tracing/notes — create a day-note. ``id`` + ``created`` are server-set."""

    text: str = Field(..., min_length=1, max_length=2000, description="the note text (the LogInput.note cap)")
    remindAt: str | None = Field(default=None, description="HH:MM VN reminder time (None = none) (#75)")
    remindDate: str | None = Field(
        default=None,
        description="#125: YYYY-MM-DD FUTURE date for a ONE-SHOT remind (None = no one-shot). "
        "Set → a repeat='once' reminder at remindDate@remindAt; absent → the #121 remindRepeat path.")
    remindRepeat: RemindRepeat = Field(default="off", description="daily|weekdays|off (#75)")
    remindChannel: RemindChannel = Field(default="in_app", description="in_app|email|discord (#111)")

    @field_validator("text")
    @classmethod
    def _text_not_blank(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("text must not be blank")
        return s

    @field_validator("remindAt")
    @classmethod
    def _remind_at_hhmm(cls, v: str | None) -> str | None:
        return _validate_hhmm(v)

    @field_validator("remindDate")
    @classmethod
    def _remind_date_fmt(cls, v: str | None) -> str | None:
        return _validate_date(v)


class NoteUpdate(BaseModel):
    """PUT /tracing/notes/{id} — partial update; only supplied fields change. To CLEAR the remind,
    pass remindRepeat='off' (the linked reminder is then deleted, mirroring the activity clear path)."""

    text: str | None = Field(default=None, min_length=1, max_length=2000)
    remindAt: str | None = Field(default=None, description="HH:MM VN reminder time (#75)")
    remindDate: str | None = Field(default=None, description="#125: YYYY-MM-DD future date for a one-shot remind")
    remindRepeat: RemindRepeat | None = Field(default=None, description="daily|weekdays|off (#75)")
    remindChannel: RemindChannel | None = Field(default=None, description="in_app|email|discord (#111)")

    @field_validator("text")
    @classmethod
    def _text_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("text must not be blank")
        return s

    @field_validator("remindAt")
    @classmethod
    def _remind_at_hhmm(cls, v: str | None) -> str | None:
        return _validate_hhmm(v)

    @field_validator("remindDate")
    @classmethod
    def _remind_date_fmt(cls, v: str | None) -> str | None:
        return _validate_date(v)


class Note(BaseModel):
    """A day-note (GET /tracing/notes list item + the create/update echo). honest-mirror shape."""

    id: str = Field(..., description="the note id (the autoincrement PK, stringified)")
    text: str = Field(..., description="the note text")
    remindAt: str | None = Field(default=None, description="HH:MM VN reminder time, or None (#75)")
    remindDate: str | None = Field(default=None, description="#125: YYYY-MM-DD future date for a one-shot remind, or None")
    remindRepeat: RemindRepeat = Field(default="off", description="daily|weekdays|off (#75)")
    remindChannel: RemindChannel = Field(default="in_app", description="in_app|email|discord (#111)")
    created: str = Field(..., description="ISO-8601 (VN) when the note was created")


# --------------------------------------------------------------------------- #
# TRACING-TEMPLATE #137 T1: a template-SET = a saved NAMED LIST of rich          #
# activities (a reusable routine). 1-click import → all members become today's   #
# activities (goal=1 binary todos w/ time+remind preset). Model B (DESIGN_137):  #
# tracing_template_set {id, name, activities JSON[]}; read/written/imported WHOLE.#
# (Replaces the rejected #109 1-word CHIP model — the chip CRUD stays dormant.)   #
# --------------------------------------------------------------------------- #
class TemplateMember(BaseModel):
    """One activity in a template-set's list. content = the activity name (a binary todo on import);
    time = a scheduled HH:MM (#136, independent of the reminder); remindRepeat≠off → the imported
    activity gets a reminder at ``time``, on ``remindChannel`` (#75/#111/#136)."""

    content: str = Field(..., min_length=1, max_length=120, description="the activity name (binary todo)")
    time: str | None = Field(default=None, description="HH:MM VN scheduled time, or None (#136)")
    remindRepeat: RemindRepeat = Field(default="off", description="off|daily|weekdays|custom — off = no reminder (#172)")
    remindChannel: RemindChannel = Field(default="in_app", description="in_app|email|discord (#111)")
    remindDays: list[int] | None = Field(default=None, description="TRACING-ALARM (#172): weekday mask Mon0..Sun6 when remindRepeat='custom'")

    @field_validator("content")
    @classmethod
    def _content_not_blank(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("content must not be blank")
        return s

    @field_validator("time")
    @classmethod
    def _time_hhmm(cls, v: str | None) -> str | None:
        return _validate_hhmm(v)

    @field_validator("remindDays")  # #172: each int 0..6, deduped + sorted
    @classmethod
    def _remind_days_valid(cls, v: list[int] | None) -> list[int] | None:
        return _validate_remind_days(v)

    @model_validator(mode="after")
    def _custom_needs_days(self) -> "TemplateMember":  # #172: custom requires non-empty days
        _require_days_for_custom(self.remindRepeat, self.remindDays)
        return self


class TemplateSetInput(BaseModel):
    """Create/replace payload for a template-set (POST + PUT). The id is server-set (POST) or the
    path param (PUT); the body is name + the member list. A blank name → 422."""

    name: str = Field(..., min_length=1, max_length=80, description="the set name, e.g. 'Buổi sáng'")
    activities: list[TemplateMember] = Field(default_factory=list, description="ordered member list")

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("name must not be blank")
        return s


class TemplateSet(BaseModel):
    """A saved template-set (GET list item + create/update echo). honest-mirror shape."""

    id: str = Field(..., description="the set id (slug or generated)")
    name: str = Field(..., description="the set name")
    activities: list[TemplateMember] = Field(default_factory=list, description="ordered member list")
