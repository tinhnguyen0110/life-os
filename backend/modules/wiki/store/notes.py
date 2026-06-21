"""modules/wiki/store/notes.py — wiki_notes cache CRUD.

Insert/replace/read/delete the disposable SQLite cache row for a note. Called by
the single writer AFTER the md file is committed (md = source of truth)."""

from __future__ import annotations

import sqlite3

from store import db

from ._base import _lock


def upsert_note_cache(
    *, note_id: int, title: str, aliases_json: str, status: str, note_type: str,
    trust_tier: str, author: str, tags_json: str, content_hash: str,
    created: str, updated: str, capture_source: str = "quick_add",
    folder: str = "",
) -> None:
    """Insert-or-replace the cache row for a note. Called by the single writer
    AFTER the md file is committed (md is source of truth; this is the index).
    ``capture_source`` is set on create and preserved across edits (an edit doesn't
    change where the note was captured) — the writer passes the existing value on
    update. ``folder`` is the W-Explorer virtual path (''=root); a move updates it."""
    conn = db.get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO wiki_notes (id, title, aliases, status, note_type, "
            "trust_tier, author, tags, content_hash, created, updated, capture_source, "
            "folder) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "title=excluded.title, aliases=excluded.aliases, status=excluded.status, "
            "note_type=excluded.note_type, trust_tier=excluded.trust_tier, "
            "author=excluded.author, tags=excluded.tags, "
            "content_hash=excluded.content_hash, updated=excluded.updated, "
            "capture_source=excluded.capture_source, folder=excluded.folder",
            (note_id, title, aliases_json, status, note_type, trust_tier, author,
             tags_json, content_hash, created, updated, capture_source, folder),
        )
        conn.commit()


def set_deleted_at(note_id: int, deleted_at: str | None) -> bool:
    """#94 SOFT-delete: set (or clear, on restore) the cache row's deleted_at tombstone for ONE note.
    SCOPED to the single id (the #72 wipe lesson — never a blanket UPDATE). Returns True if a row was
    updated (the note exists). The .md rewrite (the source of truth) is done by the caller; this keeps
    the cache row in sync so the live queries can exclude/include it."""
    conn = db.get_conn()
    with _lock:
        cur = conn.execute(
            "UPDATE wiki_notes SET deleted_at = ? WHERE id = ?", (deleted_at, int(note_id))
        )
        conn.commit()
        return cur.rowcount > 0


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
