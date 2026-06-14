"""modules/wiki/proposals_store.py — proposal queue + MCP audit persistence (W4a).

Two append-structured tables on the shared SQLite connection (same pattern as
``modules/wiki/store.py``):

  - ``wiki_proposals`` — the human-ratified review queue (D-W4.1). One general
    table for every proposal kind (note/link/merge/moc). pending → accepted |
    rejected. Mutations only fire on ACCEPT, via the M1 single-writer (D-W4.2);
    a row here is pure INTENT until then.
  - ``wiki_mcp_audit`` — append-only immutable audit log (D-W4.4). Every MCP call
    (read OR write) appends a row; ``correlation_id`` groups one agent session.
    NEVER updated/deleted (immutable forensics — spec L141).

Idempotent registration at import, mirroring ``store/db.py`` + ``wiki_store``. The
shared ``_lock`` guards statements against the scheduler thread on the same
connection (writes are already serialized by nothing here — proposals are NOT in
the note single-writer queue; they're plain rows. The APPLY of an accepted
proposal IS serialized, because it goes through the note queue).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from typing import Any

from store import db

logger = logging.getLogger("life-os.wiki.proposals_store")

_lock = threading.Lock()

# kind ∈ note_create | note_edit | link_add | link_remove | merge | moc
# status ∈ pending | accepted | rejected
# payload_json = the kind-specific mutation intent (see proposals_schema).
# applied_note_id = the note the apply landed on (created id, or edit/merge target).
PROPOSALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS wiki_proposals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    kind            TEXT    NOT NULL,
    target_id       INTEGER,                       -- the note concerned (NULL for create/moc)
    payload_json    TEXT    NOT NULL DEFAULT '{}', -- kind-specific intent
    rationale       TEXT    NOT NULL DEFAULT '',
    actor           TEXT    NOT NULL DEFAULT 'agent',
    status          TEXT    NOT NULL DEFAULT 'pending',
    correlation_id  TEXT,                          -- groups one agent session (D-W4.4)
    created         TEXT    NOT NULL,              -- ISO-8601 UTC
    decided         TEXT,                          -- set on accept/reject
    decided_by      TEXT,                          -- who ratified
    applied_note_id INTEGER                        -- note the apply landed on
);
CREATE INDEX IF NOT EXISTS idx_wiki_proposals_status ON wiki_proposals(status);
CREATE INDEX IF NOT EXISTS idx_wiki_proposals_corr ON wiki_proposals(correlation_id);

CREATE TABLE IF NOT EXISTS wiki_mcp_audit (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tool            TEXT    NOT NULL,              -- the MCP tool / endpoint called
    params_json     TEXT    NOT NULL DEFAULT '{}',
    actor           TEXT    NOT NULL DEFAULT 'agent',
    correlation_id  TEXT,
    ts              TEXT    NOT NULL               -- ISO-8601 UTC
);
CREATE INDEX IF NOT EXISTS idx_wiki_mcp_audit_corr ON wiki_mcp_audit(correlation_id);
CREATE INDEX IF NOT EXISTS idx_wiki_mcp_audit_ts ON wiki_mcp_audit(ts);
"""


def init_proposal_tables() -> sqlite3.Connection:
    """Register proposal + audit tables on the shared connection. Idempotent;
    re-callable after a test rebinds ``db.DB_PATH`` (conftest resets it)."""
    conn = db.get_conn()
    with _lock:
        conn.executescript(PROPOSALS_SCHEMA)
        conn.commit()
    return conn


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(text: str | None) -> dict[str, Any]:
    """Parse a payload_json/params_json cell → dict (defensive: malformed/NULL →
    {} so a single corrupt row never 500s the whole queue read)."""
    if not text:
        return {}
    try:
        v = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}
    return v if isinstance(v, dict) else {}


