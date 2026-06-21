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


# #96: how many raw op_log rows to scan to fill ``limit`` LIVE entries after excluding soft-
# deleted/empty-title + dedup-by-noteId. A note can have many ops (create+edits+softdelete), so
# over-pull generously; bounded so a huge op_log doesn't scan unbounded.
_RECENT_OVERSCAN = 200


def _recent_activity(limit: int) -> list[dict[str, Any]]:
    """op_log → ``[{ts, op, actor, noteId, noteTitle, detail}]`` newest-first, ONE entry per LIVE
    note (#96). The op_log is append-only so a soft-deleted/merged note's ops still sit in it —
    we check each note's CURRENT cache status at read time and EXCLUDE:
      - soft-deleted notes (deleted_at NOT NULL — #94 hid them from tree/search; recentActivity
        must match, else the user's daily_brief.wikiContext leaks trash),
      - empty-title notes (a junk/never-titled note — nothing to show),
    then DEDUP by noteId keeping the NEWEST op (the rows are seq-DESC so the first-seen per noteId
    IS the newest), then cap to ``limit``. Order: over-scan → exclude → dedup → cap (so the limit
    returns N REAL live notes, not N pre-filter). One source → fixes EVERY consumer (the brief's
    wikiContext + the wiki overview)."""
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    # over-pull (≥ limit) so filtering still yields up to `limit` live entries.
    scan = max(int(limit), 1) if limit <= 0 else min(_RECENT_OVERSCAN, max(int(limit) * 10, 50))
    for o in recent_ops(limit=scan):
        nid = o["noteId"]
        if nid is None or nid in seen:
            continue  # ops with no note, or a noteId already emitted (dedup — keep newest)
        row = wiki_store.get_note_cache(nid)
        if row is None:
            continue                       # hard-deleted / never-cached → nothing live to show
        keys = row.keys()
        if "deleted_at" in keys and row["deleted_at"] is not None:
            continue                       # #94/#96: soft-deleted → hidden (matches tree/search)
        title = row["title"]
        if not title:
            continue                       # empty-title junk → skip
        seen.add(nid)
        out.append({
            "ts": o["ts"], "op": o["kind"], "actor": o["actor"],
            "noteId": nid, "noteTitle": title, "detail": o["detail"],
        })
        if len(out) >= limit:
            break                          # filled `limit` LIVE entries
    return out
