"""modules/reminders/store.py — reminders persistence (REMINDERS-1, #27).

One module-owned SQLite table, ``reminders``, on the shared connection (same init-on-first-use
pattern as news/macro store.py — NOT in core db.py SCHEMA, kept module-scoped). Reminders are
relational alarm/agenda rows (CRUD + due/done filters + the tick lifecycle), so SQLite, not
md_store. Single-user; a module-level lock serialises writes on the shared connection.

Filter boundaries (LOCKED, UTC, ``<=`` inclusive — see list_reminders):
  today  = due_at ≤ end-of-today (23:59:59 UTC) AND not done.
  week   = due_at ≤ now + 7 days       AND not done.
  undone = not done (any due).
  all / unknown = everything, newest-due first (lenient — unknown filter → all).
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta, timezone

from store import db

_lock = threading.Lock()

REMINDERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS reminders (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT    NOT NULL,
    note             TEXT,
    due_at           TEXT    NOT NULL,                 -- ISO-8601 datetime due
    repeat           TEXT    NOT NULL DEFAULT 'once',  -- once | daily | weekly
    re_notify_every  INTEGER,                          -- minutes (#29)
    max_times        INTEGER,                          -- (#29)
    notified_count   INTEGER NOT NULL DEFAULT 0,       -- (#29)
    done_at          TEXT,                             -- ISO-8601 when ticked, else NULL
    created          TEXT    NOT NULL                  -- ISO-8601 created
);
CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(due_at);
CREATE INDEX IF NOT EXISTS idx_reminders_done ON reminders(done_at);
"""

# The columns selected for a Reminder row (stable order; reader maps these to the model).
_COLS = ("id, title, note, due_at, repeat, re_notify_every, max_times, "
         "notified_count, done_at, created")


def init_reminders_tables() -> sqlite3.Connection:
    """Register the reminders table on the shared connection. Idempotent; safe to call
    repeatedly and after a test rebinds ``db.DB_PATH``."""
    conn = db.get_conn()
    with _lock:
        conn.executescript(REMINDERS_SCHEMA)
        conn.commit()
    return conn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_reminder(*, title: str, note: str | None, due_at: str, repeat: str,
                    re_notify_every: int | None, max_times: int | None,
                    created: str) -> int:
    """Insert a reminder. Returns the new row id. notified_count starts 0, done_at NULL."""
    init_reminders_tables()
    conn = db.get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO reminders(title, note, due_at, repeat, re_notify_every, max_times, "
            "notified_count, done_at, created) VALUES (?,?,?,?,?,?,0,NULL,?)",
            (title, note, due_at, repeat, re_notify_every, max_times, created),
        )
        conn.commit()
        rid = cur.lastrowid
        assert rid is not None
        return int(rid)


def get_reminder(reminder_id: int) -> sqlite3.Row | None:
    """One reminder by id, or None if absent."""
    init_reminders_tables()
    conn = db.get_conn()
    with _lock:
        return conn.execute(
            f"SELECT {_COLS} FROM reminders WHERE id = ?", (int(reminder_id),)
        ).fetchone()


def tick_reminder(reminder_id: int, *, ts: str) -> sqlite3.Row | None:
    """Mark a reminder done (set done_at). IDEMPOTENT: re-ticking an already-done reminder is a
    no-op (done_at UNCHANGED — keeps the first tick's timestamp) and returns the row, NOT an
    error. Returns None if the reminder does not exist."""
    init_reminders_tables()
    conn = db.get_conn()
    with _lock:
        row = conn.execute(
            f"SELECT {_COLS} FROM reminders WHERE id = ?", (int(reminder_id),)
        ).fetchone()
        if row is None:
            return None
        if row["done_at"] is None:  # only set on the FIRST tick (idempotent re-tick = no-op)
            conn.execute("UPDATE reminders SET done_at = ? WHERE id = ?", (ts, int(reminder_id)))
            conn.commit()
            row = conn.execute(
                f"SELECT {_COLS} FROM reminders WHERE id = ?", (int(reminder_id),)
            ).fetchone()
        return row


def delete_reminder(reminder_id: int) -> bool:
    """Delete a reminder. Returns True if a row was removed, False if it didn't exist (→ 404)."""
    init_reminders_tables()
    conn = db.get_conn()
    with _lock:
        cur = conn.execute("DELETE FROM reminders WHERE id = ?", (int(reminder_id),))
        conn.commit()
        return cur.rowcount > 0


def list_reminders(filter_key: str | None) -> list[sqlite3.Row]:
    """Reminders matching ``filter_key``, newest-due first. Boundaries are UTC, ``<=`` inclusive:

      today  = due_at ≤ end-of-today (23:59:59.999999 UTC) AND done_at IS NULL.
      week   = due_at ≤ now + 7 days                        AND done_at IS NULL.
      undone = done_at IS NULL (any due).
      all / unknown = everything (lenient — an unknown filter falls back to all).

    The ISO-8601 due_at strings compare lexicographically in UTC order (all stored UTC), so a
    string ``<=`` boundary is a correct time comparison. Returns raw rows; the reader maps +
    fail-opens on a malformed row."""
    init_reminders_tables()
    key = (filter_key or "all").strip().lower()
    now = _now()

    where = ""
    params: tuple = ()
    if key == "today":
        eod = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        where = "WHERE due_at <= ? AND done_at IS NULL"
        params = (eod.isoformat(),)
    elif key == "week":
        wk = now + timedelta(days=7)
        where = "WHERE due_at <= ? AND done_at IS NULL"
        params = (wk.isoformat(),)
    elif key == "undone":
        where = "WHERE done_at IS NULL"
    # all / unknown → no WHERE (lenient: an unrecognised filter returns everything)

    conn = db.get_conn()
    with _lock:
        return conn.execute(
            f"SELECT {_COLS} FROM reminders {where} ORDER BY due_at DESC, id DESC", params
        ).fetchall()


def canonical_filter(filter_key: str | None) -> str:
    """The filter as applied (an unknown/empty key → 'all', mirroring list_reminders' leniency).
    The reader echoes this so a caller sees which filter actually ran."""
    key = (filter_key or "all").strip().lower()
    return key if key in ("today", "week", "undone", "all") else "all"
