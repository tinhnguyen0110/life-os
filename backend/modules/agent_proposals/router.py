"""modules/agent_proposals/router.py — REST surface for the human review-apply loop (MCP-4).

Mounts at ``/agent-proposals`` via the registry (``MODULE``). Locked envelope ({success,
data, warning?}). The human reviews the agent's pending proposals and disposes:

  GET  /agent-proposals                 list proposals (default: status=pending)
  GET  /agent-proposals/{id}            one proposal (404 if unknown)
  GET  /agent-proposals/{id}/audit      the accept/reject audit trail for one proposal
  POST /agent-proposals/{id}/accept     ACCEPT → apply to the target module (idempotent)
  POST /agent-proposals/{id}/reject     REJECT → status flip, no apply (idempotent)

Apply logic lives in ``mcp_servers/proposals_service.py`` (the human-only apply layer).
Accept/reject are idempotent: calling twice never applies twice. No auth (single-user,
no-auth app — these are human-triggered local calls; the gate is that they're separate
from the agent's enqueue-only channel, not an auth check).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from core.base import BaseModule
from core.responses import ok

from mcp_servers import proposals_service as svc
from mcp_servers import proposals_store as store

logger = logging.getLogger("life-os.agent_proposals.router")

router = APIRouter(tags=["agent-proposals"])


@router.get("")
def list_agent_proposals(status: str | None = "pending", module: str | None = None,
                         limit: int = 200):
    """Agent proposals (newest first). Defaults to status=pending (the review queue);
    pass ``status=`` (empty) or another status to widen. Optional ``module`` filter."""
    # An explicit empty string means "all statuses" (don't filter).
    status_filter = status or None
    proposals = svc.list_proposals(status=status_filter, module=module, limit=limit)
    return ok(data={"proposals": proposals, "counts": svc.count_by_status()})


@router.get("/{proposal_id}")
def get_agent_proposal(proposal_id: int):
    """One proposal by id. 404 if unknown."""
    proposal = svc.get_proposal(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"proposal {proposal_id} not found")
    return ok(data=proposal)


@router.get("/{proposal_id}/audit")
def get_agent_proposal_audit(proposal_id: int):
    """The accept/reject audit trail for one proposal (who/what/when)."""
    if svc.get_proposal(proposal_id) is None:
        raise HTTPException(status_code=404, detail=f"proposal {proposal_id} not found")
    return ok(data={"audit": svc.list_audit(proposal_id=proposal_id)})


@router.post("/{proposal_id}/accept")
def accept_agent_proposal(proposal_id: int, decided_by: str = "user"):
    """ACCEPT → apply the proposal to its target module's real create service. Idempotent
    (a 2nd accept does NOT re-apply). 404 if unknown. The response carries the applied
    state — ``appliedRef`` (the created entry id) on success, or ``applyError`` if the
    kind has no apply handler / the apply failed."""
    try:
        result = svc.accept(proposal_id, decided_by=decided_by)
    except svc.ProposalNotFound:
        raise HTTPException(status_code=404, detail=f"proposal {proposal_id} not found")
    warning = result.get("applyError")
    return ok(data=result, warning=warning)


@router.post("/{proposal_id}/reject")
def reject_agent_proposal(proposal_id: int, decided_by: str = "user"):
    """REJECT → flip status to rejected. NEVER applies. Idempotent. 404 if unknown."""
    try:
        result = svc.reject(proposal_id, decided_by=decided_by)
    except svc.ProposalNotFound:
        raise HTTPException(status_code=404, detail=f"proposal {proposal_id} not found")
    return ok(data=result)


def _ensure_tables() -> None:
    """Idempotently register the agent_proposals tables when the module mounts, so the
    queue exists even before the MCP write-server has run (the human surface and the
    agent channel share the same table on the shared db)."""
    try:
        store.init_proposal_tables()
    except Exception as exc:  # noqa: BLE001 — never block mount on a table init hiccup
        logger.error("agent_proposals table init failed: %s", exc)


_ensure_tables()

MODULE = BaseModule(name="agent-proposals", router=router)
