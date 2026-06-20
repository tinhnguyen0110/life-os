"""modules/wiki/reader/note_view.py — wiki_get modes (WIKI-RETRIEVAL-2 #21).

Transform a resolved Note into a mode-specific view so an agent reads structure cheaply, NOT the
full 6KB body every time:
  - ``full``    (DEFAULT, backward-compat) — the whole note (note.model_dump()), UNCHANGED.
  - ``outline`` — the heading structure (## ToC) + a 1-line preview/section + note metadata
    (kind/status/folder/tags). NO body. (outline → spot the chapter → get that section.)
  - ``section`` (+ ``heading``) — ONLY that section's content (from the heading to the next
    same-or-higher heading). A 6KB note → ~500 chars.

The SAME fn backs REST /wiki/notes/{id} and the MCP wiki_get_note → byte-identical (#24).
"""

from __future__ import annotations

import re
from typing import Any

from ..schema import Note

# A markdown ATX heading line: 1–6 '#' + a space + text. (Setext '===' underlines not supported —
# the vault writes ATX.) Captures (level, text).
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def _meta(note: Note) -> dict[str, Any]:
    """The note's navigation metadata (no body) — same fields the tree note-stub exposes + tags."""
    return {"kind": note.noteType, "status": note.status,
            "folder": note.folder, "tags": list(note.tags)}


def _parse_headings(body: str) -> list[dict[str, Any]]:
    """Extract ATX headings → ``[{level, text, line}]`` in document order (line = 0-based)."""
    out: list[dict[str, Any]] = []
    for i, line in enumerate((body or "").splitlines()):
        m = _HEADING_RE.match(line)
        if m:
            out.append({"level": len(m.group(1)), "text": m.group(2).strip(), "line": i})
    return out


def _first_nonblank_after(lines: list[str], start: int) -> str | None:
    """The first non-blank, non-heading line after index ``start`` (a 1-line section preview)."""
    for ln in lines[start + 1:]:
        s = ln.strip()
        if s and not _HEADING_RE.match(ln):
            return s
        if _HEADING_RE.match(ln):  # next heading reached → this section has no body line
            return None
    return None


def _section(body: str, heading: str) -> dict[str, Any] | None:
    """The content of the section whose heading text == ``heading`` (case-insensitive), from that
    heading line UP TO the next same-or-higher-level heading (exclusive). None if no such heading.
    Returns ``{heading, level, content}`` (content excludes the heading line itself)."""
    lines = (body or "").splitlines()
    target = heading.strip().lower()
    start = None
    start_level = 0
    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line)
        if m and m.group(2).strip().lower() == target:
            start, start_level = i, len(m.group(1))
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        m = _HEADING_RE.match(lines[j])
        if m and len(m.group(1)) <= start_level:  # next same-or-higher heading → section ends
            end = j
            break
    content = "\n".join(lines[start + 1:end]).strip()
    return {"heading": lines[start].lstrip("#").strip(), "level": start_level, "content": content}


def note_view(note: Note, mode: str = "full", heading: str | None = None) -> dict[str, Any]:
    """Render a Note in the requested mode (#21). Returns:
      - full    → the bare ``note.model_dump()`` UNCHANGED (backward-compat — the pre-#21 shape;
                  the FE/agent that read the full note still get the exact same dict, no wrapper).
      - outline → {mode:'outline', title, meta:{kind,status,folder,tags}, headings:[{level,text,
                   line,preview}]}. NO body.
      - section → {mode:'section', heading, section:{heading,level,content}|null,
                  sectionFound:bool}. A missing/unknown ``heading`` → sectionFound:false (honest,
                  not a crash). NB ``sectionFound`` (not ``found``) so it doesn't collide with the
                  MCP note-existence ``found`` wrapper when this view is merged into it.
    An unknown mode falls back to ``full`` (lenient). The mode is encoded in outline/section's
    own ``mode`` field; ``full`` stays the bare note (so existing callers are unaffected)."""
    m = (mode or "full").strip().lower()
    if m == "outline":
        lines = (note.content or "").splitlines()
        headings = []
        for h in _parse_headings(note.content):
            headings.append({**h, "preview": _first_nonblank_after(lines, h["line"])})
        return {"mode": "outline", "title": note.title, "meta": _meta(note), "headings": headings}
    if m == "section":
        if not heading:
            return {"mode": "section", "heading": heading, "section": None, "sectionFound": False}
        sec = _section(note.content, heading)
        return {"mode": "section", "heading": heading, "section": sec, "sectionFound": sec is not None}
    # full (default / unknown) — the whole note dict, UNCHANGED (backward-compat: bare, no wrapper).
    return note.model_dump()
