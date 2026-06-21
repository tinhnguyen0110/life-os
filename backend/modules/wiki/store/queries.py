"""modules/wiki/store/queries.py — W1c graph + overview aggregate queries (C3/C4/C5).

Read-only roll-ups over wiki_notes + wiki_links: counts, the inbox (fleeting),
degree/neighbors/edges for the graph view + cluster detection, and the link-count
helpers behind the refine ≥1-link gate."""

from __future__ import annotations

import sqlite3

from store import db

from ._base import _lock


def all_notes(order_by: str = "id") -> list[sqlite3.Row]:
    """All live note cache rows. ``order_by`` ∈ {id, created} (validated)."""
    col = "created" if order_by == "created" else "id"
    conn = db.get_conn()
    with _lock:
        return conn.execute(
            f"SELECT * FROM wiki_notes ORDER BY {col} ASC"  # noqa: S608 (col whitelisted)
        ).fetchall()


def count_notes() -> int:
    conn = db.get_conn()
    with _lock:
        return int(conn.execute("SELECT COUNT(*) AS c FROM wiki_notes").fetchone()["c"])


def count_by_status() -> dict[str, int]:
    """``{status: count}`` over live notes."""
    conn = db.get_conn()
    with _lock:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS c FROM wiki_notes GROUP BY status"
        ).fetchall()
    return {r["status"]: int(r["c"]) for r in rows}


def count_resolved_links() -> int:
    conn = db.get_conn()
    with _lock:
        return int(conn.execute(
            "SELECT COUNT(*) AS c FROM wiki_links WHERE is_resolved = 1"
        ).fetchone()["c"])


def count_ghost_links() -> int:
    conn = db.get_conn()
    with _lock:
        return int(conn.execute(
            "SELECT COUNT(*) AS c FROM wiki_links WHERE is_resolved = 0"
        ).fetchone()["c"])


def note_ids_with_resolved_link() -> set[int]:
    """Ids of notes touching ≥1 RESOLVED edge (as source OR target). Used for
    orphan detection + pctWithLink."""
    conn = db.get_conn()
    with _lock:
        rows = conn.execute(
            "SELECT source_id AS nid FROM wiki_links WHERE is_resolved = 1 "
            "UNION SELECT target_id AS nid FROM wiki_links WHERE is_resolved = 1 "
            "AND target_id IS NOT NULL"
        ).fetchall()
    return {int(r["nid"]) for r in rows if r["nid"] is not None}


def degree(note_id: int) -> int:
    """Total RESOLVED edges touching a note (in + out). Ghost edges don't count
    (a ghost has no real other endpoint)."""
    conn = db.get_conn()
    with _lock:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM wiki_links "
            "WHERE is_resolved = 1 AND (source_id = ? OR target_id = ?)",
            (int(note_id), int(note_id)),
        ).fetchone()
    return int(row["c"])


def resolved_neighbors(note_id: int) -> set[int]:
    """Ids directly connected to ``note_id`` by a resolved edge (either direction)."""
    conn = db.get_conn()
    with _lock:
        rows = conn.execute(
            "SELECT target_id AS nid FROM wiki_links "
            "WHERE is_resolved = 1 AND source_id = ? AND target_id IS NOT NULL "
            "UNION "
            "SELECT source_id AS nid FROM wiki_links "
            "WHERE is_resolved = 1 AND target_id = ?",
            (int(note_id), int(note_id)),
        ).fetchall()
    return {int(r["nid"]) for r in rows}


def edges_among(note_ids: set[int]) -> list[sqlite3.Row]:
    """All resolved edges whose BOTH endpoints are in ``note_ids`` (the ego set).
    Empty set → []."""
    if not note_ids:
        return []
    conn = db.get_conn()
    placeholders = ",".join("?" * len(note_ids))
    ids = [int(i) for i in note_ids]
    sql = (
        f"SELECT source_id, target_id, type, is_resolved FROM wiki_links "
        f"WHERE is_resolved = 1 AND source_id IN ({placeholders}) "
        f"AND target_id IN ({placeholders})"
    )
    with _lock:
        return conn.execute(sql, ids + ids).fetchall()


