"""modules/wiki/reader/stale.py — wiki staleness + contradiction-candidate detector (#41, SPEC A6).

A READ-ONLY detector (NO auto-fix) that flags two things for human/agent review:

  1. STALE notes — an ``evergreen`` note (meant to be a stable, refined, load-bearing note) that
     has gone untouched > N days AND has ≥1 inbound backlink (something links to it → it matters).
     ``fleeting``/``developing`` notes are NOT flagged (fleeting is expected to churn; developing is
     in-progress). An evergreen with ZERO inbound is an ORPHAN, a different concern (overview.orphans),
     not flagged here.

  2. CONTRADICTION-CANDIDATES (heuristic v1, deterministic, NO AI) — a pair of notes that link each
     other (mutual ``[[ ]]``) with DIVERGENT trust tiers (one ``verified``, one ``candidate``). This
     is a human-review FLAG ("these two connected notes disagree in trust — reconcile?"), NOT a claim
     that the content contradicts (no AI judges content — honest-mirror).

PERF: uses the bulk ``store.inbound_counts()`` (one GROUP BY) joined in-memory against
``all_notes()`` — it does NOT call ``backlinks(id)`` per-note (that builds per-source snippets =
wasted work + O(n) queries). 2 queries total, not n×backlinks.

``now`` is injectable for testable days-since (default = real UTC now).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .. import store as wiki_store

# the staleness window default — overridden by the caller (the AppConfig knob staleThresholdDays).
DEFAULT_STALE_DAYS = 90


def _days_since(iso: str, now: datetime) -> float | None:
    """Whole+fractional days between an ISO-8601 timestamp and ``now``. Unparseable → None
    (treated as 'unknown age' → NOT flagged, honest — never crash on a malformed timestamp)."""
    try:
        dt = datetime.fromisoformat(iso)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:                       # naive → assume UTC (the write-boundary convention)
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt.astimezone(timezone.utc)).total_seconds() / 86400.0


def stale_notes(threshold_days: int = DEFAULT_STALE_DAYS,
                now: datetime | None = None) -> dict[str, Any]:
    """The detector (read-only). Returns::

        {stale: [{id, title, updated, daysSince, inboundCount, status}],  # stalest first
         contradictionCandidates: [{pair: [id1, id2], reason}],
         thresholdDays: int,
         staleCount: int, candidateCount: int}

    STALE = status=='evergreen' AND daysSince(updated) > threshold_days AND inboundCount >= 1.
    Honest-empty (no flags) → empty lists + 0 counts. ``now`` injectable for tests.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    inbound = wiki_store.inbound_counts()        # {target_id: count} — ONE GROUP BY (perf)
    rows = wiki_store.all_notes()

    stale: list[dict[str, Any]] = []
    for r in rows:
        if r["status"] != "evergreen":           # only evergreen — fleeting/developing expected to move
            continue
        nid = int(r["id"])
        ic = inbound.get(nid, 0)
        if ic < 1:                               # orphan-evergreen is overview.orphans' concern, not stale
            continue
        days = _days_since(r["updated"], now)
        if days is None or days <= threshold_days:
            continue
        stale.append({
            "id": nid, "title": r["title"], "updated": r["updated"],
            "daysSince": round(days, 1), "inboundCount": ic, "status": r["status"],
        })
    stale.sort(key=lambda s: s["daysSince"], reverse=True)   # stalest first

    # contradiction-candidate v1: mutually-linked pair with divergent trust tier (verified↔candidate).
    tier_by_id = {int(r["id"]): r["trust_tier"] for r in rows}
    title_by_id = {int(r["id"]): r["title"] for r in rows}
    candidates: list[dict[str, Any]] = []
    for a, b in wiki_store.mutual_link_pairs():
        ta, tb = tier_by_id.get(a), tier_by_id.get(b)
        if ta and tb and ta != tb and {ta, tb} == {"verified", "candidate"}:
            candidates.append({
                "pair": [a, b],
                "titles": [title_by_id.get(a, ""), title_by_id.get(b, "")],
                "reason": "mutually-linked notes with divergent trust tier "
                          "(verified ↔ candidate) — human review for contradiction",
            })

    return {
        "stale": stale,
        "contradictionCandidates": candidates,
        "thresholdDays": threshold_days,
        "staleCount": len(stale),
        "candidateCount": len(candidates),
    }
