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
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

import yaml

from . import store as wiki_store
from .schema import Note, NoteCreateInput, NoteUpdateInput

logger = logging.getLogger("life-os.wiki.service")

OpKind = Literal["create", "update", "delete", "merge", "refine"]


class NoteNotFound(Exception):
    """Raised by the worker when an update/delete targets a missing note → router 404."""


class MergeError(Exception):
    """Raised when a merge is invalid (same id) → router 422."""


class RefineGateError(Exception):
    """Raised when REFINE is blocked by the ≥1-link hard gate (D9) → router 422."""


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


def _render(note: Note, capture_source: str = "quick_add") -> str:
    """Note → ``---\\n<frontmatter>\\n---\\n<body>``. contentHash is NOT written
    (it's derived cache, not authored — A1). ``captureSource`` IS authored (it's
    provenance, set once at capture)."""
    fm = {
        "id": note.id,
        "title": note.title,
        "aliases": note.aliases,
        "status": note.status,
        "noteType": note.noteType,
        "trustTier": note.trustTier,
        "author": note.author,
        "tags": note.tags,
        "captureSource": capture_source,
        "created": note.created,
        "updated": note.updated,
    }
    block = yaml.safe_dump(fm, sort_keys=True, allow_unicode=True).strip()
    return f"---\n{block}\n---\n{note.content}"


def _parse_capture_source(content: str) -> str:
    """Recover ``captureSource`` from a note md document's frontmatter (default
    quick_add if absent / malformed). Kept separate so the frozen Note response
    model doesn't need a new field — captureSource lives in frontmatter + cache,
    surfaced only by the inbox reader."""
    text = content.lstrip("﻿")
    if not text.startswith("---"):
        return "quick_add"
    parts = text[len("---"):].split("\n---", 1)
    if len(parts) < 2:
        return "quick_add"
    try:
        fm = yaml.safe_load(parts[0])
    except yaml.YAMLError:
        return "quick_add"
    if isinstance(fm, dict) and fm.get("captureSource"):
        return str(fm["captureSource"])
    return "quick_add"


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


def _commit_note(note: Note, message: str, capture_source: str = "quick_add") -> str:
    """Write the note md file (1 git commit) + upsert the cache row + refresh the
    resolver index + re-derive this note's outbound edges. Returns sha.

    Order (A2 + B2): md write (source of truth, fail-closed) → cache upsert →
    resolver-index refresh (wiki_aliases) → edge re-derivation (wiki_links). The
    cache/index/edges are the disposable index; md is authoritative. Edges are
    re-derived from the body on EVERY write so they always match the body (B2).
    ``capture_source`` is provenance (set at create, preserved on edit by the caller).
    """
    sha = wiki_store.write_note_file(note.id, _render(note, capture_source), message)
    wiki_store.upsert_note_cache(
        note_id=note.id, title=note.title, aliases_json=_json(note.aliases),
        status=note.status, note_type=note.noteType, trust_tier=note.trustTier,
        author=note.author, tags_json=_json(note.tags),
        content_hash=note.contentHash, created=note.created, updated=note.updated,
        capture_source=capture_source,
    )
    # B2 — refresh the title/alias→id resolver index for THIS note, then re-derive
    # its outbound edges from the (new) body against the (now-current) index.
    wiki_store.replace_aliases(note.id, note.title, note.aliases)
    _derive_links(note)
    # B4 — auto-resolve ghosts: any pre-existing ghost edge whose target_title now
    # matches this note's title/alias → flip to resolved pointing at this id.
    _resolve_ghosts_for(note)
    # C1 — sync the FTS index for this note (disposable full-text cache).
    wiki_store.fts_upsert(note.id, title=note.title, body=note.content,
                          aliases=note.aliases, tags=note.tags)
    return sha


def _resolve_ghosts_for(note: Note) -> None:
    """Flip any ghost edge whose ``target_title`` matches this note's title or an
    alias (case-insensitive) to resolved → ``target_id = note.id`` (B4). Runs after
    the alias index refresh so the new/renamed note is already resolvable. This is
    what makes a `[[Atomicity principle]]` ghost auto-resolve the moment a note
    titled "Atomicity principle" is created."""
    titles = {t for t in ({note.title, *note.aliases}) if t and t.strip()}
    for t in titles:
        wiki_store.resolve_ghosts_to(t, note.id)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# B1 — wikilink parser                                                          #
# --------------------------------------------------------------------------- #
# Matches [[ ... ]] with an optional |display. The inner target is either an
# integer id ([[47]] / [[47|disp]]) or a title ([[Title]] / [[Title|disp]]).
# Inline typed-link syntax ([[supports::47]]) is intentionally NOT supported —
# edge type is set via API later, default 'relates' (B1 rationale).
_WIKILINK_RE = re.compile(r"\[\[\s*([^\[\]|]+?)\s*(?:\|\s*([^\[\]]*?)\s*)?\]\]")


