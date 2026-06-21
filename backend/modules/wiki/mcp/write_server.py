"""modules/wiki/mcp/write_server.py — MCP WRITE server for the wiki (Sprint W4c → #25).

WIKI-WRITE-THROUGH (#25, USER-CHỐT + team-lead-approved — reverses the W4c proposals-only
DEFAULT): external Claude Code reads (W4b) → WRITES (here) → the note lands NOW (the default
``wikiAgentAutonomous=ON`` auto-applies via the create_proposal→accept chokepoint), and the
human TRACES/OVERRIDES after the fact (op-log + note CRUD). Wiki is agent-centric and every
mutation is memory-reversible, so the agent writes through; only IRREVERSIBLE ops would gate,
and wiki has none. The escape hatch: flip ``wikiAgentAutonomous`` OFF → proposals-only (writes
land pending for human ratify in P1) — the W4c posture, on demand.

THE STRUCTURAL GATE (still STRUCTURAL, still valuable — unchanged by #25):
This module imports ONLY:
  - ``create_proposal`` (the SINGLE chokepoint — every write flows through it; when autonomous
    it auto-accepts INSIDE create_proposal, so this module STILL never imports accept directly),
  - ``ProposalCreateInput`` (the proposal schema),
  - ``proposals_store.append_audit`` — append-only audit, not a vault mutation.
It does NOT import any note-mutation fn (create_note/update_note/delete_note/merge_notes/
refine_note), the queue ``enqueue``, NOR ``accept_proposal``/``reject_proposal`` directly. A
test asserts none of those are reachable in this module's namespace — the write still goes
THROUGH the one chokepoint (audited + reversible), proven by grep+AST. (The auto-apply is the
chokepoint's job, not a bypass — flip the setting to audit/disable; no code path skips the
proposal+audit record.)

``rationale`` is now OPTIONAL (#25 — the required-friction is dropped; write-through is the
default). The op-log + the proposal record are the trace, not a mandatory justification string.

Run:  python -m modules.wiki.mcp.write_server   (stdio; a SEPARATE Claude Code
mcp registration from the read server)

NOTE: no ``from __future__ import annotations`` — FastMCP introspects real param
annotations at registration (stringized annotations crash issubclass), same as the
read server.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

# ENQUEUE-ONLY imports (the M4 gate — see module docstring + the no-mutate test).
# create_proposal records INTENT only; it does NOT apply. We import the bare fn
# (NOT the proposals_service module) so accept/reject are not reachable from here.
from modules.wiki.proposals_service import create_proposal
from modules.wiki.proposals_schema import ProposalCreateInput, ProposalKind
from modules.wiki import proposals_store

# WIKI-LINK-CORRECTNESS (#26): correlationId is now PER-OPERATION (one fresh id per propose
# call), NOT per-session. The dogfood saw note#76 + link#77 share one session id → an agent
# couldn't tell two independent writes apart. A per-op id makes each write traceable on its own
# (the human/agent groups by id = ONE operation). SESSION_ID stays as a process tag (for logs /
# a coarse "this server instance") but is NOT used as the proposal correlationId anymore.
SESSION_ID = uuid.uuid4().hex
ACTOR = "mcp:writer"


def _new_correlation_id() -> str:
    """A fresh correlation id per propose operation (#26 — per-op, not per-session)."""
    return uuid.uuid4().hex


class RationaleRequired(Exception):
    """Raised when a propose tool is called with an empty rationale (D-W4c.3 — the
    agent must explain every write)."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit(tool: str, params: dict[str, Any], *, correlation_id: str) -> None:
    """Append one audit row per MCP propose call (D-W4c.4), tagged with the PER-OP correlation id
    (#26). Fail-soft: an audit failure must NOT break the propose the agent asked for (the proposal
    already enqueued; audit is a secondary add-on — memory fail-closed-write-fail-soft-addon)."""
    try:
        proposals_store.append_audit(
            tool=tool, params=params, actor=ACTOR,
            correlation_id=correlation_id, ts=_now_iso(),
        )
    except Exception:  # noqa: BLE001 — audit is best-effort; never break a propose
        pass


def _resolve_link_target(target: str) -> dict[str, Any]:
    """WIKI-LINK-CORRECTNESS (#26): resolve a link ``target`` (id or title) + surface the status,
    so a non-existent/mistyped target isn't a SILENT ghost. Reuses the wiki store's resolution
    (same primitives _derive_links uses — no reinvention). Does NOT block (a ghost can be
    intentional); just tells the agent:
      - exact-1 match  → {"targetResolved": <id>}
      - title >1 match → {"targetAmbiguous": [ids]} (the link still writes; the index uses lowest id)
      - 0 match        → {"targetGhost": True, "targetNote": "<target> matches no existing note — created as a ghost link"}
    """
    from modules.wiki import store as wiki_store
    t = str(target).strip()
    if t.isdigit():  # id link — resolved iff that note exists
        tid = int(t)
        if wiki_store.note_cache_exists(tid):
            return {"targetResolved": tid}
        return {"targetGhost": True,
                "targetNote": f"note id {tid} does not exist — created as a ghost link"}
    # title link
    count = wiki_store.resolve_title_count(t)
    if count == 0:
        return {"targetGhost": True,
                "targetNote": f"'{t}' matches no existing note — created as a ghost link"}
    if count > 1:
        # >1 match — the link index resolves to the LOWEST id (see _derive_links). Surface the
        # count + the id actually used (the store exposes the lowest-id resolver + the count, not
        # a full id list — reporting count + chosen id is the honest, cheap signal).
        return {"targetAmbiguous": True, "targetMatchCount": count,
                "targetResolvedTo": wiki_store.resolve_title(t),
                "targetNote": f"'{t}' matches {count} notes — the link index uses the lowest id"}
    return {"targetResolved": wiki_store.resolve_title(t)}


def _clean_rationale(rationale: str | None) -> str:
    """WIKI-WRITE-THROUGH (#25): rationale is now OPTIONAL (the required-friction is dropped —
    write-through is the default, the agent need not justify every write). Returns the stripped
    rationale, or "" if absent. (Kept as a helper so a future re-tightening is one place.)"""
    return (rationale or "").strip()


def _enqueue(kind: ProposalKind, *, target_id: int | None, payload: dict[str, Any],
             rationale: str | None, tool: str,
             extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Shared path: audit → create_proposal (auto-apply-eligible). WIKI-WRITE-THROUGH (#25):
    with the wikiAgentAutonomous default ON, create_proposal AUTO-APPLIES via the SAME
    create_proposal→accept chokepoint (audited, reversible) → the note lands NOW. The result
    LEADS with the real ``noteId`` (the applied note) so the agent can immediately ``get`` it —
    NOT the proposal-id (the dogfood confusion this fixes). When the toggle is OFF (escape hatch)
    the proposal stays pending → applied=False, noteId=None (proposals-only restored).

    #26: a PER-OP correlation id (one per call, not per-session) tags the audit + the proposal.
    ``extra`` merges caller-supplied status into the result (link tools pass the target-resolution
    status — targetResolved/targetAmbiguous/targetGhost).

    F1-S1 (trust boundary keys on the CALLER): only this MCP write-server passes
    auto_apply_eligible=True; the REST router (human channel) NEVER does → a REST POST can't
    auto-apply by spoofing actor. rationale is now OPTIONAL (#25)."""
    r = _clean_rationale(rationale)
    corr = _new_correlation_id()  # #26: per-OPERATION correlation id
    _audit(tool, {"kind": kind, "targetId": target_id, "payload": payload}, correlation_id=corr)
    proposal = create_proposal(
        ProposalCreateInput(kind=kind, targetId=target_id, payload=payload,
                            rationale=r, actor=ACTOR, correlationId=corr),
        auto_apply_eligible=True,
    )
    applied = proposal.get("status") == "accepted" and proposal.get("appliedNoteId") is not None
    # Agent-facing result: lead with the note-id when applied (write-through); else proposal-id
    # (toggle OFF → pending). Keep the full proposal for trace/back-compat.
    result: dict[str, Any] = {
        "noteId": proposal.get("appliedNoteId") if applied else None,
        "applied": applied,
        "status": proposal.get("status"),
        "proposalId": proposal.get("id"),
        "correlationId": corr,  # #26: the per-op id (each write traceable on its own)
        "decidedBy": proposal.get("decidedBy"),
        "warning": proposal.get("warning"),
        "proposal": proposal,
    }
    if extra:
        result.update(extra)
    return result


# --------------------------------------------------------------------------- #
# Write tools — WIKI-WRITE-THROUGH (#25): each WRITES the note NOW (the default   #
# wikiAgentAutonomous=ON auto-applies via the create_proposal→accept chokepoint,   #
# audited + reversible) and returns the real ``noteId`` so the agent can ``get``   #
# it immediately. Toggle OFF → proposals-only (returns applied=False, pending).    #
# ``rationale`` is OPTIONAL. Names kept (propose_*) for the stable tool contract.  #
# --------------------------------------------------------------------------- #
def propose_note(title: str, content: str, rationale: str | None = None,
                 tags: list[str] | None = None, folder: str | None = None) -> dict[str, Any]:
    """Create a NEW note (kind=note_create). WIKI-WRITE-THROUGH: writes NOW (default) → returns
    the real ``noteId`` (get it to confirm); toggle OFF → pending. ``rationale`` optional.
    ``folder`` (#80): the virtual folder to file the note under (e.g. "Repos" for a repo-memory
    note); None/'' = root (back-compat — existing callers unaffected). Lets an agent file a note in
    a folder via MCP (was silently dropped before → landed at root) — matches the REST create."""
    payload: dict[str, Any] = {"title": title, "content": content, "tags": tags or []}
    if folder:  # only thread a non-empty folder (None/'' → root, the back-compat default)
        payload["folder"] = folder
    return _enqueue("note_create", target_id=None, payload=payload,
                    rationale=rationale, tool="propose_note")


def propose_edit(note_id: int, rationale: str | None = None, title: str | None = None,
                 content: str | None = None) -> dict[str, Any]:
    """EDIT an existing note (kind=note_edit). Only the given fields change. WIKI-WRITE-THROUGH:
    applies NOW (default) → returns ``noteId``; toggle OFF → pending. ``rationale`` optional."""
    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if content is not None:
        payload["content"] = content
    return _enqueue("note_edit", target_id=int(note_id), payload=payload,
                    rationale=rationale, tool="propose_edit")


def propose_link(from_note_id: int, target: str, rationale: str | None = None) -> dict[str, Any]:
    """ADD a [[target]] link to a note's body (kind=link_add). ``target`` is a note id or title.
    WIKI-WRITE-THROUGH: applies NOW (default) → returns ``noteId``; OFF → pending. rationale optional.

    WIKI-LINK-CORRECTNESS (#26): the result SURFACES the target-resolution status so a mistyped/
    nonexistent target isn't a SILENT ghost — {targetResolved:<id>} | {targetAmbiguous:True,...} |
    {targetGhost:True, targetNote:"..."}. The link still WRITES (a ghost can be intentional — auto-
    resolves later when a matching note appears, B4); the status just tells the agent what happened."""
    status = _resolve_link_target(target)
    return _enqueue("link_add", target_id=int(from_note_id),
                    payload={"target": str(target)}, rationale=rationale,
                    tool="propose_link", extra=status)


def propose_unlink(note_id: int, target: str, rationale: str | None = None) -> dict[str, Any]:
    """REMOVE a [[target]] link from a note's body (kind=link_remove). WIKI-WRITE-THROUGH: applies
    NOW (default) → returns ``noteId``; OFF → pending. ``rationale`` optional."""
    return _enqueue("link_remove", target_id=int(note_id),
                    payload={"target": str(target)}, rationale=rationale,
                    tool="propose_unlink")


def propose_merge(source_id: int, target_id: int, rationale: str | None = None) -> dict[str, Any]:
    """MERGE source_id INTO target_id (kind=merge). WIKI-WRITE-THROUGH: applies NOW (default) →
    returns ``noteId`` (the target); OFF → pending. ``rationale`` optional."""
    payload = {"sourceId": int(source_id), "targetId": int(target_id)}
    return _enqueue("merge", target_id=int(target_id), payload=payload,
                    rationale=rationale, tool="propose_merge")


def propose_moc(title: str, content: str, rationale: str | None = None,
                folder: str | None = None) -> dict[str, Any]:
    """Create a Map-of-Content note (kind=moc) — a note whose body links members + articulates a
    throughline. WIKI-WRITE-THROUGH: writes NOW (default) → returns ``noteId``; OFF → pending.
    ``rationale`` optional. ``folder`` (#80): the virtual folder; None/'' = root (back-compat)."""
    payload: dict[str, Any] = {"title": title, "content": content}
    if folder:
        payload["folder"] = folder
    return _enqueue("moc", target_id=None, payload=payload,
                    rationale=rationale, tool="propose_moc")


def wiki_delete_note(note_id: int, rationale: str | None = None) -> dict[str, Any]:
    """#94: SOFT-delete a note (kind=note_softdelete) — RECOVERABLE (sets a deletedAt tombstone,
    KEEPS the .md + cache + links; hidden from live views). Restore via wiki_restore_note. WIKI-
    WRITE-THROUGH: applies NOW (default) → returns ``noteId``; toggle OFF → pending. Subsumes the
    #90-GAP2 delete tool. Mirrors REST DELETE /wiki/notes/{id} (which is also soft now)."""
    return _enqueue("note_softdelete", target_id=int(note_id), payload={},
                    rationale=rationale, tool="wiki_delete_note")


def wiki_restore_note(note_id: int, rationale: str | None = None) -> dict[str, Any]:
    """#94: RESTORE a soft-deleted note (kind=note_restore) — clears the tombstone, the note is fully
    BACK in every view (links/aliases intact). WIKI-WRITE-THROUGH: applies NOW (default) → returns
    ``noteId``; toggle OFF → pending. Mirrors REST POST /wiki/notes/{id}/restore."""
    return _enqueue("note_restore", target_id=int(note_id), payload={},
                    rationale=rationale, tool="wiki_restore_note")


# Registry (name → logic fn) — single source of truth; tests + FastMCP iterate it.
TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "propose_note": propose_note,
    "propose_edit": propose_edit,
    "propose_link": propose_link,
    "propose_unlink": propose_unlink,
    "propose_merge": propose_merge,
    "propose_moc": propose_moc,
    "wiki_delete_note": wiki_delete_note,     # #94 soft-delete (subsumes #90-GAP2)
    "wiki_restore_note": wiki_restore_note,   # #94 restore
}


# --------------------------------------------------------------------------- #
# FastMCP server — registers each propose tool over stdio. Lazy (build_server)   #
# so importing this module for the no-mutate test doesn't spin up a server.      #
# --------------------------------------------------------------------------- #
def build_server(transport_security: Any = None, stateless_http: bool = False) -> Any:
    """Construct the FastMCP write server with all 6 propose tools registered.

    ``transport_security`` (default None = stdio-identical) is threaded into FastMCP so
    main.py can mount this over streamable-http (DNS-rebinding OFF for remote/LAN clients,
    MCP-HTTP). None keeps the stdio entrypoint + the propose-only gate behaviourally unchanged.

    ``stateless_http`` (default False = stdio-identical) → MCP-STATELESS (#75): True = no
    per-session state, so a backend RESTART does NOT drop HTTP clients. Propose tools are
    pure request/response (enqueue + return), so stateless loses nothing. main.py passes
    True for the HTTP mount; the stdio main() entrypoint keeps False."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("life-os-wiki-write", transport_security=transport_security,
                  stateless_http=stateless_http)
    mcp.add_tool(propose_note, description=propose_note.__doc__)
    mcp.add_tool(propose_edit, description=propose_edit.__doc__)
    mcp.add_tool(propose_link, description=propose_link.__doc__)
    mcp.add_tool(propose_unlink, description=propose_unlink.__doc__)
    mcp.add_tool(propose_merge, description=propose_merge.__doc__)
    mcp.add_tool(propose_moc, description=propose_moc.__doc__)
    mcp.add_tool(wiki_delete_note, description=wiki_delete_note.__doc__)    # #94
    mcp.add_tool(wiki_restore_note, description=wiki_restore_note.__doc__)  # #94
    return mcp


def main() -> None:
    """stdio entrypoint — Claude Code launches this via its mcp config (SEPARATE
    registration from the read server)."""
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
