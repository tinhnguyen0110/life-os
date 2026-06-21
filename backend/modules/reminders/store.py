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
    notified_count   INTEGER NOT NULL DEFAULT 0,       -- (#29) times Discord-notified this period
    last_notified    TEXT,                             -- (#29) ISO of the last notify, else NULL
    done_at          TEXT,                             -- ISO-8601 when ticked, else NULL
    created          TEXT    NOT NULL,                 -- ISO-8601 created
    source           TEXT    NOT NULL DEFAULT 'manual', -- TRACING-REMINDERS (#75): manual | tracing
    activity_id      TEXT,                             -- (#75) the tracing activity id when source=tracing
    mail_escalated   INTEGER NOT NULL DEFAULT 0        -- #51: 1 = overdue-past-cap high/mail fired once (spam-proof)
);
CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(due_at);
CREATE INDEX IF NOT EXISTS idx_reminders_done ON reminders(done_at);
"""
# NOTE the activity_id index is created in init AFTER the ALTER migration (a pre-#75 table won't have
# the column when executescript runs, so the index can't be in the schema-script — it would crash on
# an existing table: "no such column activity_id"). Created post-migration below.

# The columns selected for a Reminder row (stable order; reader maps these to the model).
# REMINDERS-3 (#29): +last_notified. TRACING-REMINDERS (#75): +source, +activity_id.
_COLS = ("id, title, note, due_at, repeat, re_notify_every, max_times, "
         "notified_count, last_notified, done_at, created, source, activity_id, "
         "mail_escalated")  # #51


def init_reminders_tables() -> sqlite3.Connection:
    """Register the reminders table on the shared connection. Idempotent; safe to call
    repeatedly and after a test rebinds ``db.DB_PATH``.

    REMINDERS-3 (#29) migration: CREATE TABLE IF NOT EXISTS won't add ``last_notified`` to a
    pre-#29 table, so ALTER it in when missing (idempotent — only adds if absent). Keeps an
    existing live store working after the field landed."""
    conn = db.get_conn()
    with _lock:
        conn.executescript(REMINDERS_SCHEMA)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(reminders)").fetchall()}
        if "last_notified" not in cols:
            conn.execute("ALTER TABLE reminders ADD COLUMN last_notified TEXT")
        # TRACING-REMINDERS (#75) migration: add source/activity_id to a pre-#75 table (idempotent).
        if "source" not in cols:
            conn.execute("ALTER TABLE reminders ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'")
        if "activity_id" not in cols:
            conn.execute("ALTER TABLE reminders ADD COLUMN activity_id TEXT")
        if "mail_escalated" not in cols:  # #51 — overdue-past-cap high/mail escalation flag (spam-proof)
            conn.execute("ALTER TABLE reminders ADD COLUMN mail_escalated INTEGER NOT NULL DEFAULT 0")
        # the activity_id index — AFTER the ALTER (the column now exists on both new + migrated tables).
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reminders_activity ON reminders(activity_id, source)")
        conn.commit()
    return conn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_reminder(*, title: str, note: str | None, due_at: str, repeat: str,
                    re_notify_every: int | None, max_times: int | None,
                    created: str, source: str = "manual",
                    activity_id: str | None = None) -> int:
    """Insert a reminder. Returns the new row id. notified_count starts 0, done_at NULL. ``source``
    defaults 'manual' (the user path); the tracing service passes source='tracing'+activity_id (#75)."""
    init_reminders_tables()
    conn = db.get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO reminders(title, note, due_at, repeat, re_notify_every, max_times, "
            "notified_count, done_at, created, source, activity_id) "
            "VALUES (?,?,?,?,?,?,0,NULL,?,?,?)",
            (title, note, due_at, repeat, re_notify_every, max_times, created, source, activity_id),
        )
        conn.commit()
        rid = cur.lastrowid
        assert rid is not None
        return int(rid)


def find_by_activity(activity_id: str, source: str = "tracing") -> sqlite3.Row | None:
    """TRACING-REMINDERS (#75): the linked reminder for an activity (by activity_id + source), or
    None. The upsert key — find-existing before create, so a re-sync updates not duplicates."""
    init_reminders_tables()
    conn = db.get_conn()
    with _lock:
        return conn.execute(
            f"SELECT {_COLS} FROM reminders WHERE activity_id = ? AND source = ? "
            "ORDER BY id ASC LIMIT 1", (activity_id, source),
        ).fetchone()


def update_reminder(reminder_id: int, *, title: str, due_at: str, repeat: str) -> sqlite3.Row | None:
    """TRACING-REMINDERS (#75): update the tracing-linked reminder's title/due_at/repeat (the fields
    the activity drives). Resets the notify counters (a re-synced time = a fresh period). Returns the
    updated row, or None if absent."""
    init_reminders_tables()
    conn = db.get_conn()
    with _lock:
        cur = conn.execute(
            "UPDATE reminders SET title = ?, due_at = ?, repeat = ?, notified_count = 0, "
            "last_notified = NULL WHERE id = ?",
            (title, due_at, repeat, int(reminder_id)),
        )
        conn.commit()
        if cur.rowcount == 0:
            return None
        return conn.execute(
            f"SELECT {_COLS} FROM reminders WHERE id = ?", (int(reminder_id),)
        ).fetchone()


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


# --------------------------------------------------------------------------- #
# REMINDERS-3 (#29) — the notify-engine store helpers                            #
# --------------------------------------------------------------------------- #
def undone_reminders() -> list[sqlite3.Row]:
    """All UN-DONE reminders (done_at IS NULL) — the notify routine's scan set. A ticked reminder
    is excluded (tick-ends-series, SEMANTIC 1). Returns raw rows (the service decides per-row)."""
    init_reminders_tables()
    conn = db.get_conn()
    with _lock:
        return conn.execute(
            f"SELECT {_COLS} FROM reminders WHERE done_at IS NULL ORDER BY due_at ASC, id ASC"
        ).fetchall()


def mark_notified(reminder_id: int, *, notified_count: int, last_notified: str) -> None:
    """Record a fire: set notified_count + last_notified for the reminder (#29)."""
    conn = db.get_conn()
    with _lock:
        conn.execute(
            "UPDATE reminders SET notified_count = ?, last_notified = ? WHERE id = ?",
            (int(notified_count), last_notified, int(reminder_id)),
        )
        conn.commit()


def set_mail_escalated(reminder_id: int) -> None:
    """#51: mark a reminder's overdue-past-cap high/mail escalation as FIRED (spam-proof — it never
    re-fires). SCOPED to the single id (the #72 wipe lesson — never a blanket UPDATE)."""
    conn = db.get_conn()
    with _lock:
        conn.execute(
            "UPDATE reminders SET mail_escalated = 1 WHERE id = ?", (int(reminder_id),)
        )
        conn.commit()


def roll_repeat(reminder_id: int, *, new_due_at: str) -> None:
    """SEMANTIC 1 (roll-on-fire): a repeat reminder fired → roll due_at forward (+period) + RESET
    notified_count=0 + last_notified=NULL so the next period fires fresh. ``once`` never calls this.
    #51: also reset mail_escalated=0 — a fresh period can re-escalate if it goes overdue-past-cap
    (decided + logged: roll resets the escalation flag like it resets notified_count)."""
    conn = db.get_conn()
    with _lock:
        conn.execute(
            "UPDATE reminders SET due_at = ?, notified_count = 0, last_notified = NULL, "
            "mail_escalated = 0 WHERE id = ?",
            (new_due_at, int(reminder_id)),
        )
        conn.commit()