def parse_wikilinks(body: str) -> list[dict[str, Any]]:
    """Extract wikilinks from a note body (B1).

    Returns a list of ``{target_id:int|None, target_title:str|None, display:str|None}``
    — one per DISTINCT target (deduped, first occurrence's display wins). An
    all-digit inner token is an id link ([[47]]); anything else is a title link
    ([[Title]]) resolved later. Empty ``[[]]``/`[[ | x]]` (no target) is skipped.
    """
    seen: dict[str, dict[str, Any]] = {}
    for m in _WIKILINK_RE.finditer(body or ""):
        target = m.group(1).strip()
        display = (m.group(2) or "").strip() or None
        if not target:
            continue
        if target.isdigit():
            key = f"id:{int(target)}"
            entry = {"target_id": int(target), "target_title": None, "display": display}
        else:
            key = f"title:{target.lower()}"
            entry = {"target_id": None, "target_title": target, "display": display}
        if key not in seen:  # dedup: first occurrence wins
            seen[key] = entry
    return list(seen.values())


def _derive_links(note: Note) -> None:
    """Parse the note body → resolve each link → persist the fresh outbound edge
    set (B2). Runs in the writer's cache-update step (single-threaded, after the
    alias index is refreshed). A ghost link ([[Title]] with no matching note) is
    stored unresolved; W1b-T2 auto-resolves it on target create.

    Self-link ([[47]] in note 47) and circular links persist without special-
    casing — no crash, low value, not rejected (B1).
    """
    parsed = parse_wikilinks(note.content)
    links: list[dict[str, Any]] = []
    for p in parsed:
        if p["target_id"] is not None:
            # id link — resolved iff that note exists in the cache.
            tid = p["target_id"]
            resolved = wiki_store.note_cache_exists(tid)
            links.append({
                "target_id": tid if resolved else None,
                "target_title": None if resolved else str(tid),
                "type": "relates", "is_resolved": resolved, "display": p["display"],
            })
        else:
            title = p["target_title"]
            tid = wiki_store.resolve_title(title)
            if tid is not None and wiki_store.resolve_title_count(title) > 1:
                logger.warning(
                    "wiki link [[%s]] in note %s resolves to multiple notes — "
                    "using lowest id %s", title, note.id, tid,
                )
            links.append({
                "target_id": tid,
                "target_title": None if tid is not None else title,
                "type": "relates", "is_resolved": tid is not None,
                "display": p["display"],
            })
    wiki_store.replace_links(note.id, links)


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
    if op.kind == "merge":
        return _apply_merge(op)
    if op.kind == "refine":
        return _apply_refine(op)
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
    sha = _commit_note(note, f"create wiki note {note_id}",
                       capture_source=inp.captureSource)
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
    # captureSource is provenance — preserve it across edits (read from the md the
    # note was last written with). A refine/edit never changes where it was captured.
    cap = _parse_capture_source(wiki_store.read_note_file(note_id) or "")
    op_kind = op.payload.get("op_kind", "edit")  # refine reuses this path (C6)
    sha = _commit_note(note, f"{op_kind} wiki note {note_id}", capture_source=cap)
    wiki_store.append_op(op_id=op.op_id, kind=op_kind, note_id=note_id,
                         actor=op.actor, ts=now, commit_sha=sha)
    return note


def _would_be_link_count(note_id: int, new_body: str) -> int:
    """Compute the link count the note WOULD have after a refine edit, WITHOUT
    writing (C6 gate). = outbound links parsed from the new body (resolved or
    ghost, both count as authored links) + existing resolved inbound edges."""
    outbound = len(parse_wikilinks(new_body))
    inbound = len(wiki_store.links_to(note_id, resolved_only=True))
    return outbound + inbound


def _apply_refine(op: Op) -> Note:
    """REFINE (C6/D9): the update-path + the ≥1-link HARD GATE, checked BEFORE the
    write so a blocked refine doesn't mutate the note.

      - linkCount(after edit) ≥ 1 → apply normally (status flip etc.), op_log `refine`.
      - linkCount == 0 AND vault in cold-start (totalNotes < threshold) → ALLOW +
        a warning (the first notes have nothing to link to).
      - linkCount == 0 AND vault NOT cold-start → RefineGateError (router 422).
    """
    from core.config import settings

    note_id = op.note_id
    assert note_id is not None
    existing = _read_note(note_id)
    if existing is None:
        raise NoteNotFound(str(note_id))
    inp: NoteUpdateInput = op.payload["input"]
    new_body = inp.content if inp.content is not None else existing.content

    link_count = _would_be_link_count(note_id, new_body)
    if link_count == 0:
        total = wiki_store.count_notes()
        threshold = settings.wiki_cold_start_min_notes
        if total >= threshold:
            raise RefineGateError(
                f"refine requires ≥1 link (vault has {total} notes; "
                f"cold-start exception only below {threshold})"
            )
        # Cold-start: allow, but warn.
        op.warning = (
            f"cold-start: refined without a link (vault has {total} note(s), "
            f"under the {threshold}-note threshold)"
        )

    # Delegate to the update mechanics with the `refine` op kind.
    op.payload["op_kind"] = "refine"
    return _apply_update(op)


