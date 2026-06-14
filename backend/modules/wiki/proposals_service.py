"""modules/wiki/proposals_service.py — proposal queue logic + apply-on-accept (W4a).

The M4 trust boundary enforced in CODE:
  - CREATE a proposal = record INTENT only (one ``wiki_proposals`` row, pending).
    NOTHING is written to the vault. An AI write can never land here.
  - ACCEPT = dispatch the equivalent M1 mutation THROUGH the existing single-writer
    queue (``service.create_note`` / ``update_note`` / ``merge_notes``). Proposals
    never write note files directly — all mutation stays in the one auditable place
    (D-W4.2 / spec D3). Then flip the row to ``accepted`` + record the landed note id.
  - REJECT = flip the row to ``rejected``. NOTHING is applied.

Apply-handlers per kind (D-W4.1):
  note_create / moc → service.create_note(NoteCreateInput(**payload))
  note_edit         → service.update_note(targetId, NoteUpdateInput(**payload))
  link_add          → read note body, append "[[target]]", update_note (link is
                      derived from the body — there is no standalone link write)
  link_remove       → read note body, strip the "[[target]]" occurrences, update_note
  merge             → service.merge_notes(payload.sourceId, payload.targetId)

Concurrency / idempotency: ``mark_decided`` flips the row pending→terminal ONLY if
still pending (a guarded UPDATE), so a double-accept or accept-after-reject is a
no-op (returns AlreadyDecided). The mutation is dispatched BEFORE the flip; if the
mutation raises, the row stays pending (fail-closed: a failed apply must remain
visible in the queue to retry, never silently consumed — memory
``fail-closed-write-fail-soft-addon``).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from . import proposals_store as pstore
from . import service
from .proposals_schema import ProposalCreateInput
from .schema import NoteCreateInput, NoteUpdateInput

logger = logging.getLogger("life-os.wiki.proposals_service")


class ProposalNotFound(Exception):
    """Raised when a proposal id is absent → router 404."""


class AlreadyDecided(Exception):
    """Raised when accept/reject targets a non-pending proposal → router 409."""


class ApplyError(Exception):
    """Raised when an accepted proposal's payload is invalid / its mutation fails
    → router 422. The proposal stays pending (fail-closed) so it can be retried."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Create (record intent only — no vault write)                                 #
# --------------------------------------------------------------------------- #
def create_proposal(inp: ProposalCreateInput) -> dict[str, Any]:
    """Enqueue one pending proposal. Records INTENT only — nothing is applied to
    the vault until a human accepts. Returns the stored proposal dict."""
    now = _now_iso()
    pid = pstore.insert_proposal(
        kind=inp.kind, target_id=inp.targetId, payload=inp.payload,
        rationale=inp.rationale, actor=inp.actor,
        correlation_id=inp.correlationId, created=now,
    )
    _audit("propose", {"proposalId": pid, "kind": inp.kind, "targetId": inp.targetId},
           actor=inp.actor, correlation_id=inp.correlationId, ts=now)
    logger.info("wiki proposal %s created (kind=%s actor=%s)", pid, inp.kind, inp.actor)
    result = pstore.get_proposal(pid)
    assert result is not None  # just inserted
    return result


def _audit(tool: str, params: dict[str, Any], *, actor: str,
           correlation_id: str | None, ts: str | None = None) -> None:
    """Append one immutable audit row for a proposal-queue action (D-W4.4). Every
    create/accept/reject is audited. Fail-SOFT: an audit-write failure must NOT
    fail the primary action (the proposal mutation already succeeded) — log +
    swallow (memory fail-closed-write-fail-soft-addon: audit is a secondary add-on)."""
    try:
        pstore.append_audit(tool=tool, params=params, actor=actor,
                            correlation_id=correlation_id, ts=ts or _now_iso())
    except Exception:  # noqa: BLE001 — audit is best-effort; never break the action
        logger.exception("wiki proposal audit append failed (tool=%s)", tool)


def get_proposal(proposal_id: int) -> dict[str, Any] | None:
    return pstore.get_proposal(proposal_id)


def list_proposals(status: str | None = None) -> list[dict[str, Any]]:
    return pstore.list_proposals(status)


