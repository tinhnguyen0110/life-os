"""modules/tracing/store.py — tracing persistence (DAILY-TRACING-P1, #65).

Two module-owned SQLite tables on the shared connection (same init-on-first-use pattern as
reminders/news/macro — NOT in core db.py SCHEMA, kept module-scoped):
  - ``tracing_activities`` — habit defs (id slug PK, goal, archive flag).
  - ``tracing_logs``       — raw sessions (time-series; the derive source). Index (activity_id, date).

Defs are structured + logs are time-series/derive-heavy → SQLite, not md_store (md is for
git-versioned prose). Single-user; a module-level lock serialises writes on the shared connection.
"""

from __future__ import annotations

import sqlite3
import threading

from store import db

_lock = threading.Lock()

TRACING_SCHEMA = """
CREATE TABLE IF NOT EXISTS tracing_activities (
    id        TEXT    PRIMARY KEY,          -- caller-chosen stable slug, e.g. 'run'
    name      TEXT    NOT NULL,
    emoji     TEXT    NOT NULL DEFAULT '',
    icon      TEXT    NOT NULL DEFAULT '',
    unit      TEXT    NOT NULL DEFAULT '',
    goal      REAL    NOT NULL DEFAULT 0,
    color     TEXT    NOT NULL DEFAULT '',
    created   TEXT    NOT NULL,
    archived  INTEGER NOT NULL DEFAULT 0,
    remind_at     TEXT,                          -- TRACING-REMINDERS (#75): HH:MM VN, or NULL
    remind_repeat TEXT NOT NULL DEFAULT 'off'    -- (#75) daily | weekdays | off
);
CREATE TABLE IF NOT EXISTS tracing_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id TEXT    NOT NULL,           -- FK → tracing_activities.id (not enforced; single-user)
    date        TEXT    NOT NULL,           -- YYYY-MM-DD, VN-day bucket
    ts          TEXT    NOT NULL,           -- ISO-8601 of the session
    val         REAL    NOT NULL,           -- measured value in the activity's unit
    dur_min     INTEGER,                    -- session duration in minutes, or NULL
    note        TEXT                        -- optional session note
);
CREATE INDEX IF NOT EXISTS idx_tracing_logs_act_date ON tracing_logs(activity_id, date);
CREATE TABLE IF NOT EXISTS tracing_template (
    id      TEXT    PRIMARY KEY,           -- template slug (matches a seed id to OVERRIDE it, or new)
    name    TEXT    NOT NULL DEFAULT '',
    emoji   TEXT    NOT NULL DEFAULT '',
    icon    TEXT    NOT NULL DEFAULT '',
    unit    TEXT    NOT NULL DEFAULT '',
    goal    REAL    NOT NULL DEFAULT 0,
    color   TEXT    NOT NULL DEFAULT '',
    hidden  INTEGER NOT NULL DEFAULT 0      -- #109 tombstone: 1 = this id (a seed) is hidden from the list
);
"""

_ACT_COLS = ("id, name, emoji, icon, unit, goal, color, created, archived, "
             "remind_at, remind_repeat")  # TRACING-REMINDERS (#75): +remind_at, +remind_repeat
_LOG_COLS = "id, activity_id, date, ts, val, dur_min, note"
_TPL_COLS = "id, name, emoji, icon, unit, goal, color, hidden"  # #109 template override row


def init_tracing_tables() -> sqlite3.Connection:
    """Register the tracing tables on the shared connection. Idempotent; safe after a test
    rebinds ``db.DB_PATH`` (each store fn calls this first, like reminders).

    TRACING-REMINDERS (#75) migration: add remind_at/remind_repeat to a pre-#75 table (idempotent)."""
    conn = db.get_conn()
    with _lock:
        conn.executescript(TRACING_SCHEMA)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(tracing_activities)").fetchall()}
        if "remind_at" not in cols:
            conn.execute("ALTER TABLE tracing_activities ADD COLUMN remind_at TEXT")
        if "remind_repeat" not in cols:
            conn.execute("ALTER TABLE tracing_activities ADD COLUMN remind_repeat TEXT NOT NULL DEFAULT 'off'")
        conn.commit()
    return conn


