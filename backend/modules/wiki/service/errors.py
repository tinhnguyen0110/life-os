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
