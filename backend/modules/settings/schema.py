"""modules/settings/schema.py — global AppConfig (S12, FROZEN).

The system config the Settings screen edits + the routines read at runtime. Defaults =
the CURRENT hardcoded behavior (so an absent/fresh config.md reproduces today's app):
automationEnabled=True, briefHour=8, idleThresholdDays=7, patternCheckEnabled=True,
errorChannel="inapp", timezone="Asia/Ho_Chi_Minh", displayName="".

Per-field validation at the boundary → a bad PATCH field is a 422 echoing WHICH field
(not a silent clamp). PATCH is partial (AppConfigPatch — all optional); GET returns the
full resolved AppConfig.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ErrorChannel = Literal["discord", "inapp", "none"]


class AppConfig(BaseModel):
    """The full resolved global config (GET /settings returns this)."""

    automationEnabled: bool = Field(default=True, description="master switch — scheduled routines run when True")
    briefHour: int = Field(default=8, ge=0, le=23, description="hour-of-day (UTC) morning-pull + brief run")
    idleThresholdDays: int = Field(default=7, ge=1, description="idle-hunter flags projects idle > this many days")
    patternCheckEnabled: bool = Field(default=True, description="pattern-check (build-to-90) routine on/off")
    errorChannel: ErrorChannel = Field(default="inapp", description="where routine errors surface")
    timezone: str = Field(default="Asia/Ho_Chi_Minh", min_length=1, max_length=64, description="display timezone label (stored-only this sprint)")
    displayName: str = Field(default="", max_length=80, description="owner display name (stored-only this sprint; may be empty)")
    # W4d (USER-ORDERED, reverses D8 proposals-only). ON = agent/MCP writes apply to
    # the vault DIRECTLY (auto-accepted via the proposal chokepoint, decidedBy=
    # "agent:auto", still fully audited + visible in P1 history). OFF (default) =
    # proposals-only, human ratifies in P1 (the north-star). Defaults OFF so the safe
    # behavior holds for a fresh/absent config.
    wikiAgentAutonomous: bool = Field(default=False, description="ON = agent writes apply directly (bypass the human-ratify queue); OFF (default) = proposals-only")
    # FINANCE-ASSISTANT P3 (#55): the capital-size risk thresholds allocation_target reads —
    # USER-CONFIGURABLE (the user owns their risk appetite; we default, they override). Capital
    # < small → may tilt aggressive; ≥ large → fractional-Kelly conservative; smooth between.
    # NOT hardcoded in the tool (team-lead lock).
    riskCapitalSmallUsd: float = Field(default=50000.0, ge=0, description="capital below this → may tilt aggressive (allocation_target)")
    riskCapitalLargeUsd: float = Field(default=500000.0, ge=0, description="capital at/above this → fractional-Kelly conservative (allocation_target)")
    # SIDEBAR-UX (#72): user-pinned sidebar routes (ordered) → render a "Ghim" group at the
    # top. Persisted BACKEND (not localStorage) so pins SYNC across devices (Tailscale multi-
    # device). Stored as-is (no route validation — a route the user pinned then we renamed
    # must NOT 422; the FE skips routes that don't resolve). Empty list = no pins.
    pinnedRoutes: list[str] = Field(default_factory=list, description="user-pinned sidebar routes (ordered) — render a 'Ghim' group at the top; synced via /settings (multi-device)")


class AppConfigPatch(BaseModel):
    """Partial update (PATCH /settings) — every field optional; only provided keys change.
    Same per-field constraints as AppConfig → a bad value is a per-field 422."""

    model_config = {"extra": "forbid"}  # an unknown field is a 422, not silently ignored

    automationEnabled: bool | None = Field(default=None)
    briefHour: int | None = Field(default=None, ge=0, le=23)
    idleThresholdDays: int | None = Field(default=None, ge=1)
    patternCheckEnabled: bool | None = Field(default=None)
    errorChannel: ErrorChannel | None = Field(default=None)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    displayName: str | None = Field(default=None, max_length=80)  # may be empty (stored-only)
    wikiAgentAutonomous: bool | None = Field(default=None)  # W4d toggle (USER-ORDERED)
    # FINANCE-ASSISTANT P3 (#55): user-editable capital-size risk thresholds.
    riskCapitalSmallUsd: float | None = Field(default=None, ge=0)
    riskCapitalLargeUsd: float | None = Field(default=None, ge=0)
    # SIDEBAR-UX (#72): the pinned-routes mirror. None = don't touch the stored pins; an
    # EMPTY list [] = CLEAR the pins (exclude_none keeps [] in the merge → persists the clear).
    pinnedRoutes: list[str] | None = Field(default=None)
