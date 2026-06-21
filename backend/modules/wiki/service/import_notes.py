"""modules/wiki/service/import_notes.py — #93 wiki import (.md / .txt → note).

Import an existing .md (YAML frontmatter) or .txt (plain body) into the wiki, REUSING the
existing machinery: ``serialize.extract_frontmatter`` (the ONE YAML parser) + ``crud.create_note``
→ ``_apply_create`` (1 git commit, [[link]] resolution, cache). NO re-implemented parsing, NO
queue/apply bypass.

Pure + testable: ``import_files([(filename, content), ...], actor)`` → per-file result rows. A bad
file (malformed frontmatter / empty / wrong extension / bad status enum) → an agent-readable error
row, the OTHER files still import (batch never fails wholesale). DECIDED + logged (## Assumptions):
per-file results, not all-or-nothing.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from core.agent_errors import ErrorCode, agent_error
from pydantic import ValidationError

from ..schema import NoteCreateInput
from .crud import create_note
from .serialize import FrontmatterError, extract_frontmatter

logger = logging.getLogger("life-os.wiki.import")

# md-first (user): only .md / .txt. Anything else → an agent-readable wrong-extension error.
_ALLOWED_EXT = {".md", ".txt"}
_MAX_BYTES = 1_000_000  # 1 MB per file — a sane import cap (oversized → agent-error, not OOM)

# frontmatter keys we map into NoteCreateInput (others ignored — forward-compat).
_FM_FIELDS = ("title", "tags", "folder", "status", "trustTier", "noteType", "author")


def _err_row(filename: str, code: ErrorCode, message: str, hint: str) -> dict[str, Any]:
    """A per-file failure result carrying the agent-readable error (NOT a created note)."""
    return {
        "filename": filename, "ok": False, "noteId": None, "title": None,
        "error": agent_error(code, message, hint)["error"],
    }


def _title_from_txt(body: str, filename: str) -> str:
    """A .txt has no frontmatter → title = the first non-empty line, else the filename stem."""
    for line in body.splitlines():
        s = line.strip().lstrip("#").strip()  # tolerate a leading markdown '# heading'
        if s:
            return s[:200]
    return os.path.splitext(os.path.basename(filename))[0] or "untitled"


def _build_input(filename: str, content: str) -> NoteCreateInput:
    """Parse ONE file → a NoteCreateInput (raises FrontmatterError / ValidationError / ValueError on
    a bad file — the caller maps that to an agent-error row).

    - .md (or content with a `---` fence): frontmatter → fields, body → content; [[links]] in the
      body resolve later in _apply_create. Missing frontmatter keys → NoteCreateInput defaults; the
      title falls back to the first body line / filename if frontmatter has none.
    - .txt (no frontmatter): body → content, title = first non-empty line / filename, status fleeting.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext and ext not in _ALLOWED_EXT:
        raise ValueError(f"unsupported file type '{ext}' — only .md and .txt are supported")
    if not content.strip():
        raise ValueError("file is empty — nothing to import")

    fm, body = extract_frontmatter(content)  # raises FrontmatterError on a malformed `---` block
    if fm is None:
        # plain-body doc (.txt, or a .md with no frontmatter) — title from first line / filename.
        return NoteCreateInput(content=body, title=_title_from_txt(body, filename),
                               captureSource="import")
    # .md WITH frontmatter — map the known keys; absent keys fall to NoteCreateInput defaults.
    fields: dict[str, Any] = {k: fm[k] for k in _FM_FIELDS if k in fm and fm[k] is not None}
    title = fields.get("title") or _title_from_txt(body, filename)  # frontmatter title else fallback
    fields["title"] = title
    fields["content"] = body
    fields["captureSource"] = "import"
    # NoteCreateInput Literal-validates status/noteType/trustTier (bad value → ValidationError →
    # the caller's agent-error row) + normalizes folder. extra="forbid" → an unknown mapped key 422s,
    # but we only pass _FM_FIELDS (known), so a junk frontmatter key is simply ignored above.
    return NoteCreateInput(**fields)


def import_one(filename: str, content: str, actor: str = "human") -> dict[str, Any]:
    """Import ONE file → a result row. Reuses create_note (→ _apply_create: 1 commit, link-resolve,
    cache). A bad file → an agent-error row (NO note created), never a raise to the caller."""
    if len(content.encode("utf-8")) > _MAX_BYTES:
        return _err_row(filename, "INVALID_INPUT",
                        f"file too large ({len(content.encode('utf-8'))} bytes; max {_MAX_BYTES})",
                        "split the file or remove non-text content — only small .md/.txt import")
    try:
        inp = _build_input(filename, content)
    except FrontmatterError as exc:
        return _err_row(filename, "INVALID_INPUT", f"bad frontmatter in {filename}: {exc}",
                        "frontmatter must be valid YAML between two '---' fences (or omit it)")
    except ValidationError as exc:
        # a Literal field (status/noteType/trustTier) out of range → honest agent-error, NOT a
        # silent default (the file claimed a value we can't honor; surface it).
        errs = exc.errors()
        first: dict[str, Any] = dict(errs[0]) if errs else {}
        loc = ".".join(str(p) for p in first.get("loc", []))
        return _err_row(filename, "INVALID_INPUT",
                        f"invalid field in {filename}: {loc}: {first.get('msg', 'invalid')}",
                        "fix the frontmatter field (e.g. status ∈ fleeting|developing|evergreen)")
    except ValueError as exc:  # empty / unsupported-ext / our own raises
        return _err_row(filename, "INVALID_INPUT", str(exc),
                        "import only non-empty .md or .txt files")
    try:
        note = create_note(inp, actor=actor)  # the EXISTING path — 1 commit + [[link]] resolution
    except Exception as exc:  # noqa: BLE001 — a create failure is per-file, not a batch-killer
        logger.error("wiki import: create failed for %s: %s", filename, exc)
        return _err_row(filename, "UPSTREAM_DOWN", f"could not create the note from {filename}: "
                        f"{type(exc).__name__}", "retry; if it persists the wiki store may be locked")
    return {"filename": filename, "ok": True, "noteId": note.id, "title": note.title, "error": None}


def import_files(files: list[tuple[str, str]], actor: str = "human") -> dict[str, Any]:
    """Import a batch of (filename, content) → ``{imported: [result rows], createdCount}``. Per-file
    fail-soft: one bad file yields its agent-error row, the rest still import (batch never fails)."""
    rows = [import_one(fn, content, actor=actor) for fn, content in files]
    created = sum(1 for r in rows if r["ok"])
    return {"imported": rows, "createdCount": created}
