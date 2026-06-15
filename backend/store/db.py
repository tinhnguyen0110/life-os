"""store/db.py — SQLite time-series store (C5, ARCH §6).

Holds ONLY things queried by time (ARCH §6 — metadata lives in md_store, not here):
  - ``price_history``        — asset price points over time (market/finance)
  - ``run_log``              — routine execution log (automation/activity)
  - ``claude_usage_history`` — claude usage samples over time (claude_usage)

Single-user local file. WAL mode for concurrent read during a write. Schema is
created idempotently on first connect (``init_db`` runs at app boot).
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

from core.config import settings

logger = logging.getLogger("life-os.db")

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

# Optional override set by init_db(path) / tests. None → use settings.db_path.
DB_PATH: Path | None = None

# --- Schema (idempotent) ---------------------------------------------------
# All time columns are ISO-8601 UTC strings (sortable lexicographically), kept
# as TEXT for direct readability when an external tool inspects the DB.
SCHEMA = """
CREATE TABLE IF NOT EXISTS price_history (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    asset     TEXT    NOT NULL,
    price     REAL    NOT NULL,
    currency  TEXT    NOT NULL DEFAULT 'USD',
    source    TEXT,
    ts        TEXT    NOT NULL          -- ISO-8601 UTC
);
CREATE INDEX IF NOT EXISTS idx_price_asset_ts ON price_history(asset, ts);

CREATE TABLE IF NOT EXISTS run_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    routine_id  TEXT    NOT NULL,
    status      TEXT    NOT NULL,        -- 'ok' | 'warn' | 'error'
    detail      TEXT,
    started_at  TEXT    NOT NULL,        -- ISO-8601 UTC
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_runlog_routine_ts ON run_log(routine_id, started_at);

CREATE TABLE IF NOT EXISTS claude_usage_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT    NOT NULL,      -- ISO-8601 UTC (sample time)
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd      REAL    NOT NULL DEFAULT 0,
    model         TEXT,
    source        TEXT
);
CREATE INDEX IF NOT EXISTS idx_usage_ts ON claude_usage_history(ts);

-- Portfolio equity snapshots — one row per UTC DAY (day is the PK so re-snapshotting
-- a day upserts: the day's value is its latest snapshot = the day's close). A daily
-- equity curve doesn't need intra-day noise; this keeps the series clean + bounded.
CREATE TABLE IF NOT EXISTS portfolio_snapshot (
    day          TEXT    PRIMARY KEY,    -- 'YYYY-MM-DD' (UTC) — one row per day
    ts           TEXT    NOT NULL,       -- full ISO-8601 UTC of the latest snapshot that day
    total_value  REAL    NOT NULL,
    by_channel   TEXT    NOT NULL DEFAULT '{}'  -- JSON {channel: value}
);
CREATE INDEX IF NOT EXISTS idx_snapshot_day ON portfolio_snapshot(day);
"""


def _db_path() -> Path:
    # Precedence: module-level DB_PATH override (set by init_db/tests) → settings.
    return Path(DB_PATH) if DB_PATH is not None else Path(settings.db_path)


def _last_id(cur: sqlite3.Cursor) -> int:
    """Cursor.lastrowid is typed int|None; on our autoincrement INSERTs it is set."""
    rowid = cur.lastrowid
    if rowid is None:  # pragma: no cover - defensive; never happens on INSERT
        raise RuntimeError("INSERT did not yield a lastrowid")
    return int(rowid)


def get_conn() -> sqlite3.Connection:
    """Return the process-wide connection, creating + migrating it on first call.

    ``check_same_thread=False`` because the scheduler thread and request threads
    share one connection guarded by ``_lock``. Row factory yields dict-like rows.
    """
    global _conn
    with _lock:
        if _conn is not None:
            return _conn
        path = _db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.executescript(SCHEMA)
        conn.commit()
        _conn = conn
        logger.info("SQLite ready at %s (WAL)", path)
        return _conn


def init_db(path: Path | str | None = None) -> sqlite3.Connection:
    """Ensure the DB file + schema exist. Safe to call repeatedly (boot hook).

    Args:
        path: optional explicit DB path. When given it becomes the active
              ``DB_PATH`` and any existing connection is rebound to it (lets
              tests target a tmp file). When None, uses ``settings.db_path``.

    Returns the live connection so callers/tests can use it directly.
    """
    global DB_PATH
    if path is not None:
        DB_PATH = Path(path)
        # Drop any stale connection bound to a previous path.
        close_db()
    return get_conn()


def close_db() -> None:
    """Close the shared connection (app shutdown / test teardown)."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


