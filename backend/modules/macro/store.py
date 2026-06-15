"""modules/macro/store.py — macro time-series persistence (MACRO-1).

One append-structured table, ``macro_history``, on the shared SQLite connection (same
pattern as ``price_history`` + the wiki stores). A row = one observation of one macro
indicator: ``(indicator, value, ts, source)``. Idempotent registration; the shared
``_lock`` guards statements against the scheduler thread on the same connection.

Upsert-by-(indicator, ts): re-fetching the same observation date does NOT duplicate the
row — it updates value/source. This keeps the series clean when the daily poller and an
on-demand refresh both see the same latest FRED point.
"""

from __future__ import annotations

import sqlite3
import threading

from store import db

_lock = threading.Lock()

MACRO_SCHEMA = """
CREATE TABLE IF NOT EXISTS macro_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator   TEXT    NOT NULL,              -- fed_funds_rate | cpi | dxy
    value       REAL    NOT NULL,
    ts          TEXT    NOT NULL,              -- ISO-8601 UTC observation date
    source      TEXT    NOT NULL DEFAULT 'fred',
    UNIQUE(indicator, ts)
);
CREATE INDEX IF NOT EXISTS idx_macro_indicator_ts ON macro_history(indicator, ts);
"""


def init_macro_tables() -> sqlite3.Connection:
    """Register the macro_history table on the shared connection. Idempotent;
    re-callable after a test rebinds ``db.DB_PATH``."""
    conn = db.get_conn()
    with _lock:
        conn.executescript(MACRO_SCHEMA)
        conn.commit()
    return conn


def record_point(indicator: str, value: float, ts: str, source: str = "fred") -> None:
    """Upsert one observation. Re-recording the same (indicator, ts) updates the value/
    source instead of duplicating (idempotent capture)."""
    conn = db.get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO macro_history(indicator, value, ts, source) VALUES (?,?,?,?) "
            "ON CONFLICT(indicator, ts) DO UPDATE SET value=excluded.value, source=excluded.source",
            (indicator, float(value), ts, source),
        )
        conn.commit()


def latest(indicator: str) -> sqlite3.Row | None:
    """Most recent observation for an indicator, or None if none stored."""
    conn = db.get_conn()
    with _lock:
        return conn.execute(
            "SELECT indicator, value, ts, source FROM macro_history "
            "WHERE indicator = ? ORDER BY ts DESC LIMIT 1",
            (indicator,),
        ).fetchone()


def recent(indicator: str, limit: int = 2) -> list[sqlite3.Row]:
    """The most recent ``limit`` observations for an indicator, NEWEST first (used to
    derive latest + previous for the trend)."""
    conn = db.get_conn()
    with _lock:
        return conn.execute(
            "SELECT indicator, value, ts, source FROM macro_history "
            "WHERE indicator = ? ORDER BY ts DESC LIMIT ?",
            (indicator, int(limit)),
        ).fetchall()


def history(indicator: str, since: str | None = None, limit: int = 1000) -> list[sqlite3.Row]:
    """Observations for an indicator, OLDEST→newest. ``since`` filters by ts >= since."""
    conn = db.get_conn()
    with _lock:
        if since is not None:
            rows = conn.execute(
                "SELECT indicator, value, ts, source FROM macro_history "
                "WHERE indicator = ? AND ts >= ? ORDER BY ts ASC LIMIT ?",
                (indicator, since, int(limit)),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT indicator, value, ts, source FROM macro_history "
                "WHERE indicator = ? ORDER BY ts ASC LIMIT ?",
                (indicator, int(limit)),
            ).fetchall()
    return rows


def count(indicator: str) -> int:
    """How many observations are stored for an indicator."""
    conn = db.get_conn()
    with _lock:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM macro_history WHERE indicator = ?", (indicator,)
        ).fetchone()
    return int(row["c"]) if row else 0
