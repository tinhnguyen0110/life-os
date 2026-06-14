"""modules/wiki/reader/graph.py — ego-graph (C3) + cluster detection (W5a, D-W5.1).

``ego_graph`` is a depth-bounded BFS neighborhood; ``detect_clusters`` finds MOC-
candidate communities (connected components over resolved edges, size + density
gated). NO vectors / NO AI — deterministic graph work only."""

from __future__ import annotations

from typing import Any

from .. import store as wiki_store


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