# --- Insert helpers (the three time-series writers) -------------------------
def record_price(asset: str, price: float, ts: str, currency: str = "USD",
                 source: str | None = None) -> int:
    """Insert a price point. Returns the new row id."""
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO price_history(asset, price, currency, source, ts) VALUES (?,?,?,?,?)",
            (asset, float(price), currency, source, ts),
        )
        conn.commit()
        return _last_id(cur)


def latest_price(asset: str) -> sqlite3.Row | None:
    """Most recent price_history row for ``asset``, or None if no points yet."""
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "SELECT asset, price, currency, source, ts FROM price_history "
            "WHERE asset = ? ORDER BY ts DESC, id DESC LIMIT 1",
            (asset,),
        )
        return cur.fetchone()


def prices_for(asset: str, since: str | None = None, limit: int | None = None) -> list[sqlite3.Row]:
    """price_history rows for ``asset``, oldest→newest.

    ``since`` (ISO-8601 UTC) filters to ts >= since; ``limit`` caps the count
    (most-recent ``limit`` rows, still returned oldest→newest).
    """
    conn = get_conn()
    with _lock:
        if limit is not None:
            # Take the most-recent `limit`, then re-sort ascending for the caller.
            sql = ("SELECT asset, price, currency, source, ts FROM price_history "
                   "WHERE asset = ?")
            params: list[object] = [asset]
            if since is not None:
                sql += " AND ts >= ?"
                params.append(since)
            sql += " ORDER BY ts DESC, id DESC LIMIT ?"
            params.append(int(limit))
            rows = conn.execute(sql, tuple(params)).fetchall()
            return list(reversed(rows))
        sql = ("SELECT asset, price, currency, source, ts FROM price_history "
               "WHERE asset = ?")
        params = [asset]
        if since is not None:
            sql += " AND ts >= ?"
            params.append(since)
        sql += " ORDER BY ts ASC, id ASC"
        return conn.execute(sql, tuple(params)).fetchall()


def price_at_or_before(asset: str, ts: str) -> sqlite3.Row | None:
    """Latest price_history row for ``asset`` with ts <= the given ts. None if none."""
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "SELECT asset, price, currency, source, ts FROM price_history "
            "WHERE asset = ? AND ts <= ? ORDER BY ts DESC, id DESC LIMIT 1",
            (asset, ts),
        )
        return cur.fetchone()


def clear_prices(asset: str) -> int:
    """Delete ALL price_history rows for ``asset``. Returns the row count removed.

    Test-support / maintenance helper: lets a test guarantee a clean slate for an asset
    regardless of ambient DB state (deterministic point-in-time / nearest assertions),
    and lets an operator drop a polluted symbol. Scoped to one asset — never a blanket wipe."""
    conn = get_conn()
    with _lock:
        cur = conn.execute("DELETE FROM price_history WHERE asset = ?", (asset,))
        conn.commit()
        return cur.rowcount


def price_range(asset: str) -> tuple[str, str] | None:
    """The (earliest_ts, latest_ts) bounds of ``asset``'s price_history, or None if no
    points. Used to tell the caller when a requested ts falls OUTSIDE the owned range."""
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "SELECT MIN(ts) AS lo, MAX(ts) AS hi FROM price_history WHERE asset = ?",
            (asset,),
        )
        row = cur.fetchone()
        if row is None or row["lo"] is None:
            return None
        return row["lo"], row["hi"]


def nearest_price(asset: str, ts: str) -> sqlite3.Row | None:
    """The price_history row for ``asset`` whose ts is CLOSEST to the requested ``ts``
    (either side). None if the asset has no points. Used for point-in-time lookup that
    degrades honestly when ts is outside the owned range (returns the nearest edge, and
    the caller warns). Distance is computed on the ISO-8601 strings via julianday()."""
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "SELECT asset, price, currency, source, ts FROM price_history "
            "WHERE asset = ? ORDER BY ABS(julianday(ts) - julianday(?)) ASC, id ASC LIMIT 1",
            (asset, ts),
        )
        return cur.fetchone()


def price_days(asset: str) -> set[str]:
    """The set of UTC calendar days ('YYYY-MM-DD') that ``asset`` already has at least
    one price point on. Used by the backfill engine to dedup — a day already present is
    NOT re-inserted, so backfill is idempotent (re-running fills only genuine gaps).
    Derived from the ts TEXT prefix (ISO-8601 → first 10 chars = the date)."""
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "SELECT DISTINCT substr(ts, 1, 10) AS day FROM price_history WHERE asset = ?",
            (asset,),
        )
        return {row["day"] for row in cur.fetchall() if row["day"]}


