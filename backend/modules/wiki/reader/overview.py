"""modules/wiki/reader/overview.py — vault overview (C4) + inbox reader (C5).

``overview`` rolls up vault stats + orphans + recent activity (pctWithLink None on an
empty vault — never div-by-zero); ``inbox`` lists fleeting notes awaiting triage."""

from __future__ import annotations

from typing import Any

from .. import store as wiki_store
from ._helpers import _capture_source, _now_iso, _snippet_of_body
from .oplog import _recent_activity


def overview(activity_limit: int = 20) -> tuple[dict[str, Any], str | None]:
    """Vault overview (C4). Returns ``(data, warning)``:
    ``{stats, inbox, orphans, recentActivity, proposalCount}``.

    ``pctWithLink`` = notes-with-≥1-resolved-link / total × 100 → **None on an
    empty vault** (totalNotes==0) with a warning, NEVER 0 / div-by-zero (risk-(e)).
    ``proposalCount`` = the number of PENDING wiki proposals awaiting human ratification
    (NB3: was hardcoded 0 — now reads the live wiki_proposals queue)."""
    total = wiki_store.count_notes()
    by_status = wiki_store.count_by_status()
    linked_ids = wiki_store.note_ids_with_resolved_link()
    warning: str | None = None
    if total == 0:
        pct_with_link: float | None = None
        warning = "empty vault — no notes yet"
    else:
        pct_with_link = round(len(linked_ids) / total * 100, 1)

    # orphans = notes with degree 0 (no resolved edge), newest-untouched first.
    orphans = []
    for row in wiki_store.all_notes():
        if row["id"] not in linked_ids:
            orphans.append({
                "id": row["id"], "title": row["title"], "status": row["status"],
                "degree": 0, "lastTouched": row["updated"],
            })

    stats = {
        "totalNotes": total,
        "byStatus": {
            "fleeting": by_status.get("fleeting", 0),
            "developing": by_status.get("developing", 0),
            "evergreen": by_status.get("evergreen", 0),
        },
        "totalLinks": wiki_store.count_resolved_links(),
        "orphanCount": len(orphans),
        "ghostLinkCount": wiki_store.count_ghost_links(),
        "pctWithLink": pct_with_link,
        "asOf": _now_iso(),
    }
    data = {
        "stats": stats,
        "inbox": inbox()["items"],
        "orphans": orphans,
        "recentActivity": _recent_activity(activity_limit),
        # NB3: pending wiki proposals awaiting human ratification (was hardcoded 0).
        "proposalCount": _pending_proposal_count(),
    }
    return data, warning


def _pending_proposal_count() -> int:
    """Number of PENDING wiki proposals (the queue badge). Fail-soft: a proposals-store
    hiccup (e.g. table not yet inited on a fresh vault) must NOT break the read-only
    overview — returns 0, not a 500. Reads the SEPARATE wiki_proposals queue."""
    try:
        from .. import proposals_service
        return int(proposals_service.count_by_status().get("pending", 0))
    except Exception:
        return 0


def inbox() -> dict[str, Any]:
    """Fleeting notes awaiting triage, oldest→newest (C5). ``aiSuggest: null``
    (no embedded AI — M4). ``rawContent`` = a body snippet."""
    items = []
    for row in wiki_store.fleeting_notes():
        items.append({
            "id": row["id"],
            "title": row["title"] or None,
            "status": row["status"],
            "rawContent": _snippet_of_body(row["id"]),
            "captured": row["created"],
            "captureSource": _capture_source(row),
            "linkCount": wiki_store.outbound_link_count(row["id"]),
            "aiSuggest": None,  # M4
        })
    return {"items": items}
