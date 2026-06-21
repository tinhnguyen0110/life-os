"""modules/brief/schema.py — the daily brief shapes (S11, FROZEN).

Template-based (NO AI): a deterministic roll-up of the other modules + a numbered,
severity-ordered priority list. ``source`` is "template" (NOT an AI model label — the
in-app brief is rule-based; ARCH §11's Claude-generated brief is the later MCP phase).

Self-describing-raw: ``summary`` carries structured numbers (netWorth/projectsActive/
claudePct/alertsToday) so the FE composes the display + an agent reads the API; the
priority ``source`` + ``severity`` make each line traceable to the rule that emitted it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["info", "warn", "urgent"]
# REMINDERS-4 (#30): +reminders. DAILY-TRACING-P4 (#65): +tracing (the streak-at-risk rule's source).
PrioritySource = Literal["market", "projects", "claude", "finance", "alerts", "reminders", "tracing"]


class Priority(BaseModel):
    """One numbered priority line. ``n`` is the 1-based DISPLAY rank assigned AFTER the
    severity sort (1 = most severe); ``source`` names the rule that emitted it."""

    n: int = Field(..., ge=0, description="display rank, 1-based after the severity sort (0 = pre-sort placeholder)")
    text: str = Field(..., description="the human priority line (plain text; FE styles)")
    source: PrioritySource
    severity: Severity


class BriefSummary(BaseModel):
    """Structured roll-up numbers (FE composes the display string; agent reads these).
    None where the source is down/absent — honest no-data, not a fabricated 0."""

    netWorth: float | None = Field(None, description="finance.totalValue (None if finance down)")
    projectsActive: int = Field(0, ge=0, description="count(not-abandoned & health in act/slow)")
    claudePct: float | None = Field(None, description="claude.pct (None if claude down)")
    alertsToday: int = Field(0, ge=0, description="count(market alerts fired today)")


class Brief(BaseModel):
    """The daily brief. ``priorities`` is severity-ordered (urgent>warn>info), capped ~5.
    ``priorities=[]`` is the honest-empty state (nothing urgent — NOT a failure)."""

    generatedAt: str = Field(..., description="ISO-8601 assembly time")
    asOf: str = Field(..., description="oldest source freshness (≈ claude cache date)")
    source: str = Field("template", description="'template' — rule-based, NOT AI this build")
    summary: BriefSummary
    priorities: list[Priority] = Field(default_factory=list)
    stale: bool = Field(False, description="any source stale (claude cache old) → don't imply live")
    warnings: list[str] = Field(default_factory=list, description="per-source fail-soft notes")
