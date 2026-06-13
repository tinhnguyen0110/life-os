"""modules/wiki — Wiki-LLM Knowledge Module (M1 Wiki Core, Sprint W1a).

Integer-ID atomic notes (``wiki/notes/<id>.md`` — filename = id, immutable; title
in frontmatter, mutable). Two stores: md+git (source of truth, 1 commit/write) +
SQLite cache (``wiki_notes`` + append-only ``wiki_op_log``). ALL mutations flow
through a single-writer changes-queue (op-log substrate, also the M3 sync base).

SEPARATE from the string-ID ``notes`` module (different name/subdir/tables) —
user-approved new module, not a rewrite.

The registry discovers ``MODULE`` from ``router.py`` (the fallback path, like the
projects module — no MODULE in this ``__init__``).
"""
