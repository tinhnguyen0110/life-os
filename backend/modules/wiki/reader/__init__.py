"""modules/wiki/reader — wiki read-side (Sprint W1a-T3 + W1b/W1c/W5a).

Read-only derived views over the wiki cache + op_log. Reads never mutate and never
go through the changes-queue — so unlike store/service there is NO shared mutable
state here (no lock, no queue): every function is a pure projection over the store.

----------------------------------------------------------------------------
PACKAGE LAYOUT (refactor: was one 582-LOC reader.py; behavior + public API are
IDENTICAL — every public name is re-exported flat so ``reader.X`` / ``wiki_reader.X``
keeps working byte-for-byte):

  _helpers  — small shared read helpers (title/snippet/capture-source) — no state
  oplog     — recent_ops + _recent_activity (the activity feed)
  reindex   — reindex_note (the A5/W1c reindex SEAM)
  backlinks — backlinks (B3) + search (C1) + unlinked_mentions (C2)
  graph     — ego_graph (C3) + detect_clusters / _connected_components (W5a)
  overview  — overview (C4) + inbox (C5)
  tree      — folder_tree (W-Explorer) + mocs (D-W5.2)

The only cross-submodule calls are read composition (overview→inbox/_recent_activity,
ego_graph→detect_clusters, backlinks→unlinked_mentions) — plain function imports, no
cycles. reindex lazily imports ``..service`` (the parse lives there), exactly as the
original single-file module did.
"""

from __future__ import annotations

# op_log feed.
from .oplog import recent_ops

# reindex seam.
from .reindex import reindex_note

# backlinks + search + unlinked mentions.
from .backlinks import backlinks, search, unlinked_mentions

# ego-graph + global (whole-vault) graph + cluster detection.
from .graph import detect_clusters, ego_graph, global_graph

# composed note neighborhood (#23): graph + backlinks in one call.
from .context import context

# overview + inbox.
from .overview import inbox, overview

# folder-tree + MOC listing.
from .tree import folder_tree, mocs

# wiki_get modes (#21): full | outline | section.
from .note_view import note_view

__all__ = [
    "recent_ops",
    "reindex_note",
    "backlinks", "search", "unlinked_mentions",
    "ego_graph", "global_graph", "detect_clusters",
    "context",
    "overview", "inbox",
    "folder_tree", "mocs",
    "note_view",
]
