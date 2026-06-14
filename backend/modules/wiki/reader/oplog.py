"""modules/wiki/reader/oplog.py — op_log read views (the activity feed).

``recent_ops`` projects ``wiki_op_log`` rows → API dicts (newest-first);
``_recent_activity`` enriches them with the live note title for the overview feed."""

from __future__ import annotations

from typing import Any

from .. import store as wiki_store
from ._helpers import _title_of


def recent_ops(limit: int = 50) -> list[dict[str, Any]]:
    """Most-recent op_log entries (newest-first), as plain dicts for the API/feed.

    Each entry: ``{seq, op_id, kind, noteId, actor, ts, commitSha, detail}``.
    ``kind`` ∈ create|edit|delete (W1a subset; links/refine/merge add later).
    """
    rows = wiki_store.recent_ops(limit=limit)
    return [
        {
            "seq": r["seq"],
            "op_id": r["op_id"],
            "kind": r["kind"],
            "noteId": r["note_id"],
            "actor": r["actor"],
            "ts": r["ts"],
            "commitSha": r["commit_sha"],
            "detail": r["detail"],
        }
        for r in rows
    ]


def _recent_activity(limit: int) -> list[dict[str, Any]]:
    """op_log → ``[{ts, op, actor, noteId, noteTitle, detail}]`` newest-first. A
    merged/deleted note's title may be gone → fall back to the op_log detail."""
    out = []
    for o in recent_ops(limit=limit):
        nid = o["noteId"]
        title = _title_of(nid) if nid is not None else ""
        out.append({
            "ts": o["ts"], "op": o["kind"], "actor": o["actor"],
            "noteId": nid, "noteTitle": title, "detail": o["detail"],
        })
    return out