def all_resolved_edges() -> list[sqlite3.Row]:
    """Every RESOLVED edge in the whole graph as ``{source_id, target_id}`` (W5a
    cluster detection — connected-components over the full edge set). Self-edges
    (source==target) are excluded — they add no connectivity between notes. A note
    with no resolved edge simply doesn't appear (isolated → not in any cluster)."""
    conn = db.get_conn()
    with _lock:
        return conn.execute(
            "SELECT source_id, target_id FROM wiki_links "
            "WHERE is_resolved = 1 AND target_id IS NOT NULL AND source_id != target_id"
        ).fetchall()


def inbound_counts() -> dict[int, int]:
    """WIKI-STALE-DETECTOR (#41): resolved-inbound count per target note, as ``{target_id: count}``,
    in ONE GROUP BY. This is the PERF-correct path for the stale detector (which needs "does each
    note have ≥1 inbound" across the WHOLE vault) — vs calling backlinks(id) per-note, which builds
    per-source snippets (wasted work) + is O(n) queries. Self-edges excluded (no self-inbound)."""
    conn = db.get_conn()
    with _lock:
        rows = conn.execute(
            "SELECT target_id, COUNT(*) AS c FROM wiki_links "
            "WHERE is_resolved = 1 AND target_id IS NOT NULL AND source_id != target_id "
            "GROUP BY target_id"
        ).fetchall()
    return {int(r["target_id"]): int(r["c"]) for r in rows}


def mutual_link_pairs() -> list[tuple[int, int]]:
    """WIKI-STALE-DETECTOR (#41): pairs of notes that link EACH OTHER (A→B AND B→A, both resolved),
    as ordered ``(a, b)`` tuples with a < b (each pair once). A SELF-JOIN of wiki_links against
    itself on the reversed edge. Self-edges excluded. The contradiction-candidate v1 detector reads
    these + checks the two notes' trust tiers for divergence (verified ↔ candidate)."""
    conn = db.get_conn()
    with _lock:
        rows = conn.execute(
            "SELECT DISTINCT l1.source_id AS a, l1.target_id AS b "
            "FROM wiki_links l1 JOIN wiki_links l2 "
            "  ON l1.source_id = l2.target_id AND l1.target_id = l2.source_id "
            "WHERE l1.is_resolved = 1 AND l2.is_resolved = 1 "
            "  AND l1.target_id IS NOT NULL AND l2.target_id IS NOT NULL "
            "  AND l1.source_id < l1.target_id"  # ordered → each mutual pair once
        ).fetchall()
    return [(int(r["a"]), int(r["b"])) for r in rows]


def fleeting_notes() -> list[sqlite3.Row]:
    """Notes with status='fleeting', oldest→newest (the inbox)."""
    conn = db.get_conn()
    with _lock:
        return conn.execute(
            "SELECT * FROM wiki_notes WHERE status = 'fleeting' ORDER BY created ASC, id ASC"
        ).fetchall()


def outbound_link_count(note_id: int) -> int:
    """How many outbound link rows this note has (resolved + ghost)."""
    conn = db.get_conn()
    with _lock:
        return int(conn.execute(
            "SELECT COUNT(*) AS c FROM wiki_links WHERE source_id = ?", (int(note_id),)
        ).fetchone()["c"])


def total_link_count(note_id: int) -> int:
    """Total links touching a note = outbound (from body) + resolved inbound. Used
    by the refine ≥1-link gate (C6)."""
    conn = db.get_conn()
    with _lock:
        out = conn.execute(
            "SELECT COUNT(*) AS c FROM wiki_links WHERE source_id = ?", (int(note_id),)
        ).fetchone()["c"]
        inb = conn.execute(
            "SELECT COUNT(*) AS c FROM wiki_links WHERE is_resolved = 1 AND target_id = ?",
            (int(note_id),),
        ).fetchone()["c"]
    return int(out) + int(inb)
