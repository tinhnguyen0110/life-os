"""core/responses.py — C4 response envelope helpers (Sprint 0 dispatch).

Every endpoint returns the locked shape ``{success: bool, data: ..., warning?: str}``.
Modules import ``ok``/``err`` so the envelope is produced one way everywhere — FE
and external Claude Code parse a single contract.

Error codes (REST, no auth — single-user localhost): 400 / 404 / 422 / 429 / 500.
There is intentionally NO 401/403 (CLAUDE.md §2 — no auth).
"""

from __future__ import annotations

from typing import Any


def ok(data: Any = None, warning: str | None = None) -> dict[str, Any]:
    """Success envelope: ``{success: True, data, warning?}``.

    ``warning`` is omitted entirely when None (the shape's optional key).
    """
    body: dict[str, Any] = {"success": True, "data": data}
    if warning is not None:
        body["warning"] = warning
    return body


def err(message: str, data: Any = None) -> dict[str, Any]:
    """Failure envelope: ``{success: False, data, warning: message}``.

    Used inside a response body when an endpoint wants to signal a soft failure
    while still returning 200-shaped JSON. For hard HTTP errors raise
    ``fastapi.HTTPException`` with the appropriate status (400/404/422/429/500).
    """
    return {"success": False, "data": data, "warning": message}
