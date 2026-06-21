"""modules/mcp_keys/schema.py — per-KEY MCP tool-scoping shapes (#86, FROZEN).

A KEY is a filter-SELECTOR (single-user, no-auth — NOT a secret credential): a client
configures ONE MCP endpoint + ONE key, and the server narrows which tools that key sees
to ``scope`` = the UNION of its ``domains`` (mount labels) AND explicit ``tools``. #87
(the /mcp key-aware filter) + #88 (the UI) mirror these shapes — FROZEN once.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Scope(BaseModel):
    """What a key can see: the UNION of whole DOMAINS (mount labels: read/write/wiki-read/
    wiki-write/finance/reminders) AND explicit per-TOOL names. Empty `{[],[]}` = a valid
    sees-NOTHING key (distinct from no-key-at-all, which the filter treats as all-tools)."""

    domains: list[str] = Field(default_factory=list, description="mount labels the key sees in full")
    tools: list[str] = Field(default_factory=list, description="explicit tool names the key sees")


class KeyCreate(BaseModel):
    """``POST /mcp_keys`` body — label + optional scope (defaults to sees-nothing `{[],[]}`)."""

    label: str = Field(..., min_length=1, max_length=80, description="human label for the key")
    scope: Scope = Field(default_factory=Scope)

    @field_validator("label")
    @classmethod
    def _strip_label(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("label must be non-empty")
        return s


class KeyUpdate(BaseModel):
    """``PUT /mcp_keys/{key}`` body — partial. A field left None is unchanged."""

    label: str | None = Field(default=None, max_length=80)
    scope: Scope | None = None

    @field_validator("label")
    @classmethod
    def _strip_label(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("label must be non-empty when provided")
        return s


class KeyRow(BaseModel):
    """The agent-readable list row (FROZEN). ``toolCount`` = the RESOLVED union size (how many
    tools the key effectively sees against the live catalog) — so the agent/UI sees the effective
    count without re-resolving. ``key`` is the selector token."""

    key: str = Field(..., description="the key selector token")
    label: str
    scope: Scope
    toolCount: int = Field(..., ge=0, description="resolved size of (domains-union ∪ tools) vs the live catalog")
    createdAt: str = Field(..., description="ISO-8601 UTC create time")
