"""modules/wiki/service.py — wiki business logic + single-writer queue (Sprint W1a-T2).

THE load-bearing piece (D3): every note mutation — create / update / delete —
becomes an ``Op`` enqueued to ONE process-level FIFO; a SINGLE worker thread
drains it and applies ops **sequentially**. No code path writes a note file
outside this queue. This serialization is what makes:
  - integer-id gen (MAX+1) collision-free (A1),
  - the op_log a faithful replay log in apply order (A3, also the M3 sync base),
  - concurrency safe WITHOUT file locks (the queue IS the concurrency model).

The HTTP handler stays synchronous: it enqueues an Op then blocks on that op's
``threading.Event`` for the worker's result (or re-raises the worker's exception).
FastAPI runs sync endpoints in a threadpool, so blocking here doesn't stall the loop.

Apply order per op (A2): (1) assign id → (2) ``md_store.write_file`` (the 1 git
commit = durable source of truth) → (3) upsert ``wiki_notes`` cache → (4) append
``wiki_op_log``. **Step 2 fails → the op FAILS CLOSED** (exception re-raised to the
caller, nothing partially applied — a broken WRITE must be visible, memory
`fail-closed-write-fail-soft-addon`). A failure in step 3/4 after a successful md
write is logged + raised (never silently swallowed).

W1a scope: identity + store + queue + CRUD. Links / FTS / graph / refine-gate are
W1b/W1c — ``actor`` is always ``human`` here (single-user, no auth) but recorded so
W2/M4 agent writes slot in unchanged.
"""

from __future__ import annotations

import hashlib
import json
import logging
import queue
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

import yaml

from . import store as wiki_store
from .schema import Note, NoteCreateInput, NoteUpdateInput

logger = logging.getLogger("life-os.wiki.service")

OpKind = Literal["create", "update", "delete"]


class NoteNotFound(Exception):
    """Raised by the worker when an update/delete targets a missing note → router 404."""


# --------------------------------------------------------------------------- #
# Op + the single-writer queue                                                  #
# --------------------------------------------------------------------------- #
@dataclass
class Op:
    """One unit of mutation flowing through the changes-queue.

    ``payload`` carries the create/update input or {} for delete. The worker sets
    ``result`` (a Note, or None for delete) or ``error``; ``done`` is signalled
    when the op finishes so the enqueuing handler can return synchronously.
    """

    kind: OpKind
    note_id: int | None
    payload: dict[str, Any]
    actor: str = "human"
    op_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    ts: str = ""
    result: Note | None = None
    error: BaseException | None = None
    done: threading.Event = field(default_factory=threading.Event)


_queue: "queue.Queue[Op]" = queue.Queue()
_worker_started = threading.Event()
_worker_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_worker() -> None:
    """Start the single worker thread once (lazily, on first enqueue). Idempotent."""
    if _worker_started.is_set():
        return
    with _worker_lock:
        if _worker_started.is_set():
            return
        t = threading.Thread(target=_worker_loop, name="wiki-writer", daemon=True)
        t.start()
        _worker_started.set()
        logger.info("wiki single-writer worker started")


def _worker_loop() -> None:
    while True:
        op = _queue.get()
        try:
            op.result = _apply(op)
        except BaseException as exc:  # noqa: BLE001 — surface ANY failure to the caller
            op.error = exc
        finally:
            op.done.set()
            _queue.task_done()


def enqueue(op: Op) -> Note | None:
    """Submit an op to the single writer and block for its result.

    Re-raises whatever the worker raised (fail-closed: a broken write surfaces).
    This is the ONLY entry point to mutate a note — create/update/delete wrap it.
    """
    _ensure_worker()
    _queue.put(op)
    op.done.wait()
    if op.error is not None:
        raise op.error
    return op.result


# --------------------------------------------------------------------------- #
# Frontmatter render / parse (md file = source of truth)                       #
# --------------------------------------------------------------------------- #
def _body_hash(body: str) -> str:
    """sha256 of the BODY only (A1) — a frontmatter-only edit (title/status) is
    detectable separately from a body edit. Derived cache, never authored."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _render(note: Note) -> str:
    """Note → ``---\\n<frontmatter>\\n---\\n<body>``. contentHash is NOT written
    (it's derived cache, not authored — A1)."""
    fm = {
        "id": note.id,
        "title": note.title,
        "aliases": note.aliases,
        "status": note.status,
        "noteType": note.noteType,
        "trustTier": note.trustTier,
        "author": note.author,
        "tags": note.tags,
        "created": note.created,
        "updated": note.updated,
    }
    block = yaml.safe_dump(fm, sort_keys=True, allow_unicode=True).strip()
    return f"---\n{block}\n---\n{note.content}"


def _parse(content: str, note_id: int) -> Note | None:
    """Parse a note md document → Note (contentHash recomputed from body), or None
    if malformed. ``note_id`` is the filename id (authoritative over frontmatter)."""
    text = content.lstrip("﻿")
    if not text.startswith("---"):
        return None
    parts = text[len("---"):].split("\n---", 1)
    if len(parts) < 2:
        return None
    fm_block, body = parts[0], parts[1].lstrip("\n")
    try:
        fm = yaml.safe_load(fm_block)
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict):
        return None
    try:
        return Note(
            id=note_id,
            title=fm.get("title", "") or "",
            aliases=fm.get("aliases") or [],
            status=fm.get("status", "fleeting"),
            noteType=fm.get("noteType", "concept"),
            trustTier=fm.get("trustTier", "verified"),
            author=fm.get("author", "human"),
            tags=fm.get("tags") or [],
            content=body,
            created=fm["created"],
            updated=fm["updated"],
            contentHash=_body_hash(body),
        )
    except Exception:  # missing/invalid field → malformed
        return None


