"""mcp_servers/write_server.py — GATED MCP WRITE server for life-os (MCP-3).

Symmetric to the read-server, opposite capability: the read-server READS everything +
writes nothing; this server PROPOSES everything + applies nothing. It closes the
agent loop the life-os way — **the agent proposes, the human disposes**:

    external Claude Code  →  propose_*  →  pending row in the agent_proposals queue
                                          →  (human reviews + applies — SEPARATE, later)

Every write tool ENQUEUES one pending proposal (``mcp_servers.proposals_store.enqueue``)
and returns it with ``status="pending"``. NOTHING is written to any module: a proposal
is pure INTENT until a human accepts it. This is the gate.

THE CAPABILITY GATE (enqueue-only, STRUCTURAL — not a flag, mirrors wiki's write
server):
This module imports ONLY:
  - ``enqueue`` (the generic queue append — records INTENT only; the store has NO
    apply/mutate-the-target function, so even the queue layer can't change a module),
It imports NO module-mutation fn (create_entry/update_entry/delete_entry of decision/
journal, upsert_holding, register_project/abandon_project/refresh_project, NoteInput
writers, …), NO ``mark_decided`` (accept/reject is the HUMAN's action, not the agent's),
and NO ``apply``. A test (``tests/test_mcp_write.py``) asserts none of those are
reachable in this module's namespace nor imported (grep + AST) — the gate proven by
code, not by this docstring. (Inverse of the read server: read has NO enqueue; write
has enqueue-ONLY — two processes, two capability sets, least-privilege.)

Each propose tool REQUIRES a ``rationale`` — the agent must explain WHY it proposes the
write. A propose with an empty/whitespace rationale is REJECTED (RationaleRequired).

Run:  python -m mcp_servers.write_server   (stdio; a SEPARATE Claude Code mcp
registration from the read server — distinct process, distinct capability set.)

NOTE: no ``from __future__ import annotations`` — FastMCP introspects real param
annotations at registration (stringized annotations crash issubclass), same as the
read server + the wiki MCP servers.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

# ENQUEUE-ONLY import (the capability gate — see module docstring + the no-mutate test).
# enqueue records INTENT only; the store exposes no apply/mutate-the-target fn, so this
# is the entire write surface the agent channel has.
from mcp_servers.proposals_store import enqueue as _enqueue
# NG2: surface the WIKI propose tools here too, delegating to the wiki write-server's
# propose fns. They route to the SEPARATE wiki_proposals queue (W4a, via create_proposal)
# — NOT the agent_proposals queue this server's other tools use. Both queues stay
# distinct. These are ENQUEUE-ONLY (the wiki write-server itself has the no-mutate/no-
# accept gate); we import only its propose_* fns, never a wiki mutate/accept fn.
from modules.wiki.mcp.write_server import propose_note as _wiki_propose_note
from modules.wiki.mcp.write_server import propose_edit as _wiki_propose_edit
from modules.wiki.mcp.write_server import propose_link as _wiki_propose_link
from modules.wiki.mcp.write_server import propose_unlink as _wiki_propose_unlink
from modules.wiki.mcp.write_server import propose_merge as _wiki_propose_merge
from modules.wiki.mcp.write_server import propose_moc as _wiki_propose_moc

# One correlation id per server process — groups this agent session's proposals so the
# human sees them together in review.
SESSION_ID = uuid.uuid4().hex
ACTOR = "mcp:writer"


class RationaleRequired(Exception):
    """Raised when a propose tool is called with an empty rationale — the agent must
    explain every write."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_rationale(rationale: str) -> str:
    """Enforce the explain-your-write norm: a propose with an empty / whitespace-only
    rationale is rejected. Returns the stripped rationale."""
    r = (rationale or "").strip()
    if not r:
        raise RationaleRequired(
            "rationale is required — the agent must explain WHY it proposes this write"
        )
    return r


def _propose(*, module: str, kind: str, payload: dict[str, Any],
             rationale: str) -> dict[str, Any]:
    """Shared path: validate rationale → enqueue a PENDING proposal. Returns the stored
    proposal dict (status='pending'). NOTHING is applied to any module."""
    r = _require_rationale(rationale)
    return _enqueue(
        module=module, kind=kind, payload=payload, rationale=r,
        actor=ACTOR, correlation_id=SESSION_ID, created=_now_iso(),
    )


# --------------------------------------------------------------------------- #
# Propose tools — each ENQUEUES one pending proposal. Plain fns returning the    #
# stored proposal dict; the FastMCP registration wraps them. A returned proposal #
# has status="pending" — the agent confirms it queued, but it is NOT applied to   #
# any module until a human accepts it.                                           #
# --------------------------------------------------------------------------- #
def propose_decision(decision: str, confidence: int, domain: str, rationale: str,
                     thesis: str | None = None,
                     falsificationCondition: str | None = None,
                     predicted: float | None = None) -> dict[str, Any]:
    """Propose a NEW decision-journal entry (module=decision_journal, kind=decision_create).
    ``confidence`` 0-100, ``domain`` = the bias-cluster key. Lands PENDING; a human
    accepts to create it. ``rationale`` (why this decision is worth logging) REQUIRED."""
    payload = {
        "decision": decision, "confidence": confidence, "domain": domain,
        "thesis": thesis, "falsificationCondition": falsificationCondition,
        "predicted": predicted,
    }
    return _propose(module="decision_journal", kind="decision_create",
                    payload=payload, rationale=rationale)


