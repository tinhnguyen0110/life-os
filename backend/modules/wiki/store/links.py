"""modules/wiki/store/links.py — W1b typed-edge graph (B1/B2) + D6 redirects (B5).

The ``wiki_links`` concept-edge graph: outbound edges re-derived from the note body
on every write, ghost (unresolved) vs resolved edges, ghostify-on-delete and
auto-resolve-on-create, plus the ``wiki_redirects`` merge tombstone chain."""

from __future__ import annotations

import sqlite3
from typing import Any

from store import db

from ._base import _lock


# --------------------------------------------------------------------------- #
# typed-edge graph (B1/B2)                                                      #
# --------------------------------------------------------------------------- #
def replace_links(source_id: int, links: list[dict[str, Any]]) -> None:
    """Re-derive this note's outbound edges: delete its old ``wiki_links`` rows +
    insert the fresh set. Idempotent on every write so edges match the body.

    Each link dict: ``{target_id:int|None, target_title:str|None, type:str,
    is_resolved:bool, display:str|None}``.
    """
    conn = db.get_conn()
    with _lock:
        conn.execute("DELETE FROM wiki_links WHERE source_id = ?", (int(source_id),))
        if links:
            conn.executemany(
                "INSERT INTO wiki_links "
                "(source_id, target_id, target_title, type, is_resolved, display) "
                "VALUES (?,?,?,?,?,?)",
                [
                    (
                        int(source_id),
                        link.get("target_id"),
                        link.get("target_title"),
                        link.get("type", "relates"),
                        1 if link.get("is_resolved") else 0,
                        link.get("display"),
                    )
                    for link in links
                ],
            )
        conn.commit()


def clear_links_from(source_id: int) -> None:
    """Drop this note's outbound edges (on delete/merge of the source)."""
    conn = db.get_conn()
    with _lock:
        conn.execute("DELETE FROM wiki_links WHERE source_id = ?", (int(source_id),))
        conn.commit()


def links_from(source_id: int) -> list[sqlite3.Row]:
    """This note's outbound edges (resolved + ghost), in insertion order."""
    conn = db.get_conn()
    with _lock:
        return conn.execute(
            "SELECT id, source_id, target_id, target_title, type, is_resolved, display "
            "FROM wiki_links WHERE source_id = ? ORDER BY id ASC",
            (int(source_id),),
        ).fetchall()


def links_to(target_id: int, *, resolved_only: bool = True) -> list[sqlite3.Row]:
    """Inbound edges pointing at ``target_id`` (the linked-mentions source). With
    ``resolved_only`` (default) only resolved edges (a ghost has target_id NULL)."""
    conn = db.get_conn()
    sql = (
        "SELECT id, source_id, target_id, target_title, type, is_resolved, display "
        "FROM wiki_links WHERE target_id = ?"
    )
    if resolved_only:
        sql += " AND is_resolved = 1"
    sql += " ORDER BY source_id ASC"
    with _lock:
        return conn.execute(sql, (int(target_id),)).fetchall()


def ghostify_inbound(target_id: int, title: str) -> int:
    """Turn inbound edges pointing at ``target_id`` into ghosts (spec defensive
    case: deleting a note makes inbound links unresolved, NOT dangling). Sets
    ``target_id=NULL``, ``target_title=<the deleted note's title>``, ``is_resolved
    =0`` so a re-created note with that title auto-resolves them (B4). Returns the
    number of edges ghostified. If the deleted note had no title, the edges are
    left for ``replace_links`` on the source's next write to clean up (a ghost
    with an empty title can never auto-resolve)."""
    conn = db.get_conn()
    with _lock:
        cur = conn.execute(
            "UPDATE wiki_links SET target_id = NULL, target_title = ?, is_resolved = 0 "
            "WHERE target_id = ?",
            (title or "", int(target_id)),
        )
        conn.commit()
        return cur.rowcount


def ghost_links_for_title(title: str) -> list[sqlite3.Row]:
    """Unresolved (ghost) edges whose ``target_title`` matches ``title`` (CASE-
    INSENSITIVE). W1b-T2 auto-resolve-on-create flips these to resolved."""
    conn = db.get_conn()
    with _lock:
        return conn.execute(
            "SELECT id, source_id, target_title FROM wiki_links "
            "WHERE target_id IS NULL AND target_title = ? COLLATE NOCASE",
            (title.strip(),),
        ).fetchall()


def resolve_ghosts_to(title: str, note_id: int) -> int:
    """Auto-resolve (B4): flip every ghost edge whose ``target_title`` == ``title``
    (CASE-INSENSITIVE) to resolved → ``target_id = note_id``, ``is_resolved = 1``,
    ``target_title = NULL``. Returns the number of edges resolved. A self-edge
    (source == note_id) is NOT excluded — a note titling itself a prior ghost
    target is a legitimate self-link."""
    if not title or not title.strip():
        return 0
    conn = db.get_conn()
    with _lock:
        cur = conn.execute(
            "UPDATE wiki_links SET target_id = ?, is_resolved = 1, target_title = NULL "
            "WHERE target_id IS NULL AND target_title = ? COLLATE NOCASE",
            (int(note_id), title.strip()),
        )
        conn.commit()
        return cur.rowcount


# --------------------------------------------------------------------------- #
# D6 ID-redirect tombstones (B5)                                               #
# --------------------------------------------------------------------------- #
def add_redirect(old_id: int, new_id: int, created: str) -> None:
    """Write a tombstone (old_id → new_id). Replaces any existing row for old_id."""
    conn = db.get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO wiki_redirects (old_id, new_id, created) VALUES (?,?,?) "
            "ON CONFLICT(old_id) DO UPDATE SET new_id=excluded.new_id, created=excluded.created",
            (int(old_id), int(new_id), created),
        )
        conn.commit()


def get_redirect(old_id: int) -> int | None:
    """The direct redirect target for ``old_id``, or None if it isn't tombstoned."""
    conn = db.get_conn()
    with _lock:
        row = conn.execute(
            "SELECT new_id FROM wiki_redirects WHERE old_id = ?", (int(old_id),)
        ).fetchone()
    return int(row["new_id"]) if row is not None else None


def follow_redirect(note_id: int, max_depth: int = 10) -> tuple[int, bool]:
    """Follow a redirect CHAIN (old→mid→new) to the final live id, depth-capped to
    avoid a cycle hang. Returns ``(final_id, was_redirected)``. ``was_redirected``
    is True iff at least one hop was followed."""
    seen: set[int] = set()
    current = int(note_id)
    redirected = False
    for _ in range(max_depth):
        if current in seen:  # cycle guard
            break
        seen.add(current)
        nxt = get_redirect(current)
        if nxt is None:
            break
        current = nxt
        redirected = True
    return current, redirected


def repoint_inbound_links(old_id: int, new_id: int) -> int:
    """Repoint every inbound edge from ``old_id`` to ``new_id`` (B5 merge). Returns
    the count repointed. Resolved edges stay resolved, now pointing at the target."""
    conn = db.get_conn()
    with _lock:
        cur = conn.execute(
            "UPDATE wiki_links SET target_id = ? WHERE target_id = ?",
            (int(new_id), int(old_id)),
        )
        conn.commit()
        return cur.rowcount
