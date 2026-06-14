"""modules/wiki/reader/_helpers.py — small shared read-side helpers.

Pure read helpers used across the reader package: title lookup, body-snippet
extraction (frontmatter-stripped), mention-snippet around a [[..]] link, and the
defensive capture-source accessor. No shared mutable state — reads never mutate."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .. import store as wiki_store

_SNIPPET_PAD = 60  # chars of context on each side of a [[..]] mention


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _snippet_of_body(note_id: int, length: int = 140) -> str:
    """First ``length`` chars of a note's body (frontmatter stripped) — for inbox
    rawContent + activity. Cheap at M1 vault sizes."""
    body = wiki_store.read_note_file(note_id) or ""
    if body.startswith("---"):
        parts = body[len("---"):].split("\n---", 1)
        if len(parts) == 2:
            body = parts[1].lstrip("\n")
    body = body.strip()
    return body if len(body) <= length else body[:length].rstrip() + "…"


def _capture_source(row: Any) -> str:
    """The note's capture source (C5). W1c-T3 adds a ``capture_source`` cache
    column; until then default ``quick_add``. Reads defensively so this reader
    works whether or not the column exists yet."""
    try:
        cs = row["capture_source"]
        return cs or "quick_add"
    except (IndexError, KeyError):
        return "quick_add"