def propose_note(title: str, rationale: str, body: str = "",
                 tags: list[str] | None = None) -> dict[str, Any]:
    """Propose a NEW note (module=notes, kind=note_create). Lands PENDING; a human
    accepts to create it. ``rationale`` REQUIRED. (Distinct from the WIKI note
    proposal — this targets the lightweight notes module.)"""
    payload = {"title": title, "body": body, "tags": tags or []}
    return _propose(module="notes", kind="note_create", payload=payload,
                    rationale=rationale)


def propose_journal(action: str, asset: str, reason: str, rationale: str,
                    size: str = "", px: str = "", tag: str = "",
                    confidence: int | None = None) -> dict[str, Any]:
    """Propose a NEW trade-journal entry (module=journal, kind=journal_create).
    ``action`` (buy/sell/…), ``asset``, ``reason`` (the trade thesis). Lands PENDING;
    a human accepts to create it. ``rationale`` (why propose logging this trade)
    REQUIRED."""
    payload = {
        "action": action, "asset": asset, "reason": reason, "size": size,
        "px": px, "tag": tag, "confidence": confidence,
    }
    return _propose(module="journal", kind="journal_create", payload=payload,
                    rationale=rationale)


def propose_project_update(project_id: str, rationale: str,
                           progress: int | None = None, next: str | None = None,
                           desc: str | None = None) -> dict[str, Any]:
    """Propose an UPDATE to a project's human-authored status fields (module=projects,
    kind=project_update): only the given fields change. (git-derived fields like health
    are read-only — not proposable.) Lands PENDING; a human accepts to apply it.
    ``rationale`` REQUIRED."""
    payload: dict[str, Any] = {"projectId": project_id}
    if progress is not None:
        payload["progress"] = progress
    if next is not None:
        payload["next"] = next
    if desc is not None:
        payload["desc"] = desc
    return _propose(module="projects", kind="project_update", payload=payload,
                    rationale=rationale)


# --------------------------------------------------------------------------- #
# NG2 — WIKI propose tools, surfaced on the whole-app write-server. Thin         #
# delegators to the wiki write-server's propose fns → the SEPARATE wiki_proposals#
# queue (NOT agent_proposals). Each is enqueue-only + rationale-required (the     #
# wiki fns enforce both). The agent now proposes wiki writes from the one        #
# write-server alongside the other modules, queues stay distinct.                #
# --------------------------------------------------------------------------- #
def wiki_propose_note(title: str, content: str, rationale: str,
                      tags: list[str] | None = None) -> dict[str, Any]:
    """Propose a NEW wiki note → the wiki_proposals queue (W4a). Lands PENDING; a
    human ratifies in the wiki P1 queue. ``rationale`` REQUIRED."""
    return _wiki_propose_note(title, content, rationale, tags=tags)


def wiki_propose_edit(note_id: int, rationale: str, title: str | None = None,
                      content: str | None = None) -> dict[str, Any]:
    """Propose an EDIT to a wiki note → wiki_proposals queue. ``rationale`` REQUIRED."""
    return _wiki_propose_edit(note_id, rationale, title=title, content=content)


def wiki_propose_link(from_note_id: int, target: str, rationale: str) -> dict[str, Any]:
    """Propose ADDING a [[target]] link to a wiki note → wiki_proposals. ``rationale`` REQUIRED."""
    return _wiki_propose_link(from_note_id, target, rationale)


def wiki_propose_unlink(note_id: int, target: str, rationale: str) -> dict[str, Any]:
    """Propose REMOVING a [[target]] link from a wiki note → wiki_proposals. ``rationale`` REQUIRED."""
    return _wiki_propose_unlink(note_id, target, rationale)


def wiki_propose_merge(source_id: int, target_id: int, rationale: str) -> dict[str, Any]:
    """Propose MERGING wiki note source_id INTO target_id → wiki_proposals. ``rationale`` REQUIRED."""
    return _wiki_propose_merge(source_id, target_id, rationale)


def wiki_propose_moc(title: str, content: str, rationale: str) -> dict[str, Any]:
    """Propose a wiki Map-of-Content note → wiki_proposals. ``rationale`` REQUIRED."""
    return _wiki_propose_moc(title, content, rationale)


# Registry (name → logic fn) — single source of truth; tests + FastMCP iterate it.
TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "propose_decision": propose_decision,
    "propose_note": propose_note,
    "propose_journal": propose_journal,
    "propose_project_update": propose_project_update,
    # NG2: wiki propose tools → the wiki_proposals queue (separate from agent_proposals)
    "wiki_propose_note": wiki_propose_note,
    "wiki_propose_edit": wiki_propose_edit,
    "wiki_propose_link": wiki_propose_link,
    "wiki_propose_unlink": wiki_propose_unlink,
    "wiki_propose_merge": wiki_propose_merge,
    "wiki_propose_moc": wiki_propose_moc,
}


# --------------------------------------------------------------------------- #
# FastMCP server — registers each propose tool over stdio. Lazy (build_server)   #
# so importing this module for the no-mutate test doesn't spin up a server.      #
# --------------------------------------------------------------------------- #
def build_server(transport_security: Any = None) -> Any:
    """Construct the FastMCP write server with all propose tools registered.

    ``transport_security`` (default None = stdio-identical) is threaded into FastMCP so
    main.py can mount this over streamable-http (DNS-rebinding OFF for remote/LAN clients,
    MCP-HTTP). None keeps the stdio entrypoint behaviourally unchanged + the no-mutate
    capability gate intact (this adds no import/symbol — just an optional pass-through)."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("life-os-write", transport_security=transport_security)
    for fn in TOOLS.values():
        mcp.add_tool(fn, description=fn.__doc__)
    return mcp


def main() -> None:
    """stdio entrypoint — Claude Code launches this via its mcp config (SEPARATE
    registration from the read server)."""
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
