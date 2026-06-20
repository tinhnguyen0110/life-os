"""modules/reminders/service.py — reminders business logic (REMINDERS-1, #27).

CRUD + the tick lifecycle + the due/done filtered list. Coordinates store (SQLite) + reader
(fail-open mapping). NEUTRAL storage — the notify/repeat-roll behaviour is #29; #27 stores the
policy fields + the tick. Single-user, no auth.
"""

from __future__ import annotations

from . import store
from .reader import map_rows, row_to_reminder
from .schema import Reminder, ReminderInput, ReminderList, now_iso


def create(inp: ReminderInput) -> Reminder:
    """Create a reminder from a validated input (due_at already validated parseable by the schema
    → the router never reaches here with a bad due_at). Returns the stored Reminder."""
    rid = store.create_reminder(
        title=inp.title, note=inp.note, due_at=inp.due_at, repeat=inp.repeat,
        re_notify_every=inp.re_notify_every, max_times=inp.max_times, created=now_iso(),
    )
    row = store.get_reminder(rid)
    assert row is not None  # just inserted
    return row_to_reminder(row)


def get(reminder_id: int) -> Reminder | None:
    """One reminder by id, or None (→ 404 at the router)."""
    row = store.get_reminder(reminder_id)
    return row_to_reminder(row) if row is not None else None


def tick(reminder_id: int) -> Reminder | None:
    """Mark a reminder done. IDEMPOTENT — re-ticking a done reminder is a no-op (done_at keeps
    its first value), returns the reminder. None if the reminder doesn't exist (→ 404)."""
    row = store.tick_reminder(reminder_id, ts=now_iso())
    return row_to_reminder(row) if row is not None else None


def delete(reminder_id: int) -> bool:
    """Delete a reminder. True if removed, False if absent (→ 404)."""
    return store.delete_reminder(reminder_id)


def list_reminders(filter_key: str | None) -> tuple[ReminderList, list[str]]:
    """The filtered list + counts. Returns (ReminderList, warnings). Fail-open: a malformed row
    is skipped + warned, never crashes. ``undoneCount`` = how many in this list have done_at NULL
    (for 'all'/'undone' that's the undone subset; for 'today'/'week' all are undone by construction)."""
    rows = store.list_reminders(filter_key)
    reminders, warnings = map_rows(rows)
    undone = sum(1 for r in reminders if r.done_at is None)
    view = ReminderList(
        reminders=reminders,
        count=len(reminders),
        undoneCount=undone,
        filter=store.canonical_filter(filter_key),
    )
    return view, warnings
