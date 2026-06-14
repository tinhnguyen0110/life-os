"""modules/wiki/store/files.py — note md file read/write/delete.

Thin pass-through to the shared md_store (md+git = source of truth). Each write is
one atomic git commit. The path is derived from the note id (immutable, D1)."""

from __future__ import annotations

from store import md_store

from ._base import note_rel_path


def write_note_file(note_id: int, content: str, message: str) -> str:
    """Write the note md file via md_store (atomic + 1 git commit). Returns sha."""
    return md_store.write_file(note_rel_path(note_id), content, message)


def read_note_file(note_id: int) -> str | None:
    """Raw md file content, or None if the file is absent."""
    return md_store.read(note_rel_path(note_id))


def delete_note_file(note_id: int, message: str) -> str | None:
    """Delete the note md file via md_store (1 commit). Returns sha, or None if
    the file did not exist."""
    return md_store.delete_file(note_rel_path(note_id), message)