def _apply_delete(op: Op) -> None:
    note_id = op.note_id
    assert note_id is not None
    existing = _read_note(note_id)
    if existing is None:
        raise NoteNotFound(str(note_id))
    sha = wiki_store.delete_note_file(note_id, f"delete wiki note {note_id}")
    wiki_store.delete_note_cache(note_id)  # A4: hard-delete cache; op_log keeps record
    # Clean this note's resolver rows + outbound edges (disposable cache).
    wiki_store.clear_aliases(note_id)
    wiki_store.clear_links_from(note_id)
    # Spec defensive case: inbound links to a deleted note become unresolved
    # (ghost) — they keep the deleted note's title so a re-created note with that
    # title auto-resolves them (B4). NOT a dangling target_id.
    wiki_store.ghostify_inbound(note_id, existing.title)
    wiki_store.fts_delete(note_id)  # C1: drop the FTS row for the deleted note
    wiki_store.append_op(op_id=op.op_id, kind="delete", note_id=note_id,
                         actor=op.actor, ts=_now_iso(), commit_sha=sha)


def _apply_merge(op: Op) -> Note:
    """D6 merge (B5): merge ``source`` INTO ``target``. Through the queue so it's
    serialized with all other mutations. Steps:
      1. validate both exist + differ (else MergeError/NoteNotFound).
      2. delete the source md file + cache row (A4 path) + its aliases/outbound edges.
      3. write a ``wiki_redirects(source→target)`` tombstone.
      4. repoint inbound links: every edge that pointed at source now points at target.
      5. op_log ``merge``.
    Returns the TARGET note (the merge result).
    """
    src_id = op.payload["sourceId"]
    tgt_id = op.payload["targetId"]
    if src_id == tgt_id:
        raise MergeError("sourceId and targetId must differ")
    src = _read_note(src_id)
    tgt = _read_note(tgt_id)
    if src is None:
        raise NoteNotFound(str(src_id))
    if tgt is None:
        raise NoteNotFound(str(tgt_id))
    now = _now_iso()
    # Delete the source note (md + cache + its own resolver/outbound rows).
    sha = wiki_store.delete_note_file(src_id, f"merge wiki note {src_id} -> {tgt_id}")
    wiki_store.delete_note_cache(src_id)
    wiki_store.clear_aliases(src_id)
    wiki_store.clear_links_from(src_id)
    wiki_store.fts_delete(src_id)  # C1: drop the merged-away note's FTS row
    # Tombstone + repoint inbound: links to source now resolve to target (citations
    # survive). NOT ghostified (unlike a plain delete) — they follow the redirect.
    wiki_store.add_redirect(src_id, tgt_id, now)
    repointed = wiki_store.repoint_inbound_links(src_id, tgt_id)
    wiki_store.append_op(
        op_id=op.op_id, kind="merge", note_id=src_id, actor=op.actor, ts=now,
        commit_sha=sha, detail=f"merged #{src_id} → #{tgt_id} ({repointed} inbound repointed)",
    )
    return tgt


# --------------------------------------------------------------------------- #
# Read path (no queue — reads don't mutate)                                     #
# --------------------------------------------------------------------------- #
def _read_note(note_id: int) -> Note | None:
    """Read a note from its md file (source of truth). None if absent/malformed."""
    content = wiki_store.read_note_file(note_id)
    if content is None:
        return None
    return _parse(content, note_id)


def resolve_note(note_id: int) -> tuple[Note | None, str | None]:
    """Read a note, FOLLOWING a redirect tombstone if ``note_id`` was merged away
    (B5/D6). Returns ``(note, warning)``:
      - live id → ``(note, None)``.
      - tombstoned id → ``(target_note, "note #old merged into #new")`` so a stale
        citation/link resolves to the merge target instead of 404-ing.
      - truly absent (never existed / deleted, not merged) → ``(None, None)``.
    Chained redirects (old→mid→new) are followed transitively, depth-capped."""
    direct = _read_note(note_id)
    if direct is not None:
        return direct, None
    final_id, redirected = wiki_store.follow_redirect(note_id)
    if redirected:
        target = _read_note(final_id)
        if target is not None:
            return target, f"note #{note_id} merged into #{final_id}"
    return None, None


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


def merge_notes(source_id: int, target_id: int, actor: str = "human") -> Note:
    """Merge ``source`` INTO ``target`` through the queue (B5/D6). Returns the
    target note. Raises MergeError (same id → 422) / NoteNotFound (absent → 404)."""
    op = Op(kind="merge", note_id=source_id,
            payload={"sourceId": source_id, "targetId": target_id}, actor=actor)
    note = enqueue(op)
    assert note is not None
    return note


def refine_note(note_id: int, inp: NoteUpdateInput,
                actor: str = "human") -> tuple[Note, str | None]:
    """REFINE a note through the queue (C6/D9) — the ≥1-link hard gate path.
    Returns ``(note, warning)``: warning is set on the cold-start exception.
    Raises NoteNotFound (absent → 404) / RefineGateError (0-link non-cold-start → 422)."""
    op = Op(kind="refine", note_id=note_id, payload={"input": inp}, actor=actor)
    note = enqueue(op)
    assert note is not None
    return note, op.warning
