"""mcp_servers/proposals_service.py — the human-side APPLY layer for agent proposals (MCP-4).

This is the piece the write-server deliberately does NOT have. The gate (MCP-3): the
agent can only ENQUEUE pending proposals; it cannot apply them. Here is where a PENDING
proposal becomes a real module mutation — and it is reachable ONLY from the human-
triggered ``/agent-proposals`` endpoints (modules/agent_proposals/router.py), never from
the agent. The agent proposes; the human disposes.

  accept(id):  PENDING → ACCEPTED, then APPLY = call the target module's REAL create
               service (decision_journal.create_entry / notes.create_note /
               journal.create_entry). The created entry id is recorded as applied_ref.
  reject(id):  PENDING → REJECTED. NO apply.

IDEMPOTENCY (spec: "accept 2 lần không apply 2 lần"): the status flip is atomic in the
store (``mark_decided`` UPDATEs ``WHERE status='pending'`` and reports whether THIS call
transitioned the row). We apply the target-module write ONLY on a real transition, so a
second accept is a no-op that returns the already-applied state — the entry is created
exactly once.

AUDIT: every accept/reject appends an immutable ``agent_proposals_audit`` row (who,
what, when, + applied_ref / apply_error).

MODULE-TOUCH NOTE: this is the FIRST place the MCP flow calls another module's service.
It only CALLS the public create services (read-as-API) — it does NOT modify any module's
logic. The apply handlers are kept in a small registry keyed by ``kind`` so adding a new
proposable kind = adding a handler here, never editing a module.

``project_update`` has NO public partial-update service on the projects module (the
module exposes register/refresh/abandon/restore only; adding an update fn would mean
EDITING the projects module, which is out of scope). So accepting a project_update flips
the status to accepted but records an ``apply_error`` ("no apply handler for kind
project_update") instead of fabricating a write — honest, and the proposal is still
marked decided so it leaves the pending queue. (Decide-and-log: a projects partial-update
service is a future projects-module task.)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

from mcp_servers import proposals_store as store

logger = logging.getLogger("life-os.mcp.proposals_service")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProposalNotFound(Exception):
    """Raised when an accept/reject targets an unknown proposal id."""


# --------------------------------------------------------------------------- #
# Apply handlers — one per proposable ``kind``. Each takes the proposal payload  #
# and calls the target module's REAL create service, returning the created       #
# entry's id (the applied_ref). Imports are LOCAL to each handler so importing    #
# this module doesn't pull every module's service at import time (and so the      #
# capability surface is obvious: only these handlers reach a module write).       #
# --------------------------------------------------------------------------- #
def _apply_decision_create(payload: dict[str, Any]) -> str:
    from modules.decision_journal.schema import DecisionInput
    from modules.decision_journal.service import create_entry

    body = DecisionInput(
        decision=payload["decision"],
        confidence=int(payload["confidence"]),
        domain=payload["domain"],
        thesis=payload.get("thesis"),
        falsificationCondition=payload.get("falsificationCondition"),
        predicted=payload.get("predicted"),
    )
    return create_entry(body).id


def _apply_note_create(payload: dict[str, Any]) -> str:
    from modules.notes.schema import NoteInput
    from modules.notes.service import create_note

    body = NoteInput(
        title=payload["title"],
        body=payload.get("body", ""),
        tags=payload.get("tags", []),
    )
    return create_note(body).id


def _apply_journal_create(payload: dict[str, Any]) -> str:
    from typing import cast

    from modules.journal.schema import Action, JournalInput
    from modules.journal.service import create_entry

    # WRITE-LOOP-E2E (#51): the agent's propose_journal stores ``action`` AS SENT (lowercase
    # "buy"/"sell"), but JournalInput.action is Literal["BUY","SELL"] (uppercase only) → a
    # raw pass-through pydantic-fails on accept and the trade never lands. Normalize at the
    # APPLY boundary (NOT by widening the journal schema): upper-case whatever case the agent
    # sent. Fixes already-queued AND future journal_create proposals; defensive vs any case.
    # ``cast`` only satisfies the type-checker — pydantic still VALIDATES the Literal at
    # runtime (a non-BUY/SELL value raises, surfacing as an honest apply_error, not a crash).
    action = cast(Action, str(payload["action"]).upper())
    body = JournalInput(
        action=action,
        asset=payload["asset"],
        reason=payload["reason"],
        size=payload.get("size", ""),
        px=payload.get("px", ""),
        tag=payload.get("tag", ""),
        confidence=payload.get("confidence"),
    )
    return create_entry(body).id


# kind → apply handler. A kind WITHOUT a handler (e.g. project_update) accepts but
# records an apply_error instead of applying (no fabricated write, no module edit).
APPLY_HANDLERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "decision_create": _apply_decision_create,
    "note_create": _apply_note_create,
    "journal_create": _apply_journal_create,
}


# --------------------------------------------------------------------------- #
# read passthroughs (the human-review surface lists/gets the queue)             #
# --------------------------------------------------------------------------- #
def list_proposals(status: str | None = None, module: str | None = None,
                   limit: int = 200) -> list[dict[str, Any]]:
    return store.list_proposals(status=status, module=module, limit=limit)


def get_proposal(proposal_id: int) -> dict[str, Any] | None:
    return store.get_proposal(int(proposal_id))


def count_by_status() -> dict[str, int]:
    return store.count_by_status()


def list_audit(proposal_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
    return store.list_audit(proposal_id=proposal_id, limit=limit)


# --------------------------------------------------------------------------- #
# accept / reject — the HUMAN dispose actions (idempotent + audited)            #
# --------------------------------------------------------------------------- #
def accept(proposal_id: int, *, decided_by: str = "user") -> dict[str, Any]:
    """Accept a proposal: flip PENDING→ACCEPTED (atomic) then APPLY to the target
    module exactly once. Idempotent: a 2nd accept does NOT re-apply — it returns the
    already-applied state. Unknown id → ProposalNotFound."""
    existing = store.get_proposal(int(proposal_id))
    if existing is None:
        raise ProposalNotFound(f"proposal {proposal_id} not found")

    transitioned, row = store.mark_decided(
        int(proposal_id), status="accepted", decided=_now_iso(), decided_by=decided_by,
    )
    if not transitioned:
        # Already decided (accepted or rejected) — IDEMPOTENT no-op. Do NOT apply again.
        logger.info("accept(%s): already %s — no re-apply", proposal_id,
                    row["status"] if row else "?")
        return row if row is not None else existing

    # First (and only) transition → apply the target-module write exactly once.
    kind = row["kind"]
    handler = APPLY_HANDLERS.get(kind)
    applied_ref: str | None = None
    apply_error: str | None = None
    if handler is None:
        apply_error = f"no apply handler for kind {kind!r} — accepted but not applied"
        logger.warning("accept(%s): %s", proposal_id, apply_error)
    else:
        try:
            applied_ref = handler(row["payload"])
        except Exception as exc:  # noqa: BLE001 — surface the apply failure, keep status
            apply_error = f"apply failed: {type(exc).__name__}: {exc}"
            logger.error("accept(%s) apply failed: %s", proposal_id, exc)

    store.set_applied_ref(int(proposal_id), applied_ref=applied_ref, apply_error=apply_error)
    store.append_audit(
        proposal_id=int(proposal_id), action="accept", decided_by=decided_by,
        detail=(f"applied_ref={applied_ref}" if applied_ref else apply_error),
        ts=_now_iso(),
    )
    return store.get_proposal(int(proposal_id)) or row


def reject(proposal_id: int, *, decided_by: str = "user") -> dict[str, Any]:
    """Reject a proposal: flip PENDING→REJECTED. NEVER applies. Idempotent: a 2nd
    reject (or a reject after accept) is a no-op returning the current state. Unknown
    id → ProposalNotFound."""
    existing = store.get_proposal(int(proposal_id))
    if existing is None:
        raise ProposalNotFound(f"proposal {proposal_id} not found")

    transitioned, row = store.mark_decided(
        int(proposal_id), status="rejected", decided=_now_iso(), decided_by=decided_by,
    )
    if transitioned:
        store.append_audit(
            proposal_id=int(proposal_id), action="reject", decided_by=decided_by,
            detail=None, ts=_now_iso(),
        )
    else:
        logger.info("reject(%s): already %s — no-op", proposal_id,
                    row["status"] if row else "?")
    return row if row is not None else existing
