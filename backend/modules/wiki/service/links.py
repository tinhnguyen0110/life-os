"""modules/wiki/service/links.py — wikilink parser + edge derivation (B1/B2/B4).

Parses ``[[...]]`` wikilinks from a note body, resolves each to an id (or a ghost),
and persists the fresh outbound edge set on every write. Also auto-resolves ghosts
when a note titled like a prior ghost target appears, and computes the would-be link
count for the refine ≥1-link gate."""

from __future__ import annotations

import logging
import re
from typing import Any

from .. import store as wiki_store
from ..schema import Note

logger = logging.getLogger("life-os.wiki.service")

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


def _resolve_ghosts_for(note: Note) -> None:
    """Flip any ghost edge whose ``target_title`` matches this note's title or an
    alias (case-insensitive) to resolved → ``target_id = note.id`` (B4). Runs after
    the alias index refresh so the new/renamed note is already resolvable. This is
    what makes a `[[Atomicity principle]]` ghost auto-resolve the moment a note
    titled "Atomicity principle" is created."""
    titles = {t for t in ({note.title, *note.aliases}) if t and t.strip()}
    for t in titles:
        wiki_store.resolve_ghosts_to(t, note.id)


def _would_be_link_count(note_id: int, new_body: str) -> int:
    """Compute the link count the note WOULD have after a refine edit, WITHOUT
    writing (C6 gate). = outbound links parsed from the new body (resolved or
    ghost, both count as authored links) + existing resolved inbound edges."""
    outbound = len(parse_wikilinks(new_body))
    inbound = len(wiki_store.links_to(note_id, resolved_only=True))
    return outbound + inbound
