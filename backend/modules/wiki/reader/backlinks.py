"""modules/wiki/reader/backlinks.py — backlinks (B3) + FTS search (C1) + unlinked (C2).

``backlinks`` assembles linked/unlinked/outbound for a note; ``search`` is the FTS5
full-text query; ``unlinked_mentions`` finds plain-text mentions that aren't links."""

from __future__ import annotations

import json
from typing import Any

from .. import store as wiki_store
from ._helpers import _mention_snippet, _title_of


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

    return {"linked": linked, "unlinked": unlinked_mentions(note_id, exclude=seen_sources),
            "outbound": outbound}


def search(q: str, limit: int = 30) -> list[dict[str, Any]]:
    """Full-text search → ``[{id, title, snippet, status}]`` ranked by FTS5 rank
    (C1). Empty/bad query → ``[]`` (never raises — store sanitizes)."""
    return [
        {"id": r["id"], "title": r["title"], "snippet": r["snippet"], "status": r["status"]}
        for r in wiki_store.fts_search(q, limit=limit)
    ]


def unlinked_mentions(note_id: int, *, exclude: set[int] | None = None,
                      limit: int = 20) -> list[dict[str, Any]]:
    """Notes whose body mentions this note's title/alias as plain TEXT but DON'T
    link it (C2 — the W1b-deferred piece, now via FTS5). Excludes the note itself
    + any already-linked source (``exclude`` = the resolved linked-mention set) +
    notes that already link it via an edge. Capped at ``limit`` by rank.

    Returns ``[{id, title, snippet}]``. Empty if the note has no title/aliases."""
    row = wiki_store.get_note_cache(note_id)
    if row is None:
        return []
    phrases = [row["title"]] if row["title"] else []
    try:
        phrases.extend(a for a in json.loads(row["aliases"]) if a)
    except (json.JSONDecodeError, TypeError):
        pass
    if not phrases:
        return []

    excluded: set[int] = {int(note_id)}
    if exclude:
        excluded |= {int(e) for e in exclude}
    # Also exclude any note that ALREADY links this one (resolved inbound edge) —
    # a linked mention is not an UNlinked mention.
    excluded |= {r["source_id"] for r in wiki_store.links_to(note_id, resolved_only=True)}

    out: list[dict[str, Any]] = []
    for r in wiki_store.fts_phrase_search(phrases, limit=limit + len(excluded) + 5):
        sid = r["id"]
        if sid in excluded:
            continue
        out.append({"id": sid, "title": _title_of(sid), "snippet": r["snippet"]})
        if len(out) >= limit:
            break
    return out