def _commit_note(note: Note, message: str) -> str:
    """Write the note md file (1 git commit) + upsert the cache row. Returns sha.

    Order (A2): md write (source of truth, fail-closed) → cache upsert. The cache
    is the disposable index; md is authoritative.
    """
    sha = wiki_store.write_note_file(note.id, _render(note), message)
    wiki_store.upsert_note_cache(
        note_id=note.id, title=note.title, aliases_json=_json(note.aliases),
        status=note.status, note_type=note.noteType, trust_tier=note.trustTier,
        author=note.author, tags_json=_json(note.tags),
        content_hash=note.contentHash, created=note.created, updated=note.updated,
    )
    return sha


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# Worker apply (runs ONLY on the single writer thread)                          #
# --------------------------------------------------------------------------- #
def _apply(op: Op) -> Note | None:
    if op.kind == "create":
        return _apply_create(op)
    if op.kind == "update":
        return _apply_update(op)
    if op.kind == "delete":
        _apply_delete(op)
        return None
    raise ValueError(f"unknown op kind {op.kind!r}")  # pragma: no cover


def _apply_create(op: Op) -> Note:
    note_id = wiki_store.next_note_id()  # MAX+1, safe — serialized (A1)
    now = _now_iso()
    inp: NoteCreateInput = op.payload["input"]
    note = Note(
        id=note_id, title=inp.title, aliases=[], status=inp.status,
        noteType=inp.noteType, trustTier="verified", author=inp.author,
        tags=inp.tags, content=inp.content, created=now, updated=now,
        contentHash=_body_hash(inp.content),
    )
    sha = _commit_note(note, f"create wiki note {note_id}")
    wiki_store.append_op(op_id=op.op_id, kind="create", note_id=note_id,
                         actor=op.actor, ts=now, commit_sha=sha)
    return note


def _apply_update(op: Op) -> Note:
    note_id = op.note_id
    assert note_id is not None
    existing = _read_note(note_id)
    if existing is None:
        raise NoteNotFound(str(note_id))
    inp: NoteUpdateInput = op.payload["input"]
    new_title = inp.title if inp.title is not None else existing.title
    new_content = inp.content if inp.content is not None else existing.content
    new_status = inp.status if inp.status is not None else existing.status
    new_note_type = inp.noteType if inp.noteType is not None else existing.noteType
    new_trust = inp.trustTier if inp.trustTier is not None else existing.trustTier
    new_aliases = inp.aliases if inp.aliases is not None else existing.aliases
    new_tags = inp.tags if inp.tags is not None else existing.tags

    new_hash = _body_hash(new_content)
    fm_unchanged = (
        new_title == existing.title and new_status == existing.status
        and new_note_type == existing.noteType and new_trust == existing.trustTier
        and new_aliases == existing.aliases and new_tags == existing.tags
    )
    # A5 — content-hash dirty check: body identical AND frontmatter unchanged →
    # no-op touch: no new commit, no updated bump, no op_log row.
    if new_hash == existing.contentHash and fm_unchanged:
        logger.info("wiki note %s update is a no-op touch — skipping", note_id)
        return existing

    now = _now_iso()
    note = Note(
        id=note_id, title=new_title, aliases=new_aliases, status=new_status,
        noteType=new_note_type, trustTier=new_trust, author=existing.author,
        tags=new_tags, content=new_content, created=existing.created, updated=now,
        contentHash=new_hash,
    )
    sha = _commit_note(note, f"edit wiki note {note_id}")
    wiki_store.append_op(op_id=op.op_id, kind="edit", note_id=note_id,
                         actor=op.actor, ts=now, commit_sha=sha)
    return note


def _apply_delete(op: Op) -> None:
    note_id = op.note_id
    assert note_id is not None
    if _read_note(note_id) is None:
        raise NoteNotFound(str(note_id))
    sha = wiki_store.delete_note_file(note_id, f"delete wiki note {note_id}")
    wiki_store.delete_note_cache(note_id)  # A4: hard-delete cache; op_log keeps record
    wiki_store.append_op(op_id=op.op_id, kind="delete", note_id=note_id,
                         actor=op.actor, ts=_now_iso(), commit_sha=sha)


# --------------------------------------------------------------------------- #
# Read path (no queue — reads don't mutate)                                     #
# --------------------------------------------------------------------------- #
def _read_note(note_id: int) -> Note | None:
    """Read a note from its md file (source of truth). None if absent/malformed."""
    content = wiki_store.read_note_file(note_id)
    if content is None:
        return None
    return _parse(content, note_id)


# --------------------------------------------------------------------------- #
# Public CRUD (router calls these)                                              #
# --------------------------------------------------------------------------- #
def create_note(inp: NoteCreateInput, actor: str = "human") -> Note:
    """Create a fleeting note through the queue. Returns the created Note."""
    op = Op(kind="create", note_id=None, payload={"input": inp}, actor=actor)
    note = enqueue(op)
    assert note is not None
    return note


def get_note(note_id: int) -> Note | None:
    """Read one note (no queue). None if absent/malformed → router maps to 404."""
    return _read_note(note_id)


def update_note(note_id: int, inp: NoteUpdateInput, actor: str = "human") -> Note:
    """Partial-update a note through the queue. Raises NoteNotFound if absent."""
    op = Op(kind="update", note_id=note_id, payload={"input": inp}, actor=actor)
    note = enqueue(op)
    assert note is not None
    return note


def delete_note(note_id: int, actor: str = "human") -> None:
    """Delete a note through the queue. Raises NoteNotFound if absent."""
    op = Op(kind="delete", note_id=note_id, payload={}, actor=actor)
    enqueue(op)
