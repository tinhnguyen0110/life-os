"""modules/wiki/store/fts.py — W1c FTS5 full-text index (C1/C2).

A plain fts5 table synced DELETE+INSERT per write (rowid = note id). Search +
unlinked-mentions phrase-match, with user input sanitized so a stray FTS5 operator
never raises a 500."""

from __future__ import annotations

import sqlite3
from typing import Any

from store import db

from ._base import _lock, logger


def fts_upsert(note_id: int, *, title: str, body: str, aliases: list[str],
               tags: list[str]) -> None:
    """Sync a note's FTS row: DELETE the old rowid then INSERT fresh (C1). Called
    in the writer's cache-update step. rowid = note id."""
    conn = db.get_conn()
    with _lock:
        conn.execute("DELETE FROM notes_fts WHERE rowid = ?", (int(note_id),))
        conn.execute(
            "INSERT INTO notes_fts (rowid, title, body, aliases, tags) VALUES (?,?,?,?,?)",
            (int(note_id), title or "", body or "", " ".join(aliases or []),
             " ".join(tags or [])),
        )
        conn.commit()


def fts_delete(note_id: int) -> None:
    """Drop a note's FTS row (on delete/merge)."""
    conn = db.get_conn()
    with _lock:
        conn.execute("DELETE FROM notes_fts WHERE rowid = ?", (int(note_id),))
        conn.commit()


def _sanitize_fts_query(q: str) -> str:
    """Turn arbitrary user input into a safe FTS5 MATCH expression. FTS5 query
    syntax throws on stray operators/quotes/parens — so we extract word tokens and
    OR them as prefix terms. Empty result → caller returns []. NEVER raises."""
    import re as _re
    # Keep alphanumerics + unicode word chars; split on everything else.
    tokens = _re.findall(r"\w+", q or "", flags=_re.UNICODE)
    if not tokens:
        return ""
    # Quote each token (so it can't be an operator) + prefix-match for usability.
    return " OR ".join(f'"{t}"*' for t in tokens)


def fts_search(q: str, limit: int = 30, folder: str | None = None) -> list[sqlite3.Row]:
    """Full-text search → rows ``{id, title, status, folder, snippet, score}`` ranked by FTS5
    rank. WIKI-RETRIEVAL-2 (#22): +folder (for the ranked result) + ``score`` = the FTS5 ``rank``
    (bm25; MORE NEGATIVE = MORE relevant — surfaced raw so the agent sees WHY a result ranked).
    Query is sanitized (bad input → [] , never a 500). Empty q → [].

    #101 folder-scope (insight #83 — a FILTER, NOT a block): ``folder`` (non-empty) scopes to that
    folder AND its subtree (`n.folder = folder OR n.folder LIKE folder/%`); ``folder`` None/'' → whole
    vault (the unchanged default). The folder is a SQL PARAM (parameterized — FTS-special chars safe;
    the MATCH ``q`` is sanitized separately). A nonexistent folder → the LIKE matches nothing → []."""
    match = _sanitize_fts_query(q)
    if not match:
        return []
    conn = db.get_conn()
    # FTS5 requires the MATCH constraint; the optional folder clause is ANDed AFTER it.
    sql = (
        "SELECT f.rowid AS id, n.title AS title, n.status AS status, n.folder AS folder, "
        "snippet(notes_fts, 1, '<b>', '</b>', '…', 12) AS snippet, rank AS score "
        "FROM notes_fts f JOIN wiki_notes n ON n.id = f.rowid "
        "WHERE notes_fts MATCH ?"
    )
    params: list[Any] = [match]
    scope = (folder or "").strip()
    if scope:  # #101: folder + subtree; empty → no clause (whole vault, the default)
        sql += " AND (n.folder = ? OR n.folder LIKE ?)"
        params += [scope, scope + "/%"]
    sql += " ORDER BY rank LIMIT ?"
    params.append(int(limit))
    with _lock:
        try:
            return conn.execute(sql, tuple(params)).fetchall()
        except sqlite3.OperationalError as exc:  # malformed MATCH slipped through
            logger.warning("fts_search fell back on bad query %r: %s", q, exc)
            return []


def fts_phrase_search(phrases: list[str], limit: int = 50) -> list[sqlite3.Row]:
    """Match any of the given quoted PHRASES (title/aliases) → rows ``{id, snippet}``
    (C2 unlinked-mentions). Each phrase is matched as a whole (``"a b c"``) so a
    multi-word title isn't split. Returns rowid + a snippet; caller filters."""
    cleaned = [p.strip().replace('"', " ") for p in phrases if p and p.strip()]
    cleaned = [p for p in cleaned if p]
    if not cleaned:
        return []
    match = " OR ".join(f'"{p}"' for p in cleaned)
    conn = db.get_conn()
    sql = (
        "SELECT f.rowid AS id, "
        "snippet(notes_fts, 1, '<b>', '</b>', '…', 12) AS snippet "
        "FROM notes_fts f WHERE notes_fts MATCH ? ORDER BY rank LIMIT ?"
    )
    with _lock:
        try:
            return conn.execute(sql, (match, int(limit))).fetchall()
        except sqlite3.OperationalError as exc:
            logger.warning("fts_phrase_search fell back on %r: %s", phrases, exc)
            return []
