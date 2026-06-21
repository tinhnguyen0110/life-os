"""modules/wiki/service/apply.py — worker apply logic (runs ONLY on the writer thread).

``_apply`` is called by the single-writer worker loop (``_queue._worker_loop``) — it
is the serialization point. Apply order per op (A2): assign id → ``md_store.write_file``
(the 1 git commit = durable source of truth, FAIL-CLOSED) → upsert cache → append
op_log. A failed md write re-raises (nothing partially applied); a post-write cache
failure is logged + raised, never silently swallowed.
"""

from __future__ import annotations

import logging

from .. import store as wiki_store
from ..schema import Note, NoteCreateInput, NoteUpdateInput
from ._queue import Op, _now_iso
from .errors import MergeError, NoteNotFound, RefineGateError
from .links import _derive_links, _resolve_ghosts_for, _would_be_link_count
from .read import _read_note
from .serialize import _body_hash, _json, _parse_capture_source, _render

logger = logging.getLogger("life-os.wiki.service")


def _refresh_indexes(note: Note) -> None:
    """Re-sync the disposable secondary indexes for ONE note from its current state:
    the title/alias→id resolver (wiki_aliases), the outbound edges (wiki_links),
    ghost auto-resolution, and the FTS5 full-text row. Idempotent — derived purely
    from ``note``, never partial. These are the 4 post-write steps that must run on
    EVERY path that makes a note's content current: a normal write (``_commit_note``)
    AND a reindex-rebuild (reader/reindex.py, when the md changed out-of-band) — so
    wiki_search + backlinks never go stale relative to the md (WIKI-REINDEX-FTS #68).

    NOTE this is the index-only half — it does NOT write the md or the cache row
    (those are write-specific: _commit_note does the md+cache, reindex does its own
    cache upsert). Call it AFTER the cache row is current.
    """
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
        capture_source=capture_source, folder=note.folder,
    )
    # B2/B4/C1 — refresh the disposable secondary indexes (resolver + edges + ghosts +
    # FTS) for this note. Shared with reindex-rebuild via _refresh_indexes (#68, DRY).
    _refresh_indexes(note)
    return sha


# --------------------------------------------------------------------------- #
# WIKI-WRITE-FEEDBACK (#35) — capture WHY a human overrode an AGENT-written note #
# --------------------------------------------------------------------------- #
def _override_feedback_detail(note_id: int, op: Op, original_title: str) -> str | None:
    """Return an op_log ``detail`` JSON string carrying the override feedback, IFF this
    op is a human override of an AGENT-written note AND the human supplied feedback.
    Else None (→ a normal op_log row with no detail).

    Gate (the "agent learns" point):
      - op.actor must be 'human' (a human is doing the override). An agent edit/delete
        is not feedback-to-an-agent.
      - the note's MOST-RECENT PRIOR op actor must be != 'human' (mcp:writer / mcp:reader
        / agent) — i.e. the thing being overridden was agent-written. A human overriding
        their own note is NOT feedback. (Decided: the FIRST human override of agent work
        is the signal; a 2nd human edit's prior op is human → not captured — logged to
        ## Assumptions.)
      - feedback must be present in the payload (reason set). A silent override (no reason)
        → None (honest: no feedback row).

    detail shape: ``{"feedback": {"reason", "text"}, "originalTitle", "overrideKind"}``
    — originalTitle snapshotted here so it survives a delete (the note row is gone after).
    """
    if op.actor != "human":
        return None
    fb = op.payload.get("feedback")
    if not fb or not fb.get("reason"):
        return None
    prior = wiki_store.latest_op_for_note(note_id)
    if prior is None or prior["actor"] == "human":
        return None  # no prior op, or the note was last touched by a human → not agent feedback
    override_kind = "delete" if op.kind == "delete" else "edit"
    return _json({
        "feedback": {"reason": fb["reason"], "text": fb.get("text")},
        "originalTitle": original_title,
        "overrideKind": override_kind,
    })


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
        noteType=inp.noteType, trustTier=inp.trustTier, author=inp.author,  # #45: honor input (was hardcoded "verified")
        tags=inp.tags, content=inp.content, folder=inp.folder, created=now, updated=now,
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
    new_folder = inp.folder if inp.folder is not None else existing.folder

    new_hash = _body_hash(new_content)
    fm_unchanged = (
        new_title == existing.title and new_status == existing.status
        and new_note_type == existing.noteType and new_trust == existing.trustTier
        and new_aliases == existing.aliases and new_tags == existing.tags
        and new_folder == existing.folder  # W-Explorer: a move IS a change (not a no-op touch)
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
        tags=new_tags, content=new_content, folder=new_folder,
        created=existing.created, updated=now, contentHash=new_hash,
    )
    # captureSource is provenance — preserve it across edits (read from the md the
    # note was last written with). A refine/edit never changes where it was captured.
    cap = _parse_capture_source(wiki_store.read_note_file(note_id) or "")
    op_kind = op.payload.get("op_kind", "edit")  # refine reuses this path (C6)
    # #35: capture override-feedback BEFORE _commit_note appends this op (latest_op_for_note
    # must read the PRIOR op). original_title = the title BEFORE the edit (override-time).
    feedback_detail = _override_feedback_detail(note_id, op, existing.title)
    sha = _commit_note(note, f"{op_kind} wiki note {note_id}", capture_source=cap)
    wiki_store.append_op(op_id=op.op_id, kind=op_kind, note_id=note_id,
                         actor=op.actor, ts=now, commit_sha=sha, detail=feedback_detail)
    return note


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
    # #35: capture override-feedback BEFORE the delete (latest_op_for_note reads the
    # PRIOR op; original_title snapshotted from `existing` so it survives the delete).
    feedback_detail = _override_feedback_detail(note_id, op, existing.title)
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
                         actor=op.actor, ts=_now_iso(), commit_sha=sha,
                         detail=feedback_detail)


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