def recent_runs(routine_id: str, limit: int = 50) -> list[sqlite3.Row]:
    """Most-recent run_log rows for ``routine_id`` (newest first). Alert history reads this."""
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "SELECT routine_id, status, detail, started_at, finished_at FROM run_log "
            "WHERE routine_id = ? ORDER BY started_at DESC, id DESC LIMIT ?",
            (routine_id, int(limit)),
        )
        return cur.fetchall()


def all_runs(limit: int = 100) -> list[sqlite3.Row]:
    """Most-recent run_log rows across ALL routines (newest first), capped at ``limit``.

    The activity feed (S10B) reads this — ``recent_runs`` is per-routine, this is the
    cross-routine timeline. Includes ``id`` (the PK) so each run is addressable.
    """
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "SELECT id, routine_id, status, detail, started_at, finished_at FROM run_log "
            "ORDER BY started_at DESC, id DESC LIMIT ?",
            (int(limit),),
        )
        return cur.fetchall()


def run_by_id(run_id: int) -> sqlite3.Row | None:
    """One run_log row by its PK, or None. The activity detail endpoint (S10B) reads this."""
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "SELECT id, routine_id, status, detail, started_at, finished_at FROM run_log "
            "WHERE id = ?",
            (int(run_id),),
        )
        return cur.fetchone()


def record_run(routine_id: str, status: str, started_at: str,
               finished_at: str | None = None, detail: str | None = None) -> int:
    """Insert a routine run-log entry. Returns the new row id."""
    if status not in ("ok", "warn", "error"):
        raise ValueError(f"run_log.status must be ok|warn|error, got {status!r}")
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO run_log(routine_id, status, detail, started_at, finished_at) "
            "VALUES (?,?,?,?,?)",
            (routine_id, status, detail, started_at, finished_at),
        )
        conn.commit()
        return _last_id(cur)


def record_usage(ts: str, input_tokens: int = 0, output_tokens: int = 0,
                 cost_usd: float = 0.0, model: str | None = None,
                 source: str | None = None) -> int:
    """Insert a claude-usage sample. Returns the new row id."""
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO claude_usage_history(ts, input_tokens, output_tokens, cost_usd, "
            "model, source) VALUES (?,?,?,?,?,?)",
            (ts, int(input_tokens), int(output_tokens), float(cost_usd), model, source),
        )
        conn.commit()
        return _last_id(cur)


# --------------------------------------------------------------------------- #
# Portfolio equity snapshots (one row per UTC day; re-snapshot a day → upsert)   #
# --------------------------------------------------------------------------- #
def record_snapshot(ts: str, total_value: float, by_channel: str = "{}") -> str:
    """Upsert a portfolio snapshot for the UTC day of ``ts``. ``ts`` is the full
    ISO-8601 instant; the day (ts[:10]) is the PK, so re-snapshotting the same day
    REPLACES the value (latest = day's close). Returns the day key written."""
    day = ts[:10]
    conn = get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO portfolio_snapshot(day, ts, total_value, by_channel) VALUES (?,?,?,?) "
            "ON CONFLICT(day) DO UPDATE SET ts=excluded.ts, total_value=excluded.total_value, "
            "by_channel=excluded.by_channel",
            (day, ts, float(total_value), by_channel),
        )
        conn.commit()
    return day


def snapshots(since: str | None = None, limit: int | None = None) -> list[sqlite3.Row]:
    """Portfolio snapshot rows, oldest→newest. ``since`` (a 'YYYY-MM-DD' day or ISO
    instant) filters to day >= since[:10]; ``limit`` caps to the most-recent N rows
    (still returned oldest→newest)."""
    conn = get_conn()
    with _lock:
        if limit is not None:
            sql = ("SELECT day, ts, total_value, by_channel FROM portfolio_snapshot "
                   + ("WHERE day >= ? " if since else "")
                   + "ORDER BY day DESC LIMIT ?")
            params: tuple = (since[:10], int(limit)) if since else (int(limit),)
            rows = conn.execute(sql, params).fetchall()
            return list(reversed(rows))
        sql = ("SELECT day, ts, total_value, by_channel FROM portfolio_snapshot "
               + ("WHERE day >= ? " if since else "")
               + "ORDER BY day ASC")
        return conn.execute(sql, ((since[:10],) if since else ())).fetchall()
