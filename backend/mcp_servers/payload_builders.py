"""mcp_servers/payload_builders.py — payload → apply-time Input model BUILDERS (A1).

The SINGLE source of payload-shaping for the propose/apply proposal kinds. PURE: each builder maps
a raw proposal payload → the kind's pydantic Input model (raises ValidationError on a bad payload).
It lazy-imports ONLY the SCHEMA (DecisionInput/NoteInput/JournalInput), NEVER a module-mutation fn
(create_entry/create_note) — so this module is gate-safe to import from BOTH:
  - ``write_server._propose`` → build-only (discard) to VALIDATE at propose-time (a bad payload is an
    agent-error NOW, not a deferred false-pending-success at human-accept).
  - ``proposals_service._apply_*`` → build + create at apply-time.
Single source → the propose-time validation and the apply-time create can't drift (esp the journal
action case-coercion — the load-bearing #51 case).

This deliberately lives OUTSIDE proposals_service (the apply layer) so the write-server's no-mutate
gate (it must NOT import a *.service nor proposals_service) is preserved: write_server imports THIS
pure-shaping module, not the apply layer.
"""

from __future__ import annotations

from typing import Any, Callable


def build_decision_input(payload: dict[str, Any]) -> Any:
    """payload → DecisionInput (raises ValidationError on a bad field, e.g. confidence out of range)."""
    from modules.decision_journal.schema import DecisionInput

    return DecisionInput(
        decision=payload["decision"],
        confidence=int(payload["confidence"]),
        domain=payload["domain"],
        thesis=payload.get("thesis"),
        falsificationCondition=payload.get("falsificationCondition"),
        predicted=payload.get("predicted"),
    )


def build_note_input(payload: dict[str, Any]) -> Any:
    """payload → NoteInput (raises ValidationError on a bad field)."""
    from modules.notes.schema import NoteInput

    return NoteInput(
        title=payload["title"],
        body=payload.get("body", ""),
        tags=payload.get("tags", []),
    )


def build_journal_input(payload: dict[str, Any]) -> Any:
    """payload → JournalInput, with the #51 action case-coercion (the SINGLE source — both apply AND
    propose-time validation use THIS, so they can't drift).

    WRITE-LOOP-E2E (#51): the agent's propose_journal sends ``action`` lowercase ("buy"/"sell"), but
    JournalInput.action is Literal["BUY","SELL"] → upper-case it here so a valid lowercase input is
    NOT rejected (apply AND propose validate identically). pydantic still validates the Literal at
    runtime (a non-BUY/SELL value → ValidationError → an honest agent-error / apply_error)."""
    from typing import cast

    from modules.journal.schema import Action, JournalInput

    action = cast(Action, str(payload["action"]).upper())
    # #57: date + outcome have defaults (None) on JournalInput — the [call-arg] is the no-pydantic-
    # mypy-plugin gotcha (mypy reads defaulted fields as required), NOT a missing-required.
    return JournalInput(  # type: ignore[call-arg]
        action=action,
        asset=payload["asset"],
        reason=payload["reason"],
        size=payload.get("size", ""),
        px=payload.get("px", ""),
        tag=payload.get("tag", ""),
        confidence=payload.get("confidence"),
    )


# kind → the payload-builder. A kind WITHOUT a builder (e.g. project_update — the no-op-flag kind
# with no apply handler) → propose-time skips validation; apply records an apply_error.
PAYLOAD_BUILDERS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "decision_create": build_decision_input,
    "note_create": build_note_input,
    "journal_create": build_journal_input,
}
