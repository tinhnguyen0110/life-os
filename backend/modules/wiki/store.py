"""modules/wiki/store.py — wiki two-store layer (Sprint W1a, M1 Wiki Core).

Two stores, per ARCH §6 "files = source of truth, index = disposable cache":

  - **md+git** (``store/md_store.py``) — the note files ``wiki/notes/<id>.md``
    (frontmatter + body). Source of truth, portable, every write = 1 git commit.
  - **SQLite cache** (the shared ``store/db.py`` connection) — rebuildable index:
      * ``wiki_notes``  — one row per live note (the queryable cache + id source)
      * ``wiki_op_log`` — append-only episodic/replay log (A3): every mutation,
                          in apply order. NOT git history (git mixes commits +
                          isn't replay-structured — spec open-decision).

Wiki tables register idempotently on the shared connection at module import
(mirrors the time-series ``CREATE TABLE IF NOT EXISTS`` pattern in db.py). Keeping
ONE DB file + connection (vs a second wiki.db) is the simpler call — the
single-writer queue (service.py) serializes all wiki writes, so a wiki-local lock
here only guards the brief cache reads/writes against the scheduler thread.

ID generation (A1): ``next_note_id()`` = ``MAX(id)+1`` — collision-free because it
runs INSIDE the single writer (serialized). One machine, no UUID needed (D1).
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

from core.config import settings
from store import db, md_store

logger = logging.getLogger("life-os.wiki.store")

# Guards cache statements on the shared db connection. The single-writer queue
# already serializes writes; this protects the read path against the scheduler
# thread sharing the same sqlite3.Connection.
_lock = threading.Lock()

# --- Wiki cache schema (idempotent; registered on the shared db connection) --
# wiki_notes: the live-note cache + integer-id source of truth.
# wiki_op_log: append-only replay log (A3) — seq is the monotonic order.
# wiki_aliases: title/alias → id resolver SEAM (addendum c). Empty in W1a — the
#   W1b ghost-link resolver populates it + writes auto-resolve-on-create logic.
#   Standing up the table+index here so W1b plugs in without a schema change.
WIKI_SCHEMA = """
CREATE TABLE IF NOT EXISTS wiki_notes (
    id            INTEGER PRIMARY KEY,          -- integer identity (D1); MAX(id)+1
    title         TEXT    NOT NULL DEFAULT '',
    aliases       TEXT    NOT NULL DEFAULT '[]',-- JSON array
    status        TEXT    NOT NULL DEFAULT 'fleeting',
    note_type     TEXT    NOT NULL DEFAULT 'concept',
    trust_tier    TEXT    NOT NULL DEFAULT 'verified',
    author        TEXT    NOT NULL DEFAULT 'human',
    tags          TEXT    NOT NULL DEFAULT '[]',-- JSON array
    content_hash  TEXT    NOT NULL DEFAULT '',  -- sha256(body); derived cache
    created       TEXT    NOT NULL,             -- ISO-8601 UTC
    updated       TEXT    NOT NULL              -- ISO-8601 UTC
);
-- title→id resolver path (W1b uses this for [[Title]]→id). title is mutable so
-- this is a plain (non-unique) index — collisions are resolved by W1b's logic.
CREATE INDEX IF NOT EXISTS idx_wiki_notes_title ON wiki_notes(title);

CREATE TABLE IF NOT EXISTS wiki_op_log (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,  -- monotonic apply order
    op_id       TEXT    NOT NULL,
    kind        TEXT    NOT NULL,                   -- create | edit | delete (+later)
    note_id     INTEGER,
    actor       TEXT    NOT NULL DEFAULT 'human',
    ts          TEXT    NOT NULL,                   -- ISO-8601 UTC
    commit_sha  TEXT,                               -- md_store commit hash (audit)
    detail      TEXT
);
CREATE INDEX IF NOT EXISTS idx_wiki_oplog_note ON wiki_op_log(note_id, seq);