# --------------------------------------------------------------------------- #
# Activity defs                                                                 #
# --------------------------------------------------------------------------- #
def get_activity(activity_id: str) -> sqlite3.Row | None:
    """One activity def by id (incl. archived), or None if absent."""
    init_tracing_tables()
    conn = db.get_conn()
    with _lock:
        return conn.execute(
            f"SELECT {_ACT_COLS} FROM tracing_activities WHERE id = ?", (activity_id,)
        ).fetchone()


def list_activities(include_archived: bool = False) -> list[sqlite3.Row]:
    """All activity defs, created-order. Excludes archived unless ``include_archived``."""
    init_tracing_tables()
    conn = db.get_conn()
    where = "" if include_archived else "WHERE archived = 0"
    with _lock:
        return conn.execute(
            f"SELECT {_ACT_COLS} FROM tracing_activities {where} ORDER BY created ASC, id ASC"
        ).fetchall()


def create_activity(*, id: str, name: str, emoji: str, icon: str, unit: str, goal: float,
                    color: str, created: str, remind_at: str | None = None,
                    remind_repeat: str = "off") -> None:
    """Insert an activity def. Raises sqlite3.IntegrityError on a duplicate id (caller maps → 409)."""
    init_tracing_tables()
    conn = db.get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO tracing_activities(id, name, emoji, icon, unit, goal, color, created, "
            "archived, remind_at, remind_repeat) VALUES (?,?,?,?,?,?,?,?,0,?,?)",
            (id, name, emoji, icon, unit, goal, color, created, remind_at, remind_repeat),
        )
        conn.commit()


def update_activity(activity_id: str, fields: dict) -> bool:
    """Update the supplied columns of an activity def. Returns False if no such row. ``fields``
    keys are a trusted subset of the column names (the service builds it from the validated input)."""
    init_tracing_tables()
    if not fields:
        return get_activity(activity_id) is not None
    cols = ", ".join(f"{k} = ?" for k in fields)
    params = list(fields.values()) + [activity_id]
    conn = db.get_conn()
    with _lock:
        cur = conn.execute(
            f"UPDATE tracing_activities SET {cols} WHERE id = ?", params
        )
        conn.commit()
        return cur.rowcount > 0


def archive_activity(activity_id: str) -> bool:
    """Soft-delete: set archived=1. Returns False if no such row. (DELETE = archive, never a hard
    delete — the logs stay for history; single-user, reversible.)"""
    init_tracing_tables()
    conn = db.get_conn()
    with _lock:
        cur = conn.execute(
            "UPDATE tracing_activities SET archived = 1 WHERE id = ?", (activity_id,)
        )
        conn.commit()
        return cur.rowcount > 0


# --------------------------------------------------------------------------- #
# Logs (raw sessions — the derive source)                                       #
# --------------------------------------------------------------------------- #
def insert_log(*, activity_id: str, date: str, ts: str, val: float,
               dur_min: int | None, note: str | None) -> int:
    """Insert one raw session. Returns the new log id. Multiple per day accumulate (the service
    sums them at derive time — this just appends the raw row)."""
    init_tracing_tables()
    conn = db.get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO tracing_logs(activity_id, date, ts, val, dur_min, note) "
            "VALUES (?,?,?,?,?,?)",
            (activity_id, date, ts, val, dur_min, note),
        )
        conn.commit()
        lid = cur.lastrowid
        assert lid is not None
        return int(lid)


