"""modules/wiki/store/aliases.py — W1b alias index + title resolver (B2).

The (title + each alias) → id mapping that powers ``[[Title]]`` link resolution.
Rebuilt on every write so the index always reflects the live title/aliases."""

from __future__ import annotations

from store import db

from ._base import _lock


def replace_aliases(note_id: int, title: str, aliases: list[str]) -> None:
    """Replace this note's resolver rows in ``wiki_aliases`` with the current
    (title + each alias) → id mappings. Called in the writer's cache-update step
    so the index always reflects the live title/aliases. Empty title is NOT
    indexed (a raw fleeting capture with no title can't be a link target)."""
    conn = db.get_conn()
    with _lock:
        conn.execute("DELETE FROM wiki_aliases WHERE note_id = ?", (int(note_id),))
        rows = [(a, int(note_id)) for a in ({title, *aliases}) if a and a.strip()]
        if rows:
            conn.executemany(
                "INSERT INTO wiki_aliases (alias, note_id) VALUES (?,?)", rows
            )
        conn.commit()


def clear_aliases(note_id: int) -> None:
    """Drop this note's resolver rows (on delete/merge)."""
    conn = db.get_conn()
    with _lock:
        conn.execute("DELETE FROM wiki_aliases WHERE note_id = ?", (int(note_id),))
        conn.commit()


def resolve_title(title: str) -> int | None:
    """Resolve a ``[[Title]]`` (or alias) → note id, CASE-INSENSITIVELY (COLLATE
    NOCASE, B2). On a title/alias collision (two notes share it) → return the
    LOWEST id deterministically (titles SHOULD be unique — Matuschak "titles are
    APIs" — but we don't hard-enforce; the caller logs a warning). None if no
    note matches."""
    if not title or not title.strip():
        return None
    conn = db.get_conn()
    with _lock:
        rows = conn.execute(
            "SELECT DISTINCT note_id FROM wiki_aliases "
            "WHERE alias = ? COLLATE NOCASE ORDER BY note_id ASC",
            (title.strip(),),
        ).fetchall()
    if not rows:
        return None
    return int(rows[0]["note_id"])


def resolve_title_count(title: str) -> int:
    """How many DISTINCT notes resolve for ``title`` (caller warns when >1)."""
    if not title or not title.strip():
        return 0
    conn = db.get_conn()
    with _lock:
        row = conn.execute(
            "SELECT COUNT(DISTINCT note_id) AS c FROM wiki_aliases "
            "WHERE alias = ? COLLATE NOCASE",
            (title.strip(),),
        ).fetchone()
    return int(row["c"])
