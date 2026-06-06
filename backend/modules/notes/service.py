"""modules/notes/service.py — notes CRUD over md_store (Sprint 6, SPEC §S10).

Each note is `notes/<id>.md`: YAML front-matter (id/title/tags/pinned/attach/
createdAt/updatedAt) + markdown body after the closing `---`. Every write/delete
= one git commit (md_store). list_notes fail-opens on a malformed note (skip +
warn) — the stale-store lesson (cf. projects status.md, finance).

Logic (architect block, verbatim):
  - id = slug(title)-<6hex>, fallback note-<6hex>.
  - create: createdAt=updatedAt=now. update: preserve createdAt, bump updatedAt.
  - sort: pinned-first (pinned desc) → then updatedAt desc.
  - list filters: q = ci substring over title+body+joined-tags; tag = exact;
    attached = "type" or "type:ref"; pinned = bool.
  - attach free-form (no cross-module validation); ref required when type≠none.
"""

from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timezone

import yaml

from core.config import settings
from store import md_store

from .schema import Attach, Note, NoteInput

logger = logging.getLogger("life-os.notes.service")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s or "note"


def _new_id(title: str) -> str:
    return f"{_slug(title)}-{secrets.token_hex(3)}"


def _rel(note_id: str) -> str:
    return f"notes/{note_id}.md"


# --------------------------------------------------------------------------- #
# Serialize / parse                                                             #
# --------------------------------------------------------------------------- #
def _render(note: Note) -> str:
    """Note → `---\\n<front-matter>\\n---\\n<body>` document."""
    fm = {
        "id": note.id, "title": note.title, "tags": note.tags, "pinned": note.pinned,
        "attach": {"type": note.attach.type, "ref": note.attach.ref},
        "createdAt": note.createdAt, "updatedAt": note.updatedAt,
    }
    block = yaml.safe_dump(fm, sort_keys=True, allow_unicode=True).strip()
    return f"---\n{block}\n---\n{note.body}"


def _parse(content: str) -> Note | None:
    """Parse a note document → Note, or None if malformed (caller skips + warns)."""
    text = content.lstrip("﻿")
    if not text.startswith("---"):
        return None
    parts = text[len("---"):].split("\n---", 1)
    if len(parts) < 2:
        return None
    fm_block, body = parts[0], parts[1].lstrip("\n")
    try:
        fm = yaml.safe_load(fm_block)
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict):
        return None
    raw_attach = fm.get("attach") or {}
    if not isinstance(raw_attach, dict):
        raw_attach = {}
    try:
        return Note(
            id=fm["id"], title=fm["title"], body=body,
            tags=fm.get("tags") or [],
            pinned=bool(fm.get("pinned", False)),
            attach=Attach(type=raw_attach.get("type", "none"), ref=raw_attach.get("ref")),
            createdAt=fm["createdAt"], updatedAt=fm["updatedAt"],
        )
    except Exception:  # missing/invalid field → malformed, skip
        return None


def _note_ids() -> list[str]:
    """ids of all notes/<id>.md files. [] if dir absent."""
    notes_dir = settings.notes_dir
    if not notes_dir.is_dir():
        return []
    return sorted(p.stem for p in notes_dir.glob("*.md"))


# --------------------------------------------------------------------------- #
# CRUD                                                                          #
# --------------------------------------------------------------------------- #
def get_note(note_id: str) -> Note | None:
    """One note, or None if absent/malformed."""
    content = md_store.read(_rel(note_id))
    if content is None:
        return None
    return _parse(content)


def create_note(body: NoteInput) -> Note:
    """Create a note (server-set id + timestamps). One git commit. Returns it."""
    now = _now_iso()
    note = Note(
        id=_new_id(body.title), title=body.title, body=body.body, tags=body.tags,
        pinned=body.pinned, attach=body.attach, createdAt=now, updatedAt=now,
    )
    md_store.write_file(_rel(note.id), _render(note), f"create note {note.id}")
    return note


def update_note(note_id: str, body: NoteInput) -> Note | None:
    """Update a note in place (preserve createdAt, bump updatedAt). None if absent."""
    existing = get_note(note_id)
    if existing is None:
        return None
    note = Note(
        id=note_id, title=body.title, body=body.body, tags=body.tags,
        pinned=body.pinned, attach=body.attach,
        createdAt=existing.createdAt, updatedAt=_now_iso(),
    )
    md_store.write_file(_rel(note_id), _render(note), f"update note {note_id}")
    return note


def delete_note(note_id: str) -> bool:
    """Delete a note (one git commit). True if it existed, False if absent."""
    if md_store.read(_rel(note_id)) is None:
        return False
    md_store.delete_file(_rel(note_id), f"delete note {note_id}")
    return True


# --------------------------------------------------------------------------- #
# List + filters                                                                #
# --------------------------------------------------------------------------- #
def _matches_attached(note: Note, attached: str) -> bool:
    """`attached` = "type" or "type:ref"."""
    if ":" in attached:
        atype, _, ref = attached.partition(":")
        return note.attach.type == atype and (note.attach.ref or "") == ref
    return note.attach.type == attached


def list_notes(
    q: str | None = None,
    tag: str | None = None,
    attached: str | None = None,
    pinned: bool | None = None,
) -> tuple[list[Note], list[str]]:
    """Notes matching the filters; pinned-first then newest updatedAt; + warnings.

    Fail-open: a malformed note file is skipped + warned, never crashes the list.
    """
    notes: list[Note] = []
    warnings: list[str] = []
    for note_id in _note_ids():
        content = md_store.read(_rel(note_id))
        if content is None:
            continue
        note = _parse(content)
        if note is None:
            warnings.append(f"note {note_id!r} malformed — skipped")
            continue
        notes.append(note)

    if q:
        ql = q.lower()
        notes = [n for n in notes if ql in f"{n.title}\n{n.body}\n{' '.join(n.tags)}".lower()]
    if tag:
        notes = [n for n in notes if tag in n.tags]
    if attached:
        notes = [n for n in notes if _matches_attached(n, attached)]
    if pinned is not None:
        notes = [n for n in notes if n.pinned is pinned]

    # pinned-first (pinned desc) → then updatedAt desc.
    notes.sort(key=lambda n: (n.pinned, n.updatedAt), reverse=True)
    return notes, warnings
