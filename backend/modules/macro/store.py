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
    source instead of duplicating (idempotent capture).

    DXY-REAL (#15): a ``source == 'mock'`` point is NEVER persisted (early return, no row
    written). Mock is the ABSENCE of real data (the LOCKED S1 rule) — persisting it with a
    today-ts SHADOWS the real (often naturally-lagged) FRED row, freezing the indicator as
    'mock' even after real data returns. A failed fetch now records nothing → the prior real
    point stands; freshness/confidence already brake on staleness honestly. This is the single
    chokepoint covering ALL callers (refresh + the daily snapshot). Cold-start DISPLAY still
    shows mock-tagged numbers via the reader fallback in service._indicator_view — that path
    does NOT persist, so it's unaffected by this guard."""
    if source == "mock":
        return
    conn = db.get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO macro_history(indicator, value, ts, source) VALUES (?,?,?,?) "
            "ON CONFLICT(indicator, ts) DO UPDATE SET value=excluded.value, source=excluded.source",
            (indicator, float(value), ts, source),
        )
        conn.commit()


def purge_mock() -> int:
    """One-shot cleanup: DELETE every row whose ``source = 'mock'`` from macro_history.
    Returns the number of rows removed.

    DXY-REAL (#15): historical mock rows (persisted before the record_point guard) can SHADOW a
    real FRED row when their today-ts > the real (naturally-lagged) ts — so the overview shows
    'mock' even though real data exists. This removes ONLY those mock rows; real ('fred'/'live')
    rows are untouched (exact source match). Idempotent — once clean, a re-run deletes 0. NOT a
    startup hook; a re-runnable helper invoked once against the live store after the fix lands."""
    conn = db.get_conn()
    with _lock:
        cur = conn.execute("DELETE FROM macro_history WHERE source = 'mock'")
        conn.commit()
        return int(cur.rowcount)


def count_by_source(source: str) -> int:
    """How many rows carry the given exact source (e.g. 'fred'/'mock'). Used to prove a purge
    removed ONLY mock rows (the real-row count must be unchanged before/after)."""
    conn = db.get_conn()
    with _lock:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM macro_history WHERE source = ?", (source,)
        ).fetchone()
    return int(row["c"]) if row else 0


def count_all() -> int:
    """Total rows in macro_history (across all indicators/sources). For purge before/after deltas."""
    conn = db.get_conn()
    with _lock:
        row = conn.execute("SELECT COUNT(*) AS c FROM macro_history").fetchone()
    return int(row["c"]) if row else 0


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
