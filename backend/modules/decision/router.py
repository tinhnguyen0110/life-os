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


@router.get("/allocation")
def get_allocation_target(capital: float | None = None, phase: str | None = None,
                          monthly_add: float = 0.0, horizon_years: float = 3.0):
    """A NEUTRAL reference weighting (FINANCE-ASSISTANT P3): the classic Investment-Clock for the
    ``phase`` (defaults to the live macro_cycle phase) + the user's ``capital``-size → reference
    channel weights + per-channel rationale + the delta vs the static golden-path. ``capital`` is
    OPTIONAL (FINANCE-FINISH G2): omit → uses the live portfolio totalValue; pass → a what-if at
    that size. Capital-tier thresholds are user-configurable (PATCH /settings). NEUTRAL — a model
    assumption surfaced as DATA, not advice; the agent/user decides."""
    at = service.allocation_target(capital, phase=phase, monthly_add=monthly_add,
                                   horizon_years=horizon_years)
    return ok(data=at.model_dump())


@router.get("/nav-history")
def get_nav_history(date_from: str | None = None, date_to: str | None = None):
    """The daily NAV series (FINANCE-ASSISTANT P4) over the existing portfolio_snapshot table:
    ``series`` oldest→newest + ``points`` + ``range`` + a ``confidence`` (few points → low, a
    short series can't be trusted for a trend). ``?date_from&date_to`` ('YYYY-MM-DD', optional →
    full series). Fail-open: no data → empty series + confidence 0 + warning, never 500. NEUTRAL
    — data + confidence (CAGR/drawdown/vol need a longer series, out of scope)."""
    nav = service.nav_history(date_from=date_from, date_to=date_to)
    return ok(data=nav.model_dump(by_alias=True), warning=nav.warning)


@router.get("/guardian")
def get_finance_guardian():
    """The proactive scan (FINANCE-ASSISTANT P3): NEUTRAL observations the user hasn't asked
    about — each a real-data fact + evidence framed as a QUESTION (never an imperative). Real-
    data-only (a mock/empty source doesn't fire). Severity-ranked; honest-empty when nothing
    notable."""
    rep = service.finance_guardian()
    return ok(data=rep.model_dump(), warning=rep.note)


MODULE = BaseModule(name="decision", router=router)