# --------------------------------------------------------------------------- #
# wiki_proposals CRUD                                                          #
# --------------------------------------------------------------------------- #
def insert_proposal(
    *, kind: str, target_id: int | None, payload: dict[str, Any], rationale: str,
    actor: str, correlation_id: str | None, created: str,
) -> int:
    """Insert one pending proposal. Returns the new id."""
    conn = db.get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO wiki_proposals "
            "(kind, target_id, payload_json, rationale, actor, status, "
            " correlation_id, created) "
            "VALUES (?,?,?,?,?,'pending',?,?)",
            (kind, target_id, _json(payload), rationale, actor,
             correlation_id, created),
        )
        conn.commit()
        new_id = cur.lastrowid
        if new_id is None:  # pragma: no cover — INSERT always yields a rowid
            raise RuntimeError("proposal INSERT did not yield an id")
        return int(new_id)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Map a wiki_proposals row → the Proposal response dict (camelCase keys,
    payload parsed back to an object)."""
    return {
        "id": int(row["id"]),
        "kind": row["kind"],
        "targetId": row["target_id"],
        "payload": _loads(row["payload_json"]),
        "rationale": row["rationale"] or "",
        "actor": row["actor"] or "agent",
        "status": row["status"],
        "correlationId": row["correlation_id"],
        "created": row["created"],
        "decided": row["decided"],
        "decidedBy": row["decided_by"],
        "appliedNoteId": row["applied_note_id"],
    }


def get_proposal(proposal_id: int) -> dict[str, Any] | None:
    """One proposal as a response dict, or None if absent."""
    conn = db.get_conn()
    with _lock:
        row = conn.execute(
            "SELECT * FROM wiki_proposals WHERE id = ?", (int(proposal_id),)
        ).fetchone()
    return _row_to_dict(row) if row is not None else None


def list_proposals(status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    """Proposals as response dicts, newest first. ``status`` filters when given
    (else all). Unknown status → empty list (the WHERE simply matches nothing)."""
    conn = db.get_conn()
    with _lock:
        if status is None:
            rows = conn.execute(
                "SELECT * FROM wiki_proposals ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM wiki_proposals WHERE status = ? ORDER BY id DESC LIMIT ?",
                (status, int(limit)),
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


def count_by_status() -> dict[str, int]:
    """``{status: count}`` over all proposals (the queue badge source)."""
    conn = db.get_conn()
    with _lock:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS c FROM wiki_proposals GROUP BY status"
        ).fetchall()
    return {r["status"]: int(r["c"]) for r in rows}


def mark_decided(
    *, proposal_id: int, status: str, decided: str, decided_by: str,
    applied_note_id: int | None,
) -> bool:
    """Flip a proposal to accepted/rejected ONLY if it is still pending (guards
    against double-accept / accept-after-reject races). Returns True iff a row was
    updated (i.e. it WAS pending). A False means it was already decided."""
    conn = db.get_conn()
    with _lock:
        cur = conn.execute(
            "UPDATE wiki_proposals SET status = ?, decided = ?, decided_by = ?, "
            "applied_note_id = ? WHERE id = ? AND status = 'pending'",
            (status, decided, decided_by, applied_note_id, int(proposal_id)),
        )
        conn.commit()
        return cur.rowcount > 0


# --------------------------------------------------------------------------- #
# wiki_mcp_audit append + read (D-W4.4, append-only)                            #
# --------------------------------------------------------------------------- #
def append_audit(
    *, tool: str, params: dict[str, Any], actor: str,
    correlation_id: str | None, ts: str,
) -> int:
    """Append one immutable audit row (every MCP call — read OR write). Returns id.
    NEVER updated/deleted."""
    conn = db.get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO wiki_mcp_audit (tool, params_json, actor, correlation_id, ts) "
            "VALUES (?,?,?,?,?)",
            (tool, _json(params), actor, correlation_id, ts),
        )
        conn.commit()
        new_id = cur.lastrowid
        if new_id is None:  # pragma: no cover
            raise RuntimeError("audit INSERT did not yield an id")
        return int(new_id)


def recent_audit(limit: int = 100, correlation_id: str | None = None) -> list[dict[str, Any]]:
    """Most-recent audit rows (newest first). Optionally scoped to one
    correlation_id (one agent session's trail)."""
    conn = db.get_conn()
    with _lock:
        if correlation_id is None:
            rows = conn.execute(
                "SELECT id, tool, params_json, actor, correlation_id, ts "
                "FROM wiki_mcp_audit ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, tool, params_json, actor, correlation_id, ts "
                "FROM wiki_mcp_audit WHERE correlation_id = ? ORDER BY id DESC LIMIT ?",
                (correlation_id, int(limit)),
            ).fetchall()
    return [
        {
            "id": int(r["id"]), "tool": r["tool"], "params": _loads(r["params_json"]),
            "actor": r["actor"], "correlationId": r["correlation_id"], "ts": r["ts"],
        }
        for r in rows
    ]


# Register tables at import so a fresh process / first request has them ready.
init_proposal_tables()
