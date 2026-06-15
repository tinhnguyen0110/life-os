"""mcp_servers/proposals_store.py — the GENERIC agent-proposal queue (MCP-3).

The thesis: an external agent PROPOSES changes; a human DISPOSES (reviews + applies).
The wiki already has this (``wiki_proposals``) — but that table + its kinds + its
apply path are wiki-NOTE-specific (note_create/note_edit/link/merge/moc, apply via the
note single-writer). There is NO cross-module proposal queue for the rest of life-os
(decision-journal / notes / trade-journal / projects …).

This is that minimal generic queue. ONE append-structured table, ``agent_proposals``,
on the shared SQLite connection (same pattern as wiki's proposals_store + the module
stores). A row is pure INTENT:

  status flow:  pending  →  accepted | rejected            (human-only transition)

  - The AGENT (the MCP write-server) can ONLY ``enqueue`` a pending row. This module
    exposes NO apply / accept / mutate-the-target function — so the agent channel is
    STRUCTURALLY incapable of changing any module's data. A pending row sits in the
    queue until a human reviews it (a review UI / endpoint is a SEPARATE later piece;
    out of scope for MCP-3, whose job is the gated PROPOSE side).
  - ``mark_decided`` exists for the eventual human-review surface, but it ONLY flips
    the status + records who/when — it still does NOT touch the target module. Applying
    an accepted proposal (actually writing decision/note/…) is future human-side work,
    deliberately not built here so the agent path has nothing to escalate into.

Each proposal carries: ``module`` (which life-os module it targets), ``kind`` (the
operation, e.g. decision_create), an opaque ``payload`` (the proposed intent — NOT
validated against the module schema here; validation happens at human-apply time), a
REQUIRED ``rationale`` (the agent must explain WHY), ``actor`` (mcp:writer), and a
``correlation_id`` grouping one agent session.

Idempotent registration at import-time call (``init_proposal_tables``), re-callable
after a test rebinds ``db.DB_PATH`` (conftest resets it). Mirrors wiki's store so the
shared ``_lock`` guards statements against the scheduler thread on the same connection.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any

from store import db

_lock = threading.Lock()

# module  = target life-os module (decision_journal | notes | journal | projects | …)
# kind    = the proposed operation (decision_create | note_create | journal_create | project_update | …)
# status  = pending | accepted | rejected   (only a human moves it off 'pending')
# payload = the kind-specific proposed intent (opaque here; validated at apply time)
AGENT_PROPOSALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_proposals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    module          TEXT    NOT NULL,              -- target life-os module
    kind            TEXT    NOT NULL,              -- proposed operation
    payload_json    TEXT    NOT NULL DEFAULT '{}', -- proposed intent (opaque)
    rationale       TEXT    NOT NULL,              -- REQUIRED: the agent explains WHY
    actor           TEXT    NOT NULL DEFAULT 'mcp:writer',
    status          TEXT    NOT NULL DEFAULT 'pending',
    correlation_id  TEXT,                          -- groups one agent session
    created         TEXT    NOT NULL,              -- ISO-8601 UTC
    decided         TEXT,                          -- set on accept/reject (human)
    decided_by      TEXT,                          -- who ratified (human)
    applied_ref     TEXT,                          -- id of the entry the apply created (accept)
    apply_error     TEXT                           -- why an accept could not apply (e.g. no handler)
);
CREATE INDEX IF NOT EXISTS idx_agent_proposals_status ON agent_proposals(status);
CREATE INDEX IF NOT EXISTS idx_agent_proposals_module ON agent_proposals(module);
CREATE INDEX IF NOT EXISTS idx_agent_proposals_corr ON agent_proposals(correlation_id);

-- Immutable decision audit: one row per accept/reject (WHO did WHAT, WHEN). Never
-- updated/deleted — forensic trail for the human dispose action.
CREATE TABLE IF NOT EXISTS agent_proposals_audit (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id     INTEGER NOT NULL,
    action          TEXT    NOT NULL,              -- accept | reject
    decided_by      TEXT    NOT NULL,
    detail          TEXT,                          -- applied_ref / apply_error / note
    ts              TEXT    NOT NULL               -- ISO-8601 UTC
);
CREATE INDEX IF NOT EXISTS idx_agent_proposals_audit_pid ON agent_proposals_audit(proposal_id);
"""