def count_by_status() -> dict[str, int]:
    return pstore.count_by_status()


# --------------------------------------------------------------------------- #
# Apply-on-accept — dispatch the M1 mutation through the single-writer queue    #
# --------------------------------------------------------------------------- #
def _apply(proposal: dict[str, Any]) -> int | None:
    """Dispatch the proposal's intent as the equivalent M1 mutation (through the
    note single-writer queue). Returns the note id the apply landed on (created id
    for note_create/moc; the target for edit/link/merge). Raises ApplyError on a
    malformed payload or a mutation failure — the caller leaves the row pending."""
    kind = proposal["kind"]
    payload = proposal.get("payload") or {}
    target_id = proposal.get("targetId")
    actor = proposal.get("actor") or "agent"

    try:
        if kind in ("note_create", "moc"):
            # Provenance (spec §2b): a note born from a proposal carries the
            # PROPOSING actor as its author unless the payload set one explicitly,
            # so the vault records "this came from agent X", not a generic human.
            create_payload = dict(payload)
            create_payload.setdefault("author", actor)
            note = service.create_note(NoteCreateInput(**create_payload), actor=actor)
            return note.id

        if kind == "note_edit":
            if target_id is None:
                raise ApplyError("note_edit proposal has no targetId")
            note = service.update_note(target_id, NoteUpdateInput(**payload), actor=actor)
            return note.id

        if kind == "link_add":
            return _apply_link_add(target_id, payload, actor)

        if kind == "link_remove":
            return _apply_link_remove(target_id, payload, actor)

        if kind == "merge":
            src = payload.get("sourceId")
            tgt = payload.get("targetId")
            if src is None or tgt is None:
                raise ApplyError("merge proposal needs sourceId and targetId")
            note = service.merge_notes(int(src), int(tgt), actor=actor)
            return note.id

        raise ApplyError(f"unknown proposal kind {kind!r}")
    except ApplyError:
        raise
    except service.NoteNotFound as exc:
        raise ApplyError(f"target note {exc} not found") from exc
    except service.MergeError as exc:
        raise ApplyError(f"merge invalid: {exc}") from exc
    except service.RefineGateError as exc:  # pragma: no cover — edits use update, not refine
        raise ApplyError(f"refine gate: {exc}") from exc
    except (TypeError, ValueError) as exc:  # bad payload shape for the pydantic input
        raise ApplyError(f"invalid payload for {kind}: {exc}") from exc


def _wikilink_for(target: str) -> str:
    """Render the [[...]] token for a link target (an id or a title)."""
    return f"[[{str(target).strip()}]]"


def _apply_link_add(target_id: int | None, payload: dict[str, Any], actor: str) -> int:
    """Add a [[target]] link by appending it to the note body, then editing through
    the queue (links are derived from the body — B2). Idempotent: if the exact
    [[target]] token already appears in the body, the edit is a no-op touch (A5)."""
    if target_id is None:
        raise ApplyError("link_add proposal has no targetId")
    target = payload.get("target")
    if target is None or not str(target).strip():
        raise ApplyError("link_add proposal payload needs a 'target'")
    existing = service.get_note(target_id)
    if existing is None:
        raise ApplyError(f"target note {target_id} not found")
    token = _wikilink_for(target)
    if token in existing.content:
        # Already linked — record the (no-op) accept against this note.
        return target_id
    new_body = existing.content.rstrip()
    new_body = f"{new_body}\n\n{token}" if new_body else token
    note = service.update_note(target_id, NoteUpdateInput(content=new_body), actor=actor)
    return note.id


def _apply_link_remove(target_id: int | None, payload: dict[str, Any], actor: str) -> int:
    """Remove [[target]] link tokens from the note body, then edit through the
    queue. No-op (no error) if the link is absent. Strips both [[target]] and
    [[target|display]] forms for the given target."""
    if target_id is None:
        raise ApplyError("link_remove proposal has no targetId")
    target = payload.get("target")
    if target is None or not str(target).strip():
        raise ApplyError("link_remove proposal payload needs a 'target'")
    existing = service.get_note(target_id)
    if existing is None:
        raise ApplyError(f"target note {target_id} not found")
    t = re.escape(str(target).strip())
    # [[target]] or [[target|display]] — tolerate surrounding whitespace.
    pattern = re.compile(r"\[\[\s*" + t + r"\s*(?:\|[^\]]*)?\]\]")
    new_body = pattern.sub("", existing.content)
    if new_body == existing.content:  # link not present — no-op accept
        return target_id
    note = service.update_note(target_id, NoteUpdateInput(content=new_body), actor=actor)
    return note.id


