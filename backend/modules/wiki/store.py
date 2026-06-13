"""modules/wiki/store.py — wiki two-store layer (Sprint W1a, M1 Wiki Core).

Two stores, per ARCH §6 "files = source of truth, index = disposable cache":

  - **md+git** (``store/md_store.py``) — the note files ``wiki/notes/<id>.md``
    (frontmatter + body). Source of truth, portable, every write = 1 git commit.
  - **SQLite cache** (the shared ``store/db.py`` connection) — rebuildable index:
      * ``wiki_notes``  — one row per live note (the queryable cache + id source)
      * ``wiki_op_log`` — append-only episodic/replay log (A3): every mutation,
                          in apply order. NOT git history (git mixes commits +
                          isn't replay-structured — spec open-decision).

Wiki tables register idempotently on the shared connection at module import
(mirrors the time-series ``CREATE TABLE IF NOT EXISTS`` pattern in db.py). Keeping
ONE DB file + connection (vs a second wiki.db) is the simpler call — the
single-writer queue (service.py) serializes all wiki writes, so a wiki-local lock
here only guards the brief cache reads/writes against the scheduler thread.

ID generation (A1): ``next_note_id()`` = ``MAX(id)+1`` — collision-free because it
runs INSIDE the single writer (serialized). One machine, no UUID needed (D1).
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path

from core.config import settings
from store import db, md_store

logger = logging.getLogger("life-os.wiki.store")

# Guards cache statements on the shared db connection. The single-writer queue
# already serializes writes; this protects the read path against the scheduler
# thread sharing the same sqlite3.Connection.
_lock = threading.Lock()

# --- Wiki cache schema (idempotent; registered on the shared db connection) --
# wiki_notes: the live-note cache + integer-id source of truth.
# wiki_op_log: append-only replay log (A3) — seq is the monotonic order.
# wiki_aliases: title/alias → id resolver SEAM (addendum c). Empty in W1a — the
#   W1b ghost-link resolver populates it + writes auto-resolve-on-create logic.
#   Standing up the table+index here so W1b plugs in without a schema change.
WIKI_SCHEMA = """
CREATE TABLE IF NOT EXISTS wiki_notes (
    id            INTEGER PRIMARY KEY,          -- integer identity (D1); MAX(id)+1
    title         TEXT    NOT NULL DEFAULT '',
    aliases       TEXT    NOT NULL DEFAULT '[]',-- JSON array
    status        TEXT    NOT NULL DEFAULT 'fleeting',
    note_type     TEXT    NOT NULL DEFAULT 'concept',
    trust_tier    TEXT    NOT NULL DEFAULT 'verified',
    author        TEXT    NOT NULL DEFAULT 'human',
    tags          TEXT    NOT NULL DEFAULT '[]',-- JSON array
    content_hash  TEXT    NOT NULL DEFAULT '',  -- sha256(body); derived cache
    created       TEXT    NOT NULL,             -- ISO-8601 UTC
    updated       TEXT    NOT NULL              -- ISO-8601 UTC
);
-- title→id resolver path (W1b uses this for [[Title]]→id). title is mutable so
-- this is a plain (non-unique) index — collisions are resolved by W1b's logic.
CREATE INDEX IF NOT EXISTS idx_wiki_notes_title ON wiki_notes(title);

CREATE TABLE IF NOT EXISTS wiki_op_log (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,  -- monotonic apply order
    op_id       TEXT    NOT NULL,
    kind        TEXT    NOT NULL,                   -- create | edit | delete (+later)
    note_id     INTEGER,
    actor       TEXT    NOT NULL DEFAULT 'human',
    ts          TEXT    NOT NULL,                   -- ISO-8601 UTC
    commit_sha  TEXT,                               -- md_store commit hash (audit)
    detail      TEXT
);
CREATE INDEX IF NOT EXISTS idx_wiki_oplog_note ON wiki_op_log(note_id, seq);

