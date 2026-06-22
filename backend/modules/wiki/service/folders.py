"""modules/wiki/service/folders.py — WIKI-WORKDIR W1 (#127): folder lifecycle.

Folders are VIRTUAL path-prefixes; the empty-folder ANCHOR is a ``wiki_folder_meta`` row (design
§3, option B). This module is the create / soft-delete / move-rename surface:
  - create_folder(path, desc) → INSERT the anchor row (a nested empty folder now EXISTS in the tree).
  - delete_folder(path)       → SCOPED soft-delete every note in the subtree (#94 tombstone) + drop
                                 the folder_meta rows for the subtree. Recoverable (notes → trash).
  - move_folder(path, to)     → re-prefix every note under ``path`` → ``to`` + move the meta rows.

🔴 SCOPED (the #72 lesson): every op touches ONLY the named path + its subtree (folder==path OR
folder startswith path + '/'), NEVER a blanket. The note mutations route through the existing
single-writer queue (soft_delete_note / update_note) — git-per-write, one commit each.
"""

from __future__ import annotations

from .. import store as wiki_store
from ..schema import NoteUpdateInput, normalize_folder
from . import crud
from .errors import FolderError


def _subtree_match(folder: str, root: str) -> bool:
    """True if ``folder`` is the root folder itself OR inside its subtree (root + '/' prefix)."""
    return folder == root or folder.startswith(root + "/")


def _live_notes_under(path: str) -> list:
    """LIVE note cache rows whose folder is in the ``path`` subtree (soft-deleted excluded — they
    stay in trash). Each row carries id + folder."""
    out = []
    for row in wiki_store.all_notes(order_by="id"):
        fld = (row["folder"] if "folder" in row.keys() else "") or ""
        if _subtree_match(fld, path):
            out.append(row)
    return out


def create_folder(path: str, desc: str = "") -> dict:
    """#127: create a (possibly NESTED, arbitrary-depth) EMPTY folder by anchoring a
    wiki_folder_meta row at the normalized path. Returns {path, desc, created}. Raises FolderError:
      - INVALID_INPUT if the path normalizes to empty (can't create the root).
      - CONFLICT if the folder already exists (a meta row OR notes already carry the prefix).
    Idempotency choice (frozen): a duplicate is a 409 CONFLICT (not a silent no-op) so the UI/agent
    knows the name is taken."""
    norm = normalize_folder(path)
    if not norm:
        raise FolderError("INVALID_INPUT", "folder path must not be empty (cannot create the root)",
                        hint="POST a non-empty path like 'A/B/C'")
    # already exists? (a meta anchor OR a note carries the prefix)
    if wiki_store.get_folder_meta(norm) is not None:
        raise FolderError("CONFLICT", f"folder {norm!r} already exists",
                        hint="pick a different path or PUT .../meta to describe it")
    if _live_notes_under(norm):
        raise FolderError("CONFLICT", f"folder {norm!r} already exists (has notes)",
                        hint="the folder is already present via its notes")
    wiki_store.create_folder_meta(norm, desc)
    meta = wiki_store.get_folder_meta(norm) or {"desc": ""}
    return {"path": norm, "desc": meta.get("desc", ""), "created": True}


def delete_folder(path: str, actor: str = "human") -> dict:
    """#127: SOFT-delete a folder + its subtree. #94-tombstones every LIVE note under ``path``
    (recoverable — they go to trash) + removes the folder_meta rows for path + descendants. SCOPED
    to exactly that subtree. Returns {folder, deletedNotes:[ids], removedMeta:[paths], warnings:[]}.
    Raises FolderError INVALID_INPUT if path is empty (can't delete the root). honest: a folder with
    no notes + no meta still succeeds ({deletedNotes:[], removedMeta:[]}) — idempotent-ish cleanup.
    Fail-soft per note: a single note's delete error is collected as a warning, not fatal."""
    norm = normalize_folder(path)
    if not norm:
        raise FolderError("INVALID_INPUT", "cannot delete the root folder", hint="pass a sub-path")
    deleted: list[int] = []
    warnings: list[str] = []
    for row in _live_notes_under(norm):
        nid = int(row["id"])
        try:
            crud.soft_delete_note(nid, actor=actor)
            deleted.append(nid)
        except Exception as exc:  # noqa: BLE001 — fail-soft per note; the rest still delete
            warnings.append(f"note {nid}: soft-delete failed ({exc})")
    removed_meta = wiki_store.delete_folder_meta_subtree(norm)
    return {"folder": norm, "deletedNotes": deleted, "removedMeta": removed_meta,
            "warnings": warnings}


def move_folder(path: str, to: str, actor: str = "human") -> dict:
    """#127: rename/move a folder — re-prefix every LIVE note under ``path`` → ``to`` + move the
    folder_meta rows (path→to + descendants). SCOPED to that subtree. Returns
    {from, to, movedNotes:[ids], movedMeta:N, warnings:[]}. Raises FolderError:
      - INVALID_INPUT if path or ``to`` normalizes to empty, or ``to`` is inside ``path`` (can't
        move a folder into its own subtree).
      - CONFLICT if ``to`` already exists as a DIFFERENT folder (a meta row or notes), to avoid a
        silent merge.
    Fail-soft per note: a single note's update error → a warning, the rest still move."""
    src = normalize_folder(path)
    dst = normalize_folder(to)
    if not src or not dst:
        raise FolderError("INVALID_INPUT", "both the folder path and the target must be non-empty",
                        hint="PUT .../move {to: 'NewName'}")
    if src == dst:
        return {"from": src, "to": dst, "movedNotes": [], "movedMeta": 0, "warnings": ["no-op (same path)"]}
    if _subtree_match(dst, src):
        raise FolderError("INVALID_INPUT", f"cannot move {src!r} into its own subtree {dst!r}",
                        hint="pick a target outside the folder")
    # collision: the target already exists as a separate folder (meta or notes) → don't silent-merge
    if wiki_store.get_folder_meta(dst) is not None or _live_notes_under(dst):
        raise FolderError("CONFLICT", f"target {dst!r} already exists",
                        hint="pick a target that doesn't exist, or merge manually")

    moved_notes: list[int] = []
    warnings: list[str] = []
    for row in _live_notes_under(src):
        nid = int(row["id"])
        old_fld = (row["folder"] if "folder" in row.keys() else "") or ""
        new_fld = dst if old_fld == src else dst + old_fld[len(src):]
        try:
            crud.update_note(nid, NoteUpdateInput(folder=new_fld), actor=actor)
            moved_notes.append(nid)
        except Exception as exc:  # noqa: BLE001 — fail-soft per note; the rest still move
            warnings.append(f"note {nid}: move failed ({exc})")
    moved_meta = wiki_store.move_folder_meta(src, dst)
    return {"from": src, "to": dst, "movedNotes": moved_notes, "movedMeta": moved_meta,
            "warnings": warnings}
