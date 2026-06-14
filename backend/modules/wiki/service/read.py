"""modules/wiki/service/read.py — read path (no queue; reads don't mutate).

Reads a note from its md file (source of truth), and follows a D6 redirect
tombstone so a cited-then-merged note resolves to the merge target instead of 404."""

from __future__ import annotations

from .. import store as wiki_store
from ..schema import Note
from .serialize import _parse


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