-- alias→id resolver SEAM (addendum c). Empty in W1a; W1b populates one row per
-- (alias, note_id) so an alias lookup is O(1) instead of a JSON scan over
-- wiki_notes.aliases. note_id is NOT a FK to wiki_notes (the cache is disposable;
-- a stale alias row is cleaned by the reindex/W1b resolver, not enforced here).
CREATE TABLE IF NOT EXISTS wiki_aliases (
    alias    TEXT    NOT NULL,
    note_id  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wiki_aliases_alias ON wiki_aliases(alias);
CREATE INDEX IF NOT EXISTS idx_wiki_aliases_note ON wiki_aliases(note_id);

-- wiki_links: the typed concept-edge graph (B1/B2). One row per outbound link
-- from source_id. Re-derived from the note body on EVERY write (delete this
-- source's rows + insert fresh). A resolved link has target_id set + is_resolved
-- =1; a ghost link ([[Title]] with no matching note) has target_id NULL +
-- target_title set + is_resolved=0 (W1b-T2 auto-resolves it when the target is
-- created). type defaults 'relates' (NOT parsed from body — set via API later).
CREATE TABLE IF NOT EXISTS wiki_links (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id     INTEGER NOT NULL,
    target_id     INTEGER,                          -- NULL for a ghost link
    target_title  TEXT,                             -- set for a ghost link
    type          TEXT    NOT NULL DEFAULT 'relates',
    is_resolved   INTEGER NOT NULL DEFAULT 0,
    display       TEXT                              -- the [[id|display]] label, if any
);
CREATE INDEX IF NOT EXISTS idx_wiki_links_source ON wiki_links(source_id);
CREATE INDEX IF NOT EXISTS idx_wiki_links_target ON wiki_links(target_id);
CREATE INDEX IF NOT EXISTS idx_wiki_links_ghost ON wiki_links(target_title);

-- wiki_redirects: D6 ID-redirect tombstones. A merge (source→target) writes
-- (old_id=source, new_id=target). GET on a tombstoned id follows the redirect to
-- the live target (a cited-then-merged note never 404s). Chained old→mid→new is
-- followed transitively (depth-capped in the reader).
CREATE TABLE IF NOT EXISTS wiki_redirects (
    old_id   INTEGER PRIMARY KEY,   -- the merged-away (now-deleted) note id
    new_id   INTEGER NOT NULL,      -- where it redirects to
    created  TEXT    NOT NULL       -- ISO-8601 UTC
);
"""


def init_wiki_tables() -> sqlite3.Connection:
    """Register wiki tables on the shared connection. Idempotent; safe at import
    and re-callable after a test rebinds ``db.DB_PATH`` (conftest resets it)."""
    conn = db.get_conn()
    with _lock:
        conn.executescript(WIKI_SCHEMA)
        conn.commit()
    return conn


# --------------------------------------------------------------------------- #
# md+git path helpers (note files live under DATA_DIR/wiki/notes/<id>.md)        #
# --------------------------------------------------------------------------- #
def note_rel_path(note_id: int) -> str:
    """DATA_DIR-relative path of a note file. Filename = id (immutable, D1)."""
    return f"wiki/notes/{int(note_id)}.md"


def wiki_notes_dir() -> Path:
    """Absolute dir holding wiki note md files."""
    return settings.data_dir / "wiki" / "notes"


# --------------------------------------------------------------------------- #
# Integer-id source of truth (A1)                                              #
# --------------------------------------------------------------------------- #
def next_note_id() -> int:
    """``MAX(id)+1`` over wiki_notes. Collision-free ONLY when called inside the
    single-writer queue (serialized) — never call from a request handler directly."""
    conn = db.get_conn()
    with _lock:
        row = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next FROM wiki_notes").fetchone()
        return int(row["next"])


# --------------------------------------------------------------------------- #
# wiki_notes cache CRUD                                                        #
# --------------------------------------------------------------------------- #
def upsert_note_cache(
    *, note_id: int, title: str, aliases_json: str, status: str, note_type: str,
    trust_tier: str, author: str, tags_json: str, content_hash: str,
    created: str, updated: str,
) -> None:
    """Insert-or-replace the cache row for a note. Called by the single writer
    AFTER the md file is committed (md is source of truth; this is the index)."""
    conn = db.get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO wiki_notes (id, title, aliases, status, note_type, "
            "trust_tier, author, tags, content_hash, created, updated) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "title=excluded.title, aliases=excluded.aliases, status=excluded.status, "
            "note_type=excluded.note_type, trust_tier=excluded.trust_tier, "
            "author=excluded.author, tags=excluded.tags, "
            "content_hash=excluded.content_hash, updated=excluded.updated",
            (note_id, title, aliases_json, status, note_type, trust_tier, author,
             tags_json, content_hash, created, updated),
        )
        conn.commit()


def get_note_cache(note_id: int) -> sqlite3.Row | None:
    """The cache row for a note, or None if absent (hard-deleted / never created)."""
    conn = db.get_conn()
    with _lock:
        return conn.execute(
            "SELECT * FROM wiki_notes WHERE id = ?", (int(note_id),)
        ).fetchone()


def note_cache_exists(note_id: int) -> bool:
    return get_note_cache(note_id) is not None


def delete_note_cache(note_id: int) -> bool:
    """Hard-delete the cache row (A4). op_log retains the historical delete record.
    Returns True if a row was removed."""
    conn = db.get_conn()
    with _lock:
        cur = conn.execute("DELETE FROM wiki_notes WHERE id = ?", (int(note_id),))
        conn.commit()
        return cur.rowcount > 0


# --------------------------------------------------------------------------- #
# op_log append + read (A3)                                                    #
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# md file read/write/delete — thin pass-through to md_store (1 commit / write)  #
# --------------------------------------------------------------------------- #
def write_note_file(note_id: int, content: str, message: str) -> str:
    """Write the note md file via md_store (atomic + 1 git commit). Returns sha."""
    return md_store.write_file(note_rel_path(note_id), content, message)


def read_note_file(note_id: int) -> str | None:
    """Raw md file content, or None if the file is absent."""
    return md_store.read(note_rel_path(note_id))


def delete_note_file(note_id: int, message: str) -> str | None:
    """Delete the note md file via md_store (1 commit). Returns sha, or None if
    the file did not exist."""
    return md_store.delete_file(note_rel_path(note_id), message)


# --------------------------------------------------------------------------- #
# W1b — alias index + title resolver (B2)                                       #
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# W1b — typed-edge graph (B1/B2)                                                #
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
# W1b — D6 ID-redirect tombstones (B5)                                          #
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


# Register tables at import so a fresh process / first request has them ready.
init_wiki_tables()
