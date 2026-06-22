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
    empty-string desc that reads as 'described as nothing').

    🔴 NOTE (#127): this is the DESCRIBE path — a blank desc DELETES the row. To CREATE an
    empty-folder ANCHOR (a row that exists even with no desc), use ``create_folder_meta``."""
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


def create_folder_meta(folder_path: str, desc: str = "") -> bool:
    """#127: INSERT a folder ANCHOR row (the empty-folder model — a folder EXISTS if it has a
    wiki_folder_meta row). Inserts ``desc`` (default '' = anchored but undescribed). Returns True
    if a NEW row was created, False if the folder already had a meta row (idempotent — does NOT
    overwrite an existing desc). Unlike set_folder_meta, a blank desc here still ANCHORS."""
    conn = db.get_conn()
    now = datetime.now(timezone.utc).isoformat()
    d = (desc or "").strip()
    with _lock:
        cur = conn.execute(
            "INSERT INTO wiki_folder_meta(folder_path, desc, updated) VALUES (?,?,?) "
            "ON CONFLICT(folder_path) DO NOTHING",
            (folder_path, d, now),
        )
        conn.commit()
        return cur.rowcount > 0


def delete_folder_meta_subtree(folder_path: str) -> list[str]:
    """#127: DELETE the folder's meta row + ALL descendant meta rows (path == folder_path OR
    startswith folder_path + '/'). SCOPED to exactly that subtree (the #72 lesson — never a blanket).
    Returns the list of folder_paths whose meta rows were removed."""
    conn = db.get_conn()
    like = folder_path + "/%"
    with _lock:
        rows = conn.execute(
            "SELECT folder_path FROM wiki_folder_meta WHERE folder_path = ? OR folder_path LIKE ?",
            (folder_path, like),
        ).fetchall()
        removed = [r["folder_path"] for r in rows]
        conn.execute(
            "DELETE FROM wiki_folder_meta WHERE folder_path = ? OR folder_path LIKE ?",
            (folder_path, like),
        )
        conn.commit()
    return removed


def move_folder_meta(folder_path: str, to_path: str) -> int:
    """#127: re-key the folder's meta row + descendants from the ``folder_path`` prefix → ``to_path``
    (rename/move). path == folder_path → to_path; path startswith folder_path + '/' → to_path + the
    remainder. SCOPED to that subtree. Returns the count of meta rows moved. A target-key collision
    is overwritten (DELETE-old + UPSERT-new; the caller validates ``to`` first)."""
    conn = db.get_conn()
    now = datetime.now(timezone.utc).isoformat()
    like = folder_path + "/%"
    moved = 0
    with _lock:
        rows = conn.execute(
            "SELECT folder_path, desc FROM wiki_folder_meta WHERE folder_path = ? OR folder_path LIKE ?",
            (folder_path, like),
        ).fetchall()
        for r in rows:
            old = r["folder_path"]
            new = to_path if old == folder_path else to_path + old[len(folder_path):]
            conn.execute("DELETE FROM wiki_folder_meta WHERE folder_path = ?", (old,))
            conn.execute(
                "INSERT INTO wiki_folder_meta(folder_path, desc, updated) VALUES (?,?,?) "
                "ON CONFLICT(folder_path) DO UPDATE SET desc=excluded.desc, updated=excluded.updated",
                (new, r["desc"], now),
            )
            moved += 1
        conn.commit()
    return moved
