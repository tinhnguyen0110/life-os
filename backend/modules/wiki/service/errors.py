"""modules/wiki/service/errors.py — wiki service exceptions + op-kind type.

Shared by the queue, the apply logic, and the router (which maps each to an HTTP
status). Kept dependency-free so any submodule can import them without a cycle."""

from __future__ import annotations

from typing import Literal

OpKind = Literal["create", "update", "delete", "merge", "refine", "softdelete", "restore"]


class NoteNotFound(Exception):
    """Raised by the worker when an update/delete targets a missing note → router 404."""


class MergeError(Exception):
    """Raised when a merge is invalid (same id) → router 422."""


class RefineGateError(Exception):
    """Raised when REFINE is blocked by the ≥1-link hard gate (D9) → router 422."""


class FolderError(Exception):
    """#127 (WIKI-WORKDIR): a folder-op validation failure carrying an agent-readable code/hint.
    ``code`` ∈ {"INVALID_INPUT", "CONFLICT"} → the router maps it to agent_error_response (422/409).
    Carries (code, message, hint) so the boundary doesn't re-derive them."""

    def __init__(self, code: str, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
