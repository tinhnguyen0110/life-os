"""modules/wiki/store/oplog.py — wiki_op_log append + read (A3).

Append-only episodic/replay log: every mutation in apply order. NOT git history
(git mixes commits + isn't replay-structured). Rows are never updated/deleted."""

from __future__ import annotations

import sqlite3

from store import db

from ._base import _lock


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
