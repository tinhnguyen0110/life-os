"""modules/wiki/proposals_schema.py — Wiki proposal / approval-queue shapes (Sprint W4a).

The M4 trust boundary in CODE: every AI (or any non-direct) mutation lands as a
PROPOSAL row in a human-ratified review queue, never a direct vault write. The
P1 Queue screen batch-accepts heterogeneous proposals; the MCP write server
(W4c) enqueues into this same queue.

Design anchors (plan_sprint_W4.md):
  - D-W4.1: ONE general ``wiki_proposals`` table (not note-body-only ``agent_writes``)
    so link/merge/MOC/edit proposals share one review surface + one audit path.
  - D-W4.2: on ACCEPT the apply-handler dispatches the equivalent M1 mutation
    THROUGH the existing single-writer queue — proposals never write files directly.

``kind`` enum (D-W4.1):
  note_create  — propose a brand-new note          → service.create_note
  note_edit    — propose an edit to an existing note (body/title/status/tags;
                 this also covers link_add / link_remove / rewrite, since links
                 are derived from the body) → service.update_note
  link_add     — propose adding a [[target]] link to a note's body
  link_remove  — propose removing a [[target]] link from a note's body
  merge        — propose merging sourceId INTO targetId → service.merge_notes
  moc          — propose a Map-of-Content note (a note linking members) →
                 service.create_note (a note whose body is the MOC scaffold)

``status`` enum: pending → accepted | rejected (terminal).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# --- Enums (Literal-locked at the boundary) -------------------------------- #
ProposalKind = Literal[
    "note_create", "note_edit", "link_add", "link_remove", "merge", "moc",
    "note_softdelete", "note_restore",  # #94 soft-delete + restore via the proposal chokepoint
]
ProposalStatus = Literal["pending", "accepted", "rejected"]


class ProposalCreateInput(BaseModel):
    """``POST /wiki/proposals`` body — enqueue one proposal (pending).

    ``payload`` is a kind-specific JSON object carrying the mutation INTENT
    (validated per-kind in the service apply-handler, NOT here — a malformed
    payload only fails at accept-time so a proposal can always be recorded +
    audited even if its intent is later found invalid). ``targetId`` is the
    primary note the proposal concerns (None for note_create / moc which create a
    new note). ``correlationId`` threads one agent session's calls (D-W4.4).

    Per-kind ``payload`` shape (the apply-handler contract):
      note_create / moc → {title?, content?, status?, noteType?, tags?, author?}
      note_edit         → {title?, content?, status?, noteType?, trustTier?,
                           aliases?, tags?}
      link_add          → {target: "<id or title>", display?}
      link_remove       → {target: "<id or title>"}
      merge             → {sourceId: int, targetId: int}
    """

    kind: ProposalKind
    targetId: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(default="", max_length=4000)
    actor: str = Field(default="agent", max_length=200)
    correlationId: str | None = Field(default=None, max_length=200)

    @field_validator("actor")
    @classmethod
    def _strip_actor(cls, v: str) -> str:
        # Empty actor is meaningless for an audit trail — default to "agent".
        return v.strip() or "agent"


class Proposal(BaseModel):
    """A stored proposal (response model). ``decided`` / ``decidedBy`` are set only
    once a human accepts/rejects; ``appliedNoteId`` records the note the apply
    landed on (the created id for note_create/moc, the target for edit/merge) so
    the UI can deep-link the result."""

    id: int
    kind: ProposalKind
    targetId: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""
    actor: str = "agent"
    status: ProposalStatus = "pending"
    correlationId: str | None = None
    created: str
    decided: str | None = None
    decidedBy: str | None = None
    appliedNoteId: int | None = None


class DecideInput(BaseModel):
    """``POST /wiki/proposals/{id}/accept|reject`` body. ``decidedBy`` is who
    ratified (default ``human`` — single-user, no auth)."""

    decidedBy: str = Field(default="human", max_length=200)

    @field_validator("decidedBy")
    @classmethod
    def _strip_by(cls, v: str) -> str:
        return v.strip() or "human"


class BatchAcceptInput(BaseModel):
    """``POST /wiki/proposals/batch-accept`` body — accept many proposals in one
    call (the P1 Queue batch action). ``ids`` must be non-empty. Each is applied
    independently; the response reports per-id success/failure (one bad apply
    never aborts the rest)."""

    ids: list[int] = Field(min_length=1)
    decidedBy: str = Field(default="human", max_length=200)

    @field_validator("decidedBy")
    @classmethod
    def _strip_by(cls, v: str) -> str:
        return v.strip() or "human"
