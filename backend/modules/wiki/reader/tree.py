"""modules/wiki/reader/tree.py — W-Explorer virtual folder-tree + MOC listing.

``folder_tree`` builds the nested virtual tree from notes' ``folder`` fields (files
are flat at <id>.md); ``mocs`` lists ``noteType == "moc"`` notes newest-first."""

from __future__ import annotations

from typing import Any

from .. import store as wiki_store


def folder_tree() -> dict[str, Any]:
    """W-Explorer: build the VIRTUAL folder-tree from all notes' ``folder`` fields
    (NOT physical folders — the files are flat at <id>.md). A note with folder=""
    sits at the root. A folder path "A/B/C" creates nested folder nodes A→B→C.

    Returns a nested tree rooted at "":
      ``{name:"", path:"", folders:[<subtree>...], notes:[{id, title}...]}``
    where each subtree has the same shape. Folders + notes are sorted (deterministic).
    An empty vault → the root node with empty folders + notes (honest, never crash).
    Intermediate folders implied by a path (e.g. "A/B" with no note directly in "A")
    are created so the tree is fully navigable."""
    root: dict[str, Any] = {"name": "", "path": "", "folders": {}, "notes": []}

    for row in wiki_store.all_notes(order_by="id"):
        folder = (row["folder"] if "folder" in row.keys() else "") or ""
        node = root
        if folder:
            acc = []
            for seg in folder.split("/"):
                acc.append(seg)
                children = node["folders"]
                if seg not in children:
                    children[seg] = {"name": seg, "path": "/".join(acc),
                                     "folders": {}, "notes": []}
                node = children[seg]
        node["notes"].append({"id": int(row["id"]), "title": row["title"] or ""})

    def _finalize(node: dict[str, Any]) -> dict[str, Any]:
        # dict-of-children → sorted list; notes sorted by id; recurse. Deterministic.
        sub = [_finalize(node["folders"][k]) for k in sorted(node["folders"])]
        notes = sorted(node["notes"], key=lambda n: n["id"])
        return {"name": node["name"], "path": node["path"],
                "folders": sub, "notes": notes}

    return _finalize(root)


def mocs() -> dict[str, Any]:
    """List MOC-type notes (D-W5.2): notes with ``noteType == "moc"``, newest first.
    Each: ``{id, title, status, created, updated, outboundLinks}``. Empty → ``{items: []}``."""
    items = []
    for row in wiki_store.all_notes(order_by="created"):
        if row["note_type"] != "moc":
            continue
        items.append({
            "id": row["id"],
            "title": row["title"] or None,
            "status": row["status"],
            "created": row["created"],
            "updated": row["updated"],
            "outboundLinks": wiki_store.outbound_link_count(row["id"]),
        })
    items.reverse()  # all_notes is created-ASC; present newest first
    return {"items": items}
