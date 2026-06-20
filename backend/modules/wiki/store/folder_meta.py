"""modules/wiki/store/folder_meta.py — per-folder description KV (WIKI-RETRIEVAL-1 #20).

A light single-purpose store over ``wiki_folder_meta`` (folder_path PK, desc): so an agent
navigating the W-Explorer tree knows what a folder holds without reading note bodies. A folder
with NO row → no desc (the tree shows meta:null — honest-mirror, never fabricated). Read-only by
default + a set/clear path (the user/agent fills it). Same _lock + shared connection as the rest
of the wiki store."""

from __future__ import annotations

from datetime import datetime, timezone

from store import db

from ._base import _lock


def get_folder_meta(folder_path: str) -> dict | None:
    """The folder's meta ``{desc}`` or None if no row (→ meta:null in the tree). Read-only."""
    conn = db.get_conn()
    with _lock:
        row = conn.execute(
            "SELECT desc FROM wiki_folder_meta WHERE folder_path = ?", (folder_path,)
        ).fetchone()
    return {"desc": row["desc"]} if row is not None else None


def all_folder_meta() -> dict[str, dict]:
    """All folder metas as ``{folder_path: {desc}}`` (one query — the tree builder reads this once
    instead of N per-folder lookups). Empty table → {}."""
    conn = db.get_conn()
    with _lock:
        rows = conn.execute("SELECT folder_path, desc FROM wiki_folder_meta").fetchall()
    return {r["folder_path"]: {"desc": r["desc"]} for r in rows}


def set_folder_meta(folder_path: str, desc: str) -> None:
    """Upsert a folder's description. A blank desc CLEARS the row (no meta = honest-null, vs an
    empty-string desc that reads as 'described as nothing')."""
    conn = db.get_conn()
    now = datetime.now(timezone.utc).isoformat()
    d = (desc or "").strip()
    with _lock:
        if not d:
            conn.execute("DELETE FROM wiki_folder_meta WHERE folder_path = ?", (folder_path,))
        else:
            conn.execute(
                "INSERT INTO wiki_folder_meta(folder_path, desc, updated) VALUES (?,?,?) "
                "ON CONFLICT(folder_path) DO UPDATE SET desc=excluded.desc, updated=excluded.updated",
                (folder_path, d, now),
            )
        conn.commit()
