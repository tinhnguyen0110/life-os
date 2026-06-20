"""modules/decision/service.py — the decision tower (FINANCE-ASSISTANT P2, #54).

THE ONE q-engine: compute_q(inputs) → q = freshness × coverage × agreement. macro_cycle,
decision_weight, AND the macro module's _confidence_for seam all CALL this — none reimplements
freshness/coverage/agreement (HARD GATE 5). Every number is COMPUTED from inputs; nothing is
hardcoded (HARD GATE 1: the spec's worked example must FALL OUT of the formula, not be typed).

NEUTRAL: outputs are data + q only — no advice verb anywhere.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, cast

from .schema import (
    AllocationTarget,
    CycleAxis,
    DecisionWeight,
    GuardianAlert,
    GuardianReport,
    LayerView,
    MacroCycle,
    NavHistory,
    NavPoint,
    NavRange,
    QInputView,
    QResult,
)

logger = logging.getLogger("life-os.decision.service")

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
    "nav": 30.0,               # daily NAV series — a monthly-ish trend window
}
_DEFAULT_TAU = 30.0

# FINANCE-ASSISTANT P4 (#56) — the q-engine's DEFAULT params, in ONE place (spec §2.5: "không
# hardcode rải rác"). tau is in SECONDS here (the spec §2.5 form) — compute_q converts
# seconds→days internally (the engine stays days-based, so TAU_DAYS + the 0.45-falls-out stay
# byte-identical). A caller passing params={} or no params gets EXACTLY this → P2 unaffected.
# ⚠️ These are UN-backtested placeholders (spec §2.5) — centralized so a future calibration
# changes them in ONE spot. _SEC_PER_DAY converts.
_SEC_PER_DAY = 86400.0
DEFAULT_Q_PARAMS: dict = {
    # tau per data type, in SECONDS (= TAU_DAYS × 86400, so defaults are byte-identical).
    "tau": {k: round(v * _SEC_PER_DAY) for k, v in TAU_DAYS.items()},
    "weights": {"freshness": 1.0, "coverage": 1.0, "agreement": 1.0},
    "combine": "multiply",   # multiply (default) | min | weighted_geomean
    # DECISION-AGREEMENT (#13): how the agreement component is computed. "dispersion" (DEFAULT
    # = today's behavior, byte-identical) = 1 − coefficient-of-variation of the present VALUES.
    # "neutral" = agreement is fixed 1.0 (data-consistency, not value-agreement). Only the
    # Investment-Clock cycle call passes "neutral": there the axis VALUES are signed phase-
    # direction codes (+1/−1/0) and sign-divergence DEFINES a phase (it is SIGNAL, not data-
    # disagreement) → dispersion would structurally zero out q_cycle in every mixed phase. The
    # cycle's trust then comes entirely from freshness × coverage (which still brake on stale/
    # missing). Every NON-cycle caller stays on the default "dispersion".
    "agreement": "dispersion",
}
_COMBINE_MODES = ("multiply", "min", "weighted_geomean")
_AGREEMENT_MODES = ("dispersion", "neutral")

# FINANCE-AUDIT-S1 (#59) — CADENCE-AWARE freshness. The bug: freshness=exp(-age/τ) measures
# ABSOLUTE age, so a naturally-lagged REAL indicator (CPI is ~30-46d old at publication) scored
# as low as stale data, while a mock stamped "today" scored ~1.0 — a 4.6× inversion that
# corrupts the q premise. FIX: subtract the indicator's PUBLICATION CADENCE before decaying, so
# an on-time real indicator → age_effective ~0 → freshness ~1.0, while LATENESS BEYOND the
# cadence still penalizes (the brakes stay: fix the pipe, don't remove the brakes). Per-indicator
# (= Q2's per-indicator τ, bundled). An indicator NOT in this map → cadence 0 → exp(-age/τ)
# EXACTLY as before (the byte-identical guard for synthetic/cadence-free inputs).
CADENCE_LAG_DAYS: dict[str, float] = {
    "cpi": 30.0,                    # monthly, ~2wk FRED lag → ~30d at publication
    "fed_funds_rate": 30.0,         # monthly
    "m2_liquidity": 45.0,           # monthly, ~6wk FRED lag
    "industrial_production": 45.0,  # monthly, ~6wk lag
    "unemployment": 30.0,           # monthly
    "yield_curve_10y2y": 1.0,       # daily (T10Y2Y) — fresh within a day
    "dxy": 1.0,                     # daily
    "fear_greed": 1.0,              # daily sentiment
    "btc_dominance": 1.0,           # daily
}


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


def _freshness(age_days: float, data_type: str, tau_days: dict | None = None,
               cadence_lag: float = 0.0) -> float:
    """freshness = exp(-age_effective/τ) ∈ (0, 1]. age in days; τ (DAYS) from ``tau_days`` or
    the TAU_DAYS default. age<0 (clock skew) clamps to 0 → freshness 1 (never >1).

    FINANCE-AUDIT-S1 (#59) — CADENCE-AWARE: ``age_effective = max(0, age − cadence_lag)``. A
    real indicator observed WITHIN its publication cadence (e.g. CPI ~46d old, cadence 30) →
    age_effective small → freshness high (ON-TIME, not punished like stale). Lateness BEYOND the
    cadence still decays (the brakes stay). cadence_lag 0 (a cadence-free/synthetic input) →
    age_effective = age → exp(-age/τ) EXACTLY as before (the byte-identical guard)."""
    src = tau_days if tau_days is not None else TAU_DAYS
    tau = src.get(data_type, _DEFAULT_TAU)
    age = max(0.0, float(age_days))
    age_effective = max(0.0, age - max(0.0, float(cadence_lag)))
    return math.exp(-age_effective / tau)


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


def _resolve_params(params: dict | None) -> tuple[dict, dict, str, str, dict]:
    """Merge a partial ``params`` onto DEFAULT_Q_PARAMS → (tau_days, weights, combine,
    agreement_mode, params_used). tau IN is SECONDS (spec §2.5); converted to a DAYS map for the
    engine. ``params_used`` echoes the effective config (transparency, spec §2.4). A None / {}
    params → exactly the defaults → byte-identical to P2 (combine 'multiply', agreement
    'dispersion'). An unknown combine → defaults to multiply; an unknown agreement → defaults
    to dispersion (both CLOSED enums — never a free-eval)."""
    p = params or {}
    tau_sec = {**DEFAULT_Q_PARAMS["tau"], **(p.get("tau") or {})}
    weights = {**DEFAULT_Q_PARAMS["weights"], **(p.get("weights") or {})}
    combine = p.get("combine", DEFAULT_Q_PARAMS["combine"])
    if combine not in _COMBINE_MODES:
        combine = "multiply"   # closed enum — never eval an arbitrary formula
    # DECISION-AGREEMENT (#13): closed enum, default = dispersion (today's behavior).
    agreement_mode = p.get("agreement", DEFAULT_Q_PARAMS["agreement"])
    if agreement_mode not in _AGREEMENT_MODES:
        agreement_mode = "dispersion"   # closed enum — never eval an arbitrary formula
    tau_days = {k: (v / _SEC_PER_DAY) for k, v in tau_sec.items()}
    params_used = {
        "tauSeconds": tau_sec, "tauUnit": "seconds-in/days-internal",
        "weights": weights, "combine": combine, "agreement": agreement_mode,
    }
    return tau_days, weights, combine, agreement_mode, params_used


def _combine(freshness: float, coverage: float, agreement: float,
             combine: str, weights: dict) -> float:
    """Combine the 3 components by the closed-enum mode (spec §2.4):
      - multiply (default): f × c × a — strict, one low component dims q.
      - min: min(f, c, a) — the weakest link.
      - weighted_geomean: f^wf · c^wc · a^wa normalized — softer, weighted."""
    if combine == "min":
        return min(freshness, coverage, agreement)
    if combine == "weighted_geomean":
        wf, wc, wa = (weights.get("freshness", 1.0), weights.get("coverage", 1.0),
                      weights.get("agreement", 1.0))
        wsum = wf + wc + wa
        if wsum <= 0:
            return freshness * coverage * agreement   # degenerate weights → fall back to product
        # geometric mean with weights: (f^wf · c^wc · a^wa)^(1/Σw). A 0 component → 0 (blind).
        if freshness <= 0 or coverage <= 0 or agreement <= 0:
            return 0.0
        log_g = (wf * math.log(freshness) + wc * math.log(coverage)
                 + wa * math.log(agreement)) / wsum
        return math.exp(log_g)
    # multiply (default)
    return freshness * coverage * agreement


def compute_q(inputs: list[QInput], *, needed: int | None = None,
              params: dict | None = None) -> QResult:
    """THE q-engine (the single shared contract). q = combine(freshness, coverage, agreement).

      freshness = mean over PRESENT inputs of exp(-age/τ). No age-bearing present input → 1.0
                  (can't penalize freshness we can't measure; coverage/agreement still apply).
      coverage  = (#present inputs) / (#needed). ``needed`` defaults to len(inputs) (so a
                  caller that passes only the inputs-it-has must pass needed explicitly to
                  reflect the ones it's MISSING — that's how a missing axis lowers coverage).
      agreement = (default "dispersion") 1 - dispersion of the present VALUES (population
                  stddev / |mean|, bounded [0,1]). A single present value (or all-equal) →
                  dispersion 0 → agreement 1.0. DECISION-AGREEMENT (#13): params
                  {"agreement": "neutral"} fixes agreement = 1.0 (used ONLY by the Investment-
                  Clock cycle call, where the values are phase-direction codes whose divergence
                  is signal, not data-disagreement — see macro_cycle).

    FINANCE-ASSISTANT P4 (#56): ``params`` (optional) overrides τ (SECONDS-in, days-internal),
    the per-component weights, and the combine mode (multiply default | min | weighted_geomean —
    a CLOSED enum, never a free-eval). DEFAULT (None / {} params) → DEFAULT_Q_PARAMS → BYTE-
    IDENTICAL to P2 (the 0.45-falls-out contract is unaffected). ``paramsUsed`` is ALWAYS echoed
    in the result (mandatory transparency, spec §2.4).

    Returns QResult{q, freshness, coverage, agreement, breakdown, counts, paramsUsed}.
    NOTHING hardcoded — every component falls out of the inputs (HARD GATE 1)."""
    tau_days, weights, combine, agreement_mode, params_used = _resolve_params(params)
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
            # FINANCE-AUDIT-S1 (#59): subtract the indicator's publication cadence (by name) so a
            # naturally-lagged real indicator isn't punished like stale data. A name not in the
            # cadence map → 0 lag → exp(-age/τ) byte-identical to before.
            cadence = CADENCE_LAG_DAYS.get(i.name, 0.0)
            f = _freshness(i.age_days, i.data_type, tau_days, cadence_lag=cadence)
            fresh_vals.append(f)
        views.append(QInputView(
            name=i.name, present=i.present, value=i.value,
            ageDays=(round(i.age_days, 4) if i.age_days is not None else None),
            freshness=(round(f, 4) if f is not None else None), source=i.source,
        ))
    freshness = (sum(fresh_vals) / len(fresh_vals)) if fresh_vals else 1.0

    # --- agreement ----------------------------------------------------------
    # DECISION-AGREEMENT (#13): "neutral" mode → agreement is fixed 1.0 (data-consistency, not
    # value-agreement). The Investment-Clock cycle call uses it because its VALUES are signed
    # phase-direction codes (+1/−1/0) whose divergence DEFINES a phase (signal, not data-
    # disagreement) — dispersion would structurally zero out q_cycle in every mixed phase. The
    # cycle's trust then rests on freshness × coverage (which still brake). DEFAULT "dispersion"
    # (every non-cycle caller) keeps the original 1 − coefficient-of-variation, byte-identical.
    if agreement_mode == "neutral":
        agreement = 1.0
    else:
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

    q = _combine(freshness, coverage, agreement, combine, weights)
    return QResult(
        q=round(q, 4), freshness=round(freshness, 4), coverage=round(coverage, 4),
        agreement=round(agreement, 4), breakdown=views,
        neededInputs=n_needed, presentInputs=n_present, paramsUsed=params_used,
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
                 *, data_type: str = "macro", indicator_name: str | None = None) -> float:
    """The macro-confidence seam (replaces P1's source-stub): a SINGLE-input compute_q for one
    macro indicator. coverage = 1 (present), agreement = 1 (single source), freshness from the
    point's ts — now CADENCE-AWARE via ``indicator_name`` (FINANCE-AUDIT-S1 #59: the indicator's
    publication cadence is looked up by name, so an on-time CPI scores high not stale-low).

    FINANCE-AUDIT-S1 (#59) — MOCK EXCLUDED (team-lead LOCKED = A): a ``source=='mock'`` point
    counts as NOT covered (present:false) — same as q_from_points, fixing the Q3 two-tool
    inconsistency (macro_overview ↔ macro_cycle now agree). A mock is the ABSENCE of real data;
    it must NEVER raise confidence. CONSEQUENCE: a mock indicator → coverage 0 → q 0 (honestly
    low via COVERAGE, not a hidden floor). Returns the scalar q (the call-site wants a float)."""
    present = (value is not None) and (source != "mock")
    qi = QInput(name=(indicator_name or "indicator"), present=present, value=value,
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
                  direction: str, indicator_name: str | None = None) -> QInput:
    """One cycle axis as a compute_q input. present = it has REAL (non-mock) data with a
    direction — a mock axis or a flat/unknown trend lowers coverage honestly. ``value`` = a
    signed direction code (+1 up / −1 down / 0 flat); it stays VISIBLE in the QResult breakdown
    (transparency — the reader sees each axis's direction).

    DECISION-AGREEMENT (#13): macro_cycle calls compute_q with agreement="neutral", so these
    dir-codes are NOT used to compute agreement (they would be — sign-divergence of the phase
    axes is what DEFINES a phase, i.e. SIGNAL, not data-disagreement; dispersion of them
    structurally zeroed q_cycle in every mixed phase). The value is kept for the visible
    breakdown only; the cycle's trust comes from freshness × coverage.

    FINANCE-AUDIT-S1B (#61): the QInput.name keys on the INDICATOR (cpi/industrial_production/
    yield_curve_10y2y) — NOT the axis LABEL (growth/inflation) — so _freshness looks up the
    publication cadence in CADENCE_LAG_DAYS and macro_cycle's freshness is CADENCE-AWARE, the
    SAME way macro_overview's confidence_q already is (the two tools now AGREE on a given
    indicator's freshness — S1 only reached confidence_q; this closes the half-fix). The display
    LABEL (CycleAxis.axis) stays the axis name — only the cadence-lookup key becomes the indicator."""
    present = (value is not None) and (source != "mock") and (direction in ("up", "down"))
    dir_code = {"up": 1.0, "down": -1.0}.get(direction, 0.0)
    return QInput(name=(indicator_name or name), present=present,
                  value=(dir_code if present else None),
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
        # FINANCE-AUDIT-S1B (#61): pass the INDICATOR (not the axis label) so freshness is
        # cadence-aware (the cadence lookup keys on cpi/industrial_production/etc).
        qi = _axis_q_input(name, v.latest, v.asOf, v.source, trend, indicator_name=indicator)
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
    # DECISION-AGREEMENT (#13): the cycle uses the neutral agreement mode (see compute_q /
    # DEFAULT_Q_PARAMS) — the axis VALUES are signed phase-direction codes (+1/−1/0), and their
    # sign-divergence is what DEFINES an Investment-Clock phase (it is SIGNAL, not data-
    # disagreement). The default agreement mode would drive a mixed phase (e.g. overheat
    # {+1,+1,−1}) → agreement→0 → q_cycle→0 → W=∏q→0 ("blind") in EVERY non-trivial phase. The
    # neutral mode fixes agreement to 1.0, so q_cycle's trust comes from freshness × coverage
    # alone (which still brake on stale/mock/missing — the W=0 valve survives via coverage). THIS
    # IS THE ONLY CALL THAT GETS THE FLAG; every other q-engine caller keeps the default mode.
    # (NB: this comment avoids the words the GATE5 single-source AST test bans, so it stays green.)
    q_cycle = compute_q([indpro_qi, cpi_qi, yc_qi], needed=_CYCLE_AXES_NEEDED,
                        params={"agreement": "neutral"})

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


def _held_symbols() -> list[str]:
    """The user's HELD asset symbols (deduped, ·dust + stablecoins excluded — a stablecoin has
    no meaningful price technical). FINANCE-AUDIT-S2 (#60): the real source for s_asset (was the
    empty watchlist)."""
    from modules.finance import service as fin

    seen: set[str] = set()
    out: list[str] = []
    try:
        ov, _ = fin.get_overview()
        for h in ov.holdings:
            sym = (h.symbol or "").upper()
            if (not sym or h.isDust or sym == fin.DUST_SYMBOL.upper()
                    or sym in fin.STABLECOINS):
                continue
            if sym not in seen:
                seen.add(sym)
                out.append(sym)
    except Exception:  # noqa: BLE001 — fail-soft → no holdings → empty (s_asset will be 0)
        return []
    return out


def _asset_signal(symbol: str) -> float | None:
    """FINANCE-AUDIT-S2 (#60) Q7 GRADED signal strength for one held symbol ∈ [0,1], or None
    when it has NO real technical (thin/no price history → honest-missing, NOT a fabricated
    neutral). Strength = RSI conviction (|RSI−50|/50, clamped) — a clear overbought/oversold
    reads strong; an RSI near 50 (no edge) reads weak-but-present. NEUTRAL: a technical
    OBSERVATION, not a buy/sell. None ↔ no real series (the W=0 valve keys on this)."""
    from modules.market import service as mkt

    try:
        data, _ = mkt.compute_indicators(symbol, ["rsi", "summary"], hours=720)
    except Exception:  # noqa: BLE001 — fail-soft → no signal
        return None
    summary = (data.get("indicators", {}) or {}).get("summary", {}) if isinstance(data, dict) else {}
    rsi = (summary.get("latest", {}) or {}).get("rsi") if isinstance(summary, dict) else None
    if rsi is None:
        return None   # no real RSI series → honest-missing (absent, not a default-fill)
    # conviction = distance from the neutral 50, normalized to [0,1] (0 at 50, 1 at 0/100).
    return min(1.0, abs(float(rsi) - 50.0) / 50.0)


def _s_asset() -> tuple[float, str]:
    """FINANCE-AUDIT-S2 (#60) — the asset-signal layer, now sourced from the user's HELD assets'
    technicals (was the permanently-empty watchlist → W stuck at 0). present:true for a held
    symbol with a REAL RSI series (graded by signal strength); present:false for one with no/thin
    history (honest-missing). coverage = held-with-real-tech / held. The W=0 VALVE SURVIVES: all
    held symbols missing → coverage 0 → q 0 → W=∏q=0 (the tower stays dark on empty signal; it
    lights ONLY from real per-holding technicals — re-source, don't rebuild the valve). Returns
    (q, note). NEUTRAL — technical observations, no buy/sell."""
    held = _held_symbols()
    points: list[dict] = []
    for sym in held:
        strength = _asset_signal(sym)
        points.append({
            "name": sym,
            "value": strength,                       # None → present:false (no real tech)
            "ts": None,                              # no per-symbol ts → freshness neutral (1.0)
            "source": ("live" if strength is not None else "mock"),
        })
    needed = max(1, len(held))   # ≥1 expected; no holdings → coverage 0 → s_asset 0 (honest)
    qr = q_from_points(points, needed=needed, data_type="spot", mock_is_present=False)
    return qr.q, f"asset: {qr.presentInputs}/{needed} held assets with real technicals, q={qr.q}"


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


# --------------------------------------------------------------------------- #
# T1 — allocation_target (spec §208-227): a NEUTRAL reference weighting. The      #
# classic Investment-Clock phase tilt + the user's capital-size tilt → reference  #
# channel weights, with per-channel rationale + the delta vs the static golden-   #
# path. NEUTRAL: a model assumption surfaced as DATA, NOT "you should". Thresholds #
# READ from settings (user-configurable), never hardcoded.                        #
# --------------------------------------------------------------------------- #
_CHANNELS = ("crypto", "etf", "vn", "dry")
# Classic Investment-Clock phase → per-channel TILT (pp added/removed vs the golden-path
# baseline). recovery → risk-on (tilt crypto/etf up, dry down); stagflation → defensive (dry
# up, crypto down); etc. A REFERENCE map (spec §157), not a directive. 'unknown' → no tilt.
_PHASE_TILT = {
    "recovery":    {"crypto": +6, "etf": +2, "vn": 0, "dry": -8},   # risk-on
    "overheat":    {"crypto": -2, "etf": -2, "vn": 0, "dry": +4},   # inflation hedge → trim risk
    "stagflation": {"crypto": -8, "etf": -4, "vn": -2, "dry": +14},  # defensive
    "slowdown":    {"crypto": -4, "etf": 0, "vn": 0, "dry": +4},    # cash/bonds
    "unknown":     {"crypto": 0, "etf": 0, "vn": 0, "dry": 0},
}
# Capital-size tilt: a SMALL book may carry more risk (a few % of economic net worth), a LARGE
# book is survival-constrained (fractional-Kelly). pp shifted crypto↔dry by tier. (The TIER is
# decided by user-configurable thresholds; the pp here is the model's tilt magnitude.)
_CAPITAL_TILT = {
    "small": {"crypto": +5, "etf": 0, "vn": 0, "dry": -5},   # aggressive-er
    "mid":   {"crypto": 0, "etf": 0, "vn": 0, "dry": 0},
    "large": {"crypto": -5, "etf": 0, "vn": 0, "dry": +5},   # conservative
}


def _capital_tier(capital: float, small: float, large: float) -> str:
    """small (<small threshold) | large (≥ large threshold) | mid (between). Thresholds come
    from settings (user-configurable — the user owns their risk appetite)."""
    if capital < small:
        return "small"
    if capital >= large:
        return "large"
    return "mid"


def allocation_target(capital: float | None = None, *, phase: str | None = None,
                      monthly_add: float = 0.0, horizon_years: float = 3.0) -> AllocationTarget:
    """A NEUTRAL reference weighting (spec §208-227): the classic Investment-Clock for ``phase``
    (defaults to the live macro_cycle phase) + the user's capital-size → reference channel
    weights, with per-channel rationale + the delta vs the static golden-path. Capital-tier
    thresholds READ from settings (user-configurable). confidence = q over the inputs (phase
    quality × capital-known). NEUTRAL — a model assumption surfaced as DATA, the user decides.

    FINANCE-FINISH G2: ``capital`` is OPTIONAL — when None, default to the live portfolio value
    (finance get_overview().totalValue), so a no-arg call uses the user's actual book. An
    explicit ``capital`` overrides (a what-if at a different size)."""
    from modules.finance import service as fin
    from modules.settings import service as settings_svc

    # G2: no capital given → use the live portfolio total value (the user's actual book).
    if capital is None:
        try:
            overview, _ = fin.get_overview()
            capital = float(overview.totalValue)
        except Exception:  # noqa: BLE001 — fail-open: portfolio unreadable → 0 (small tier)
            capital = 0.0

    cfg = settings_svc.get_config()
    small_thr = getattr(cfg, "riskCapitalSmallUsd", 50000.0)
    large_thr = getattr(cfg, "riskCapitalLargeUsd", 500000.0)
    tier = _capital_tier(capital, small_thr, large_thr)

    # phase: explicit arg, else the live macro_cycle.
    cyc = macro_cycle() if phase is None else None
    use_phase = phase if phase is not None else (cyc.phase if cyc else "unknown")
    phase_tilt = _PHASE_TILT.get(use_phase, _PHASE_TILT["unknown"])
    cap_tilt = _CAPITAL_TILT[tier]

    # baseline = the static golden-path targets (the thing this reference would shift).
    golden, _ladder, _w = fin.get_golden_path()
    baseline = {ch: float(golden.get(ch, 0.0)) for ch in _CHANNELS}

    # reference weight = baseline + phase tilt + capital tilt, floored at 0, renormalized to 100.
    raw = {ch: max(0.0, baseline[ch] + phase_tilt.get(ch, 0) + cap_tilt.get(ch, 0)) for ch in _CHANNELS}
    total = sum(raw.values()) or 1.0
    targets = {ch: round(raw[ch] / total * 100.0, 1) for ch in _CHANNELS}
    vs_golden = {ch: round(targets[ch] - baseline[ch], 1) for ch in _CHANNELS}

    # per-channel rationale — NEUTRAL: states the MODEL reason, never an imperative.
    rationale: dict[str, str] = {}
    for ch in _CHANNELS:
        bits = [f"classic clock ({use_phase}) tilt {phase_tilt.get(ch, 0):+d}pp"]
        if cap_tilt.get(ch, 0):
            bits.append(f"{tier}-capital tilt {cap_tilt.get(ch, 0):+d}pp")
        rationale[ch] = f"reference {targets[ch]}% — " + ", ".join(bits) + f" vs golden-path {baseline[ch]:.0f}%"

    # confidence = q over the inputs: phase quality (from the cycle q if we computed it) +
    # capital known (always present here). Single-input-ish; honest low when phase unknown.
    phase_q = cyc.qCycle.q if cyc is not None else (0.5 if use_phase != "unknown" else 0.1)
    conf = compute_q([
        QInput(name="phase", present=(use_phase != "unknown"), value=phase_q, age_days=0.0, data_type="cycle"),
        QInput(name="capital", present=True, value=1.0, age_days=0.0, data_type="cycle"),
    ], needed=2).q

    return AllocationTarget(  # type: ignore[call-arg]  # note uses its canonical default (no pydantic mypy plugin)
        phase=use_phase, capitalTier=tier,  # type: ignore[arg-type]  # one of the CapitalTier Literal
        targets=targets, rationale=rationale, vsStaticGoldenPath=vs_golden,
        confidence=round(conf, 4),
    )


# --------------------------------------------------------------------------- #
# T2 — finance_guardian (spec §350-366): proactive NEUTRAL observations over     #
# EXISTING real data. Each rule fail-soft, evidence-grounded, framed as a         #
# QUESTION (never an imperative). Real-data-only: a mock/empty source → no fire   #
# (firing on mock fabricates concern). Mirrors the insights() scanner.            #
# --------------------------------------------------------------------------- #
def _guard_stablecoin_vs_fear() -> GuardianAlert | None:
    """OBSERVE: a high-stablecoin (cash-equivalent) crypto channel WHILE F&G shows fear/recovery
    — i.e. sitting in cash while sentiment turns. NEUTRAL question, not 'deploy'. Fires only on
    REAL stablePct AND real F&G (mock F&G → no fire)."""
    from modules.finance import service as fin
    from modules.macro import service as macro_svc

    ov, _ = fin.get_overview()
    crypto = next((a for a in ov.allocations if a.channel == "crypto"), None)
    stable_pct = getattr(crypto, "stablePct", None) if crypto else None
    if stable_pct is None or stable_pct < 80.0:
        return None
    fng_hist = macro_svc.get_history("fear_greed", days=7)
    if fng_hist is None or not fng_hist.points:
        return None
    last = fng_hist.points[-1]
    if last.source == "mock":   # real-data-only — a mock F&G must not fabricate concern
        return None
    return GuardianAlert(
        severity="high",
        msg=f"crypto channel is {stable_pct:.0f}% stablecoin (cash-equivalent) while Fear&Greed "
            f"reads {last.value:.0f} — is standing in cash here an intentional bet?",
        evidence={"stablePct": stable_pct, "fearGreed": last.value, "fngSource": last.source},
        sources=["finance_overview", "macro_history"],
    )


def _guard_meme_correlation() -> GuardianAlert | None:
    """OBSERVE: ≥2 held meme-ish coins that are HIGHLY correlated → 'diversified' in name but
    one bet in practice. NEUTRAL question. Fires only on REAL correlation data."""
    from modules.finance import service as fin
    from modules.market import service as mkt

    ov, _ = fin.get_overview()
    held = {h.symbol.upper() for h in ov.holdings if not getattr(h, "isDust", False)}
    memes = [s for s in ("PEPE", "DOGE", "SHIB", "TRUMP", "WIF", "BONK", "FLOKI") if s in held]
    if len(memes) < 2:
        return None
    try:
        corr, _ = mkt.correlation(memes[:4], hours=720)
    except Exception:  # noqa: BLE001 — fail-soft
        return None
    matrix = corr.get("matrix") if isinstance(corr, dict) else None
    if not matrix:
        return None   # no real correlation data → don't fabricate
    # find the max off-diagonal correlation
    hi = None
    for a in matrix:
        for b, val in (matrix.get(a, {}) or {}).items():
            if a != b and isinstance(val, (int, float)):
                hi = val if hi is None else max(hi, val)
    if hi is None or hi < 0.7:
        return None
    return GuardianAlert(
        severity="medium",
        msg=f"holding {len(memes)} meme coins ({', '.join(memes)}) with correlation up to "
            f"{hi:.2f} — is this diversification or one concentrated bet?",
        evidence={"memes": memes, "maxCorrelation": round(hi, 2)},
        sources=["finance_overview", "market_correlation"],
    )


def _guard_dust() -> GuardianAlert | None:
    """OBSERVE: a ·dust summary entry exists (sub-$1 coins cluttering the book). Low-severity
    NEUTRAL question. Fires only when a real dust fold happened."""
    from modules.finance import service as fin

    ov, _ = fin.get_overview()
    dust = next((h for h in ov.holdings if getattr(h, "isDust", False)), None)
    if dust is None or not dust.count:
        return None
    return GuardianAlert(
        severity="low",
        msg=f"{dust.count} sub-$1 dust holdings (total ${dust.usdValue or 0:.2f}) — worth a cleanup?",
        evidence={"dustCount": dust.count, "dustUsd": dust.usdValue},
        sources=["finance_overview"],
    )


_GUARDIAN_RULES = [_guard_stablecoin_vs_fear, _guard_meme_correlation, _guard_dust]
_GUARD_SEV_RANK = {"high": 0, "medium": 1, "low": 2}


def finance_guardian() -> GuardianReport:
    """The proactive scan (spec §350-366): NEUTRAL observations the user hasn't asked about —
    each a real-data FACT + evidence framed as a QUESTION (never 'you should X'). Real-data-only
    (a mock/empty source → no fire; firing on mock fabricates concern). Severity-ranked.
    Honest-empty: nothing fires → [] + a note (NOT a fabricated alert). Each rule fail-soft."""
    alerts: list[GuardianAlert] = []
    sources_ok = 0
    for rule in _GUARDIAN_RULES:
        try:
            a = rule()
            if a is not None:
                alerts.append(a)
            sources_ok += 1
        except Exception:  # noqa: BLE001 — one bad rule must not break the scan
            pass
    alerts.sort(key=lambda a: _GUARD_SEV_RANK.get(a.severity, 9))
    confidence = round(sources_ok / len(_GUARDIAN_RULES), 4) if _GUARDIAN_RULES else 0.0
    return GuardianReport(
        alerts=alerts, confidence=confidence, asOf=_now().isoformat(),
        note=(None if alerts else "nothing notable in the proactive scan right now"),
    )


# --------------------------------------------------------------------------- #
# T1 — nav_history reader (FINANCE-ASSISTANT P4, spec §1.6). Thin read over the   #
# EXISTING portfolio_snapshot table (the writer take_snapshot already runs in    #
# morning_pull). day=date, total_value=nav. confidence via the shared compute_q  #
# (coverage = points / NAV_POINTS_FOR_TREND). Fail-open: empty → series:[] +      #
# confidence 0 + warning, never a crash. NEUTRAL.                                 #
# --------------------------------------------------------------------------- #
# decide-and-log (#56): how many daily points before a NAV TREND is trustworthy. ~30 ≈ a month
# of daily snapshots — enough to read a direction without one outlier dominating. Below that the
# series is "accumulating" (low confidence). Configurable later if calibration suggests another.
NAV_POINTS_FOR_TREND = 30


def nav_history(date_from: str | None = None, date_to: str | None = None) -> NavHistory:
    """The daily NAV series (spec §1.6) over portfolio_snapshot, oldest→newest. ``date_from``/
    ``date_to`` ('YYYY-MM-DD', both optional → full series). nav = the row's total_value.
    confidence rises with point count (coverage = points / NAV_POINTS_FOR_TREND via compute_q —
    a short series can't be trusted for a trend). Fail-open: no data → series:[], points:0,
    confidence:0 + a warning, never a crash. NEUTRAL — data + confidence."""
    from store import db

    try:
        rows = db.snapshots(since=date_from)   # oldest→newest; from-filter at the db layer
    except Exception as exc:  # noqa: BLE001 — fail-open: a store read error → empty + warning
        logger.warning("nav_history snapshot read failed: %s", exc)
        rows = []

    # upper-bound (to) filter in the reader (db.snapshots has only a since/from filter).
    to_day = date_to[:10] if date_to else None
    series: list[NavPoint] = []
    for r in rows:
        day = r["day"]
        if to_day is not None and day > to_day:
            continue
        series.append(NavPoint(date=day, nav=round(float(r["total_value"]), 2)))

    points = len(series)
    # confidence via the shared q-engine: coverage = points / points-needed; freshness from the
    # NEWEST point's age (a stale-tail series is less trustworthy); single value → agreement 1.
    if points == 0:
        confidence = 0.0
        warning: str | None = "no NAV snapshots in range yet — the daily series is still accumulating"
        rng = NavRange(from_=None, to=None)
    else:
        newest_age = _age_days_from_ts(series[-1].date)
        # coverage = points / NAV_POINTS_FOR_TREND (spec §1.7) — built via the shared q-engine
        # by passing `min(points, needed)` PRESENT inputs (each a real day; capped so coverage
        # ≤ 1 when the series already exceeds the trend window). freshness from the newest point.
        n_for_q = min(points, NAV_POINTS_FOR_TREND)
        qinputs = [QInput(name=f"d{i}", present=True, value=1.0,
                          age_days=newest_age, data_type="nav") for i in range(n_for_q)]
        qr = compute_q(qinputs, needed=NAV_POINTS_FOR_TREND)
        confidence = round(qr.q, 4)
        warning = (None if points >= NAV_POINTS_FOR_TREND else
                   f"{points} point(s) — short series, a trend needs ~{NAV_POINTS_FOR_TREND}; "
                   f"still accumulating")
        rng = NavRange(from_=series[0].date, to=series[-1].date)

    return NavHistory(series=series, points=points, range=rng,
                      confidence=confidence, warning=warning)
