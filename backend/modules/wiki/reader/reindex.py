"""modules/wiki/reader/reindex.py — the reindex SEAM (A5 / W1c attach point).

Reconciles the ``wiki_notes`` cache row + ``content_hash`` against the md file (the
source of truth). Real reconciliation now (drop stale / rebuild / no-op); the full
FTS5 + link-graph rebuild hooks in HERE when needed. NOT a stub-lie."""

from __future__ import annotations

import json
import logging
from typing import Any

from .. import store as wiki_store

logger = logging.getLogger("life-os.wiki.reader")


def reindex_note(note_id: int) -> dict[str, Any]:
    """Reconcile the ``wiki_notes`` cache row against the md file (source of truth).

    The reindex SEAM (A5 / W1c attach point). In W1a it keeps the cache row +
    ``content_hash`` consistent with the on-disk md file:
      - md file absent → drop the stale cache row (note was deleted out-of-band).
      - md present, cache row missing or its ``content_hash`` stale → rebuild the
        row from the parsed file.
      - md present, cache already matches → no-op (touch ≠ rewrite).

    Returns a status dict ``{noteId, action}`` where action ∈
    ``missing_dropped | rebuilt | unchanged``. Full FTS5 + link-graph reindex is
    W1c — it hooks in HERE (after the cache reconcile) when those tables exist.
    """
    # Lazy import avoids a service<->reader import cycle; the parse lives in service.
    from .. import service as wiki_service

    raw = wiki_store.read_note_file(note_id)
    cache_row = wiki_store.get_note_cache(note_id)

    if raw is None:
        # Source file gone — the cache must not keep a phantom row.
        if cache_row is not None:
            wiki_store.delete_note_cache(note_id)
            logger.info("reindex: note %s md missing → dropped stale cache row", note_id)
            return {"noteId": note_id, "action": "missing_dropped"}
        return {"noteId": note_id, "action": "unchanged"}

    note = wiki_service._parse(raw, note_id)
    if note is None:
        # Malformed file — leave cache as-is, report (don't silently 'fix').
        logger.warning("reindex: note %s md malformed → cache left unchanged", note_id)
        return {"noteId": note_id, "action": "unchanged"}

    if cache_row is not None and cache_row["content_hash"] == note.contentHash and (
        cache_row["title"] == note.title
        and cache_row["status"] == note.status
        and cache_row["note_type"] == note.noteType
        and cache_row["trust_tier"] == note.trustTier
        and cache_row["author"] == note.author
        and cache_row["aliases"] == json.dumps(note.aliases, ensure_ascii=False)
        and cache_row["tags"] == json.dumps(note.tags, ensure_ascii=False)
    ):
        return {"noteId": note_id, "action": "unchanged"}

    # Cache missing or stale → rebuild from the parsed file (source of truth wins).
    cap = wiki_service._parse_capture_source(raw)  # preserve provenance on rebuild
    wiki_store.upsert_note_cache(
        note_id=note_id, title=note.title,
        aliases_json=json.dumps(note.aliases, ensure_ascii=False),
        status=note.status, note_type=note.noteType, trust_tier=note.trustTier,
        author=note.author, tags_json=json.dumps(note.tags, ensure_ascii=False),
        content_hash=note.contentHash, created=note.created, updated=note.updated,
        capture_source=cap,
    )
    logger.info("reindex: note %s cache rebuilt from md", note_id)
    return {"noteId": note_id, "action": "rebuilt"}
