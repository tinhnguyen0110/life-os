"""modules/wiki/schema.py — Wiki note shapes (Sprint W1a, M1 Wiki Core). FROZEN.

A wiki note is a markdown file under md_store ``wiki/notes/<id>.md`` (YAML
frontmatter + body). Identity is an **integer ID** (filename = id, never changes
— D1); ``title`` is mutable metadata. ``contentHash`` is sha256 of the BODY only
(derived cache, surfaced for W1c reindex / W2 block-id drift — NOT authored into
frontmatter).

This module is SEPARATE from the existing string-ID ``notes`` module (different
name, md subdir, tables) — user-approved new module, not a rewrite.

Frozen field list = ``plan_sprint_W1a.md`` §Schema. Links / FTS / graph / AI
suggestion fields are LATER sprints (W1b/W1c/W2) and intentionally absent here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# --- Enums (Literal-locked at the boundary) -------------------------------- #
Status = Literal["fleeting", "developing", "evergreen"]
NoteType = Literal["concept", "literature"]
TrustTier = Literal["verified", "candidate"]


class Note(BaseModel):
    """A stored wiki note (response model, ``GET /wiki/notes/{id}``).

    ``id`` is the immutable integer identity; ``title`` is mutable ("" allowed for
    a raw fleeting capture with no title yet). Timestamps are ISO-8601 UTC,
    server-set. ``contentHash`` = sha256 of the body.
    """

    id: int
    title: str = ""
    aliases: list[str] = Field(default_factory=list)
    status: Status = "fleeting"
    noteType: NoteType = "concept"
    trustTier: TrustTier = "verified"
    author: str = "human"  # human | agent:<name>
    tags: list[str] = Field(default_factory=list)
    content: str = ""  # markdown body
    created: str
    updated: str
    contentHash: str


class NoteCreateInput(BaseModel):
    """``POST /wiki/notes`` body — id + timestamps assigned server-side.

    Capture = raw dump → status defaults ``fleeting``; title/links come at REFINE
    (a fleeting note legitimately has no title). ``author`` recorded so W2/M4
    agent writes slot in unchanged.
    """

    content: str = ""
    title: str = Field(default="", max_length=200)
    status: Status = "fleeting"
    noteType: NoteType = "concept"
    tags: list[str] = Field(default_factory=list)
    author: str = "human"
    # Where this capture came from (mock inbox field). command_bar | quick_add |
    # mcp_agent | daily_note. Free-form str (not Literal) so a new source doesn't
    # break the boundary; defaults quick_add.
    captureSource: str = "quick_add"

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: str) -> str:
        return v.strip()


class MergeInput(BaseModel):
    """``POST /wiki/notes/merge`` body (B5/D6). Merge ``sourceId`` INTO ``targetId``:
    source is deleted, a redirect tombstone (source→target) is written, inbound
    links repointed. Both required; equal ids → 422; either absent → 404."""

    sourceId: int
    targetId: int


class NoteUpdateInput(BaseModel):
    """``PUT /wiki/notes/{id}`` body — partial update (all fields optional).

    A field left ``None`` is unchanged; a present field overwrites. ``status`` /
    ``noteType`` / ``trustTier`` are Literal-validated (bad value → 422). Title is
    whitespace-stripped and capped at 200 chars.
    """

    title: str | None = Field(default=None, max_length=200)
    content: str | None = None
    status: Status | None = None
    noteType: NoteType | None = None
    trustTier: TrustTier | None = None
    aliases: list[str] | None = None
    tags: list[str] | None = None

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: str | None) -> str | None:
        return v.strip() if v is not None else None
