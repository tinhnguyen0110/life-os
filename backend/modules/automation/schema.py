"""modules/automation/schema.py — Automation shapes (Sprint 10A, SPEC §S13). FROZEN.

GET /routines → RoutinesView (the catalog merged with run_log stats). A routine =
a rule-based job (NO AI). triggerLabel is a human display string; lastRun/lastResult/
runs come from run_log per id. enabled is the persisted toggle (md_store).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Trigger = Literal["interval", "cron", "date", "event"]
RunResult = Literal["ok", "warn", "error"]


class RoutineInfo(BaseModel):
    """One routine + its run_log stats (GET /routines → routines[])."""

    id: str
    name: str
    trigger: Trigger
    triggerLabel: str = Field(..., description="human display, e.g. '22:00 mỗi tối'")
    desc: str
    action: str
    enabled: bool
    lastRun: str | None = Field(None, description="ISO-8601 of newest run_log row, else None")
    lastResult: RunResult | None = Field(None, description="newest run's status, else None")
    runs: int = Field(..., ge=0, description="total run_log count for this id")


class RoutinesView(BaseModel):
    """GET /routines .data — all routines + roll-up stats."""

    routines: list[RoutineInfo] = Field(default_factory=list)
    activeCount: int = Field(..., ge=0, description="enabled count")
    total: int = Field(..., ge=0)
    runsToday: int = Field(..., ge=0, description="run_log rows started today")
    lastRunAt: str | None = Field(None, description="newest run_log row overall, else None")


class ToggleInput(BaseModel):
    """PATCH /routines/{id} body."""

    enabled: bool


class RunResultView(BaseModel):
    """POST /routines/{id}/run → the recorded run."""

    id: str
    status: RunResult
    detail: str
    startedAt: str
    finishedAt: str
