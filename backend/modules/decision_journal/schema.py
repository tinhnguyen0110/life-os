"""modules/decision_journal/schema.py — Decision Journal shapes (Sprint W7 A2, FROZEN).

A general DECISION (not a trade): the decision + thesis + falsification condition +
a confidence% (the probability claim) → on resolve, an outcome (right/wrong) drives
calibration. ``domain`` is the free-form bias-cluster key (investment/project/...).

confidence is REQUIRED (0-100, the probability claim — 422 out of range). ``predicted``
is an optional explicit 0-1 probability; if absent, Brier derives it from confidence/100.
``status``/``outcome`` model the open→resolved lifecycle (outcome None while open).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Status = Literal["open", "resolved"]
Outcome = Literal["right", "wrong"]


class DecisionEntry(BaseModel):
    """A stored decision (response model). ``id`` + timestamps server-set."""

    id: str
    decision: str = Field(min_length=1, max_length=2000)
    thesis: str | None = Field(default=None, max_length=4000)
    falsificationCondition: str | None = Field(default=None, max_length=4000)
    confidence: int = Field(ge=0, le=100, description="probability claim 0-100 (REQUIRED)")
    predicted: float | None = Field(default=None, ge=0.0, le=1.0,
                                    description="explicit 0-1 prob; None → derive confidence/100")
    date: str
    domain: str = Field(min_length=1, max_length=200, description="bias-cluster key")
    status: Status = "open"
    outcome: Outcome | None = None  # None while open; set on resolve
    lesson: str | None = Field(default=None, max_length=4000)
    # FINANCE-ASSISTANT P3 (#55) — finance-decision fields (additive, optional; a non-finance
    # decision leaves them None). falsificationCondition already = the "invalidation". These
    # let a finance decision (domain="investment") record the EV thesis + accepted downside +
    # the decision_weight W at decision time (so the bet-size can later be correlated with the
    # outcome). They do NOT touch calibration/Brier (those key on confidence/outcome only).
    expectedEv: str | None = Field(default=None, max_length=2000, description="the EV thesis at decision time (e.g. 'positive_asymmetric')")
    worstCase: str | None = Field(default=None, max_length=2000, description="the accepted worst-case downside")
    decisionWeight: float | None = Field(default=None, ge=0.0, le=1.0, description="the decision_weight W (∏q) logged at decision time, if any")
    createdAt: str
    updatedAt: str


class DecisionInput(BaseModel):
    """POST/PUT body — id + timestamps assigned server-side. ``status``/``outcome``
    optional (a resolve sets them). Same per-field constraints as DecisionEntry."""

    decision: str = Field(min_length=1, max_length=2000)
    thesis: str | None = Field(default=None, max_length=4000)
    falsificationCondition: str | None = Field(default=None, max_length=4000)
    confidence: int = Field(ge=0, le=100)
    predicted: float | None = Field(default=None, ge=0.0, le=1.0)
    date: str | None = None  # defaults now on create
    domain: str = Field(min_length=1, max_length=200)
    status: Status | None = None
    outcome: Outcome | None = None
    lesson: str | None = Field(default=None, max_length=4000)
    # FINANCE-ASSISTANT P3 (#55) — finance-decision fields (additive, optional).
    expectedEv: str | None = Field(default=None, max_length=2000)
    worstCase: str | None = Field(default=None, max_length=2000)
    decisionWeight: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("decision", "domain")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class DecisionUpdate(BaseModel):
    """PUT body — PARTIAL update (all fields optional; PATCH-semantics). A field left
    None keeps the existing value; a present field overrides. This makes the NATURAL
    resolve call work: ``PUT {status:"resolved", outcome:"right"}`` — no need to
    resend decision/confidence/domain (W7-A2-fix: the required-field PUT 422'd the
    natural resolve). Same per-field constraints as DecisionEntry."""

    decision: str | None = Field(default=None, min_length=1, max_length=2000)
    thesis: str | None = Field(default=None, max_length=4000)
    falsificationCondition: str | None = Field(default=None, max_length=4000)
    confidence: int | None = Field(default=None, ge=0, le=100)
    predicted: float | None = Field(default=None, ge=0.0, le=1.0)
    date: str | None = None
    domain: str | None = Field(default=None, min_length=1, max_length=200)
    status: Status | None = None
    outcome: Outcome | None = None
    lesson: str | None = Field(default=None, max_length=4000)
    # FINANCE-ASSISTANT P3 (#55) — finance-decision fields (additive, optional; partial update).
    expectedEv: str | None = Field(default=None, max_length=2000)
    worstCase: str | None = Field(default=None, max_length=2000)
    decisionWeight: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("decision", "domain")
    @classmethod
    def _strip_opt(cls, v: str | None) -> str | None:
        return v.strip() if v is not None else None


class CalibrationBand(BaseModel):
    """One confidence band vs actual outcome-right rate (resolved + confident only).
    Mirrors the trade journal's band shape so the FE renders one way."""

    band: str = Field(..., description="e.g. '90-100'")
    predicted: float = Field(..., description="band midpoint")
    actual: float = Field(..., description="%(outcome=='right') within the band — the THESIS axis")
    n: int = Field(..., ge=1, description="count in band (n=0 bands omitted)")


class BiasFlag(BaseModel):
    """A domain whose resolved-wrong-rate exceeds the threshold over the min sample
    (rule-based bias detection — no LLM, min-n gate against sparse-data false positives)."""

    domain: str
    wrongRate: float = Field(..., description="count(outcome=='wrong')/n in the domain")
    n: int = Field(..., ge=1, description="resolved count in the domain (only flagged when ≥ min-n)")


class DecisionStats(BaseModel):
    """GET /decision-journal .data — entries + derived calibration/bias stats."""

    entries: list[DecisionEntry] = Field(default_factory=list)
    count: int = Field(..., ge=0)
    resolvedCount: int = Field(..., ge=0, description="status=resolved AND outcome in (right,wrong)")
    brier: float | None = Field(None, description="mean((p-o)^2) over resolved; None if 0 resolved; lower=better")
    calibration: list[CalibrationBand] = Field(default_factory=list)
    biasFlags: list[BiasFlag] = Field(default_factory=list)
