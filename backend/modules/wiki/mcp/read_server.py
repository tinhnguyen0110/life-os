"""modules/wiki/mcp/read_server.py — MCP READ-only server for the wiki (Sprint W4b).

External Claude Code connects over **stdio** and READS the vault: search, overview,
inbox, ego-graph, get-note, backlinks, recent-ops. It then synthesizes and (via the
SEPARATE write server, W4c) PROPOSES writes into the W4a queue. This server can
NEVER write — that capability split IS the M4 security gate (spec L142/L145).

THE M4 GATE (D-W4b.2 — least-privilege, STRUCTURAL not a flag):
This module imports ONLY:
  - read fns: ``reader`` (search/overview/inbox/ego_graph/backlinks/recent_ops),
    ``service.get_note`` (the read path — no queue),
  - ``proposals_store.append_audit`` — appends to the audit table ONLY; it is NOT a
    vault mutation (write-only-to-its-own-table), so auditing reads does not give
    this server note-write capability.
It does NOT import the write-proposal service layer, nor any note-mutation fn
(create/update/merge/delete), nor the queue ``enqueue``. A test
(test_wiki_mcp_read.py) asserts none of those write symbols are reachable in this
module's namespace — the gate proven by grep+AST, not a docstring claim.

Run:  python -m modules.wiki.mcp.read_server   (stdio; registered in Claude Code config)

NAMING: nested under modules/wiki (not a top-level ``mcp/``) so it doesn't shadow
the SDK at /app — see the package __init__ for why.

NOTE: this module deliberately does NOT use ``from __future__ import annotations``.
FastMCP introspects each tool's parameter annotations at registration via
``issubclass(annotation, Context)`` — with stringized (future) annotations that call
raises ``TypeError: issubclass() arg 1 must be a class``. Real (non-string)
annotations are required for the SDK to build the tool schema.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

# READ-ONLY imports only (the M4 gate — see module docstring + the no-write test).
from modules.wiki import reader
from modules.wiki import proposals_store
from modules.wiki.service import get_note as _get_note
# verify_citations is a PURE read-verify fn (reads notes, follows redirects, NEVER
# mutates) — importing the bare fn keeps the read server write-incapable.
from modules.wiki.citations import verify_citations as _verify_citations

# One correlation id per server process (groups this agent session's calls, D-W4b.3).
SESSION_ID = uuid.uuid4().hex
ACTOR = "mcp:reader"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit(tool: str, params: dict[str, Any]) -> None:
    """Append one audit row per MCP call (D-W4b.3 — spec "every call"). Fail-soft:
    an audit failure must NOT break the read the agent asked for (audit is a
    secondary add-on; the read already succeeded — memory
    fail-closed-write-fail-soft-addon)."""
    try:
        proposals_store.append_audit(
            tool=tool, params=params, actor=ACTOR,
            correlation_id=SESSION_ID, ts=_now_iso(),
        )
    except Exception:  # noqa: BLE001 — audit is best-effort; never break a read
        pass


# --------------------------------------------------------------------------- #
# Tool logic — plain fns returning JSON-serializable dicts. Each = call the      #
# existing read fn + audit. Kept separate from the FastMCP registration so tests #
# can exercise the logic without standing up stdio.                              #
# Every tool returns a dict (never a bare list/None) so the agent gets a stable  #
# envelope; a missing note returns {found: False, ...} not a crash.              #
# --------------------------------------------------------------------------- #
def wiki_search(q: str = "", query: str = "", limit: int = 5) -> dict[str, Any]:
    """Full-text search the vault → RANKED top-K results (WIKI-RETRIEVAL-2 #22 — default top-5,
    each {id,title,folder,snippet,score} so the agent sees WHY it matched, NO body → drill via
    wiki_get). Accepts ``q`` OR ``query`` (alias; q wins if both given). Bad/empty/FTS-special →
    empty results (reader sanitizes; never raises). Same reader.search as REST /wiki/search (#24)."""
    term = q or query
    _audit("wiki_search", {"q": term, "limit": limit})
    return {"results": reader.search(term, limit=limit)}


def wiki_overview() -> dict[str, Any]:
    """Vault overview: stats, inbox, orphans, recentActivity, proposalCount."""
    _audit("wiki_overview", {})
    data, warning = reader.overview()
    return {"overview": data, "warning": warning}


def wiki_inbox() -> dict[str, Any]:
    """Fleeting notes awaiting triage (oldest→newest)."""
    _audit("wiki_inbox", {})
    return reader.inbox()


# WIKI-RETRIEVAL-3 (#23, F1=b): the granular MCP tools wiki_graph + wiki_backlinks were REMOVED
# from the MCP surface — wiki_context SUPERSETS both (graph + backlinks in one call), so the agent
# has fewer, fatter tools (the dogfood fewer-tools fix) with ZERO capability lost. The REST
# endpoints (/wiki/graph, /wiki/notes/{id}/backlinks) and the reader fns (ego_graph, backlinks)
# STAY — only the MCP tool registrations went away.


def wiki_get_note(note_id: int, mode: str = "full", heading: str | None = None) -> dict[str, Any]:
    """One note by its INTEGER id (the citation key — the agent cites "note 47", D1). A missing
    note → {found: False} (not a crash).

    WIKI-RETRIEVAL-2 (#21) ``mode``: full (DEFAULT — {found, note:<full dict>}, backward-compat) |
    outline (heading ToC + meta, NO body) | section (+``heading`` → only that section). The note
    payload is reader.note_view(...) — the SAME fn REST /wiki/notes/{id} uses → byte-identical
    (#24). ``found`` here = the note EXISTS; for section, ``sectionFound`` = the heading was found."""
    _audit("wiki_get_note", {"note_id": note_id, "mode": mode, "heading": heading})
    note = _get_note(int(note_id))
    if note is None:
        return {"found": False, "note_id": int(note_id)}
    view = reader.note_view(note, mode=mode, heading=heading)
    if (mode or "full").strip().lower() == "outline" or (mode or "full").strip().lower() == "section":
        return {"found": True, **view}  # outline/section: merge the view (carries its own 'mode')
    return {"found": True, "note": view}  # full: the bare note dict (backward-compat)


def wiki_context(note_id: int, depth: int = 2) -> dict[str, Any]:
    """WIKI-RETRIEVAL-3 (#23): a note's FULL neighborhood in ONE call — the COMPOSING tool that
    SUPERSEDES the (now removed, F1=b) granular wiki_graph + wiki_backlinks: an agent navigating a
    note gets its graph + backlinks together instead of 2-3 separate tool calls (the dogfood 'too
    many wiki tools' fix). NO logic dup — it calls the SAME ``reader.context`` the REST /context
    endpoint does, which composes the SAME reader fns the old granular tools used, so ``graph`` is
    byte-identical to the old wiki_graph(id)["graph"] and ``backlinks`` to the old
    wiki_backlinks(id) — ZERO capability lost, just consolidated.

    Returns ``{found, note_id, graph:{center,nodes,edges,clusters}, backlinks:{linked,unlinked,
    outbound}}``. A missing note (ego_graph None) → ``{found: False, note_id}`` (the wiki
    missing-note convention; never crashes). Same composed dict as REST /wiki/notes/{id}/context
    → MCP≡REST byte-identical (#24)."""
    _audit("wiki_context", {"note_id": note_id, "depth": depth})
    return reader.context(int(note_id), int(depth))


def wiki_suggest_links(note_id: int, limit: int = 5) -> dict[str, Any]:
    """WIKI-SUGGEST-LINK (#34): top 3-5 NEW link candidates for a note → {suggestedLinks:
    [{id, title, relevance}]}. FTS over the note's text, EXCLUDING the note itself + notes already
    linked from it (resolved outbound), more-relevant first (relevance = FTS5 rank). Helps the agent
    link a freshly-written note + keep the graph connected. DETERMINISTIC (no AI), SUGGEST-ONLY
    (never applies a link). Missing note / no matches → {suggestedLinks: []}. Same reader.suggest_links
    the REST GET /wiki/notes/{id}/suggested-links calls → MCP≡REST byte-identical (#24)."""
    _audit("wiki_suggest_links", {"note_id": note_id, "limit": limit})
    return {"suggestedLinks": reader.suggest_links(int(note_id), int(limit))}


def wiki_stale() -> dict[str, Any]:
    """WIKI-STALE-DETECTOR (#41): the read-only staleness + contradiction-candidate detector →
    {stale:[{id,title,updated,daysSince,inboundCount,status}], contradictionCandidates:[{pair,titles,
    reason}], thresholdDays, staleCount, candidateCount}. STALE = evergreen + updated > the
    staleThresholdDays config knob + ≥1 inbound; fleeting/developing/orphan-evergreen NOT flagged.
    Contradiction v1 = mutually-linked notes with divergent trust tier (verified↔candidate) — a
    deterministic human-review FLAG, NO AI. Read-only (no auto-fix); honest-empty. Same
    reader.stale_notes the REST GET /wiki/stale calls (same config threshold) → MCP≡REST
    byte-identical (#24)."""
    _audit("wiki_stale", {})
    from modules.settings.service import get_config
    return reader.stale_notes(threshold_days=get_config().staleThresholdDays)


def wiki_recent_ops(limit: int = 50) -> dict[str, Any]:
    """Recent wiki mutations (the op-log activity feed), newest first."""
    _audit("wiki_recent_ops", {"limit": limit})
    return {"ops": reader.recent_ops(limit=int(limit))}


def wiki_tree(folder: str | None = None, depth: int | None = None) -> dict[str, Any]:
    """The vault's virtual folder-tree (W-Explorer) for ls-style navigation WITHOUT reading bodies.
    Each folder node: {name, path, meta:{desc}|null, counts:{notes:N}, folders:[...], notes:[...]};
    each note-stub: {id, title, kind, status} (WIKI-RETRIEVAL-1 #20 — meta/counts/kind/status so an
    agent knows what a folder holds + which note is a MOC index, token-cheap, no body). ``folder``
    scopes to a subtree; ``depth`` limits nesting.

    WIKI-LINK-CORRECTNESS (#19) invariant KEPT: returns the tree DICT DIRECTLY — BYTE-IDENTICAL to
    REST ``GET /wiki/tree``'s ``data`` (same reader.folder_tree(folder,depth), no {tree:...} wrapper,
    no logic dup → MCP≡REST exactly; #24)."""
    _audit("wiki_tree", {"folder": folder, "depth": depth})
    return reader.folder_tree(folder=folder, depth=depth)


def wiki_clusters() -> dict[str, Any]:
    """MOC candidates (W5a): graph-detected clusters of linked notes, ranked by
    advisory importance. Each {members:[{id,title}], size, density, importance,
    suggestedTitle}. The agent reads these → reads members (wiki_get_note) → drafts
    an MOC + spots contradictions → propose_moc (write server). NO clusters → []."""
    _audit("wiki_clusters", {})
    return {"clusters": reader.detect_clusters()}


def wiki_verify_citations(claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Post-verify citations (W6 A1b, the anti-fabrication gate). The agent passes
    its ``[{claim, noteId, span}]`` BEFORE presenting an answer → per-claim status
    verified | rejected | ungrounded | weakly_grounded + a summary. A cited span
    that does NOT occur in the note → rejected (span_not_in_note) — a fabricated
    citation cannot pass. Read-only (reads notes, follows D6 redirects, no mutation)."""
    _audit("wiki_verify_citations", {"claimCount": len(claims or [])})
    return _verify_citations(claims or [])


# --------------------------------------------------------------------------- #
# NB3 — WIKI proposal read-back (PORTED from the shared read_server, MCP-DEDUP   #
# #70). The wiki has its OWN proposals queue (wiki_proposals, separate from the   #
# generic agent_proposals), so the agent reads the disposition of its WIKI        #
# proposals (from the wiki propose_* tools) here. READ-ONLY: report the human's   #
# verdict; the agent CANNOT accept/reject (wiki ratify is human-only at P1).      #
# Uses proposals_store (the store — already imported for the audit appender), NOT #
# proposals_service (the enqueue layer the M4 gate forbids). The store's get/list/#
# count are pure reads → byte-identical payload to the old embedded tools, gate-  #
# safe (no write/enqueue symbol enters this module).                              #
# --------------------------------------------------------------------------- #
def wiki_proposal_status(proposal_id: int) -> dict[str, Any]:
    """One WIKI proposal's disposition by id (the wiki_proposals queue — separate
    from the generic agent_proposals queue). Reports status (pending|accepted|
    rejected), appliedNoteId (the note an accept created/edited), decidedBy + decided
    (who ratified, when), kind + rationale. Unknown / malformed id → ``{found: False}``
    (honest, not a crash). READ-ONLY — the agent cannot ratify its own wiki proposal."""
    _audit("wiki_proposal_status", {"proposal_id": proposal_id})
    try:
        pid = int(proposal_id)
    except (ValueError, TypeError):
        return {"found": False, "proposalId": proposal_id}
    p = proposals_store.get_proposal(pid)
    if p is None:
        return {"found": False, "proposalId": pid}
    return {
        "found": True,
        "proposalId": p["id"],
        "kind": p["kind"],
        "status": p["status"],
        "targetId": p.get("targetId"),
        "appliedNoteId": p.get("appliedNoteId"),
        "decidedBy": p.get("decidedBy"),
        "decided": p.get("decided"),
        "rationale": p.get("rationale"),
    }


def wiki_list_proposals(status: str | None = None, limit: int = 50) -> dict[str, Any]:
    """The agent's WIKI proposals (newest-first) with their current disposition — the
    wiki review queue from the agent's POV (what's still pending vs accepted/rejected),
    plus a ``counts`` roll-up by status. Optional ``status`` filter (pending|accepted|
    rejected); unknown status → empty list. Empty queue → ``{proposals: [], counts: {}}``.
    READ-ONLY (the wiki_proposals queue — separate from agent_proposals)."""
    _audit("wiki_list_proposals", {"status": status, "limit": limit})
    # proposals_store.list_proposals(status) returns newest-first capped at the store
    # default; slice to ``limit`` here for API symmetry (byte-identical to the old tool,
    # which sliced proposals_service.list_proposals(status)[:limit] — the service is a
    # thin passthrough to this same store fn).
    proposals = proposals_store.list_proposals(status=status)[: int(limit)]
    return {"proposals": proposals, "counts": proposals_store.count_by_status()}


# Registry of (name → logic fn) — the single source of truth for what tools exist.
# Tests iterate this for parity + audit; FastMCP registration iterates it below.
TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "wiki_search": wiki_search,
    "wiki_overview": wiki_overview,
    "wiki_inbox": wiki_inbox,
    "wiki_get_note": wiki_get_note,
    # WIKI-RETRIEVAL-3 #23 (F1=b): wiki_graph + wiki_backlinks REMOVED from the MCP surface —
    # wiki_context SUPERSETS both (graph + backlinks in one call). REST + reader fns kept.
    "wiki_context": wiki_context,
    "wiki_suggest_links": wiki_suggest_links,  # WIKI-SUGGEST-LINK #34: top NEW link candidates
    "wiki_stale": wiki_stale,  # WIKI-STALE-DETECTOR #41: staleness + contradiction candidates
    "wiki_recent_ops": wiki_recent_ops,
    "wiki_tree": wiki_tree,  # WIKI-LINK-CORRECTNESS #19: MCP mirror of REST /wiki/tree
    "wiki_clusters": wiki_clusters,
    "wiki_verify_citations": wiki_verify_citations,
    # PORTED (#70) — wiki-proposal read-back (was embedded in the shared read_server)
    "wiki_proposal_status": wiki_proposal_status,
    "wiki_list_proposals": wiki_list_proposals,
}


# --------------------------------------------------------------------------- #
# FastMCP server — registers each TOOLS entry as an MCP tool over stdio.         #
# Built lazily in build_server() so importing this module (for tests / the       #
# no-write-capability check) does NOT require the SDK to spin up a server.       #
# --------------------------------------------------------------------------- #
def build_server(transport_security: Any = None, stateless_http: bool = False) -> Any:
    """Construct the FastMCP server with all read tools registered (the TOOLS dict).
    Separated from import so tests can import TOOLS without constructing the server.

    ``transport_security`` (default None = stdio-identical) is threaded into FastMCP so
    main.py can mount this over streamable-http (DNS-rebinding OFF for remote/LAN clients,
    MCP-HTTP). None keeps the stdio entrypoint + the no-write gate behaviourally unchanged.

    ``stateless_http`` (default False = stdio-identical) → MCP-STATELESS (#75): when True
    the server holds NO per-session state, so a backend RESTART does NOT drop HTTP clients
    (no mcp-session-id to re-initialize). Tools are pure request/response (no server-push/
    subscribe), so stateless loses nothing. main.py passes True for the HTTP mounts; the
    stdio main() entrypoint keeps False (a single persistent stdio connection — N/A)."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("life-os-wiki-read", transport_security=transport_security,
                  stateless_http=stateless_http)
    # Register each tool. FastMCP infers the schema from the fn signature +
    # docstring, so the wrappers' type hints + docstrings ARE the tool contract.
    mcp.add_tool(wiki_search, description=wiki_search.__doc__)
    mcp.add_tool(wiki_overview, description=wiki_overview.__doc__)
    mcp.add_tool(wiki_inbox, description=wiki_inbox.__doc__)
    mcp.add_tool(wiki_get_note, description=wiki_get_note.__doc__)
    # WIKI-RETRIEVAL-3 #23 (F1=b): wiki_graph + wiki_backlinks no longer registered (wiki_context supersets).
    mcp.add_tool(wiki_context, description=wiki_context.__doc__)
    mcp.add_tool(wiki_suggest_links, description=wiki_suggest_links.__doc__)
    mcp.add_tool(wiki_stale, description=wiki_stale.__doc__)
    mcp.add_tool(wiki_recent_ops, description=wiki_recent_ops.__doc__)
    mcp.add_tool(wiki_tree, description=wiki_tree.__doc__)  # #19: MCP mirror of REST /wiki/tree
    mcp.add_tool(wiki_clusters, description=wiki_clusters.__doc__)
    mcp.add_tool(wiki_verify_citations, description=wiki_verify_citations.__doc__)
    mcp.add_tool(wiki_proposal_status, description=wiki_proposal_status.__doc__)  # ported #70
    mcp.add_tool(wiki_list_proposals, description=wiki_list_proposals.__doc__)    # ported #70
    return mcp


def main() -> None:
    """stdio entrypoint — Claude Code launches this via its mcp config."""
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
