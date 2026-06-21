"""modules/wiki/reader/oplog.py — op_log read views (the activity feed).

``recent_ops`` projects ``wiki_op_log`` rows → API dicts (newest-first);
``_recent_activity`` enriches them with the live note title for the overview feed;
``my_feedback`` (#35) projects the override-feedback rows → agent-readable rows."""

from __future__ import annotations

import json
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


_VALID_REASONS = {"off-scope", "wrong", "duplicate", "low-quality", "outdated", "other"}


def my_feedback(limit: int = 50) -> dict[str, Any]:
    """WIKI-WRITE-FEEDBACK (#35): the override-feedback an agent reads to learn WHY a
    human overrode its notes (so it writes less junk). Newest-first, lean rows:
    ``{noteId, reason, text, overriddenAt, originalTitle, overrideKind}``.

    Reads the op_log feedback rows (store.feedback_ops), parses each ``detail`` JSON,
    and keeps only well-formed ones (valid reason + the snapshotted originalTitle/kind).
    A LIKE false-positive or a malformed detail is silently dropped (honest — never a
    crash, never a fabricated row). Empty → ``{feedback: [], count: 0}`` (honest-empty)."""
    rows = wiki_store.feedback_ops(limit=int(limit))
    out: list[dict[str, Any]] = []
    for r in rows:
        raw = r["detail"]
        if not raw:
            continue
        try:
            detail = json.loads(raw)
        except (ValueError, TypeError):
            continue
        fb = detail.get("feedback")
        if not isinstance(fb, dict):
            continue
        reason = fb.get("reason")
        if reason not in _VALID_REASONS:
            continue  # drop a malformed/false-positive row (honest, not a crash)
        out.append({
            "noteId": r["note_id"],
            "reason": reason,
            "text": fb.get("text"),
            "overriddenAt": r["ts"],
            "originalTitle": detail.get("originalTitle") or (
                _title_of(r["note_id"]) if r["note_id"] is not None else ""),
            "overrideKind": detail.get("overrideKind")
            or ("delete" if r["kind"] == "delete" else "edit"),
        })
    return {"feedback": out, "count": len(out)}


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
