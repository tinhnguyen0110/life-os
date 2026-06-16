"""modules/decision/schema.py — decision-tower shapes (FINANCE-ASSISTANT P2, #54).

Self-describing: every derived number carries its inputs so an agent can verify it without
reading code. NEUTRAL — data + q only, never advice.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Investment-Clock phase (growth × inflation). Honest 'unknown' when coverage is too thin to
# name a phase (never fabricate one).
CyclePhase = Literal["recovery", "overheat", "stagflation", "slowdown", "unknown"]


class QInputView(BaseModel):
    """One input that fed compute_q — surfaced so the q is auditable."""

    name: str = Field(..., description="which input (e.g. 'growth', 'inflation', 'yield_curve')")
    present: bool = Field(..., description="did this input have data (vs missing → lowers coverage)")
    value: float | None = Field(None, description="the observed value, if present")
    ageDays: float | None = Field(None, description="age of the point in days (freshness input), if present")
    freshness: float | None = Field(None, description="exp(-age/τ) for this input, if present")
    source: str | None = Field(None, description="'fred' | 'live' | 'mock' | ...")


class QResult(BaseModel):
    """The q-engine output: q = freshness × coverage × agreement, each ∈ [0,1], + the
    breakdown so the number is self-verifiable. NO clamp — q is the raw product."""

    q: float = Field(..., description="freshness × coverage × agreement (∈ [0,1])")
    freshness: float = Field(..., description="mean exp(-age/τ) over present inputs (1.0 if none age-bearing)")
    coverage: float = Field(..., description="(#inputs with data) / (#inputs needed)")
    agreement: float = Field(..., description="1 - dispersion; 1.0 for a single source/input")
    breakdown: list[QInputView] = Field(
        default_factory=list, description="per-input detail (present/value/age/freshness/source)")
    neededInputs: int = Field(..., ge=0, description="#inputs the consumer declared it needs (coverage denom)")
    presentInputs: int = Field(..., ge=0, description="#inputs that had data (coverage numer)")


class CycleAxis(BaseModel):
    """One Investment-Clock axis (growth / inflation / yield_curve) + its own q input."""

    axis: str = Field(..., description="'growth' | 'inflation' | 'yield_curve'")
    direction: Literal["up", "down", "flat", "unknown"] = Field(
        ..., description="descriptive trend of this axis (NEUTRAL, not a forecast)")
    present: bool = Field(..., description="did this axis have real (non-mock) data")
    detail: str = Field("", description="how the axis was derived (e.g. 'INDPRO up + UNRATE down')")


class MacroCycle(BaseModel):
    """The Investment-Clock RL state: phase (growth × inflation) + q_cycle from compute_q.
    NEUTRAL — data + q. ``favored``/``defensive`` are a REFERENCE map (which assets the
    classic clock associates with the phase), NOT advice for the user's specific book."""

    phase: CyclePhase = Field(..., description="recovery|overheat|stagflation|slowdown|unknown")
    axes: list[CycleAxis] = Field(default_factory=list, description="growth / inflation / yield_curve")
    qCycle: QResult = Field(..., description="compute_q over the cycle axes (coverage<1 when an axis is mock/missing)")
    favored: list[str] = Field(
        default_factory=list, description="reference: asset classes the classic clock favors in this phase")
    defensive: list[str] = Field(
        default_factory=list, description="reference: classic-clock defensive classes in this phase")
    confidence: float = Field(..., description="= qCycle.q (how much to trust the phase call)")
    warning: str | None = Field(None, description="honest note when an axis is mock/missing (coverage<1)")


class LayerView(BaseModel):
    """One layer of the decision-weight product (q + where it came from)."""

    layer: str = Field(..., description="'q_cycle' | 'q_macro' | 'q_flow' | 's_asset'")
    q: float = Field(..., description="this layer's q (∈ [0,1]); 0 = no data → blinds the whole W")
    note: str = Field("", description="what this layer measured + why its q is what it is")