def logs_for_activity(activity_id: str, *, since_date: str | None = None) -> list[sqlite3.Row]:
    """Raw sessions for one activity, oldest→newest (by ts). Optional ``since_date`` (inclusive,
    YYYY-MM-DD) windows to recent days (the 12-week derive only needs the last 84 days)."""
    init_tracing_tables()
    conn = db.get_conn()
    where = "WHERE activity_id = ?"
    params: list = [activity_id]
    if since_date is not None:
        where += " AND date >= ?"
        params.append(since_date)
    with _lock:
        return conn.execute(
            f"SELECT {_LOG_COLS} FROM tracing_logs {where} ORDER BY ts ASC, id ASC", params
        ).fetchall()


def logs_since(since_date: str) -> list[sqlite3.Row]:
    """ALL sessions on/after ``since_date`` (YYYY-MM-DD), across every activity — the heatmap's
    derive source (it needs all activities' daily sums together). Oldest→newest."""
    init_tracing_tables()
    conn = db.get_conn()
    with _lock:
        return conn.execute(
            f"SELECT {_LOG_COLS} FROM tracing_logs WHERE date >= ? ORDER BY ts ASC, id ASC",
            (since_date,),
        ).fetchall()


# --------------------------------------------------------------------------- #
# TRACING-UX T1 (#109): task-template OVERRIDE rows (the user layer; SEED lives  #
# in service.py as immutable code). The merge SEED ⊕ OVERRIDE happens in service.#
# Every fn is SCOPED to tracing_template — NEVER touches tracing_activities/logs #
# (the #72 scoped-delete lesson: a template reset must not wipe real activities). #
# --------------------------------------------------------------------------- #
def list_template_overrides() -> list[sqlite3.Row]:
    """All user override rows (incl. tombstones, hidden=1). The service merges these onto the seed."""
    init_tracing_tables()
    conn = db.get_conn()
    with _lock:
        return conn.execute(
            f"SELECT {_TPL_COLS} FROM tracing_template ORDER BY id ASC"
        ).fetchall()


def upsert_template(*, id: str, name: str, emoji: str, icon: str, unit: str,
                    goal: float, color: str) -> None:
    """Insert-or-replace a user template override (hidden reset to 0 — upserting un-hides a
    previously-tombstoned seed). Caller validated the payload (→ 422 before here)."""
    init_tracing_tables()
    conn = db.get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO tracing_template(id, name, emoji, icon, unit, goal, color, hidden) "
            "VALUES (?,?,?,?,?,?,?,0) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, emoji=excluded.emoji, "
            "icon=excluded.icon, unit=excluded.unit, goal=excluded.goal, color=excluded.color, "
            "hidden=0",
            (id, name, emoji, icon, unit, goal, color),
        )
        conn.commit()


def tombstone_template(id: str) -> None:
    """Mark a SEED id hidden (a tombstone override: a row with hidden=1). Idempotent — upserts the
    flag. Used when the user deletes a seed (the seed lives in code, so we record a hide-marker)."""
    init_tracing_tables()
    conn = db.get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO tracing_template(id, name, hidden) VALUES (?, '', 1) "
            "ON CONFLICT(id) DO UPDATE SET hidden=1",
            (id,),
        )
        conn.commit()


def delete_template_override(id: str) -> bool:
    """Remove a user template override row entirely (used to delete a user-created template). Returns
    True if a row was removed. (A SEED has no row → False; the router routes a seed-delete to
    tombstone_template instead.) SCOPED to tracing_template."""
    init_tracing_tables()
    conn = db.get_conn()
    with _lock:
        cur = conn.execute("DELETE FROM tracing_template WHERE id = ?", (id,))
        conn.commit()
        return cur.rowcount > 0


def reset_templates() -> int:
    """RESET: delete ALL override rows → the list returns to pure SEED. Returns the count deleted.
    🔴 SCOPED: ``DELETE FROM tracing_template`` ONLY — NEVER touches tracing_activities / tracing_logs
    (the #72 blanket-delete lesson: resetting templates must not wipe the user's real habits/logs)."""
    init_tracing_tables()
    conn = db.get_conn()
    with _lock:
        cur = conn.execute("DELETE FROM tracing_template")
        conn.commit()
        return cur.rowcount
