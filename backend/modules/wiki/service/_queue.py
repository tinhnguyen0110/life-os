"""modules/wiki/service/_queue.py — THE single-writer queue (D3, load-bearing).

Every note mutation becomes an ``Op`` enqueued to ONE process-level FIFO; a SINGLE
worker thread drains it and applies ops sequentially. No code path writes a note
file outside this queue. This serialization is what makes integer-id gen (MAX+1)
collision-free (A1), the op_log a faithful replay log (A3), and concurrency safe
WITHOUT file locks (the queue IS the concurrency model).

🔴 SHARED-STATE INVARIANT: ``_queue`` / ``_worker_started`` / ``_worker_lock`` are
module-level singletons created HERE, once. Every submodule that needs them imports
THIS module's objects — they are never re-created per-submodule. (The service used
to be one 607-LOC file; the split must keep exactly ONE queue + ONE worker.)

The HTTP handler stays synchronous: ``enqueue`` puts an Op then blocks on its
``threading.Event`` for the worker's result (or re-raises the worker's exception).
FastAPI runs sync endpoints in a threadpool, so blocking here doesn't stall the loop.
"""

from __future__ import annotations

import logging
import queue
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..schema import Note
from .errors import OpKind

logger = logging.getLogger("life-os.wiki.service")


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
    warning: str | None = None  # set by refine on the cold-start exception (C6)
    error: BaseException | None = None
    done: threading.Event = field(default_factory=threading.Event)


# The ONE queue + worker-start guards for the whole process. Created once, here.
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
    # Lazy import to avoid a circular dependency (apply imports the queue's Op type).
    # The worker thread is the ONLY caller of _apply — the serialization point.
    from .apply import _apply

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
