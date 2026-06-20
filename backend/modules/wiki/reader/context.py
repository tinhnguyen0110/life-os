"""modules/wiki/reader/context.py — WIKI-RETRIEVAL-3 (#23): a note's FULL neighborhood in ONE call.

``context`` is the COMPOSING read — it folds ``ego_graph`` (the graph neighborhood) and
``backlinks`` (linked / unlinked / outbound) into one payload, so an agent navigating a note gets
both in a single tool/endpoint call instead of 2-3 separate ones (the dogfood "too many wiki tools"
fix). It is PURE COMPOSITION: no logic of its own — it calls the SAME reader fns the granular
``ego_graph`` / ``backlinks`` do, so each sub-payload is byte-identical to the granular result.

Living in ``reader`` (not the MCP/REST layer) is what makes the MCP tool ``wiki_context`` and the
REST endpoint ``GET /wiki/notes/{id}/context`` byte-identical BY CONSTRUCTION (#24) — both just call
``reader.context(...)``, exactly as the existing #24 pairs both call ``reader.ego_graph`` /
``reader.backlinks`` / ``reader.note_view``.

Return shape::

    {found: True, note_id, graph: {center, nodes, edges, clusters}, backlinks: {linked, unlinked, outbound}}

A missing center note (``ego_graph`` returns None) → ``{found: False, note_id}`` (the wiki
missing-note convention; never crashes). ``graph`` IS ``ego_graph(note_id, depth)``; ``backlinks``
IS ``backlinks(note_id)``.
"""

from __future__ import annotations

from typing import Any

from .backlinks import backlinks
from .graph import ego_graph


def context(note_id: int, depth: int = 2) -> dict[str, Any]:
    """A note's graph + backlinks in one composed payload (see module docstring). Pure compose over
    ego_graph + backlinks — no duplicated logic. ego_graph None (missing note) → {found:False,
    note_id}; present → {found:True, note_id, graph, backlinks}."""
    g = ego_graph(int(note_id), int(depth))
    if g is None:
        return {"found": False, "note_id": int(note_id)}
    return {
        "found": True,
        "note_id": int(note_id),
        "graph": g,
        "backlinks": backlinks(int(note_id)),
    }