class DecisionWeight(BaseModel):
    """The combiner: W = q_cycle × q_macro × q_flow × s_asset — PURE PRODUCT, NO inter-layer
    clamp (the hierarchy is enforced BY the multiply, not by min(qᵢ, q_{i-1})). A layer at 0
    → W=0 ("blind = don't bet"). ``weight`` and ``confidence`` are TWO SEPARATE numbers (legend
    below) — weight = signal strength; confidence = how much to trust the measurement."""

    weight: float = Field(..., description="W = ∏ qᵢ (signal STRENGTH; ∈ [0,1]). NOT confidence.")
    verdict: str = Field(..., description="NEUTRAL descriptive band of the weight (e.g. 'thin'/'moderate'/'strong') — data, not advice")
    breakdown: list[LayerView] = Field(default_factory=list, description="per-layer q + note")
    bindingConstraint: str = Field(..., description="the DIMMEST layer (argmin q) — where adding data would help most")
    explanation: str = Field(..., description="NEUTRAL one-line of how W was formed (no advice verb)")
    confidence: float = Field(
        ..., description="how much to TRUST the weight measurement (mean layer q) — SEPARATE from weight")
    legend: str = Field(
        "weight = signal strength (∏ of layer q); confidence = trust in the measurement. "
        "High weight + low confidence = a strong-looking signal you can't yet trust.",
        description="the weight-vs-confidence legend so the two are never conflated")


# --------------------------------------------------------------------------- #
# T1 — allocation_target (FINANCE-ASSISTANT P3, spec §208-227). A NEUTRAL        #
# REFERENCE weighting: classic Investment-Clock (phase) + the user's capital-     #
# size implies this weighting — surfaced as DATA with the rationale, NOT advice.  #
# --------------------------------------------------------------------------- #
CapitalTier = Literal["small", "mid", "large"]


class AllocationTarget(BaseModel):
    """A NEUTRAL reference weighting (NOT an order): the classic Investment-Clock for the
    given ``phase`` + the user's ``capitalTier`` implies these channel weights. ``rationale``
    explains each channel's weight; ``vsStaticGoldenPath`` shows the delta from the fixed
    golden-path so the agent sees what the model would shift. ``confidence`` = q over the
    inputs' quality. The user (or the agent) decides — this surfaces what the model implies."""

    phase: str = Field(..., description="the macro_cycle phase this weighting is FOR (recovery|overheat|...|unknown)")
    capitalTier: CapitalTier = Field(..., description="small (<riskCapitalSmallUsd) | mid | large (≥riskCapitalLargeUsd)")
    targets: dict[str, float] = Field(..., description="reference weight % per channel (sums ~100)")
    rationale: dict[str, str] = Field(
        default_factory=dict, description="per-channel: WHY this weight (classic-clock + capital-size)")
    vsStaticGoldenPath: dict[str, float] = Field(
        default_factory=dict, description="per-channel delta vs the fixed golden-path (target − goldenpath)")
    confidence: float = Field(..., description="q over the inputs (phase quality + capital known); ∈ [0,1]")
    note: str = Field(
        "REFERENCE weighting from the classic Investment-Clock + your capital size — a model "
        "assumption surfaced as DATA, not an instruction. You decide.",
        description="the neutrality note (this is a reference model, not advice)")


# --------------------------------------------------------------------------- #
# T2 — finance_guardian (FINANCE-ASSISTANT P3, spec §350-366). Proactive NEUTRAL #
# observations over EXISTING real data — each alert is an OBSERVATION + evidence  #
# framed as a QUESTION, never an imperative. Mirrors the insights() scanner.      #
# --------------------------------------------------------------------------- #
class GuardianAlert(BaseModel):
    """One proactive observation: a real-data fact + evidence, framed as a QUESTION (NEUTRAL —
    never 'you should X'). ``sources`` names the read paths it observed (auditable)."""

    severity: Literal["high", "medium", "low"] = Field(..., description="high|medium|low")
    msg: str = Field(..., description="the observation, framed as a question (no advice verb)")
    evidence: dict = Field(default_factory=dict, description="the real numbers it derived from")
    sources: list[str] = Field(default_factory=list, description="the read tools it observed")


class GuardianReport(BaseModel):
    """The proactive scan: NEUTRAL observations the user hasn't asked about (the mentor's
    'unknown unknowns'). Real-data-only — a rule whose source is mock/empty does NOT fire
    (firing on mock fabricates concern). Severity-ranked, honest-empty when nothing notable."""

    alerts: list[GuardianAlert] = Field(default_factory=list)
    confidence: float = Field(..., description="data quality behind the scan (∈ [0,1])")
    asOf: str = Field(..., description="ISO-8601 UTC of the scan")
    note: str | None = Field(None, description="honest note when nothing fired (vs a fabricated alert)")
