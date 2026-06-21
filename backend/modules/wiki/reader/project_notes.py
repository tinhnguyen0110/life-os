"""modules/wiki/reader/project_notes.py — PROJECT-MEMORY (#42): a project's wiki notes ("memory").

An agent asking about project X should get its accumulated wiki notes injected as context, so it
reasons WITH the project's memory. The LINK CONVENTION (F1=a) is the TAG ``project:<id>`` — a note
that relates to project X carries the tag ``project:X`` (multi-valued: a note can tag several
projects; non-destructive; the folder stays free for browsing). The tag is the AUTHORITATIVE link.

``project_notes(project_id)`` returns the lean note list for a project — notes whose tags contain
``project:<project_id>``, newest-updated first, top-N (default 10). Lean shape (no body, token-cheap):
``[{id, title, status, updated, snippet}]``. A project with no tagged notes → ``[]`` (honest-empty).
TAG-SCOPED: a note tagged ``project:other`` or untagged does NOT appear (the distinguishing — it's
not all-notes). Read-only; deterministic; no AI.

PERF: one ``store.notes_with_tag`` query (LIKE on the tags JSON, ordered updated DESC) — NOT a
load-all-notes-then-filter, and NOT a per-note re-fetch (the #41 inbound_counts lesson).
"""

from __future__ import annotations

import json
from typing import Any

from .. import store as wiki_store
from ._helpers import _snippet_of_body


def project_tag(project_id: str) -> str:
    """The canonical link tag for a project — ``project:<id>``. One place so the write-side
    (a future tag-suggest) and the read-side agree on the exact token."""
    return f"project:{project_id}"


def project_notes(project_id: str, limit: int = 10) -> list[dict[str, Any]]:
    """A project's notes (see module docstring): notes tagged ``project:<project_id>``, newest-
    updated first, top ``limit`` (default 10), lean ``{id, title, status, updated, snippet}``.
    Empty/blank project_id or no tagged notes → ``[]`` (honest, never raises)."""
    pid = (project_id or "").strip()
    if not pid:
        return []
    rows = wiki_store.notes_with_tag(project_tag(pid))  # ordered updated DESC at the store
    out: list[dict[str, Any]] = []
    for r in rows[: int(limit)]:
        nid = int(r["id"])
        out.append({
            "id": nid,
            "title": r["title"],
            "status": r["status"],
            "updated": r["updated"],
            "snippet": _snippet_of_body(nid),
        })
    return out


# kept for symmetry / a defensive caller — parse a row's tags JSON to a list (the store column is a
# JSON string array). Not used by project_notes (the LIKE filter does the matching) but handy + safe.
def _tags_of(row: Any) -> list[str]:
    try:
        val = json.loads(row["tags"] or "[]")
        return [str(t) for t in val] if isinstance(val, list) else []
    except (ValueError, TypeError, KeyError, IndexError):
        return []
