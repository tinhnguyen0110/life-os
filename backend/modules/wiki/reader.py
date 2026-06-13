"""modules/wiki/reader.py — wiki read-side (Sprint W1a-T3).

Read-only derived views over the wiki cache + op_log. Reads never mutate and never
go through the changes-queue.

W1a-T3 surface:
  - ``recent_ops(limit)`` — the episodic/replay activity feed (reads ``wiki_op_log``,
    newest-first). W1's "recent activity" panel reads this later.
  - ``reindex_note(note_id)`` — the reindex SEAM. In W1a it reconciles the
    ``wiki_notes`` cache row + ``content_hash`` against the md file (the source of
    truth) — e.g. after an out-of-band file edit, or to rebuild a dropped cache
    row. The FULL reindex (FTS5 index + link-graph rebuild) is W1c; this seam is
    where that work attaches. It is NOT a stub-lie: it does real cache
    reconciliation now and returns an honest status of what it did.

Overview stats / inbox / ego-graph readers are W1c.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from . import store as wiki_store

logger = logging.getLogger("life-os.wiki.reader")


def recent_ops(limit: int = 50) -> list[dict[str, Any]]:
    """Most-recent op_log entries (newest-first), as plain dicts for the API/feed.

    Each entry: ``{seq, op_id, kind, noteId, actor, ts, commitSha, detail}``.
    ``kind`` ∈ create|edit|delete (W1a subset; links/refine/merge add later).
    """
    rows = wiki_store.recent_ops(limit=limit)
    return [
        {
            "seq": r["seq"],
            "op_id": r["op_id"],
            "kind": r["kind"],
            "noteId": r["note_id"],
            "actor": r["actor"],
            "ts": r["ts"],
            "commitSha": r["commit_sha"],
            "detail": r["detail"],
        }
        for r in rows
    ]


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
    from . import service as wiki_service

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
    wiki_store.upsert_note_cache(
        note_id=note_id, title=note.title,
        aliases_json=json.dumps(note.aliases, ensure_ascii=False),
        status=note.status, note_type=note.noteType, trust_tier=note.trustTier,
        author=note.author, tags_json=json.dumps(note.tags, ensure_ascii=False),
        content_hash=note.contentHash, created=note.created, updated=note.updated,
    )
    logger.info("reindex: note %s cache rebuilt from md", note_id)
    return {"noteId": note_id, "action": "rebuilt"}


# --------------------------------------------------------------------------- #
# W1b — backlinks (B3)                                                          #
# --------------------------------------------------------------------------- #
_SNIPPET_PAD = 60  # chars of context on each side of a [[..]] mention


def _title_of(note_id: int) -> str:
    row = wiki_store.get_note_cache(note_id)
    return row["title"] if row is not None else ""


def _mention_snippet(source_id: int, target_id: int) -> str:
    """A short body excerpt around where ``source`` links ``target`` — matching
    EITHER link form: by id (``[[47]]``/``[[47|..]]``) OR by the target's title or
    an alias (``[[Title]]``/``[[Title|..]]``), case-insensitive. Empty string if
    not locatable. Read from the md body (source of truth); cheap at M1 sizes."""
    import re as _re

    body = wiki_store.read_note_file(source_id) or ""
    # Strip frontmatter so the snippet is body text, not yaml.
    if body.startswith("---"):
        parts = body[len("---"):].split("\n---", 1)
        if len(parts) == 2:
            body = parts[1].lstrip("\n")

    # Build the set of targets that resolve to this note: its id + title + aliases.
    targets: list[str] = [str(int(target_id))]
    row = wiki_store.get_note_cache(target_id)
    if row is not None:
        if row["title"]:
            targets.append(row["title"])
        try:
            targets.extend(a for a in json.loads(row["aliases"]) if a)
        except (json.JSONDecodeError, TypeError):
            pass
    alt = "|".join(_re.escape(t) for t in targets)
    m = _re.search(rf"\[\[\s*(?:{alt})\s*(?:\|[^\[\]]*)?\]\]", body, _re.IGNORECASE)
    if not m:
        return ""
    start = max(0, m.start() - _SNIPPET_PAD)
    end = min(len(body), m.end() + _SNIPPET_PAD)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(body) else ""
    return f"{prefix}{body[start:end].strip()}{suffix}"


def backlinks(note_id: int) -> dict[str, Any]:
    """Backlinks for a note (B3) — matches the mock ``data-wiki.js`` shape:

      ``{linked:[{id,title,snippet,anchor?}], unlinked:[{id,title,snippet}],
         outbound:[{id,title,isResolved}|{ghost,isResolved:false}]}``

    - **linked:** resolved inbound edges (other notes' ``[[id]]`` → this note),
      deduped by source note, with a body snippet around the mention. ``anchor``
      (``^block-id``) is W2 — absent in W1b.
    - **unlinked:** plain-text mentions of this title/alias that AREN'T linked →
      **`[]` in W1b** (needs FTS5; populated W1c — shape present, honest-mirror).
    - **outbound:** this note's edges — resolved as ``{id,title,isResolved:true}``,
      ghosts as ``{ghost:<title>, isResolved:false}``.
    """
    # linked — dedup by source note (one row per backlinking note).
    seen_sources: set[int] = set()
    linked: list[dict[str, Any]] = []
    for row in wiki_store.links_to(note_id, resolved_only=True):
        src = row["source_id"]
        if src in seen_sources:
            continue
        seen_sources.add(src)
        linked.append({
            "id": src,
            "title": _title_of(src),
            "snippet": _mention_snippet(src, note_id),
        })

    # outbound — resolved + ghost edges of this note.
    outbound: list[dict[str, Any]] = []
    for row in wiki_store.links_from(note_id):
        if row["is_resolved"] and row["target_id"] is not None:
            outbound.append({
                "id": row["target_id"],
                "title": _title_of(row["target_id"]),
                "isResolved": True,
            })
        else:
            outbound.append({
                "ghost": row["target_title"] or "",
                "isResolved": False,
            })

    return {"linked": linked, "unlinked": [], "outbound": outbound}
