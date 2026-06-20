"""modules/reminders/schema.py — Reminder shapes (REMINDERS-1, #27).

The FROZEN reminder contract (#28 MCP + #31 FE mirror THIS — schema-freeze-gate). A reminder is
a single-user alarm/agenda item: a title + a due instant + an optional repeat/re-notify policy
(the policy fields are STORED here but only ACTED on by the #29 notify routine). NEUTRAL storage —
no AI, no auth, no multi-user.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Repeat = Literal["once", "daily", "weekly"]


def _parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 datetime (accepts a trailing 'Z'). Raises ValueError if unparseable —
    the caller (router) maps that to 422 so a bad due_at never stores a row."""
    s = (value or "").strip()
    if not s:
        raise ValueError("must be a non-empty ISO-8601 datetime")
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _to_utc_iso(value: str) -> str:
    """REMINDERS-1A: normalize a parsed ISO-8601 due_at to a UTC ISO string. This makes the
    store's lexicographic ``due_at <= boundary`` compare correct (the store assumes all-UTC; a
    raw non-UTC offset string would mis-sort — e.g. '2026-06-21T02:00:00+07:00' is actually
    2026-06-20T19:00:00Z = today-in-UTC, but raw-string-sorted it falls AFTER an end-of-today-UTC
    boundary → wrongly excluded). Rules:
      - offset-aware (Z or ±HH:MM) → astimezone(UTC).
      - NAIVE (no tz, e.g. '2026-06-21T02:00:00') → ASSUMED UTC (decide-and-log: single-user,
        simplest honest rule; attach tzinfo=UTC, do NOT astimezone a naive dt — that would use
        the ambiguous system-local tz). Logged to ## Assumptions: "naive due_at → assumed UTC."
    Raises ValueError (→ 422) for an unparseable input via _parse_iso."""
    dt = _parse_iso(value)
    if dt.tzinfo is None:  # naive → assume UTC (attach, don't local-convert)
        dt = dt.replace(tzinfo=timezone.utc)
    else:                  # offset-aware → convert to UTC
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


class ReminderInput(BaseModel):
    """Create payload. due_at is validated parseable (→ 422 on bad input, no row stored).
    The policy fields (re_notify_every / max_times) are stored for #29; #27 doesn't act on them."""

    title: str = Field(..., min_length=1, max_length=200, description="what to be reminded of")
    note: str | None = Field(default=None, max_length=2000, description="optional detail")
    due_at: str = Field(..., description="ISO-8601 datetime the reminder is due")
    repeat: Repeat = Field(default="once", description="once | daily | weekly")
    re_notify_every: int | None = Field(default=None, ge=1, description="minutes between re-notifies (#29)")
    max_times: int | None = Field(default=None, ge=1, description="max notify count (#29)")

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("title must not be blank")
        return s

    @field_validator("note")
    @classmethod
    def _note_strip(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s or None

    @field_validator("due_at")
    @classmethod
    def _due_parseable(cls, v: str) -> str:
        # REMINDERS-1A: validate parseable (→ 422) AND store UTC-NORMALIZED, so the store's
        # lexicographic due_at-vs-boundary compare is correct for any offset/naive input (the
        # raw-string bug: a +07:00 today-in-UTC due_at sorted as tomorrow → wrongly filtered).
        return _to_utc_iso(v)  # raises ValueError → 422 on a bad input; returns a UTC ISO string


class Reminder(BaseModel):
    """The stored reminder (the FROZEN read shape #28/#31 mirror)."""

    id: int
    title: str = Field(..., min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=2000)
    due_at: str = Field(..., description="ISO-8601 datetime due")
    repeat: Repeat = Field(default="once")
    re_notify_every: int | None = Field(default=None, ge=1, description="minutes between re-notifies (#29)")
    max_times: int | None = Field(default=None, ge=1, description="max notify count (#29)")
    notified_count: int = Field(default=0, ge=0, description="times notified so far (#29)")
    done_at: str | None = Field(default=None, description="ISO-8601 when ticked done, else None")
    created: str = Field(..., description="ISO-8601 created timestamp")


class ReminderList(BaseModel):
    """A filtered list + counts (the GET /reminders response data)."""

    reminders: list[Reminder] = Field(default_factory=list)
    count: int = Field(..., ge=0, description="number of reminders in this filtered list")
    undoneCount: int = Field(..., ge=0, description="number of undone reminders in this filtered list")
    filter: str = Field(..., description="the filter applied (today|week|undone|all)")


def now_iso() -> str:
    """Current UTC instant, ISO-8601. The single now() source for the module."""
    return datetime.now(timezone.utc).isoformat()
