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
    sha = _commit_note(note, f"{op_kind} wiki note {note_id}", capture_source=cap)
    wiki_store.append_op(op_id=op.op_id, kind=op_kind, note_id=note_id,
                         actor=op.actor, ts=now, commit_sha=sha)
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
