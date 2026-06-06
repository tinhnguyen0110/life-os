"""modules/graveyard/router.py — Graveyard REST endpoint (Sprint 8, SPEC §S4).

Mounts at ``/graveyard`` via the registry (``MODULE``). Locked envelope. Read-only
(no routine) — aggregates the abandoned set on demand.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from core.base import BaseModule
from core.responses import ok

from . import service

logger = logging.getLogger("life-os.graveyard.router")

router = APIRouter(tags=["graveyard"])


@router.get("")
def get_graveyard():
    """Abandoned projects + pattern stats (peak/reasons/reached-vs-before-user/lessons)."""
    return ok(data=service.get_graveyard().model_dump())


MODULE = BaseModule(name="graveyard", router=router)
