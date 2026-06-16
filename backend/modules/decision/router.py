"""modules/decision/router.py — decision-tower REST endpoints (FINANCE-ASSISTANT P2, #54).

Mounts at ``/decision`` via the registry (``MODULE``). Locked envelope ({success, data,
warning?}). NEUTRAL — data + q only.

  GET /decision/macro-cycle      Investment-Clock phase + qCycle (the RL state)
  GET /decision/weight           W = ∏ qᵢ + binding_constraint (the decision tower's tip)

The q-engine (compute_q) is a pure importable fn in service.py — these endpoints expose the
macro_cycle + decision_weight tools that compose it. Auto-discovered: adding this folder IS
the wiring; core/main.py is NOT edited.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from core.base import BaseModule
from core.responses import ok

from . import service

logger = logging.getLogger("life-os.decision.router")

router = APIRouter(tags=["decision"])


@router.get("/macro-cycle")
def get_macro_cycle():
    """The Investment-Clock RL state: phase (growth × inflation) + qCycle (compute_q over the
    axes). NEUTRAL — data + q; favored/defensive are the classic-clock REFERENCE map, not
    advice. Honest on missing axes (coverage<1 → lower q + warning; phase 'unknown' if too
    thin, never fabricated)."""
    cyc = service.macro_cycle()
    return ok(data=cyc.model_dump(), warning=cyc.warning)


@router.get("/weight")
def get_decision_weight():
    """The decision tower's tip: W = q_cycle × q_macro × q_flow × s_asset (pure product, no
    clamp) + binding_constraint (the dimmest layer). weight (signal strength) and confidence
    (trust in the measurement) are SEPARATE numbers (see the legend). NEUTRAL — the agent
    reads W + the breakdown and decides."""
    dw = service.decision_weight()
    return ok(data=dw.model_dump())


MODULE = BaseModule(name="decision", router=router)