# --------------------------------------------------------------------------- #
# Decide (accept applies; reject does not)                                      #
# --------------------------------------------------------------------------- #
def accept_proposal(proposal_id: int, decided_by: str = "human") -> dict[str, Any]:
    """ACCEPT: apply the mutation through the single-writer, THEN flip the row to
    accepted (recording the landed note id). Order matters — apply first so a
    failed apply leaves the row pending (fail-closed). Raises ProposalNotFound /
    AlreadyDecided / ApplyError."""
    proposal = pstore.get_proposal(proposal_id)
    if proposal is None:
        raise ProposalNotFound(str(proposal_id))
    if proposal["status"] != "pending":
        raise AlreadyDecided(f"proposal {proposal_id} already {proposal['status']}")

    applied_note_id = _apply(proposal)  # raises ApplyError → row stays pending

    flipped = pstore.mark_decided(
        proposal_id=proposal_id, status="accepted", decided=_now_iso(),
        decided_by=decided_by, applied_note_id=applied_note_id,
    )
    if not flipped:  # lost a race — another caller decided it between our checks
        raise AlreadyDecided(f"proposal {proposal_id} was decided concurrently")
    _audit("accept", {"proposalId": proposal_id, "appliedNoteId": applied_note_id},
           actor=decided_by, correlation_id=proposal.get("correlationId"))
    result = pstore.get_proposal(proposal_id)
    assert result is not None
    logger.info("wiki proposal %s accepted → note %s", proposal_id, applied_note_id)
    return result


def reject_proposal(proposal_id: int, decided_by: str = "human") -> dict[str, Any]:
    """REJECT: flip the row to rejected. NOTHING is applied to the vault. Raises
    ProposalNotFound / AlreadyDecided."""
    proposal = pstore.get_proposal(proposal_id)
    if proposal is None:
        raise ProposalNotFound(str(proposal_id))
    if proposal["status"] != "pending":
        raise AlreadyDecided(f"proposal {proposal_id} already {proposal['status']}")
    flipped = pstore.mark_decided(
        proposal_id=proposal_id, status="rejected", decided=_now_iso(),
        decided_by=decided_by, applied_note_id=None,
    )
    if not flipped:
        raise AlreadyDecided(f"proposal {proposal_id} was decided concurrently")
    _audit("reject", {"proposalId": proposal_id},
           actor=decided_by, correlation_id=proposal.get("correlationId"))
    result = pstore.get_proposal(proposal_id)
    assert result is not None
    logger.info("wiki proposal %s rejected", proposal_id)
    return result


def batch_accept(ids: list[int], decided_by: str = "human") -> dict[str, Any]:
    """Accept many proposals (the P1 batch action). Each is applied independently;
    one failure NEVER aborts the rest (one bad proposal can't block the batch).

    Returns ``{results: [{id, ok, proposal?, error?}], accepted: N, failed: M}``:
    one ``results`` entry per requested id (preserving order), ``ok`` True/False,
    the applied proposal on success or an ``error`` string on failure.
    """
    results: list[dict[str, Any]] = []
    accepted = 0
    for pid in ids:
        try:
            p = accept_proposal(pid, decided_by=decided_by)
            results.append({"id": pid, "ok": True, "proposal": p})
            accepted += 1
        except ProposalNotFound:
            results.append({"id": pid, "ok": False, "error": "not found"})
        except AlreadyDecided as exc:
            results.append({"id": pid, "ok": False, "error": str(exc)})
        except ApplyError as exc:
            results.append({"id": pid, "ok": False, "error": str(exc)})
    return {"results": results, "accepted": accepted, "failed": len(ids) - accepted}
