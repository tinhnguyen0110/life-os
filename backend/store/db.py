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
