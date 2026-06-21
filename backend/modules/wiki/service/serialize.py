"""modules/wiki/service/serialize.py — frontmatter render / parse.

The note md file is the source of truth; these turn a ``Note`` into its ``---``-
fenced document and back. ``contentHash`` is derived from the body (never authored);
``captureSource`` is provenance authored once at capture. All pure — no queue, no db."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import yaml

from ..schema import Note


def _body_hash(body: str) -> str:
    """sha256 of the BODY only (A1) — a frontmatter-only edit (title/status) is
    detectable separately from a body edit. Derived cache, never authored."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


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
        "folder": note.folder,
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


class FrontmatterError(ValueError):
    """A `---`-fenced frontmatter block that is present but UNPARSEABLE (bad YAML, or YAML that
    isn't a mapping). Distinct from "no frontmatter at all" (a plain-body doc) — the import path
    turns THIS into an agent-readable error, but treats no-frontmatter as a plain note."""


def extract_frontmatter(content: str) -> tuple[dict[str, Any] | None, str]:
    """Split a note md document into (frontmatter-dict, body). The SINGLE YAML-frontmatter parse —
    reused by ``_parse`` (note md → Note) AND the #93 import path (md → NoteCreateInput).

    - No leading ``---`` fence → ``(None, <the whole content as body>)`` — a plain-body doc.
    - A ``---`` fence that is malformed (no closing fence / bad YAML / non-mapping) → raise
      ``FrontmatterError`` (the import surfaces an agent-readable error; never a junk note).
    - A valid fence → ``(fm_dict, body)``.
    """
    text = content.lstrip("﻿")
    if not text.startswith("---"):
        return None, text  # plain-body doc (no frontmatter)
    parts = text[len("---"):].split("\n---", 1)
    if len(parts) < 2:
        raise FrontmatterError("frontmatter opened with '---' but never closed with a '---' fence")
    fm_block, body = parts[0], parts[1].lstrip("\n")
    try:
        fm = yaml.safe_load(fm_block)
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"frontmatter is not valid YAML: {exc}") from exc
    if not isinstance(fm, dict):
        raise FrontmatterError("frontmatter must be a YAML mapping (key: value), not a scalar/list")
    return fm, body


def _parse(content: str, note_id: int) -> Note | None:
    """Parse a note md document → Note (contentHash recomputed from body), or None
    if malformed. ``note_id`` is the filename id (authoritative over frontmatter)."""
    try:
        fm, body = extract_frontmatter(content)
    except FrontmatterError:
        return None  # _parse keeps its None-on-malformed contract (the cache reindex path)
    if fm is None:
        return None  # a stored note md always has frontmatter; absent → malformed for _parse
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
            # W-Explorer: absent folder (a pre-folder note) → "" (root) — the
            # migration-safe default; an existing note renders identically.
            folder=fm.get("folder") or "",
            created=fm["created"],
            updated=fm["updated"],
            contentHash=_body_hash(body),
        )
    except Exception:  # missing/invalid field → malformed
        return None
