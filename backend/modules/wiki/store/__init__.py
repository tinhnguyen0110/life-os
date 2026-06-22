"""modules/wiki/store — wiki two-store layer (Sprint W1a, M1 Wiki Core).

Two stores, per ARCH §6 "files = source of truth, index = disposable cache":

  - **md+git** (``store/md_store.py``) — the note files ``wiki/notes/<id>.md``
    (frontmatter + body). Source of truth, portable, every write = 1 git commit.
  - **SQLite cache** (the shared ``store/db.py`` connection) — rebuildable index:
      * ``wiki_notes``  — one row per live note (the queryable cache + id source)
      * ``wiki_op_log`` — append-only episodic/replay log (A3): every mutation,
                          in apply order. NOT git history (git mixes commits +
                          isn't replay-structured — spec open-decision).

Wiki tables register idempotently on the shared connection at module import
(mirrors the time-series ``CREATE TABLE IF NOT EXISTS`` pattern in db.py). Keeping
ONE DB file + connection (vs a second wiki.db) is the simpler call — the
single-writer queue (service.py) serializes all wiki writes, so a wiki-local lock
here only guards the brief cache reads/writes against the scheduler thread.

ID generation (A1): ``next_note_id()`` = ``MAX(id)+1`` — collision-free because it
runs INSIDE the single writer (serialized). One machine, no UUID needed (D1).

----------------------------------------------------------------------------
PACKAGE LAYOUT (refactor: was one 759-LOC store.py; behavior + public API are
IDENTICAL — every name below is re-exported flat so ``wiki_store.X`` keeps working):

  _base    — shared ``_lock`` + schema + ``init_wiki_tables`` + path helpers + id source
  notes    — wiki_notes cache CRUD
  oplog    — wiki_op_log append + read (A3)
  files    — note md file read/write/delete (md_store pass-through)
  aliases  — alias index + title resolver (B2)
  links    — typed-edge graph (B1/B2) + D6 redirect tombstones (B5)
  fts      — FTS5 full-text + phrase search (C1/C2)
  queries  — graph + overview aggregate queries (C3/C4/C5)

All submodules share the ONE ``_base._lock`` (imported, not re-created) so the
concurrency behavior is exactly what the single 759-LOC file had.
"""

from __future__ import annotations

# Shared primitives (schema, lock, init, path helpers, id source).
from ._base import (
    WIKI_SCHEMA,
    _lock,
    _migrate,
    init_wiki_tables,
    logger,
    next_note_id,
    note_rel_path,
    wiki_notes_dir,
)

# wiki_notes cache CRUD.
from .notes import (
    delete_note_cache,
    get_note_cache,
    note_cache_exists,
    set_deleted_at,
    upsert_note_cache,
)

# op_log (A3). #35: + latest_op_for_note (agent-actor detection) + feedback_ops (read-back).
from .oplog import append_op, feedback_ops, latest_op_for_note, recent_ops

# md file pass-through.
from .files import delete_note_file, read_note_file, write_note_file

# alias index + title resolver (B2).
from .aliases import (
    clear_aliases,
    replace_aliases,
    resolve_title,
    resolve_title_count,
)

# typed-edge graph (B1/B2) + redirect tombstones (B5).
from .links import (
    add_redirect,
    clear_links_from,
    follow_redirect,
    get_redirect,
    ghost_links_for_title,
    ghostify_inbound,
    links_from,
    links_to,
    repoint_inbound_links,
    replace_links,
    resolve_ghosts_to,
)

# FTS5 full-text + phrase search (C1/C2).
from .fts import (
    _sanitize_fts_query,
    fts_delete,
    fts_phrase_search,
    fts_search,
    fts_upsert,
)

# per-folder description KV (WIKI-RETRIEVAL-1 #20).
from .folder_meta import (
    all_folder_meta,
    create_folder_meta,
    delete_folder_meta_subtree,
    get_folder_meta,
    move_folder_meta,
    set_folder_meta,
)

# graph + overview aggregate queries (C3/C4/C5).
from .queries import (
    all_notes,
    trash_notes,
    all_resolved_edges,
    count_by_status,
    count_ghost_links,
    count_notes,
    count_resolved_links,
    degree,
    edges_among,
    fleeting_notes,
    inbound_counts,
    mutual_link_pairs,
    note_ids_with_resolved_link,
    notes_with_tag,
    outbound_link_count,
    resolved_neighbors,
    total_link_count,
)

__all__ = [
    # _base — incl. the internals the original single-file module exposed at
    # top level (kept accessible so the public surface is byte-for-byte the same).
    "WIKI_SCHEMA", "init_wiki_tables", "next_note_id", "note_rel_path",
    "wiki_notes_dir", "_lock", "_migrate", "logger", "_sanitize_fts_query",
    # notes
    "upsert_note_cache", "get_note_cache", "note_cache_exists", "delete_note_cache",
    "set_deleted_at",
    # oplog
    "append_op", "recent_ops", "latest_op_for_note", "feedback_ops",
    # files
    "write_note_file", "read_note_file", "delete_note_file",
    # aliases
    "replace_aliases", "clear_aliases", "resolve_title", "resolve_title_count",
    # links
    "replace_links", "clear_links_from", "links_from", "links_to",
    "ghostify_inbound", "ghost_links_for_title", "resolve_ghosts_to",
    "add_redirect", "get_redirect", "follow_redirect", "repoint_inbound_links",
    # fts
    "fts_upsert", "fts_delete", "fts_search", "fts_phrase_search",
    # queries
    "all_notes", "trash_notes", "count_notes", "count_by_status", "count_resolved_links",
    "count_ghost_links", "note_ids_with_resolved_link", "degree",
    "resolved_neighbors", "edges_among", "all_resolved_edges", "fleeting_notes",
    "inbound_counts", "mutual_link_pairs",  # WIKI-STALE-DETECTOR #41
    "notes_with_tag",  # PROJECT-MEMORY #42
    "outbound_link_count", "total_link_count",
    # folder-meta KV (#20) + folder lifecycle anchor (#127)
    "get_folder_meta", "all_folder_meta", "set_folder_meta",
    "create_folder_meta", "delete_folder_meta_subtree", "move_folder_meta",
]

# Register tables at import so a fresh process / first request has them ready
# (identical to the old single-file module's import-time call).
init_wiki_tables()
