"""modules/wiki/citations.py — citation post-verify (Sprint W6 A1b, spec L120-121).

The anti-fabrication GUARANTEE for Trụ C ("code guarantees, prompt only reduces").
An external Claude Code agent answers wiki queries with ``{claim, noteId, span}``
citations; M2 in-app chat was DROPPED, so this is a STATELESS verify service the
agent calls BEFORE presenting its answer. Deterministic code checks each citation:
does the cited note EXIST, and does the cited span ACTUALLY occur in it? A
fabricated citation cannot be passed off as grounded.

PURE — no HTTP, no mutation, fully unit-testable. Read-only (reuses
``service.resolve_note`` which follows D6 redirects so a stale citation to a
merged-away note still verifies against the merge target).

Per-claim status (the derivation, implemented exactly):
  - ungrounded      — noteId missing/null (claim asserted with NO citation).
  - rejected        — note absent (noteId not found, even after redirect) →
                      reason note_not_found. OR span present but NOT in the note →
                      reason span_not_in_note (the anti-fabrication guarantee).
  - verified        — note exists AND the (non-empty) span occurs in title+body.
                      If the citation pointed at a merged-away id, resolvedNoteId =
                      the final live id.
  - weakly_grounded — note exists but span empty/whitespace-only (names a real note
                      but quotes no passage — surfaced, NOT rejected).

Span match: normalize BOTH the span and the note text by collapsing all whitespace
runs (incl. newlines) to single spaces + stripping ends (`" ".join(s.split())`),
then a CASE-SENSITIVE substring check. Searchable text = ``title + "\\n" + content``
(a citation to a titular claim verifies).
"""

from __future__ import annotations

from typing import Any

from . import service


def _normalize(text: str) -> str:
    """Collapse all whitespace runs (incl. newlines/tabs) to single spaces + strip.
    Applied to BOTH sides so a multi-line / oddly-spaced span matches the note's
    flowing text. Case is preserved (case-SENSITIVE match)."""
    return " ".join((text or "").split())


def _verify_one(claim: dict[str, Any]) -> dict[str, Any]:
    """Verify a single citation → one result dict (see module docstring for status
    rules). ``claim`` keys: claim (str), noteId (int|None), span (str|None)."""
    claim_text = claim.get("claim", "") or ""
    note_id = claim.get("noteId")
    span = claim.get("span")

    base: dict[str, Any] = {
        "claim": claim_text, "noteId": note_id,
        "status": "", "reason": None, "resolvedNoteId": None,
    }

    # 1. No citation at all → ungrounded.
    if note_id is None:
        return {**base, "status": "ungrounded", "reason": "no_citation"}

    # 2. Resolve (follows D6 redirect tombstone). A non-positive id can never exist
    #    (ids are MAX+1 starting at 1) → resolve_note returns None → rejected.
    note, warning = service.resolve_note(int(note_id))
    if note is None:
        return {**base, "status": "rejected", "reason": "note_not_found"}

    # The citation may have pointed at a merged-away id; record the final live id
    # when a redirect was followed (warning non-None).
    resolved_id = note.id if warning is not None else None

    # 3/4. Span check.
    span_norm = _normalize(span) if span is not None else ""
    if not span_norm:
        # Names a real note but quotes no passage → weakly grounded (not rejected).
        return {**base, "status": "weakly_grounded", "reason": "no_span",
                "resolvedNoteId": resolved_id}

    searchable = _normalize(f"{note.title}\n{note.content}")
    if span_norm in searchable:
        return {**base, "status": "verified", "reason": None,
                "resolvedNoteId": resolved_id}
    # Span does not occur in the note → the anti-fabrication rejection.
    return {**base, "status": "rejected", "reason": "span_not_in_note",
            "resolvedNoteId": resolved_id}


def verify_citations(claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Post-verify a batch of citations (W6 A1b). Returns:
    ``{results: [{claim, noteId, status, reason, resolvedNoteId}], summary: {...}}``.
    Empty ``claims`` → empty results + all-zero summary (never crashes)."""
    results = [_verify_one(c) for c in claims]
    summary = {
        "verified": sum(1 for r in results if r["status"] == "verified"),
        "rejected": sum(1 for r in results if r["status"] == "rejected"),
        "ungrounded": sum(1 for r in results if r["status"] == "ungrounded"),
        "weaklyGrounded": sum(1 for r in results if r["status"] == "weakly_grounded"),
        "total": len(results),
    }
    return {"results": results, "summary": summary}