def init_proposal_tables() -> sqlite3.Connection:
    """Register the agent_proposals table on the shared connection. Idempotent;
    re-callable after a test rebinds ``db.DB_PATH``."""
    conn = db.get_conn()
    with _lock:
        conn.executescript(AGENT_PROPOSALS_SCHEMA)
        conn.commit()
    return conn


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(text: str | None) -> dict[str, Any]:
    """Parse a payload_json cell → dict (defensive: malformed/NULL → {} so one corrupt
    row never 500s the whole queue read)."""
    if not text:
        return {}
    try:
        v = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}
    return v if isinstance(v, dict) else {}


def _col(row: sqlite3.Row, name: str) -> Any:
    """Defensive column access: a row from an older schema (pre-applied_ref) lacks the
    new columns — return None rather than raising IndexError."""
    try:
        return row[name]
    except (IndexError, KeyError):
        return None


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Map an agent_proposals row → a response dict (camelCase, payload parsed back)."""
    return {
        "id": row["id"],
        "module": row["module"],
        "kind": row["kind"],
        "payload": _loads(row["payload_json"]),
        "rationale": row["rationale"] or "",
        "actor": row["actor"],
        "status": row["status"],
        "correlationId": row["correlation_id"],
        "created": row["created"],
        "decided": row["decided"],
        "decidedBy": row["decided_by"],
        "appliedRef": _col(row, "applied_ref"),
        "applyError": _col(row, "apply_error"),
    }


# --------------------------------------------------------------------------- #
# enqueue — the ONLY write the agent channel can perform. Inserts a pending      #
# row; returns the stored proposal dict. NEVER touches the target module.       #
# --------------------------------------------------------------------------- #
def enqueue(
    *, module: str, kind: str, payload: dict[str, Any], rationale: str,
    actor: str, correlation_id: str | None, created: str,
) -> dict[str, Any]:
    """Insert one PENDING agent proposal and return the stored dict. This is the sole
    mutation the agent path is capable of — a queue append, not a module write."""
    conn = db.get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO agent_proposals "
            "(module, kind, payload_json, rationale, actor, status, correlation_id, created) "
            "VALUES (?,?,?,?,?,'pending',?,?)",
            (module, kind, _json(payload), rationale, actor, correlation_id, created),
        )
        conn.commit()
        new_id = cur.lastrowid
        if new_id is None:  # pragma: no cover — INSERT always yields a rowid
            raise RuntimeError("agent_proposals INSERT did not yield an id")
        row = conn.execute(
            "SELECT * FROM agent_proposals WHERE id = ?", (int(new_id),)
        ).fetchone()
    return _row_to_dict(row)


# --------------------------------------------------------------------------- #
# read side — for the eventual human-review surface (NOT the agent channel).     #
# --------------------------------------------------------------------------- #
def get_proposal(proposal_id: int) -> dict[str, Any] | None:
    conn = db.get_conn()
    with _lock:
        row = conn.execute(
            "SELECT * FROM agent_proposals WHERE id = ?", (int(proposal_id),)
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_proposals(status: str | None = None, module: str | None = None,
                   limit: int = 200) -> list[dict[str, Any]]:
    """Proposals newest-first, optionally filtered by status and/or module."""
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if module:
        clauses.append("module = ?")
        params.append(module)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(int(limit))
    conn = db.get_conn()
    with _lock:
        rows = conn.execute(
            f"SELECT * FROM agent_proposals{where} ORDER BY id DESC LIMIT ?",  # noqa: S608 — clauses are literal
            tuple(params),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def count_by_status() -> dict[str, int]:
    conn = db.get_conn()
    with _lock:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS c FROM agent_proposals GROUP BY status"
        ).fetchall()
    return {r["status"]: r["c"] for r in rows}


def mark_decided(proposal_id: int, *, status: str, decided: str, decided_by: str,
                 applied_ref: str | None = None,
                 apply_error: str | None = None) -> tuple[bool, dict[str, Any] | None]:
    """HUMAN-only: ATOMICALLY flip a PENDING proposal to accepted/rejected + record
    who/when (+ applied_ref/apply_error on accept). Returns ``(transitioned, row)``:

      - ``transitioned`` is True ONLY if THIS call moved the row off 'pending'. The
        UPDATE is guarded ``WHERE status='pending'`` so a 2nd call on an already-decided
        proposal updates 0 rows → ``transitioned=False``. This is the IDEMPOTENCY
        pivot: the apply layer applies the target-module write ONLY when transitioned
        is True, so accepting twice never applies twice.
      - ``row`` is the current proposal dict (post-update), or None if the id is unknown.

    Does NOT itself write the target module — the SERVICE layer applies (calls the real
    module create) and passes the resulting ``applied_ref`` back in. Keeping the
    apply OUT of the store keeps the store db-only (the agent path can't reach a module
    write through it)."""
    if status not in ("accepted", "rejected"):
        raise ValueError("status must be 'accepted' or 'rejected'")
    conn = db.get_conn()
    with _lock:
        cur = conn.execute(
            "UPDATE agent_proposals SET status = ?, decided = ?, decided_by = ?, "
            "applied_ref = ?, apply_error = ? WHERE id = ? AND status = 'pending'",
            (status, decided, decided_by, applied_ref, apply_error, int(proposal_id)),
        )
        conn.commit()
        transitioned = cur.rowcount > 0
        row = conn.execute(
            "SELECT * FROM agent_proposals WHERE id = ?", (int(proposal_id),)
        ).fetchone()
    return transitioned, (_row_to_dict(row) if row else None)


def set_applied_ref(proposal_id: int, *, applied_ref: str | None = None,
                    apply_error: str | None = None) -> None:
    """Persist the apply result onto an already-accepted row (used when the service
    applies AFTER the status transition). Append-style: only sets the given field."""
    conn = db.get_conn()
    with _lock:
        if applied_ref is not None:
            conn.execute("UPDATE agent_proposals SET applied_ref = ? WHERE id = ?",
                         (applied_ref, int(proposal_id)))
        if apply_error is not None:
            conn.execute("UPDATE agent_proposals SET apply_error = ? WHERE id = ?",
                         (apply_error, int(proposal_id)))
        conn.commit()


# --------------------------------------------------------------------------- #
# Decision audit — one immutable row per accept/reject (WHO did WHAT, WHEN)      #
# --------------------------------------------------------------------------- #
def append_audit(*, proposal_id: int, action: str, decided_by: str,
                 detail: str | None, ts: str) -> None:
    """Append one decision-audit row. Never updated/deleted (forensic trail)."""
    conn = db.get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO agent_proposals_audit (proposal_id, action, decided_by, detail, ts) "
            "VALUES (?,?,?,?,?)",
            (int(proposal_id), action, decided_by, detail, ts),
        )
        conn.commit()


def list_audit(proposal_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
    """Decision-audit rows newest-first, optionally for one proposal."""
    conn = db.get_conn()
    with _lock:
        if proposal_id is None:
            rows = conn.execute(
                "SELECT * FROM agent_proposals_audit ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM agent_proposals_audit WHERE proposal_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (int(proposal_id), int(limit)),
            ).fetchall()
    return [
        {"id": r["id"], "proposalId": r["proposal_id"], "action": r["action"],
         "decidedBy": r["decided_by"], "detail": r["detail"], "ts": r["ts"]}
        for r in rows
    ]
