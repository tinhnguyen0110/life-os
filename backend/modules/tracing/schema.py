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

from pydantic import BaseModel, Field, field_validator

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
RemindRepeat = Literal["daily", "weekdays", "off"]


def _validate_hhmm(v: str | None) -> str | None:
    """Validate a HH:MM (24h) time-of-day string, or None. Raises ValueError (→ 422) on a bad time."""
    if v is None:
        return None
    s = v.strip()
    if not s:
        return None
    datetime.strptime(s, "%H:%M")  # raises ValueError on a malformed time → 422
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
    remindAt: str | None = Field(default=None, description="HH:MM VN reminder time (None = none) (#75)")
    remindRepeat: RemindRepeat = Field(default="off", description="daily|weekdays|off (#75)")

    @field_validator("id", "name")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("must not be blank")
        return s

    @field_validator("remindAt")
    @classmethod
    def _remind_at_hhmm(cls, v: str | None) -> str | None:
        return _validate_hhmm(v)


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
    remindAt: str | None = Field(default=None, description="HH:MM VN reminder time (#75)")
    remindRepeat: RemindRepeat | None = Field(default=None, description="daily|weekdays|off (#75)")

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("name must not be blank")
        return s

    @field_validator("remindAt")
    @classmethod
    def _remind_at_hhmm(cls, v: str | None) -> str | None:
        return _validate_hhmm(v)


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
    remindAt: str | None = Field(default=None, description="HH:MM VN reminder time, or None (#75)")
    remindRepeat: RemindRepeat = Field(default="off", description="daily|weekdays|off (#75)")


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
    remindAt: str | None = Field(default=None, description="HH:MM VN reminder time, or None (#75)")
    remindRepeat: RemindRepeat = Field(default="off", description="daily|weekdays|off (#75)")
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
