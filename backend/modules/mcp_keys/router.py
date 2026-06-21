"""modules/mcp_keys/router.py — per-KEY MCP scoping CRUD (#86).

REST CRUD over the key store. Registry auto-discovers ``MODULE`` → mounts at ``/mcp_keys``
(NO core/main.py edit). Responses = ``{success, data}``; a missing key on PUT/DELETE → the
agent-readable NOT_FOUND envelope (core/agent_errors), NOT a bare 404/500.
"""

from __future__ import annotations

from fastapi import APIRouter

from core.agent_errors import agent_error_response
from core.base import BaseModule
from core.responses import ok

from . import service
from .schema import KeyCreate, KeyUpdate

router = APIRouter(tags=["mcp_keys"])


def _key_not_found(key: str):
    """The agent-readable NOT_FOUND for a missing key (404). NOTE: the closed ErrorCode enum has
    no 'mcp_key_not_found' literal — the canonical code is NOT_FOUND; the message names what's
    missing + the hint points at the list (logged to Assumptions)."""
    return agent_error_response(
        "NOT_FOUND", f"mcp key not found: {key[:6]}…",  # truncated — never log/echo the full token
        hint="GET /mcp_keys for the valid keys",
    )


@router.post("")
def create_key(body: KeyCreate):
    """Create a key (generated selector token) → returns the full row INCLUDING the new ``key``."""
    return ok(data=service.create_key(body.label, body.scope))


@router.get("")
def list_keys():
    """All keys as lean agent-readable rows (key/label/scope/toolCount/createdAt), newest-first."""
    return ok(data=service.list_keys())


@router.put("/{key}")
def update_key(key: str, body: KeyUpdate):
    """Partial-update a key's label/scope. 404 (agent_error) if no such key."""
    row = service.update_key(key, label=body.label, scope=body.scope)
    if row is None:
        return _key_not_found(key)
    return ok(data=row)


@router.delete("/{key}")
def delete_key(key: str):
    """Remove a key. 404 (agent_error) if no such key."""
    if not service.delete_key(key):
        return _key_not_found(key)
    return ok(data={"deleted": key})


MODULE = BaseModule(name="mcp_keys", router=router)
