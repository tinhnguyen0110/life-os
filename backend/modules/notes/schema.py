"""modules/notes/schema.py — Notes shapes (Sprint 6, SPEC §S10). FROZEN.

A note is a markdown file under md_store `notes/<id>.md` (YAML front-matter +
body). `attach{type,ref}` links a note to a project, a finance channel, or
nothing. `pinned` notes sort first. id/timestamps are server-set; NoteInput is
the create/update body (pin toggle = PUT with pinned flipped).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

AttachType = Literal["project", "channel", "none"]


class Attach(BaseModel):
    """What a note is attached to. ref required when type != 'none'. Free-form ref
    (no cross-module validation — single-user, attach is a soft tag)."""

    type: AttachType = "none"
    ref: str | None = None  # project id / channel id / None


class Note(BaseModel):
    """A stored note. id = slug(title)-<6hex>; timestamps ISO-8601 UTC."""

    id: str
    title: str
    body: str = ""
    tags: list[str] = Field(default_factory=list)
    pinned: bool = False
    attach: Attach = Field(default_factory=Attach)
    createdAt: str
    updatedAt: str


class NoteInput(BaseModel):
    """POST/PUT body — id + timestamps are assigned server-side.

    Pin toggle is via PUT (send the full body with pinned flipped) — no separate
    /pin endpoint (one update path, north-star).
    """

    title: str = Field(..., min_length=1, max_length=200)
    body: str = ""
    tags: list[str] = Field(default_factory=list)
    pinned: bool = False
    attach: Attach = Field(default_factory=Attach)

    @model_validator(mode="after")
    def _ref_required_when_attached(self) -> "NoteInput":
        if self.attach.type != "none" and not (self.attach.ref and self.attach.ref.strip()):
            raise ValueError("attach.ref is required when attach.type is not 'none'")
        return self
