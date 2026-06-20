"""modules/wiki/mcp/write_server.py — MCP WRITE server for the wiki (Sprint W4c).

CLOSES THE M4 LOOP: external Claude Code reads (W4b) → PROPOSES (here) → human
ratifies in P1 → the vault changes. Every write tool ENQUEUES a proposal into the
W4a queue (status=pending); it NEVER touches the vault directly and NEVER accepts
(accept is the HUMAN's action in P1, not the agent's). That is the M4 pillar:
the agent proposes, the human disposes.

THE M4 GATE (D-W4c.1/2 — enqueue-only, STRUCTURAL):
This module imports ONLY:
  - ``create_proposal`` (the enqueue entry — records INTENT only; W4a verified it
    writes NOTHING to the vault until a human accepts),
  - ``ProposalCreateInput`` (the proposal schema),
  - ``proposals_store.append_audit`` — append-only to the audit table, not a vault
    mutation.
It does NOT import any note-mutation fn (create_note/update_note/delete_note/
merge_notes/refine_note), the queue ``enqueue``, NOR ``accept_proposal``/
``reject_proposal`` (the human ratifies, not the agent). A test asserts none of
those are reachable in this module's namespace — gate proven by grep+AST, not a
docstring claim. (Inverse of the read server: read has NO enqueue; write has
enqueue-ONLY — two processes, two capability sets, spec L142.)

Each propose tool REQUIRES a ``rationale`` (spec L62 "with explanation of WHY") —
a write tool with no rationale is REJECTED. The agent must justify every write.

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

# One correlation id per server process — groups this agent session's proposals so
# the human sees them together in P1 (D-W4c.3).
SESSION_ID = uuid.uuid4().hex
ACTOR = "mcp:writer"


class RationaleRequired(Exception):
    """Raised when a propose tool is called with an empty rationale (D-W4c.3 — the
    agent must explain every write)."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit(tool: str, params: dict[str, Any]) -> None:
    """Append one audit row per MCP propose call (D-W4c.4). Fail-soft: an audit
    failure must NOT break the propose the agent asked for (the proposal already
    enqueued; audit is a secondary add-on — memory fail-closed-write-fail-soft-addon)."""
    try:
        proposals_store.append_audit(
            tool=tool, params=params, actor=ACTOR,
            correlation_id=SESSION_ID, ts=_now_iso(),
        )
    except Exception:  # noqa: BLE001 — audit is best-effort; never break a propose
        pass


def _require_rationale(rationale: str) -> str:
    """Enforce the explain-your-write norm (D-W4c.3): a propose with an empty /
    whitespace-only rationale is rejected. Returns the stripped rationale."""
    r = (rationale or "").strip()
    if not r:
        raise RationaleRequired(
            "rationale is required — the agent must explain WHY it proposes this write"
        )
    return r


def _enqueue(kind: ProposalKind, *, target_id: int | None, payload: dict[str, Any],
             rationale: str, tool: str) -> dict[str, Any]:
    """Shared path: validate rationale → audit → enqueue a PENDING proposal. Returns
    the stored proposal dict. NOTHING is applied to the vault (W4a invariant)."""
    r = _require_rationale(rationale)
    _audit(tool, {"kind": kind, "targetId": target_id, "payload": payload})
    # F1-S1: the MCP write-server is the AGENT channel → it (and ONLY it) is
    # auto-apply-eligible. The REST router does NOT pass this, so a human-channel
    # POST can never auto-apply regardless of the actor string it sends. The trust
    # boundary keys on the CALLER (this server), not on inp.actor.
    return create_proposal(
        ProposalCreateInput(kind=kind, targetId=target_id, payload=payload,
                            rationale=r, actor=ACTOR, correlationId=SESSION_ID),
        auto_apply_eligible=True,
    )


# --------------------------------------------------------------------------- #
# Propose tools — each ENQUEUES one pending proposal (D-W4c.3). Plain fns        #
# returning the stored proposal dict; the FastMCP registration wraps them.      #
# A returned proposal has status="pending" — the agent can confirm it queued,    #
# but it is NOT in the vault until a human accepts in P1.                        #
# --------------------------------------------------------------------------- #
def propose_note(title: str, content: str, rationale: str,
                 tags: list[str] | None = None) -> dict[str, Any]:
    """Propose a NEW note (kind=note_create). Lands as pending; a human accepts in
    P1 to create it. ``rationale`` (why this note matters) is REQUIRED."""
    payload = {"title": title, "content": content, "tags": tags or []}
    return _enqueue("note_create", target_id=None, payload=payload,
                    rationale=rationale, tool="propose_note")


def propose_edit(note_id: int, rationale: str, title: str | None = None,
                 content: str | None = None) -> dict[str, Any]:
    """Propose an EDIT to an existing note (kind=note_edit). Only the given fields
    change. Lands pending; human accepts in P1. ``rationale`` REQUIRED."""
    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if content is not None:
        payload["content"] = content
    return _enqueue("note_edit", target_id=int(note_id), payload=payload,
                    rationale=rationale, tool="propose_edit")


def propose_link(from_note_id: int, target: str, rationale: str) -> dict[str, Any]:
    """Propose ADDING a [[target]] link to a note's body (kind=link_add). ``target``
    is a note id or title. Lands pending; human accepts in P1. ``rationale`` REQUIRED."""
    return _enqueue("link_add", target_id=int(from_note_id),
                    payload={"target": str(target)}, rationale=rationale,
                    tool="propose_link")


def propose_unlink(note_id: int, target: str, rationale: str) -> dict[str, Any]:
    """Propose REMOVING a [[target]] link from a note's body (kind=link_remove).
    Lands pending; human accepts in P1. ``rationale`` REQUIRED."""
    return _enqueue("link_remove", target_id=int(note_id),
                    payload={"target": str(target)}, rationale=rationale,
                    tool="propose_unlink")


def propose_merge(source_id: int, target_id: int, rationale: str) -> dict[str, Any]:
    """Propose MERGING source_id INTO target_id (kind=merge). Lands pending; human
    accepts in P1. ``rationale`` (why these are duplicates) REQUIRED."""
    payload = {"sourceId": int(source_id), "targetId": int(target_id)}
    return _enqueue("merge", target_id=int(target_id), payload=payload,
                    rationale=rationale, tool="propose_merge")


def propose_moc(title: str, content: str, rationale: str) -> dict[str, Any]:
    """Propose a Map-of-Content note (kind=moc) — a note whose body links members
    + articulates a throughline. Lands pending; human accepts in P1. ``rationale``
    REQUIRED."""
    payload = {"title": title, "content": content}
    return _enqueue("moc", target_id=None, payload=payload,
                    rationale=rationale, tool="propose_moc")


# Registry (name → logic fn) — single source of truth; tests + FastMCP iterate it.
TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "propose_note": propose_note,
    "propose_edit": propose_edit,
    "propose_link": propose_link,
    "propose_unlink": propose_unlink,
    "propose_merge": propose_merge,
    "propose_moc": propose_moc,
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
    return mcp


def main() -> None:
    """stdio entrypoint — Claude Code launches this via its mcp config (SEPARATE
    registration from the read server)."""
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
