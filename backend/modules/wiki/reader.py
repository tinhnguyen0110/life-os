"""modules/wiki/reader.py — wiki read-side (Sprint W1a-T3).

Read-only derived views over the wiki cache + op_log. Reads never mutate and never
go through the changes-queue.

W1a-T3 surface:
  - ``recent_ops(limit)`` — the episodic/replay activity feed (reads ``wiki_op_log``,
    newest-first). W1's "recent activity" panel reads this later.
  - ``reindex_note(note_id)`` — the reindex SEAM. In W1a it reconciles the
    ``wiki_notes`` cache row + ``content_hash`` against the md file (the source of
    truth) — e.g. after an out-of-band file edit, or to rebuild a dropped cache
    row. The FULL reindex (FTS5 index + link-graph rebuild) is W1c; this seam is
    where that work attaches. It is NOT a stub-lie: it does real cache
    reconciliation now and returns an honest status of what it did.

Overview stats / inbox / ego-graph readers are W1c.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from . import store as wiki_store

logger = logging.getLogger("life-os.wiki.reader")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def reindex_note(note_id: int) -> dict[str, Any]:
    """Reconcile the ``wiki_notes`` cache row against the md file (source of truth).

    The reindex SEAM (A5 / W1c attach point). In W1a it keeps the cache row +
    ``content_hash`` consistent with the on-disk md file:
      - md file absent → drop the stale cache row (note was deleted out-of-band).
      - md present, cache row missing or its ``content_hash`` stale → rebuild the
        row from the parsed file.
      - md present, cache already matches → no-op (touch ≠ rewrite).

    Returns a status dict ``{noteId, action}`` where action ∈
    ``missing_dropped | rebuilt | unchanged``. Full FTS5 + link-graph reindex is
    W1c — it hooks in HERE (after the cache reconcile) when those tables exist.
    """
    # Lazy import avoids a service<->reader import cycle; the parse lives in service.
    from . import service as wiki_service

    raw = wiki_store.read_note_file(note_id)
    cache_row = wiki_store.get_note_cache(note_id)

    if raw is None:
        # Source file gone — the cache must not keep a phantom row.
        if cache_row is not None:
            wiki_store.delete_note_cache(note_id)
            logger.info("reindex: note %s md missing → dropped stale cache row", note_id)
            return {"noteId": note_id, "action": "missing_dropped"}
        return {"noteId": note_id, "action": "unchanged"}

    note = wiki_service._parse(raw, note_id)
    if note is None:
        # Malformed file — leave cache as-is, report (don't silently 'fix').
        logger.warning("reindex: note %s md malformed → cache left unchanged", note_id)
        return {"noteId": note_id, "action": "unchanged"}

    if cache_row is not None and cache_row["content_hash"] == note.contentHash and (
        cache_row["title"] == note.title
        and cache_row["status"] == note.status
        and cache_row["note_type"] == note.noteType
        and cache_row["trust_tier"] == note.trustTier
        and cache_row["author"] == note.author
        and cache_row["aliases"] == json.dumps(note.aliases, ensure_ascii=False)
        and cache_row["tags"] == json.dumps(note.tags, ensure_ascii=False)
    ):
        return {"noteId": note_id, "action": "unchanged"}

    # Cache missing or stale → rebuild from the parsed file (source of truth wins).
    cap = wiki_service._parse_capture_source(raw)  # preserve provenance on rebuild
    wiki_store.upsert_note_cache(
        note_id=note_id, title=note.title,
        aliases_json=json.dumps(note.aliases, ensure_ascii=False),
        status=note.status, note_type=note.noteType, trust_tier=note.trustTier,
        author=note.author, tags_json=json.dumps(note.tags, ensure_ascii=False),
        content_hash=note.contentHash, created=note.created, updated=note.updated,
        capture_source=cap,
    )
    logger.info("reindex: note %s cache rebuilt from md", note_id)
    return {"noteId": note_id, "action": "rebuilt"}


# --------------------------------------------------------------------------- #
# W1b — backlinks (B3)                                                          #
# --------------------------------------------------------------------------- #
_SNIPPET_PAD = 60  # chars of context on each side of a [[..]] mention


def _title_of(note_id: int) -> str:
    row = wiki_store.get_note_cache(note_id)
    return row["title"] if row is not None else ""


def _mention_snippet(source_id: int, target_id: int) -> str:
    """A short body excerpt around where ``source`` links ``target`` — matching
    EITHER link form: by id (``[[47]]``/``[[47|..]]``) OR by the target's title or
    an alias (``[[Title]]``/``[[Title|..]]``), case-insensitive. Empty string if
    not locatable. Read from the md body (source of truth); cheap at M1 sizes."""
    import re as _re

    body = wiki_store.read_note_file(source_id) or ""
    # Strip frontmatter so the snippet is body text, not yaml.
    if body.startswith("---"):
        parts = body[len("---"):].split("\n---", 1)
        if len(parts) == 2:
            body = parts[1].lstrip("\n")

    # Build the set of targets that resolve to this note: its id + title + aliases.
    targets: list[str] = [str(int(target_id))]
    row = wiki_store.get_note_cache(target_id)
    if row is not None:
        if row["title"]:
            targets.append(row["title"])
        try:
            targets.extend(a for a in json.loads(row["aliases"]) if a)
        except (json.JSONDecodeError, TypeError):
            pass
    alt = "|".join(_re.escape(t) for t in targets)
    m = _re.search(rf"\[\[\s*(?:{alt})\s*(?:\|[^\[\]]*)?\]\]", body, _re.IGNORECASE)
    if not m:
        return ""
    start = max(0, m.start() - _SNIPPET_PAD)
    end = min(len(body), m.end() + _SNIPPET_PAD)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(body) else ""
    return f"{prefix}{body[start:end].strip()}{suffix}"


def backlinks(note_id: int) -> dict[str, Any]:
    """Backlinks for a note (B3) — matches the mock ``data-wiki.js`` shape:

      ``{linked:[{id,title,snippet,anchor?}], unlinked:[{id,title,snippet}],
         outbound:[{id,title,isResolved}|{ghost,isResolved:false}]}``

    - **linked:** resolved inbound edges (other notes' ``[[id]]`` → this note),
      deduped by source note, with a body snippet around the mention. ``anchor``
      (``^block-id``) is W2 — absent in W1b.
    - **unlinked:** plain-text mentions of this title/alias that AREN'T linked →
      **`[]` in W1b** (needs FTS5; populated W1c — shape present, honest-mirror).
    - **outbound:** this note's edges — resolved as ``{id,title,isResolved:true}``,
      ghosts as ``{ghost:<title>, isResolved:false}``.
    """
    # linked — dedup by source note (one row per backlinking note).
    seen_sources: set[int] = set()
    linked: list[dict[str, Any]] = []
    for row in wiki_store.links_to(note_id, resolved_only=True):
        src = row["source_id"]
        if src in seen_sources:
            continue
        seen_sources.add(src)
        linked.append({
            "id": src,
            "title": _title_of(src),
            "snippet": _mention_snippet(src, note_id),
        })

    # outbound — resolved + ghost edges of this note.
    outbound: list[dict[str, Any]] = []
    for row in wiki_store.links_from(note_id):
        if row["is_resolved"] and row["target_id"] is not None:
            outbound.append({
                "id": row["target_id"],
                "title": _title_of(row["target_id"]),
                "isResolved": True,
            })
        else:
            outbound.append({
                "ghost": row["target_title"] or "",
                "isResolved": False,
            })

    return {"linked": linked, "unlinked": unlinked_mentions(note_id, exclude=seen_sources),
            "outbound": outbound}


# --------------------------------------------------------------------------- #
# W1c — FTS search (C1) + unlinked-mentions (C2)                                #
# --------------------------------------------------------------------------- #
def search(q: str, limit: int = 30) -> list[dict[str, Any]]:
    """Full-text search → ``[{id, title, snippet, status}]`` ranked by FTS5 rank
    (C1). Empty/bad query → ``[]`` (never raises — store sanitizes)."""
    return [
        {"id": r["id"], "title": r["title"], "snippet": r["snippet"], "status": r["status"]}
        for r in wiki_store.fts_search(q, limit=limit)
    ]


def _snippet_of_body(note_id: int, length: int = 140) -> str:
    """First ``length`` chars of a note's body (frontmatter stripped) — for inbox
    rawContent + activity. Cheap at M1 vault sizes."""
    body = wiki_store.read_note_file(note_id) or ""
    if body.startswith("---"):
        parts = body[len("---"):].split("\n---", 1)
        if len(parts) == 2:
            body = parts[1].lstrip("\n")
    body = body.strip()
    return body if len(body) <= length else body[:length].rstrip() + "…"


def unlinked_mentions(note_id: int, *, exclude: set[int] | None = None,
                      limit: int = 20) -> list[dict[str, Any]]:
    """Notes whose body mentions this note's title/alias as plain TEXT but DON'T
    link it (C2 — the W1b-deferred piece, now via FTS5). Excludes the note itself
    + any already-linked source (``exclude`` = the resolved linked-mention set) +
    notes that already link it via an edge. Capped at ``limit`` by rank.

    Returns ``[{id, title, snippet}]``. Empty if the note has no title/aliases."""
    row = wiki_store.get_note_cache(note_id)
    if row is None:
        return []
    phrases = [row["title"]] if row["title"] else []
    try:
        phrases.extend(a for a in json.loads(row["aliases"]) if a)
    except (json.JSONDecodeError, TypeError):
        pass
    if not phrases:
        return []

    excluded: set[int] = {int(note_id)}
    if exclude:
        excluded |= {int(e) for e in exclude}
    # Also exclude any note that ALREADY links this one (resolved inbound edge) —
    # a linked mention is not an UNlinked mention.
    excluded |= {r["source_id"] for r in wiki_store.links_to(note_id, resolved_only=True)}

    out: list[dict[str, Any]] = []
    for r in wiki_store.fts_phrase_search(phrases, limit=limit + len(excluded) + 5):
        sid = r["id"]
        if sid in excluded:
            continue
        out.append({"id": sid, "title": _title_of(sid), "snippet": r["snippet"]})
        if len(out) >= limit:
            break
    return out


# --------------------------------------------------------------------------- #
# W1c — ego-graph (C3)                                                          #
# --------------------------------------------------------------------------- #
def ego_graph(note_id: int, depth: int = 2) -> dict[str, Any] | None:
    """Ego-graph 1–2 hop around ``note_id`` (C3). BFS over RESOLVED edges (both
    directions) to ``depth`` hops. Returns ``{center, nodes:[{id,title,status,
    degree}], edges:[{source,target,type,isResolved}], clusters:[]}`` — or None if
    the center note doesn't exist.

    Ghost links are a flag on edges, NOT phantom nodes (the graph contains only
    real notes; the FE renders ghost visuals). clusters = [] in W1c (deterministic
    clustering deferred — NO fake AI; real cluster-detection is M4).
    Performance: bounded to the neighborhood (depth-2 BFS + one edges-in-set
    query), well under the 200-note <1s gate."""
    if wiki_store.get_note_cache(note_id) is None:
        return None
    depth = 2 if depth >= 2 else 1

    visited: set[int] = {int(note_id)}
    frontier: set[int] = {int(note_id)}
    for _ in range(depth):
        nxt: set[int] = set()
        for nid in frontier:
            nxt |= wiki_store.resolved_neighbors(nid)
        nxt -= visited
        if not nxt:
            break
        visited |= nxt
        frontier = nxt

    nodes = []
    for nid in sorted(visited):
        row = wiki_store.get_note_cache(nid)
        if row is None:
            continue
        nodes.append({
            "id": nid, "title": row["title"], "status": row["status"],
            "degree": wiki_store.degree(nid),
        })
    edges = [
        {"source": e["source_id"], "target": e["target_id"],
         "type": e["type"], "isResolved": bool(e["is_resolved"])}
        for e in wiki_store.edges_among(visited)
    ]
    # W5a (D-W5.1): the detected clusters that this ego-neighborhood touches — so
    # the FE can style/group members. Only clusters intersecting the visible nodes
    # are included (member ids restricted to the ego set for rendering).
    visible_clusters = []
    for c in detect_clusters():
        member_ids = {m["id"] for m in c["members"]}
        if member_ids & visited:
            visible_clusters.append({
                "members": [m for m in c["members"] if m["id"] in visited],
                "size": c["size"], "density": c["density"],
                "importance": c["importance"], "suggestedTitle": c["suggestedTitle"],
            })
    return {"center": int(note_id), "nodes": nodes, "edges": edges,
            "clusters": visible_clusters}


# --------------------------------------------------------------------------- #
# W1c — overview stats + recent activity (C4)                                   #
# --------------------------------------------------------------------------- #
def overview(activity_limit: int = 20) -> tuple[dict[str, Any], str | None]:
    """Vault overview (C4). Returns ``(data, warning)``:
    ``{stats, inbox, orphans, recentActivity, proposalCount}``.

    ``pctWithLink`` = notes-with-≥1-resolved-link / total × 100 → **None on an
    empty vault** (totalNotes==0) with a warning, NEVER 0 / div-by-zero (risk-(e)).
    ``proposalCount`` = 0 (AI proposals are M4)."""
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
        "proposalCount": 0,  # AI proposals land at M4
    }
    return data, warning


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


# --------------------------------------------------------------------------- #
# W1c — inbox reader (C5)                                                       #
# --------------------------------------------------------------------------- #
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


def _capture_source(row: Any) -> str:
    """The note's capture source (C5). W1c-T3 adds a ``capture_source`` cache
    column; until then default ``quick_add``. Reads defensively so this reader
    works whether or not the column exists yet."""
    try:
        cs = row["capture_source"]
        return cs or "quick_add"
    except (IndexError, KeyError):
        return "quick_add"


# --------------------------------------------------------------------------- #
# W5a — SYNTHESIZE substrate: graph cluster detection + MOC listing (D-W5.1/2)  #
# --------------------------------------------------------------------------- #
def _connected_components(adj: dict[int, set[int]]) -> list[set[int]]:
    """Connected components of an undirected graph (BFS flood-fill). ``adj`` maps
    each node to its neighbor set. Deterministic (sorted iteration). Returns one
    set of node-ids per component."""
    seen: set[int] = set()
    components: list[set[int]] = []
    for start in sorted(adj):
        if start in seen:
            continue
        comp: set[int] = set()
        stack = [start]
        while stack:
            n = stack.pop()
            if n in comp:
                continue
            comp.add(n)
            seen.add(n)
            stack.extend(adj[n] - comp)
        components.append(comp)
    return components


def detect_clusters() -> list[dict[str, Any]]:
    """Graph community detection (D-W5.1) — NO vector. A cluster (MOC candidate) is
    a connected component over the RESOLVED-edge graph with ``size ≥
    wiki_cluster_min_size`` AND internal link-density ``≥ wiki_cluster_min_density``.

    density = (# undirected resolved edges among members) / (max possible edges =
    n·(n−1)/2). importance = size × density is ADVISORY (D-W5.3) — it ranks
    candidates, never gates pruning. Each cluster carries its members (id+title),
    size, density, importance, and a deterministic ``suggestedTitle`` hint (the
    highest-degree member's title — NOT AI; the LLM drafts the real MOC via MCP).

    Ranked by importance desc, then size desc, then lowest member id (stable).
    Isolated / under-threshold notes don't appear. Bounded graph work — well under
    the 200-note <1s gate (one edge scan + BFS + per-cluster counts).
    """
    from core.config import settings

    edges = wiki_store.all_resolved_edges()
    # Build the undirected adjacency from resolved edges.
    adj: dict[int, set[int]] = {}
    undirected: set[tuple[int, int]] = set()
    for e in edges:
        a, b = int(e["source_id"]), int(e["target_id"])
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
        undirected.add((a, b) if a < b else (b, a))

    min_size = settings.wiki_cluster_min_size
    min_density = settings.wiki_cluster_min_density

    components = _connected_components(adj)
    # F1-P1 (perf): bucket each edge into its component in ONE pass (O(E)) instead of
    # rescanning the whole edge set per component (the old O(C·E)=O(n²)). Both endpoints
    # of a resolved edge are in the same component (connectivity), so a node→component
    # map + one edge pass gives identical internal-edge counts. Behavior-preserving.
    comp_of: dict[int, int] = {}
    for ci, comp in enumerate(components):
        for nid in comp:
            comp_of[nid] = ci
    internal_count: dict[int, int] = {}
    for (a, _b) in undirected:
        cid = comp_of.get(a)
        if cid is not None:
            internal_count[cid] = internal_count.get(cid, 0) + 1

    clusters: list[dict[str, Any]] = []
    for ci, comp in enumerate(components):
        n = len(comp)
        if n < min_size:
            continue
        internal = internal_count.get(ci, 0)
        max_possible = n * (n - 1) / 2
        density = (internal / max_possible) if max_possible else 0.0
        if density < min_density:
            continue
        members = []
        best_title, best_degree = None, -1
        for nid in sorted(comp):
            row = wiki_store.get_note_cache(nid)
            title = (row["title"] if row is not None else "") or f"note {nid}"
            members.append({"id": nid, "title": title})
            deg = len(adj.get(nid, set()))
            if deg > best_degree:
                best_degree, best_title = deg, title
        clusters.append({
            "members": members,
            "size": n,
            "density": round(density, 3),
            "importance": round(n * density, 3),  # advisory only (D-W5.3)
            "suggestedTitle": best_title,          # deterministic hint, NOT AI
        })

    clusters.sort(key=lambda c: (-c["importance"], -c["size"], c["members"][0]["id"]))
    return clusters


def mocs() -> dict[str, Any]:
    """List MOC-type notes (D-W5.2): notes with ``noteType == "moc"``, newest first.
    Each: ``{id, title, status, created, updated, outboundLinks}``. Empty → ``{items: []}``."""
    items = []
    for row in wiki_store.all_notes(order_by="created"):
        if row["note_type"] != "moc":
            continue
        items.append({
            "id": row["id"],
            "title": row["title"] or None,
            "status": row["status"],
            "created": row["created"],
            "updated": row["updated"],
            "outboundLinks": wiki_store.outbound_link_count(row["id"]),
        })
    items.reverse()  # all_notes is created-ASC; present newest first
    return {"items": items}