-- alias→id resolver SEAM (addendum c). Empty in W1a; W1b populates one row per
-- (alias, note_id) so an alias lookup is O(1) instead of a JSON scan over
-- wiki_notes.aliases. note_id is NOT a FK to wiki_notes (the cache is disposable;
-- a stale alias row is cleaned by the reindex/W1b resolver, not enforced here).
CREATE TABLE IF NOT EXISTS wiki_aliases (
    alias    TEXT    NOT NULL,
    note_id  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wiki_aliases_alias ON wiki_aliases(alias);
CREATE INDEX IF NOT EXISTS idx_wiki_aliases_note ON wiki_aliases(note_id);
"""


def init_wiki_tables() -> sqlite3.Connection:
    """Register wiki tables on the shared connection. Idempotent; safe at import
    and re-callable after a test rebinds ``db.DB_PATH`` (conftest resets it)."""
    conn = db.get_conn()
    with _lock:
        conn.executescript(WIKI_SCHEMA)
        conn.commit()
    return conn


# --------------------------------------------------------------------------- #
# md+git path helpers (note files live under DATA_DIR/wiki/notes/<id>.md)        #
# --------------------------------------------------------------------------- #
def note_rel_path(note_id: int) -> str:
    """DATA_DIR-relative path of a note file. Filename = id (immutable, D1)."""
    return f"wiki/notes/{int(note_id)}.md"


def wiki_notes_dir() -> Path:
    """Absolute dir holding wiki note md files."""
    return settings.data_dir / "wiki" / "notes"


# --------------------------------------------------------------------------- #
# Integer-id source of truth (A1)                                              #
# --------------------------------------------------------------------------- #
def next_note_id() -> int:
    """``MAX(id)+1`` over wiki_notes. Collision-free ONLY when called inside the
    single-writer queue (serialized) — never call from a request handler directly."""
    conn = db.get_conn()
    with _lock:
        row = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next FROM wiki_notes").fetchone()
        return int(row["next"])


# --------------------------------------------------------------------------- #
# wiki_notes cache CRUD                                                        #
# --------------------------------------------------------------------------- #
def upsert_note_cache(
    *, note_id: int, title: str, aliases_json: str, status: str, note_type: str,
    trust_tier: str, author: str, tags_json: str, content_hash: str,
    created: str, updated: str,
) -> None:
    """Insert-or-replace the cache row for a note. Called by the single writer
    AFTER the md file is committed (md is source of truth; this is the index)."""
    conn = db.get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO wiki_notes (id, title, aliases, status, note_type, "
            "trust_tier, author, tags, content_hash, created, updated) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "title=excluded.title, aliases=excluded.aliases, status=excluded.status, "
            "note_type=excluded.note_type, trust_tier=excluded.trust_tier, "
            "author=excluded.author, tags=excluded.tags, "
            "content_hash=excluded.content_hash, updated=excluded.updated",
            (note_id, title, aliases_json, status, note_type, trust_tier, author,
             tags_json, content_hash, created, updated),
        )
        conn.commit()


def get_note_cache(note_id: int) -> sqlite3.Row | None:
    """The cache row for a note, or None if absent (hard-deleted / never created)."""
    conn = db.get_conn()
    with _lock:
        return conn.execute(
            "SELECT * FROM wiki_notes WHERE id = ?", (int(note_id),)
        ).fetchone()


def note_cache_exists(note_id: int) -> bool:
    return get_note_cache(note_id) is not None


def delete_note_cache(note_id: int) -> bool:
    """Hard-delete the cache row (A4). op_log retains the historical delete record.
    Returns True if a row was removed."""
    conn = db.get_conn()
    with _lock:
        cur = conn.execute("DELETE FROM wiki_notes WHERE id = ?", (int(note_id),))
        conn.commit()
        return cur.rowcount > 0


# --------------------------------------------------------------------------- #
# op_log append + read (A3)                                                    #
# --------------------------------------------------------------------------- #
def append_op(
    *, op_id: str, kind: str, note_id: int | None, actor: str, ts: str,
    commit_sha: str | None = None, detail: str | None = None,
) -> int:
    """Append one op_log row (append-only — never updated/deleted). Returns seq."""
    conn = db.get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO wiki_op_log (op_id, kind, note_id, actor, ts, commit_sha, detail) "
            "VALUES (?,?,?,?,?,?,?)",
            (op_id, kind, note_id, actor, ts, commit_sha, detail),
        )
        conn.commit()
        seq = cur.lastrowid
        if seq is None:  # pragma: no cover - INSERT always yields a rowid
            raise RuntimeError("op_log INSERT did not yield a seq")
        return int(seq)


def recent_ops(limit: int = 50) -> list[sqlite3.Row]:
    """Most-recent op_log rows (newest first), capped at ``limit``. The reader
    wraps this for the W1 activity feed."""
    conn = db.get_conn()
    with _lock:
        return conn.execute(
            "SELECT seq, op_id, kind, note_id, actor, ts, commit_sha, detail "
            "FROM wiki_op_log ORDER BY seq DESC LIMIT ?",
            (int(limit),),
        ).fetchall()


# --------------------------------------------------------------------------- #
# md file read/write/delete — thin pass-through to md_store (1 commit / write)  #
# --------------------------------------------------------------------------- #
def write_note_file(note_id: int, content: str, message: str) -> str:
    """Write the note md file via md_store (atomic + 1 git commit). Returns sha."""
    return md_store.write_file(note_rel_path(note_id), content, message)


def read_note_file(note_id: int) -> str | None:
    """Raw md file content, or None if the file is absent."""
    return md_store.read(note_rel_path(note_id))


def delete_note_file(note_id: int, message: str) -> str | None:
    """Delete the note md file via md_store (1 commit). Returns sha, or None if
    the file did not exist."""
    return md_store.delete_file(note_rel_path(note_id), message)


# Register tables at import so a fresh process / first request has them ready.
init_wiki_tables()
