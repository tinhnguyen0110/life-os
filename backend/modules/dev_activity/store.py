"""modules/dev_activity/store.py — dev-activity persistence (DEV-TRACING-P1, #63).

One module-owned SQLite table, ``dev_activity``, on the shared connection (same init-on-first-use
pattern as tracing/reminders/news — NOT in core db.py SCHEMA). Time-series per (date × repo ×
source), so SQLite not md. UPSERT per (date, repo, source) → a re-scan is IDEMPOTENT (the scan
re-derives each day's totals from git and overwrites the row, never double-counts). Single-user;
a module-level lock serialises writes on the shared connection.
"""

from __future__ import annotations

import sqlite3
import threading

from store import db

_lock = threading.Lock()

DEV_ACTIVITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS dev_activity (
    date        TEXT    NOT NULL,           -- YYYY-MM-DD, VN-day
    repo        TEXT    NOT NULL,           -- repo basename
    source      TEXT    NOT NULL,           -- 'you' | 'other'
    commits     INTEGER NOT NULL DEFAULT 0,
    loc_added   INTEGER NOT NULL DEFAULT 0, -- LOC_SKIP-filtered (informational)
    loc_deleted INTEGER NOT NULL DEFAULT 0,
    first_ts    TEXT,                        -- earliest commit HH:MM (VN) that day, or NULL
    last_ts     TEXT,                        -- latest commit HH:MM (VN) that day, or NULL
    PRIMARY KEY (date, repo, source)
);
CREATE INDEX IF NOT EXISTS idx_dev_activity_date ON dev_activity(date, repo);
CREATE TABLE IF NOT EXISTS dev_activity_meta (
    key   TEXT PRIMARY KEY,   -- DEV-ACTIVITY-STORE (#77): scan metadata (e.g. 'last_scanned')
    value TEXT
);
"""

_COLS = "date, repo, source, commits, loc_added, loc_deleted, first_ts, last_ts"
_META_LAST_SCANNED = "last_scanned"  # the meta key for the most-recent scan timestamp


def init_dev_activity_tables() -> sqlite3.Connection:
    """Register the dev_activity table on the shared connection. Idempotent; safe after a test
    rebinds ``db.DB_PATH`` (each store fn calls this first, like the sibling modules)."""
    conn = db.get_conn()
    with _lock:
        conn.executescript(DEV_ACTIVITY_SCHEMA)
        conn.commit()
    return conn


def upsert_day(*, date: str, repo: str, source: str, commits: int, loc_added: int,
               loc_deleted: int, first_ts: str | None, last_ts: str | None) -> None:
    """UPSERT one (date, repo, source) aggregate. A re-scan REPLACES the row (idempotent — the
    scan re-derives the full day from git, so overwrite is correct, never accumulate)."""
    init_dev_activity_tables()
    conn = db.get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO dev_activity(date, repo, source, commits, loc_added, loc_deleted, "
            "first_ts, last_ts) VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(date, repo, source) DO UPDATE SET commits=excluded.commits, "
            "loc_added=excluded.loc_added, loc_deleted=excluded.loc_deleted, "
            "first_ts=excluded.first_ts, last_ts=excluded.last_ts",
            (date, repo, source, commits, loc_added, loc_deleted, first_ts, last_ts),
        )
        conn.commit()


def rows_since(since_date: str) -> list[sqlite3.Row]:
    """All aggregate rows on/after ``since_date`` (YYYY-MM-DD), newest-day-first. The reader's
    derive source. Returns raw rows (the reader maps + fail-opens on a malformed row)."""
    init_dev_activity_tables()
    conn = db.get_conn()
    with _lock:
        return conn.execute(
            f"SELECT {_COLS} FROM dev_activity WHERE date >= ? ORDER BY date DESC, repo ASC",
            (since_date,),
        ).fetchall()


def row_count() -> int:
    """Total dev_activity aggregate rows (any date). Lets the reader distinguish never-scanned
    (0 rows + no last_scanned) from scanned-but-no-activity-in-window (#77 honest-empty)."""
    init_dev_activity_tables()
    conn = db.get_conn()
    with _lock:
        return int(conn.execute("SELECT COUNT(*) FROM dev_activity").fetchone()[0])


def set_last_scanned(ts: str) -> None:
    """DEV-ACTIVITY-STORE (#77): record the most-recent scan timestamp (the WRITE path stamps this so
    the read path can surface honest freshness). Idempotent upsert on the meta key."""
    init_dev_activity_tables()
    conn = db.get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO dev_activity_meta(key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (_META_LAST_SCANNED, ts),
        )
        conn.commit()


def get_last_scanned() -> str | None:
    """The most-recent scan timestamp (ISO), or None if never scanned (#77 honest staleness)."""
    init_dev_activity_tables()
    conn = db.get_conn()
    with _lock:
        row = conn.execute(
            "SELECT value FROM dev_activity_meta WHERE key = ?", (_META_LAST_SCANNED,)
        ).fetchone()
    return row["value"] if row is not None else None
