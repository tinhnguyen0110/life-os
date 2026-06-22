"""modules/wiki/reader/tree.py — W-Explorer virtual folder-tree + MOC listing.

``folder_tree`` builds the nested virtual tree from notes' ``folder`` fields (files
are flat at <id>.md); ``mocs`` lists ``noteType == "moc"`` notes newest-first."""

from __future__ import annotations

from typing import Any

from .. import store as wiki_store


def folder_tree(folder: str | None = None, depth: int | None = None) -> dict[str, Any]:
    """W-Explorer: build the VIRTUAL folder-tree from all notes' ``folder`` fields
    (NOT physical folders — the files are flat at <id>.md). A note with folder=""
    sits at the root. A folder path "A/B/C" creates nested folder nodes A→B→C.

    Returns a nested tree rooted at "" (or at ``folder`` when given — a scoped subtree):
      ``{name, path, meta:{desc}|null, counts:{notes:N}, folders:[<subtree>...],
         notes:[{id, title, kind, status}...]}``
    where each subtree has the same shape. WIKI-RETRIEVAL-1 (#20) enriches the tree so an agent
    navigates it like ``ls`` WITHOUT reading bodies:
      - per-folder ``meta:{desc}`` from wiki_folder_meta, or ``null`` if no row (honest, never
        fabricated); ``counts:{notes:N}`` = notes DIRECTLY in that folder (not its subtree).
      - per-note ``kind`` (note_type) + ``status`` (from the note's real fields) — so a MOC
        (kind="moc") is spottable as the index to read first. NO body (token-cheap navigation).
    ``folder`` scopes the result to that subtree (None/'' = whole vault). ``depth`` limits nesting
    (depth=0 → the node's own notes + folder NAMES only, no deeper recursion; None = unlimited).
    Folders + notes are sorted (deterministic). Empty vault / unknown folder → an honest empty node."""
    root: dict[str, Any] = {"name": "", "path": "", "folders": {}, "notes": []}

    for row in wiki_store.all_notes(order_by="id"):
        fld = (row["folder"] if "folder" in row.keys() else "") or ""
        node = root
        if fld:
            acc = []
            for seg in fld.split("/"):
                acc.append(seg)
                children = node["folders"]
                if seg not in children:
                    children[seg] = {"name": seg, "path": "/".join(acc),
                                     "folders": {}, "notes": []}
                node = children[seg]
        # #20: per-note kind + status from the note's real fields (no body).
        node["notes"].append({
            "id": int(row["id"]), "title": row["title"] or "",
            "kind": row["note_type"], "status": row["status"],
        })

    metas = wiki_store.all_folder_meta()  # {folder_path: {desc}} — one query, honest-null else

    # #127 (the empty-folder anchor): a folder EXISTS if it has notes (prefix, walked above) OR a
    # wiki_folder_meta row. UNION the meta-keys into the tree so a meta-only / EMPTY / nested folder
    # shows as an honest node (counts:0). Seed every ancestor segment of each meta path (so "A/B/C"
    # with no notes still nests A→B→C). The note-prefix walk + this pass union in ONE place.
    for meta_path in metas:
        if not meta_path:  # "" = root meta, no node to seed
            continue
        node = root
        acc = []
        for seg in meta_path.split("/"):
            acc.append(seg)
            children = node["folders"]
            if seg not in children:
                children[seg] = {"name": seg, "path": "/".join(acc), "folders": {}, "notes": []}
            node = children[seg]

    def _finalize(node: dict[str, Any], remaining: int | None) -> dict[str, Any]:
        # #20: meta (honest-null when no row) + counts (notes directly here). depth limits
        # recursion: remaining==0 → don't descend into subfolders (folder names still listed
        # as shallow nodes so the agent knows they exist, but not their contents).
        if remaining is not None and remaining <= 0:
            sub: list[dict[str, Any]] = [
                {"name": node["folders"][k]["name"], "path": node["folders"][k]["path"],
                 "meta": metas.get(node["folders"][k]["path"]),
                 "counts": {"notes": len(node["folders"][k]["notes"])},
                 "folders": [], "notes": []}
                for k in sorted(node["folders"])
            ]
        else:
            nxt = None if remaining is None else remaining - 1
            sub = [_finalize(node["folders"][k], nxt) for k in sorted(node["folders"])]
        notes = sorted(node["notes"], key=lambda n: n["id"])
        return {"name": node["name"], "path": node["path"],
                "meta": metas.get(node["path"]),          # {desc} or None (honest-mirror)
                "counts": {"notes": len(notes)},          # notes DIRECTLY in this folder
                "folders": sub, "notes": notes}

    # scope to a subtree if ``folder`` is given (descend the path; unknown → honest empty node).
    start = root
    target = (folder or "").strip("/")
    if target:
        for seg in target.split("/"):
            nxt_node = start["folders"].get(seg)
            if nxt_node is None:  # unknown folder → honest empty node at that path
                return {"name": seg, "path": target, "meta": metas.get(target),
                        "counts": {"notes": 0}, "folders": [], "notes": []}
            start = nxt_node

    return _finalize(start, depth)


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
