"""modules/claude_usage/router.py — Claude Usage REST endpoints (Sprint 7, T2).

Mounts at ``/claude-usage`` via the registry (``MODULE``). Locked envelope
``{success, data, warning?}``. GET serves the composite usage view; PUT sets the
manual override (cap / resetIn / weekly — data not on disk). No routine (read
stats-cache on demand). Endpoint path uses a hyphen per ARCH §7 (/claude-usage).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from core.base import BaseModule
from core.responses import ok

from . import service
from .schema import ManualOverride

logger = logging.getLogger("life-os.claude_usage.router")

router = APIRouter(tags=["claude-usage"])


@router.get("")
def get_usage(window: str = "5h"):
    """The composite Claude usage view. Live transcripts → stats-cache → empty."""
    usage = service.get_usage(window=window)
    warning = None
    if usage.tokenSource == "none":
        warning = "no token data — transcripts dir + stats-cache.json both absent"
    elif usage.stale:
        warning = f"token data is stale (as of {usage.asOf})"
    return ok(data=usage.model_dump(), warning=warning)


@router.put("/override")
def set_override(body: ManualOverride):
    """Set the manual override (cap / resetIn / weekly). One md_store commit."""
    usage = service.set_override(body)
    return ok(data=usage.model_dump())


# name uses underscore (URL-safe per BaseModule); registry mounts at /claude_usage.
# ARCH §7 calls it /claude-usage — expose a clean prefix via the module name.
MODULE = BaseModule(name="claude-usage", router=router)
