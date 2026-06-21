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


# --------------------------------------------------------------------------- #
# WIKI-CONTEXT (#36) — daily_brief enriched from the wiki graph. ADDITIVE +     #
# DETERMINISTIC (NO LLM): recent note activity + notable clusters pulled from    #
# the wiki reader (recent_ops + detect_clusters), NOT summarized by a model.     #
# Self-describing-raw + honest (empty lists, never a fabricated note/cluster).   #
# --------------------------------------------------------------------------- #
class RecentNote(BaseModel):
    """One recent wiki mutation surfaced into the brief (newest-first). SIGNAL, not advice."""

    noteId: int = Field(..., description="the note's id")
    title: str = Field(..., description="the note's title at the op (best-effort for a deleted note)")
    kind: Literal["create", "edit"] = Field(..., description="create | edit (delete/merge excluded — gone)")
    ts: str = Field(..., description="ISO-8601 UTC time of the op")


class ClusterRef(BaseModel):
    """One notable wiki cluster (MOC candidate) — mirrors the reader's detect_clusters
    shape (label = suggestedTitle, noteCount = size). Advisory interest signal."""

    label: str = Field(..., description="the cluster's deterministic suggestedTitle (NOT AI)")
    noteCount: int = Field(..., ge=0, description="number of notes in the cluster (= size)")


class WikiContext(BaseModel):
    """The wiki-graph context block (#36): recent note activity + notable clusters.
    DETERMINISTIC pull (no model). honest-empty: no activity → empty lists (not faked);
    wiki source down → empty lists + a warning (the block is still present, honest-blind)."""

    recentNotes: list[RecentNote] = Field(default_factory=list)
    clusters: list[ClusterRef] = Field(default_factory=list)
    asOf: str = Field(..., description="ISO-8601 UTC time the context was assembled")
    source: Literal["wiki"] = Field("wiki", description="source tag (always 'wiki')")
    warnings: list[str] = Field(default_factory=list, description="wiki-read fail-soft notes")


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
    # WIKI-CONTEXT (#36): ADDITIVE + OPTIONAL (None for old consumers / backward-compat).
    # Present (with possibly-empty lists) whenever the brief assembles; None only if the
    # whole wiki context build is skipped. Old consumers ignore an unknown field.
    wikiContext: WikiContext | None = Field(
        default=None, description="#36: wiki-graph context (recent notes + clusters), deterministic")
