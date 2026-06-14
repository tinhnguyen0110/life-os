"""modules/reliability/schema.py — Reliability Harness report shapes (Sprint W8 A3).

The harness runs CHECKS (grounding-eval, fail-closed gates); each check runs CASES.
A case passes iff actual==expected; a check passes iff all its cases pass; the suite
passes iff all checks pass. Computed, not persisted (deterministic, in-code corpus).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CaseResult(BaseModel):
    """One corpus case run through a checker."""

    label: str
    expected: str
    actual: str
    passed: bool
    detail: str | None = None  # e.g. the reason mismatch, or a target-raised error


class CheckResult(BaseModel):
    """One reliability check (a group of cases) — e.g. grounding-eval or a gate."""

    name: str
    passed: bool
    cases: list[CaseResult] = Field(default_factory=list)


class ReliabilityReport(BaseModel):
    """GET /reliability .data — the full suite run."""

    checks: list[CheckResult] = Field(default_factory=list)
    passed: bool = Field(..., description="True iff every check passed")
    summary: dict[str, Any] = Field(..., description="{total, passed, failed} over all cases")
