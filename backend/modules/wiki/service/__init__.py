"""modules/wiki/service — wiki business logic + single-writer queue (Sprint W1a-T2).

THE load-bearing piece (D3): every note mutation — create / update / delete / merge
/ refine — becomes an ``Op`` enqueued to ONE process-level FIFO; a SINGLE worker
thread drains it and applies ops sequentially. No code path writes a note file
outside this queue. This serialization is what makes integer-id gen (MAX+1)
collision-free (A1), the op_log a faithful replay log in apply order (A3), and
concurrency safe WITHOUT file locks (the queue IS the concurrency model).

----------------------------------------------------------------------------
PACKAGE LAYOUT (refactor: was one 607-LOC service.py; behavior + public API are
IDENTICAL — every public name is re-exported flat so ``wiki_service.X`` / ``service.X``
keeps working byte-for-byte):

  errors    — NoteNotFound / MergeError / RefineGateError + OpKind
  _queue    — 🔴 THE single queue: Op + _queue/_worker_* singletons + enqueue/worker
  serialize — frontmatter render/parse (_render/_parse/_parse_capture_source/_body_hash)
  links     — wikilink parse + edge derivation (parse_wikilinks/_derive_links/...)
  read      — read path (_read_note/resolve_note) — no queue
  apply     — worker apply logic (_apply + _apply_* + _commit_note), writer-thread only
  crud      — public CRUD wrapping enqueue (create/update/delete/merge/refine_note)

🔴 SHARED-STATE INVARIANT (the Task-8 lesson applied): there is exactly ONE queue +
ONE worker for the whole process. They live in ``_queue`` as module singletons; every
submodule imports THOSE objects (apply/crud import ``_queue.Op``/``enqueue``; the worker
loop lazily imports ``apply._apply``). No submodule re-creates a queue. Verified by
identity in the sprint check.
"""

from __future__ import annotations

# Exceptions + op-kind type.
from .errors import MergeError, NoteNotFound, OpKind, RefineGateError

# Queue machinery (Op + the single writer). enqueue is the only mutation entry point.
from ._queue import Op, enqueue

# Frontmatter render/parse (md = source of truth).
from .serialize import (
    _body_hash,
    _json,
    _parse,
    _parse_capture_source,
    _render,
)

# Wikilink parser + edge derivation.
from .links import (
    _derive_links,
    _resolve_ghosts_for,
    _would_be_link_count,
    parse_wikilinks,
)

# Read path (no queue).
from .read import _read_note, resolve_note

# Worker apply logic (writer-thread only).
from .apply import (
    _apply,
    _apply_create,
    _apply_delete,
    _apply_merge,
    _apply_refine,
    _apply_update,
    _commit_note,
)

# Public CRUD (router + other modules call these).
from .crud import (
    create_note,
    delete_note,
    get_note,
    merge_notes,
    refine_note,
    update_note,
)

__all__ = [
    # errors
    "NoteNotFound", "MergeError", "RefineGateError", "OpKind",
    # queue
    "Op", "enqueue",
    # public CRUD
    "create_note", "get_note", "update_note", "delete_note", "merge_notes",
    "refine_note",
    # read
    "resolve_note",
    # link parsing (tests + citations use parse_wikilinks)
    "parse_wikilinks",
    # serialize internals tests touch
    "_parse", "_parse_capture_source",
    # internals the original single-file module exposed at top level — kept
    # accessible so the public surface is byte-for-byte the same (not part of the
    # supported API, but re-exported to avoid any silent surface shrink).
    "_apply", "_apply_create", "_apply_update", "_apply_delete", "_apply_merge",
    "_apply_refine", "_commit_note", "_derive_links", "_resolve_ghosts_for",
    "_would_be_link_count", "_read_note", "_render", "_body_hash", "_json",
]
