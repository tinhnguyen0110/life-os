"""modules/wiki/router.py — Wiki REST endpoints (Sprint W1a).

Mounts at ``/wiki`` via the registry (``MODULE`` below). Adding this folder is the
ONLY wiring needed — no edit to ``core/`` or ``main.py`` (registry auto-discovers
``MODULE`` from this file, the projects/notes fallback path).

W1a scope = identity + store + single-writer queue + CRUD. Links/FTS/graph are
W1b/W1c. This router is HTTP shape + status codes only — all mutation logic lives
in ``service.py`` (every write goes through the single-writer changes-queue).
Envelope: ``core.responses.ok`` → ``{success, data, warning?}``. Errors via
``HTTPException`` (404 missing note; 422 validation is FastAPI/Pydantic auto).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from core.base import BaseModule
from core.responses import ok

from . import proposals_service, reader, service
from .proposals_schema import (
    BatchAcceptInput,
    DecideInput,
    ProposalCreateInput,
)
from .schema import MergeInput, NoteCreateInput, NoteUpdateInput

logger = logging.getLogger("life-os.wiki.router")

router = APIRouter(tags=["wiki"])


@router.get("")
def wiki_info():
    """Liveness/info for the wiki module. The note CRUD surface is below."""
    return ok(data={"module": "wiki", "status": "ok"})


@router.get("/search")
def search(q: str = ""):
    """Full-text search → ``[{id, title, snippet, status}]`` ranked by relevance
    (C1). Empty/malformed ``q`` → empty list (never 500)."""
    return ok(data=reader.search(q))


@router.get("/overview")
def overview():
    """Vault overview (C4): ``{stats, inbox, orphans, recentActivity, proposalCount}``.
    Empty vault → ``stats.pctWithLink: null`` + a warning (never 0/div-zero)."""
    data, warning = reader.overview()
    return ok(data=data, warning=warning)


@router.get("/inbox")
def inbox():
    """Fleeting notes awaiting triage (C5), oldest→newest. ``aiSuggest: null`` (M4)."""
    return ok(data=reader.inbox())


@router.get("/graph")
def graph(note: int, depth: int = 2):
    """Ego-graph 1–2 hop around ``note`` (C3): ``{center, nodes, edges, clusters}``.
    404 if the center note is absent. ``clusters: []`` in W1c (AI clustering = M4)."""
    g = reader.ego_graph(note, depth)
    if g is None:
        raise HTTPException(status_code=404, detail=f"wiki note {note} not found")
    return ok(data=g)


@router.post("/notes")
def create_note(body: NoteCreateInput):
    """Create a note (capture → fleeting). Server-set id + timestamps. Goes through
    the single-writer queue → 1 git commit + 1 op_log row."""
    note = service.create_note(body)
    return ok(data=note.model_dump())


@router.post("/notes/merge")
def merge_notes(body: MergeInput):
    """Merge ``sourceId`` INTO ``targetId`` (B5/D6): source deleted, a redirect
    tombstone written, inbound links repointed. Returns the target note. 422 if the
    ids are equal; 404 if either note is absent."""
    try:
        note = service.merge_notes(body.sourceId, body.targetId)
    except service.MergeError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except service.NoteNotFound as exc:
        raise HTTPException(status_code=404, detail=f"wiki note {exc} not found")
    return ok(data=note.model_dump(),
              warning=f"merged #{body.sourceId} into #{body.targetId}")


@router.get("/notes/{note_id}")
def get_note(note_id: int):
    """One note. Follows a redirect tombstone (a merged-away id returns the merge
    target + a warning, NOT 404 — citations survive, B5). 404 only if the id never
    existed (or was plain-deleted, not merged)."""
    note, warning = service.resolve_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail=f"wiki note {note_id} not found")
    return ok(data=note.model_dump(), warning=warning)


@router.get("/notes/{note_id}/backlinks")
def get_backlinks(note_id: int):
    """Backlinks for a note: ``{linked, unlinked, outbound}`` (B3). 404 if the note
    is absent. ``unlinked`` ships ``[]`` in W1b (FTS-backed, populated W1c)."""
    if service.get_note(note_id) is None:
        raise HTTPException(status_code=404, detail=f"wiki note {note_id} not found")
    return ok(data=reader.backlinks(note_id))


@router.post("/notes/{note_id}/refine")
def refine_note(note_id: int, body: NoteUpdateInput):
    """REFINE a note (C6/D9): update-path + the ≥1-link HARD GATE. 404 if absent;
    422 if the note would have 0 links and the vault is past cold-start. On the
    cold-start exception (vault < threshold) it succeeds with a warning."""
    try:
        note, warning = service.refine_note(note_id, body)
    except service.NoteNotFound:
        raise HTTPException(status_code=404, detail=f"wiki note {note_id} not found")
    except service.RefineGateError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ok(data=note.model_dump(), warning=warning)


@router.put("/notes/{note_id}")
def update_note(note_id: int, body: NoteUpdateInput):
    """Partial-update a note in place (preserve created+id; bump updated unless a
    no-op touch). Goes through the queue. 404 if absent."""
    try:
        note = service.update_note(note_id, body)
    except service.NoteNotFound:
        raise HTTPException(status_code=404, detail=f"wiki note {note_id} not found")
    return ok(data=note.model_dump())


@router.delete("/notes/{note_id}")
def delete_note(note_id: int):
    """Delete a note (1 git commit removes the file; cache row hard-deleted; op_log
    keeps the delete record). 404 if absent."""
    try:
        service.delete_note(note_id)
    except service.NoteNotFound:
        raise HTTPException(status_code=404, detail=f"wiki note {note_id} not found")
    return ok(data={"deleted": note_id})


# --------------------------------------------------------------------------- #
# W4a — Proposal / approval queue (M4 trust boundary in code)                   #
# Every AI mutation lands here as a PENDING proposal; a human accepts (applies   #
# via the M1 single-writer) or rejects (nothing applied). Static paths are       #
# declared BEFORE /proposals/{proposal_id} so "batch-accept" isn't captured as   #
# an id.                                                                         #
# --------------------------------------------------------------------------- #
@router.post("/proposals")
def create_proposal(body: ProposalCreateInput):
    """Enqueue a proposal (PENDING). Records intent only — NOTHING is written to
    the vault until a human accepts. Returns the stored proposal."""
    return ok(data=proposals_service.create_proposal(body))


@router.get("/proposals")
def list_proposals(status: str = "pending"):
    """Proposals newest-first. ``status`` defaults to ``pending`` (the P1 review
    queue's default view); pass ``accepted`` / ``rejected`` to filter, or ``all``
    for every proposal. Includes a ``counts`` map for the queue badge. Empty queue
    → ``proposals: []`` (honest empty state, never 500/null)."""
    filter_status = None if status == "all" else status
    data = proposals_service.list_proposals(filter_status)
    return ok(data={"proposals": data, "counts": proposals_service.count_by_status()})


@router.post("/proposals/accept-batch")
def accept_batch_proposals(body: BatchAcceptInput):
    """Accept many proposals in one call (P1 batch action). Each applies
    independently — one failure never aborts the rest. Returns
    ``{results: [{id, ok, proposal?, error?}], accepted, failed}``."""
    return ok(data=proposals_service.batch_accept(body.ids, decided_by=body.decidedBy))


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: int):
    """One proposal. 404 if absent."""
    p = proposals_service.get_proposal(proposal_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"wiki proposal {proposal_id} not found")
    return ok(data=p)


@router.post("/proposals/{proposal_id}/accept")
def accept_proposal(proposal_id: int, body: DecideInput | None = None):
    """ACCEPT: apply the mutation through the M1 single-writer, then mark accepted.
    404 absent · 409 already decided · 422 the payload/mutation is invalid (the
    proposal stays pending so it can be retried)."""
    decided_by = (body or DecideInput()).decidedBy
    try:
        p = proposals_service.accept_proposal(proposal_id, decided_by=decided_by)
    except proposals_service.ProposalNotFound:
        raise HTTPException(status_code=404, detail=f"wiki proposal {proposal_id} not found")
    except proposals_service.AlreadyDecided as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except proposals_service.ApplyError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ok(data=p, warning=f"applied proposal #{proposal_id} → note #{p['appliedNoteId']}")


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: int, body: DecideInput | None = None):
    """REJECT: mark rejected. NOTHING is applied. 404 absent · 409 already decided."""
    decided_by = (body or DecideInput()).decidedBy
    try:
        p = proposals_service.reject_proposal(proposal_id, decided_by=decided_by)
    except proposals_service.ProposalNotFound:
        raise HTTPException(status_code=404, detail=f"wiki proposal {proposal_id} not found")
    except proposals_service.AlreadyDecided as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return ok(data=p)


MODULE = BaseModule(name="wiki", router=router)
