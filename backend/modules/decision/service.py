"""modules/decision/service.py — the decision tower (FINANCE-ASSISTANT P2, #54).

THE ONE q-engine: compute_q(inputs) → q = freshness × coverage × agreement. macro_cycle,
decision_weight, AND the macro module's _confidence_for seam all CALL this — none reimplements
freshness/coverage/agreement (HARD GATE 5). Every number is COMPUTED from inputs; nothing is
hardcoded (HARD GATE 1: the spec's worked example must FALL OUT of the formula, not be typed).

NEUTRAL: outputs are data + q only — no advice verb anywhere.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, cast

from .schema import (
    CycleAxis,
    DecisionWeight,
    LayerView,
    MacroCycle,
    QInputView,
    QResult,
)

# --------------------------------------------------------------------------- #
# τ (tau) — the freshness decay constant per DATA TYPE, in DAYS. freshness =     #
# exp(-age/τ): at age=τ freshness≈0.37, at age=0 freshness=1. Spot data decays   #
# fast (a 5-min-old quote is stale); macro/cycle decay slowly (a 30-day-old CPI  #
# is still current). (§57-87: τ per data type — spot ~5min, macro/cycle ~30d.)   #
# --------------------------------------------------------------------------- #
TAU_DAYS = {
    "spot": 5.0 / (24 * 60),   # ~5 minutes, in days
    "macro": 30.0,             # monthly macro (CPI/UNRATE/M2/INDPRO)
    "cycle": 30.0,             # the Investment-Clock axes
    "yield": 30.0,             # yield-curve (daily but slow-moving regime)
    "flow": 1.0,               # sentiment (F&G/BTC.d) — daily
}
_DEFAULT_TAU = 30.0


@dataclass
class QInput:
    """One input to compute_q. ``value`` + ``age_days`` (for freshness) + ``source``.
    ``present`` False = the input is MISSING (no data) — it lowers coverage but contributes
    no freshness/value. A mock-sourced point counts as present-but-the-caller may treat mock
    as not-covered (macro_cycle does, honestly)."""

    name: str
    present: bool = True
    value: float | None = None
    age_days: float | None = None
    data_type: str = "macro"     # picks τ
    source: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _freshness(age_days: float, data_type: str) -> float:
    """freshness = exp(-age/τ) ∈ (0, 1]. age in days; τ from the data type. age<0 (a future
    ts, clock skew) clamps to 0 → freshness 1 (treat as fresh, never >1)."""
    tau = TAU_DAYS.get(data_type, _DEFAULT_TAU)
    age = max(0.0, float(age_days))
    return math.exp(-age / tau)


def _age_days_from_ts(ts: str | None) -> float | None:
    """age in days from an ISO-8601 ts (date or datetime). None if ts is unparseable/None."""
    if not ts:
        return None
    try:
        # accept 'YYYY-MM-DD' or full ISO; normalize a bare date to midnight UTC
        s = ts.strip()
        if len(s) == 10:
            dt = datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    return (_now() - dt).total_seconds() / 86400.0


def compute_q(inputs: list[QInput], *, needed: int | None = None) -> QResult:
    """THE q-engine (the single shared contract). q = freshness × coverage × agreement.

      freshness = mean over PRESENT inputs of exp(-age/τ). No age-bearing present input → 1.0
                  (can't penalize freshness we can't measure; coverage/agreement still apply).
      coverage  = (#present inputs) / (#needed). ``needed`` defaults to len(inputs) (so a
                  caller that passes only the inputs-it-has must pass needed explicitly to
                  reflect the ones it's MISSING — that's how a missing axis lowers coverage).
      agreement = 1 - dispersion of the present VALUES (population stddev / |mean|, bounded
                  [0,1]). A single present value (or all-equal) → dispersion 0 → agreement 1.0.
                  This is per-COMPUTE-CALL: one source over agreeing inputs → 1.0; inputs that
                  point different ways → <1.

    Returns QResult{q, freshness, coverage, agreement, breakdown, needed/present counts}.
    NOTHING hardcoded — every component falls out of the inputs (HARD GATE 1)."""
    n_needed = needed if needed is not None else len(inputs)
    present = [i for i in inputs if i.present]
    n_present = len(present)

    # --- coverage -----------------------------------------------------------
    coverage = (n_present / n_needed) if n_needed > 0 else 0.0

    # --- freshness (mean over present inputs that carry an age) --------------
    fresh_vals: list[float] = []
    views: list[QInputView] = []
    for i in inputs:
        f: float | None = None
        if i.present and i.age_days is not None:
            f = _freshness(i.age_days, i.data_type)
            fresh_vals.append(f)
        views.append(QInputView(
            name=i.name, present=i.present, value=i.value,
            ageDays=(round(i.age_days, 4) if i.age_days is not None else None),
            freshness=(round(f, 4) if f is not None else None), source=i.source,
        ))
    freshness = (sum(fresh_vals) / len(fresh_vals)) if fresh_vals else 1.0

    # --- agreement = 1 - dispersion of present values -----------------------
    vals = [i.value for i in present if i.value is not None]
    if len(vals) <= 1:
        agreement = 1.0   # one (or zero) value → no dispersion → full agreement
    else:
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        std = math.sqrt(var)
        denom = abs(mean) if abs(mean) > 1e-9 else 1.0
        dispersion = min(1.0, std / denom)   # coefficient of variation, bounded [0,1]
        agreement = 1.0 - dispersion

    q = freshness * coverage * agreement   # PURE product, NO clamp
    return QResult(
        q=round(q, 4), freshness=round(freshness, 4), coverage=round(coverage, 4),
        agreement=round(agreement, 4), breakdown=views,
        neededInputs=n_needed, presentInputs=n_present,
    )


def q_from_points(points: list[dict], *, needed: int, data_type: str = "macro",
                  mock_is_present: bool = True) -> QResult:
    """Convenience: build compute_q inputs from {indicator/name, value, ts, source} point dicts.
    ``needed`` is the consumer's declared input count (so missing ones lower coverage). When
    ``mock_is_present`` is False, a source='mock' point counts as NOT covered (the macro_cycle
    honest-missing rule — a fail-open mock axis must not inflate coverage)."""
    qinputs: list[QInput] = []
    for p in points:
        src = p.get("source")
        present = bool(p.get("value") is not None) and (mock_is_present or src != "mock")
        qinputs.append(QInput(
            name=str(p.get("name") or p.get("indicator") or "?"),
            present=present,
            value=(float(p["value"]) if p.get("value") is not None else None),
            age_days=_age_days_from_ts(p.get("ts")),
            data_type=data_type, source=src,
        ))
    return compute_q(qinputs, needed=needed)


# --------------------------------------------------------------------------- #
# T4 seam — the macro module's _confidence_for delegates here (single source).   #
# --------------------------------------------------------------------------- #
def confidence_q(value: float | None, ts: str | None, source: str | None,
                 *, data_type: str = "macro") -> float:
    """The macro-confidence seam (replaces P1's source-stub): a SINGLE-input compute_q for one
    macro indicator. coverage = 1 (the indicator is the only needed input and it's present when
    value is not None), agreement = 1 (single source), freshness from the point's ts. A mock
    point still computes a real freshness/coverage q (honest — a mock value IS present, just
    flagged elsewhere by source). Returns just the scalar q (the call-site wants a float)."""
    present = value is not None
    qi = QInput(name="indicator", present=present, value=value,
                age_days=_age_days_from_ts(ts), data_type=data_type, source=source)
    return compute_q([qi], needed=1).q


# --------------------------------------------------------------------------- #
# T2 — macro_cycle: the Investment-Clock RL state (spec §134-164).               #
# phase = growth × inflation. growth = INDPRO + UNRATE trend; inflation = CPI    #
# trend; + yield_curve regime. qCycle = compute_q over the axes (a mock/missing  #
# axis lowers coverage honestly). NEUTRAL: data + q; favored/defensive are the   #
# CLASSIC-CLOCK reference map (§157 table), NOT advice for the user's book.       #
# --------------------------------------------------------------------------- #
# The Investment-Clock 4-phase reference (spec §157-164): (growth_dir, inflation_dir)
# → (phase, favored reference assets, defensive reference assets).
_CLOCK = {
    ("up", "down"): ("recovery", ["equity", "crypto"], ["gold", "cash"]),
    ("up", "up"): ("overheat", ["commodities", "gold"], ["cash"]),
    ("down", "up"): ("stagflation", ["gold", "cash"], ["equity", "crypto"]),
    ("down", "down"): ("slowdown", ["bonds", "cash", "usd"], ["equity", "crypto"]),
}
# how many cycle axes the phase call NEEDS (growth, inflation, yield_curve). PMI is proxied
# by INDPRO (the decided assumption) so it's folded into growth, not a separate needed axis.
_CYCLE_AXES_NEEDED = 3


def _axis_q_input(name: str, value: float | None, ts: str | None, source: str | None,
                  direction: str) -> QInput:
    """One cycle axis as a compute_q input. present = it has REAL (non-mock) data with a
    direction — a mock axis or a flat/unknown trend lowers coverage honestly. ``value`` for
    agreement = a signed direction code (+1 up / −1 down / 0 flat) so 'do the axes agree on
    the phase' is measurable as low dispersion of the direction codes."""
    present = (value is not None) and (source != "mock") and (direction in ("up", "down"))
    dir_code = {"up": 1.0, "down": -1.0}.get(direction, 0.0)
    return QInput(name=name, present=present, value=(dir_code if present else None),
                  age_days=_age_days_from_ts(ts), data_type="cycle", source=source)


def macro_cycle() -> MacroCycle:
    """The Investment-Clock state from the live macro axes. Reads macro module data (NO
    network of its own beyond what macro already cached). Derives growth (INDPRO+UNRATE) +
    inflation (CPI) + yield_curve regime → phase; qCycle = compute_q over the 3 axes. Honest:
    a mock/missing axis → coverage<1 → lower qCycle + warning; too-thin → phase='unknown'
    (NEVER fabricate a phase). NEUTRAL — data + q only."""
    from modules.macro import service as macro_svc

    overview, _ = macro_svc.get_overview()
    by_ind = {v.indicator: v for v in overview.indicators}

    def _axis(name: str, indicator: str, *, invert: bool = False) -> tuple[str, QInput, CycleAxis, str]:
        """Build (direction, q-input, CycleAxis, detail) for one indicator-backed axis.
        ``invert`` flips the trend (UNRATE up = growth DOWN — unemployment rising is weakness)."""
        v = by_ind.get(indicator)
        if v is None or v.latest is None:
            return "unknown", QInput(name=name, present=False), \
                CycleAxis(axis=name, direction="unknown", present=False,
                          detail=f"{indicator} missing"), f"{indicator} missing"
        trend = v.trend
        if invert:
            trend = cast("Literal['up','down','flat']", {"up": "down", "down": "up"}.get(trend, trend))
        is_real = v.source != "mock"
        qi = _axis_q_input(name, v.latest, v.asOf, v.source, trend)
        direction = cast("Literal['up','down','flat','unknown']", trend)
        return trend, qi, CycleAxis(axis=name, direction=direction, present=is_real,
                                    detail=f"{indicator} {v.trend}{' (mock)' if not is_real else ''}"), \
            f"{indicator} {v.trend}"

    # GROWTH = INDPRO trend (PMI proxy) combined with UNRATE (inverted — rising unemployment
    # = weaker growth). Use INDPRO as the primary growth signal; UNRATE refines it.
    indpro_dir, indpro_qi, indpro_axis, _ = _axis("growth", "industrial_production")
    unrate_dir, unrate_qi, _unrate_axis, _ = _axis("unemployment_growth", "unemployment", invert=True)
    # growth direction: INDPRO leads; if INDPRO unknown, fall back to inverted UNRATE.
    growth_dir = indpro_dir if indpro_dir in ("up", "down") else unrate_dir
    growth_axis = CycleAxis(
        axis="growth", direction=cast("Literal['up','down','flat','unknown']", growth_dir),
        present=indpro_axis.present, detail=f"INDPRO {indpro_dir} / UNRATE→{unrate_dir}")

    # INFLATION = CPI trend.
    infl_dir, cpi_qi, _cpi_axis, _ = _axis("inflation", "cpi")
    inflation_axis = CycleAxis(
        axis="inflation", direction=cast("Literal['up','down','flat','unknown']", infl_dir),
        present=_cpi_axis.present, detail=_cpi_axis.detail)

    # YIELD_CURVE regime (a third axis — steepening/inverted is its own signal).
    yc_dir, yc_qi, yc_axis, _ = _axis("yield_curve", "yield_curve_10y2y")

    # qCycle over the 3 cycle axes (growth via INDPRO, inflation via CPI, yield_curve).
    q_cycle = compute_q([indpro_qi, cpi_qi, yc_qi], needed=_CYCLE_AXES_NEEDED)

    # phase from (growth, inflation) — only when BOTH directions are known; else 'unknown'
    # (honest — don't fabricate a phase from a single axis).
    phase = "unknown"
    favored: list[str] = []
    defensive: list[str] = []
    if growth_dir in ("up", "down") and infl_dir in ("up", "down"):
        phase, favored, defensive = _CLOCK[(growth_dir, infl_dir)]

    # warning when coverage<1 (a mock/missing axis) or the phase couldn't be named.
    missing = [a.axis for a in (growth_axis, inflation_axis, yc_axis) if not a.present]
    warning = None
    if phase == "unknown":
        warning = "phase unknown — growth/inflation direction not both determinable from current axes"
    elif missing:
        warning = (f"phase from partial data — {', '.join(missing)} mock/missing "
                   f"(coverage {q_cycle.coverage:.2f})")

    return MacroCycle(
        phase=phase,  # type: ignore[arg-type]  # one of the CyclePhase Literal
        axes=[growth_axis, inflation_axis, yc_axis],
        qCycle=q_cycle, favored=favored, defensive=defensive,
        confidence=q_cycle.q, warning=warning,
    )


# --------------------------------------------------------------------------- #
# T3 — decision_weight: W = q_cycle × q_macro × q_flow × s_asset (spec §94-132). #
# PURE PRODUCT, NO inter-layer clamp (the §40-44 hard rule: hierarchy enforced   #
# BY the multiply, NOT by min(qᵢ, q_{i-1})). binding_constraint = argmin q. weight#
# and confidence are TWO SEPARATE numbers (§116 legend). NEUTRAL.                 #
# --------------------------------------------------------------------------- #
# Verdict is a NEUTRAL descriptive band of the weight (DATA, not advice — no buy/sell verb).
def _verdict(weight: float) -> str:
    if weight >= 0.5:
        return "strong"
    if weight >= 0.25:
        return "moderate"
    if weight > 0.0:
        return "thin"
    return "blind"   # a layer is dark → W=0 → no basis to bet


def _q_flow() -> tuple[float, str]:
    """Phase-2 MINIMAL flow layer (spec keeps this thin — market_regime is Phase 3): a simple
    q from the F&G + BTC.d daily sentiment (macro_history). present sentiment with fresh ts →
    higher q; missing → low. Returns (q, note). NEUTRAL — no risk-on/off CALL, just data q."""
    from modules.macro import service as macro_svc

    points: list[dict] = []
    for ind in ("fear_greed", "btc_dominance"):
        hist = macro_svc.get_history(ind, days=30)
        if hist is not None and hist.points:
            last = hist.points[-1]
            points.append({"name": ind, "value": last.value, "ts": last.ts, "source": last.source})
        else:
            points.append({"name": ind, "value": None, "ts": None, "source": "mock"})
    qr = q_from_points(points, needed=2, data_type="flow", mock_is_present=False)
    have = qr.presentInputs
    return qr.q, f"flow: {have}/2 sentiment signals (F&G/BTC.d), q={qr.q}"


def _s_asset() -> tuple[float, str]:
    """Phase-2 MINIMAL asset-signal layer: a simple q from the market watchlist's RSI/trend
    coverage (the existing market technicals). present technicals → higher q; empty watchlist →
    low (the §484 watchlist-gap is real). Returns (q, note). NEUTRAL — no buy/sell."""
    from modules.market import service as mkt

    try:
        items, _ = mkt.watchlist_data()
    except Exception:  # noqa: BLE001 — fail-soft → no asset signal → low q
        items = []
    points: list[dict] = []
    for it in items:
        has_tech = it.get("rsi") is not None and it.get("trend") not in (None, "flat")
        points.append({"name": it.get("symbol", "?"),
                       "value": (it.get("rsi") if has_tech else None),
                       "ts": None,   # watchlist has no per-row ts → freshness neutral (1.0)
                       "source": it.get("source", "mock")})
    needed = max(1, len(points))   # at least one asset expected; empty → coverage 0
    qr = q_from_points(points, needed=needed, data_type="spot", mock_is_present=False)
    return qr.q, f"asset: {qr.presentInputs}/{needed} symbols with RSI/trend, q={qr.q}"


def decision_weight() -> DecisionWeight:
    """The decision tower's tip: W = q_cycle × q_macro × q_flow × s_asset — PURE PRODUCT, NO
    inter-layer clamp (hierarchy is enforced BY the multiply). binding_constraint = the dimmest
    layer (where adding data helps most). weight (the ∏) and confidence (mean layer q) are
    SEPARATE — weight = signal strength, confidence = trust in the measurement (§116). NEUTRAL:
    a verdict BAND + an explanation with no advice verb; the agent decides."""
    from modules.macro import service as macro_svc

    # q_cycle (the RL state)
    cyc = macro_cycle()
    q_cycle = cyc.qCycle.q
    cyc_note = f"cycle: phase={cyc.phase}, qCycle={q_cycle}" + (
        f" ({cyc.warning})" if cyc.warning else "")

    # q_macro — the macro_overview confidence, now the REAL compute_q (the seam, T4). Use the
    # MEAN of the per-indicator q as the macro layer's q (overview-level data quality).
    overview, _ = macro_svc.get_overview()
    macro_qs = [v.confidence for v in overview.indicators]
    q_macro = round(sum(macro_qs) / len(macro_qs), 4) if macro_qs else 0.0
    macro_note = f"macro: {len(macro_qs)} indicators, mean q={q_macro}, source={overview.source}"

    # q_flow (minimal) + s_asset (minimal)
    q_flow, flow_note = _q_flow()
    s_asset, asset_note = _s_asset()

    layers = [
        LayerView(layer="q_cycle", q=round(q_cycle, 4), note=cyc_note),
        LayerView(layer="q_macro", q=round(q_macro, 4), note=macro_note),
        LayerView(layer="q_flow", q=round(q_flow, 4), note=flow_note),
        LayerView(layer="s_asset", q=round(s_asset, 4), note=asset_note),
    ]

    # W = PURE PRODUCT (no clamp). A layer at 0 → W=0 automatically.
    weight = 1.0
    for ly in layers:
        weight *= ly.q
    weight = round(weight, 4)

    # binding_constraint = the dimmest layer (argmin q) — names where to add data.
    binding = min(layers, key=lambda ly: ly.q).layer
    # confidence = how much to TRUST the weight = mean layer q (SEPARATE from weight).
    confidence = round(sum(ly.q for ly in layers) / len(layers), 4)

    explanation = (f"W = {' × '.join(str(ly.q) for ly in layers)} = {weight} "
                   f"(pure product, no clamp); dimmest layer = {binding}")

    return DecisionWeight(  # type: ignore[call-arg]  # legend uses its canonical default (no pydantic mypy plugin → can't see Field() default)
        weight=weight, verdict=_verdict(weight), breakdown=layers,
        bindingConstraint=binding, explanation=explanation, confidence=confidence,
    )
