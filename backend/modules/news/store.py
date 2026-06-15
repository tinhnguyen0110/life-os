"""modules/news/store.py — captured-news persistence (NEWS-1).

One module-owned table, ``news_items``, on the shared SQLite connection (same pattern
as ``macro_history`` / ``price_history`` / the wiki stores). A row = one captured
headline. DEDUP is enforced at the DB layer: ``url`` is UNIQUE, so re-capturing the
same story (the poller + an on-demand refresh both see it) is an idempotent upsert,
never a duplicate.

``init_news_tables()`` is idempotent and is called at the top of every public store
fn — so the table exists regardless of boot order or a test rebinding ``db.DB_PATH``
(no main.py wiring needed; self-contained).

Tags are stored as a comma-joined uppercased string and matched with a substring
query bounded by commas (exact-tag match, no false partials).
"""

from __future__ import annotations

import sqlite3
import threading

from store import db

_lock = threading.Lock()

NEWS_SCHEMA = """
CREATE TABLE IF NOT EXISTS news_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL,
    summary      TEXT    NOT NULL DEFAULT '',
    url          TEXT    NOT NULL UNIQUE,          -- dedup anchor (one story, one row)
    source       TEXT    NOT NULL DEFAULT '',
    published_ts TEXT    NOT NULL,                 -- ISO-8601 UTC
    tags         TEXT    NOT NULL DEFAULT '',      -- ",BTC,ETH," padded for exact match
    captured_at  TEXT    NOT NULL                  -- ISO-8601 UTC of capture
);
CREATE INDEX IF NOT EXISTS idx_news_published ON news_items(published_ts);
"""


def init_news_tables() -> sqlite3.Connection:
    """Register the news_items table on the shared connection. Idempotent; safe to
    call repeatedly and after a test rebinds ``db.DB_PATH``."""
    conn = db.get_conn()
    with _lock:
        conn.executescript(NEWS_SCHEMA)
        conn.commit()
    return conn


def _pad_tags(tags: list[str]) -> str:
    """Store tags as ``,A,B,C,`` so an exact-tag query ``tags LIKE '%,BTC,%'`` can't
    partial-match (e.g. 'BTC' must not match a hypothetical 'BTCASH')."""
    clean = [t.strip().upper() for t in tags if t and t.strip()]
    if not clean:
        return ","
    return "," + ",".join(clean) + ","


def _unpad_tags(stored: str) -> list[str]:
    return [t for t in (stored or "").split(",") if t]


def upsert_item(
    *, title: str, summary: str, url: str, source: str, published_ts: str,
    tags: list[str], captured_at: str,
) -> bool:
    """Insert a captured headline; dedup by url. Returns True if a NEW row was inserted,
    False if the url already existed (refreshes title/summary/tags, no dup).

    "New" is detected by an existence check BEFORE the write (inside the same lock, so
    no race) — robust regardless of captured_at collisions within one sweep.
    """
    init_news_tables()
    conn = db.get_conn()
    with _lock:
        existed = conn.execute(
            "SELECT 1 FROM news_items WHERE url = ? LIMIT 1", (url,)
        ).fetchone() is not None
        conn.execute(
            "INSERT INTO news_items(title, summary, url, source, published_ts, tags, captured_at) "
            "VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(url) DO UPDATE SET title=excluded.title, summary=excluded.summary, "
            "tags=excluded.tags, source=excluded.source",
            (title, summary, url, source, published_ts, _pad_tags(tags), captured_at),
        )
        conn.commit()
    return not existed


def list_items(tag: str | None = None, limit: int = 30) -> list[sqlite3.Row]:
    """Captured headlines, NEWEST first (by published_ts). ``tag`` (case-insensitive)
    filters to items carrying that exact tag; unknown tag → []. ``limit`` caps the count."""
    init_news_tables()
    conn = db.get_conn()
    lim = max(1, min(int(limit), 200))
    with _lock:
        if tag and tag.strip():
            needle = f"%,{tag.strip().upper()},%"
            rows = conn.execute(
                "SELECT id, title, summary, url, source, published_ts, tags FROM news_items "
                "WHERE tags LIKE ? ORDER BY published_ts DESC, id DESC LIMIT ?",
                (needle, lim),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, summary, url, source, published_ts, tags FROM news_items "
                "ORDER BY published_ts DESC, id DESC LIMIT ?",
                (lim,),
            ).fetchall()
    return rows


def count_items() -> int:
    init_news_tables()
    conn = db.get_conn()
    with _lock:
        row = conn.execute("SELECT COUNT(*) AS c FROM news_items").fetchone()
    return int(row["c"]) if row else 0


def latest_capture_ts() -> str | None:
    """The most-recent captured_at across all rows, or None if the store is empty."""
    init_news_tables()
    conn = db.get_conn()
    with _lock:
        row = conn.execute(
            "SELECT captured_at FROM news_items ORDER BY captured_at DESC LIMIT 1"
        ).fetchone()
    return row["captured_at"] if row else None
