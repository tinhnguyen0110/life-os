"""modules/reliability/router.py — Reliability Harness endpoint (Sprint W8 A3).

Mounts at ``/reliability`` via the registry (``MODULE``) — auto-discovered, no
core/main.py edit. GET runs the suite (grounding-eval + fail-closed gates) and
reports per-case pass/fail. Read-only (it RUNS checkers; the grounding probe note
is created + cleaned up inside the suite). No routine.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from core.base import BaseModule
from core.responses import ok

from . import service

logger = logging.getLogger("life-os.reliability.router")

router = APIRouter(tags=["reliability"])


@router.get("")
def reliability():
    """Run the agent-reliability suite + report. ``{checks:[{name, passed, cases:[
    {label, expected, actual, passed, detail?}]}], passed, summary:{total, passed,
    failed}}``. ``passed`` True iff every check passed (the live grounding + gate proof)."""
    return ok(data=service.run_suite().model_dump())


MODULE = BaseModule(name="reliability", router=router)
