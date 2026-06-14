"""modules/wiki/sync_store.py — M3 sync persistence (Sprint W6 A1a, option B).

Three tables on the shared SQLite connection (same idempotent pattern as
store.py / proposals_store.py):

  - ``wiki_devices`` — device registry (device_id, name, last_seen). The identity an
    op-stream is tagged with. Minimal — single-user, single-device today.
  - ``wiki_sync_cursor`` — per-device last-synced op-log seq, so an offline device
    replays exactly the ops it missed on reconnect (offline op-queue resume).
  - ``wiki_sync_conflicts`` — detected true conflicts awaiting human resolution
    (the surfacing endpoint reads these). Append-on-detect; cleared on resolve.

DEFERRED (option B, logged in §Assumptions): device-id-prefix id migration, real
transport. These tables are the mechanism; a 2nd physical device isn't here yet.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from typing import Any

from store import db

logger = logging.getLogger("life-os.wiki.sync_store")

_lock = threading.Lock()

SYNC_SCHEMA = """
CREATE TABLE IF NOT EXISTS wiki_devices (
    device_id   TEXT PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    last_seen   TEXT NOT NULL            -- ISO-8601 UTC
);

-- per-device sync cursor: the last wiki_op_log.seq this device has merged. A device
-- reconnecting replays ops with seq > cursor (the offline op-queue resume point).
CREATE TABLE IF NOT EXISTS wiki_sync_cursor (
    device_id   TEXT PRIMARY KEY,
    last_seq    INTEGER NOT NULL DEFAULT 0
);

-- detected true conflicts (same note+block edited divergently). versions_json keeps
-- EVERY version so the LWW loser is recoverable (0 data loss). status: open|resolved.
CREATE TABLE IF NOT EXISTS wiki_sync_conflicts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id       INTEGER NOT NULL,
    block_index   INTEGER NOT NULL,
    versions_json TEXT    NOT NULL DEFAULT '[]',
    status        TEXT    NOT NULL DEFAULT 'open',
    detected      TEXT    NOT NULL,
    resolved      TEXT
);
CREATE INDEX IF NOT EXISTS idx_wiki_sync_conflicts_status ON wiki_sync_conflicts(status);
CREATE INDEX IF NOT EXISTS idx_wiki_sync_conflicts_note ON wiki_sync_conflicts(note_id);
"""


def init_sync_tables() -> sqlite3.Connection:
    """Register the sync tables on the shared connection. Idempotent; re-callable
    after a test rebinds db.DB_PATH."""
    conn = db.get_conn()
    with _lock:
        conn.executescript(SYNC_SCHEMA)
        conn.commit()
    return conn


# --------------------------------------------------------------------------- #
# device registry                                                              #
# --------------------------------------------------------------------------- #
def register_device(device_id: str, name: str, last_seen: str) -> None:
    """Register or update a device (upsert on device_id, refresh name+last_seen)."""
    conn = db.get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO wiki_devices (device_id, name, last_seen) VALUES (?,?,?) "
            "ON CONFLICT(device_id) DO UPDATE SET name=excluded.name, "
            "last_seen=excluded.last_seen",
            (device_id, name, last_seen),
        )
        conn.commit()


def list_devices() -> list[dict[str, Any]]:
    """All registered devices, most-recently-seen first."""
    conn = db.get_conn()
    with _lock:
        rows = conn.execute(
            "SELECT device_id, name, last_seen FROM wiki_devices ORDER BY last_seen DESC"
        ).fetchall()
    return [{"deviceId": r["device_id"], "name": r["name"], "lastSeen": r["last_seen"]}
            for r in rows]


# --------------------------------------------------------------------------- #
# per-device sync cursor (offline-resume point)                                 #
# --------------------------------------------------------------------------- #
def get_cursor(device_id: str) -> int:
    """The last op-log seq this device merged (0 if never synced)."""
    conn = db.get_conn()
    with _lock:
        row = conn.execute(
            "SELECT last_seq FROM wiki_sync_cursor WHERE device_id = ?", (device_id,)
        ).fetchone()
    return int(row["last_seq"]) if row is not None else 0


def set_cursor(device_id: str, last_seq: int) -> None:
    """Advance a device's sync cursor (upsert)."""
    conn = db.get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO wiki_sync_cursor (device_id, last_seq) VALUES (?,?) "
            "ON CONFLICT(device_id) DO UPDATE SET last_seq=excluded.last_seq",
            (device_id, int(last_seq)),
        )
        conn.commit()


# --------------------------------------------------------------------------- #
# conflict records (the surfacing substrate)                                    #
# --------------------------------------------------------------------------- #
def record_conflict(note_id: int, block_index: int, versions: list[dict[str, Any]],
                    detected: str) -> int:
    """Persist one detected conflict (status open). versions keeps every version so
    the LWW loser is recoverable. Returns the conflict id."""
    conn = db.get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO wiki_sync_conflicts (note_id, block_index, versions_json, "
            "status, detected) VALUES (?,?,?,'open',?)",
            (int(note_id), int(block_index), json.dumps(versions, ensure_ascii=False),
             detected),
        )
        conn.commit()
        new_id = cur.lastrowid
        if new_id is None:  # pragma: no cover
            raise RuntimeError("conflict INSERT did not yield an id")
        return int(new_id)


def list_conflicts(status: str = "open") -> list[dict[str, Any]]:
    """Conflicts by status (default open) for the surfacing endpoint, newest first."""
    conn = db.get_conn()
    with _lock:
        rows = conn.execute(
            "SELECT id, note_id, block_index, versions_json, status, detected, resolved "
            "FROM wiki_sync_conflicts WHERE status = ? ORDER BY id DESC",
            (status,),
        ).fetchall()
    out = []
    for r in rows:
        try:
            versions = json.loads(r["versions_json"])
        except (json.JSONDecodeError, TypeError):
            versions = []
        out.append({
            "id": r["id"], "noteId": r["note_id"], "blockIndex": r["block_index"],
            "versions": versions, "status": r["status"],
            "detected": r["detected"], "resolved": r["resolved"],
        })
    return out


def resolve_conflict(conflict_id: int, resolved: str) -> bool:
    """Mark a conflict resolved (only if currently open). Returns True if flipped."""
    conn = db.get_conn()
    with _lock:
        cur = conn.execute(
            "UPDATE wiki_sync_conflicts SET status='resolved', resolved=? "
            "WHERE id=? AND status='open'",
            (resolved, int(conflict_id)),
        )
        conn.commit()
        return cur.rowcount > 0


# Register tables at import so a fresh process / first request has them ready.
init_sync_tables()
