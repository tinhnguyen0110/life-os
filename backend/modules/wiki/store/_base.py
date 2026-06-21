"""modules/wiki/store/_base.py — shared store primitives.

The wiki store was one 759-LOC module; it is now a package split by responsibility
(notes / oplog / files / aliases / links / fts / queries). This base module holds
the pieces every submodule shares so the split changes NO behavior:

  - the module-level ``_lock`` (one lock for the whole wiki store, exactly as
    before — every submodule imports THIS lock, they do not each make their own)
  - the SQLite cache schema + ``init_wiki_tables`` / ``_migrate``
  - md+git path helpers + the integer-id source of truth

See the package ``__init__`` for the full design note. The two-store model
(md+git = source of truth, SQLite = disposable cache) is unchanged.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

from core.config import settings
from store import db

logger = logging.getLogger("life-os.wiki.store")

# Guards cache statements on the shared db connection. The single-writer queue
# already serializes writes; this protects the read path against the scheduler
# thread sharing the same sqlite3.Connection. ONE lock for the whole wiki store —
# every submodule imports this exact object (not a per-module lock).
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
    updated       TEXT    NOT NULL,             -- ISO-8601 UTC
    capture_source TEXT   NOT NULL DEFAULT 'quick_add', -- C5 inbox (W1c)
    folder        TEXT    NOT NULL DEFAULT '',  -- W-Explorer virtual path; ''=root
    deleted_at    TEXT                          -- #94 SOFT-delete tombstone (NULL=live, ISO ts=deleted)
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

-- wiki_links: the typed concept-edge graph (B1/B2). One row per outbound link
-- from source_id. Re-derived from the note body on EVERY write (delete this
-- source's rows + insert fresh). A resolved link has target_id set + is_resolved
-- =1; a ghost link ([[Title]] with no matching note) has target_id NULL +
-- target_title set + is_resolved=0 (W1b-T2 auto-resolves it when the target is
-- created). type defaults 'relates' (NOT parsed from body — set via API later).
CREATE TABLE IF NOT EXISTS wiki_links (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id     INTEGER NOT NULL,
    target_id     INTEGER,                          -- NULL for a ghost link
    target_title  TEXT,                             -- set for a ghost link
    type          TEXT    NOT NULL DEFAULT 'relates',
    is_resolved   INTEGER NOT NULL DEFAULT 0,
    display       TEXT                              -- the [[id|display]] label, if any
);
CREATE INDEX IF NOT EXISTS idx_wiki_links_source ON wiki_links(source_id);
CREATE INDEX IF NOT EXISTS idx_wiki_links_target ON wiki_links(target_id);
CREATE INDEX IF NOT EXISTS idx_wiki_links_ghost ON wiki_links(target_title);

-- wiki_redirects: D6 ID-redirect tombstones. A merge (source→target) writes
-- (old_id=source, new_id=target). GET on a tombstoned id follows the redirect to
-- the live target (a cited-then-merged note never 404s). Chained old→mid→new is
-- followed transitively (depth-capped in the reader).
CREATE TABLE IF NOT EXISTS wiki_redirects (
    old_id   INTEGER PRIMARY KEY,   -- the merged-away (now-deleted) note id
    new_id   INTEGER NOT NULL,      -- where it redirects to
    created  TEXT    NOT NULL       -- ISO-8601 UTC
);

-- wiki_folder_meta: WIKI-RETRIEVAL-1 (#20) — a light KV of per-folder descriptions, so an agent
-- navigating the tree (like `ls`) knows what a folder holds without reading note bodies. A folder
-- with NO row → meta:null in the tree (honest-mirror, NEVER a fabricated desc). Single-purpose
-- (folder_path PK + desc); chosen over a readme/_folder-note convention to avoid body-parsing +
-- "which note is the readme" ambiguity (decide-and-log, no-overengineering). Start with ONLY desc.
CREATE TABLE IF NOT EXISTS wiki_folder_meta (
    folder_path  TEXT    PRIMARY KEY,   -- the W-Explorer virtual path (e.g. 'A/B'); '' = root
    desc         TEXT    NOT NULL,      -- human/agent description of what the folder holds
    updated      TEXT    NOT NULL       -- ISO-8601 UTC
);

-- notes_fts: FTS5 full-text index (C1). A PLAIN fts5 table (NOT content='') —
-- contentless can't produce snippet()/rank, which search + unlinked-mentions
-- require (verified on disk). It stores its own copy of the indexed text, which
-- is fine: like the rest of the SQLite side, it's a DISPOSABLE cache rebuildable
-- from the md files (md = source of truth). rowid = note id; synced DELETE+INSERT
-- in the writer's cache-update step; DELETE on delete/merge. (Architect flagged
-- (A) plain-fts5 over (B) contentless+manual-snippet; (A) shipped.)
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(title, body, aliases, tags);
"""


def init_wiki_tables() -> sqlite3.Connection:
    """Register wiki tables on the shared connection. Idempotent; safe at import
    and re-callable after a test rebinds ``db.DB_PATH`` (conftest resets it)."""
    conn = db.get_conn()
    with _lock:
        conn.executescript(WIKI_SCHEMA)
        _migrate(conn)
        conn.commit()
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive idempotent migrations for an EXISTING wiki_notes table that
    pre-dates a column (``CREATE TABLE IF NOT EXISTS`` won't add a column to a
    table that already exists). Each ALTER is guarded by a column check."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(wiki_notes)").fetchall()}
    if "capture_source" not in cols:  # W1c C5
        conn.execute(
            "ALTER TABLE wiki_notes ADD COLUMN capture_source TEXT NOT NULL "
            "DEFAULT 'quick_add'"
        )
    if "folder" not in cols:  # W-Explorer — existing notes migrate to ''=root
        conn.execute(
            "ALTER TABLE wiki_notes ADD COLUMN folder TEXT NOT NULL DEFAULT ''"
        )
    if "deleted_at" not in cols:  # #94 SOFT-delete — NULL = live; an ISO ts = soft-deleted (tombstone)
        conn.execute(
            "ALTER TABLE wiki_notes ADD COLUMN deleted_at TEXT"  # nullable; existing notes → NULL (live)
        )


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
