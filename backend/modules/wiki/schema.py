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

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


def normalize_folder(v: str) -> str:
    """Normalize a virtual folder path (W-Explorer): strip, drop leading/trailing
    "/", collapse "//"→"/", strip whitespace around each segment. "" = root. So
    "  /Projects//life-os/ " → "Projects/life-os". A path that normalizes to empty
    (e.g. "/" or "   ") → "" (root). Deterministic + idempotent."""
    if not v:
        return ""
    segments = [s.strip() for s in re.split(r"/+", v.strip()) if s.strip()]
    return "/".join(segments)

# --- Enums (Literal-locked at the boundary) -------------------------------- #
Status = Literal["fleeting", "developing", "evergreen"]
NoteType = Literal["concept", "literature", "moc"]  # moc = Map-of-Content (W5, D-W5.2)
TrustTier = Literal["verified", "candidate"]

# WIKI-WRITE-FEEDBACK (#35): the CLOSED reason set a human picks when overriding an
# AGENT-written note (edit or delete) — the structured signal an agent reads back to
# write less junk. Small + fixed (Pydantic Literal → a bad value is a 422, not a free
# string). Decided + logged to ## Assumptions.
OverrideReason = Literal[
    "off-scope", "wrong", "duplicate", "low-quality", "outdated", "other"
]
# the override kind = which mutation carried the feedback (an edit that overrode the
# agent's note, or a delete that removed it).
OverrideKind = Literal["edit", "delete"]


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
    # W-Explorer: a VIRTUAL folder path (e.g. "Projects/life-os"); "" = root. NOT a
    # physical folder — the file stays flat at <id>.md (D1). A "move" only changes this
    # field. The explorer builds a virtual tree from all notes' folder values.
    folder: str = ""
    created: str
    updated: str
    contentHash: str


class NoteCreateInput(BaseModel):
    """``POST /wiki/notes`` body — id + timestamps assigned server-side.

    Capture = raw dump → status defaults ``fleeting``; title/links come at REFINE
    (a fleeting note legitimately has no title). ``author`` recorded so W2/M4
    agent writes slot in unchanged.

    #45: ``trustTier`` is settable here (was MISSING → silently dropped → every note born
    "verified", a bug). ``extra="forbid"`` so a future unknown kwarg 422s instead of vanishing
    (the silent-drop is exactly what hid the missing-trustTier bug — a dropped field is a silent lie).
    """

    model_config = {"extra": "forbid"}  # #45: unknown field → 422, never a silent drop

    content: str = ""
    title: str = Field(default="", max_length=200)
    status: Status = "fleeting"
    noteType: NoteType = "concept"
    trustTier: TrustTier = "verified"  # #45: was missing → dropped; default unchanged when omitted
    tags: list[str] = Field(default_factory=list)
    author: str = "human"
    # Where this capture came from (mock inbox field). command_bar | quick_add |
    # mcp_agent | daily_note. Free-form str (not Literal) so a new source doesn't
    # break the boundary; defaults quick_add.
    captureSource: str = "quick_add"
    folder: str = Field(default="", max_length=500)  # W-Explorer virtual path; ""=root

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: str) -> str:
        return v.strip()

    @field_validator("folder")
    @classmethod
    def _norm_folder(cls, v: str) -> str:
        return normalize_folder(v)


class MergeInput(BaseModel):
    """``POST /wiki/notes/merge`` body (B5/D6). Merge ``sourceId`` INTO ``targetId``:
    source is deleted, a redirect tombstone (source→target) is written, inbound
    links repointed. Both required; equal ids → 422; either absent → 404."""

    sourceId: int
    targetId: int


class FolderMetaInput(BaseModel):
    """``PUT /wiki/folders/{path}/meta`` body (WIKI-RETRIEVAL-1 #20) — set a folder's description
    (the tree's ``meta:{desc}``). A blank ``desc`` CLEARS the meta (→ meta:null, honest-null)."""

    desc: str = Field(default="", max_length=500, description="what this folder holds (blank clears)")


class DeviceRegisterInput(BaseModel):
    """``POST /wiki/sync/devices`` body (M3 A1a) — register/refresh a sync device."""

    deviceId: str = Field(min_length=1, max_length=100)
    name: str = Field(default="", max_length=200)


class ConflictResolveInput(BaseModel):
    """``POST /wiki/sync/conflicts/{id}/resolve`` body — the human picks the winning
    content for a conflicted block; it's written THROUGH the single-writer queue
    (reuses update_note). ``content`` is the chosen block text."""

    noteId: int
    content: str = Field(default="", max_length=100_000)


class Citation(BaseModel):
    """One citation an external agent attached to a claim (W6 A1b). ``noteId`` +
    ``span`` are optional so an UNGROUNDED claim (no citation) is still expressible
    (→ status ungrounded). ``span`` = the literal passage the agent says supports
    the claim (substring-matched against the note; no ^block-id anchors — never built)."""

    claim: str = Field(default="", max_length=4000)
    noteId: int | None = None
    span: str | None = Field(default=None, max_length=4000)


class CitationVerifyInput(BaseModel):
    """``POST /wiki/citations/verify`` body — a batch of citations to post-verify.
    Empty ``claims`` is valid (→ empty results). The agent calls this BEFORE
    presenting its answer; the response flags fabricated/ungrounded citations."""

    claims: list[Citation] = Field(default_factory=list)


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
    # W-Explorer: setting folder = a MOVE (metadata-only; no .md rewrite, id/links
    # survive). None = unchanged; "" = move to root.
    folder: str | None = Field(default=None, max_length=500)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: str | None) -> str | None:
        return v.strip() if v is not None else None

    @field_validator("folder")
    @classmethod
    def _norm_folder(cls, v: str | None) -> str | None:
        return normalize_folder(v) if v is not None else None


# --------------------------------------------------------------------------- #
# WIKI-WRITE-FEEDBACK (#35) — the read-back row a consumer-agent reads to learn  #
# WHY a human overrode its note (so it writes less junk). Self-describing,       #
# agent-readable: every field carries its meaning; reason is the CLOSED enum.    #
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# WIKI IMPORT (#93) — upload/paste .md/.txt → note(s). The paste-JSON shape; the  #
# multipart UploadFile path adapts to the same (filename, content) pairs.          #
# --------------------------------------------------------------------------- #
class ImportFile(BaseModel):
    """One file to import (paste path): a filename (for type/title fallback) + its raw text."""

    filename: str = Field(..., min_length=1, max_length=300, description=".md or .txt name")
    content: str = Field(..., description="the raw file text (md frontmatter+body, or plain txt)")


class ImportInput(BaseModel):
    """``POST /wiki/import`` JSON body (paste path) — one or more files. The multipart UploadFile[]
    path produces the same (filename, content) pairs server-side."""

    files: list[ImportFile] = Field(..., min_length=1, description="files to import (≥1)")


class ImportResultRow(BaseModel):
    """Per-file import result (FROZEN — FE-#93 mirrors). ``ok`` → noteId+title set, error None; a bad
    file → ok False, error carries the agent_error {code,message,hint,retryable}, noteId None."""

    filename: str
    ok: bool
    noteId: int | None = None
    title: str | None = None
    error: dict[str, Any] | None = None


class FeedbackRow(BaseModel):
    """One override-feedback entry (#35): a human edited/deleted an AGENT-written note
    and recorded why. Read-back lean shape for an agent to self-correct."""

    noteId: int = Field(..., description="the note that was overridden")
    reason: OverrideReason = Field(..., description="the CLOSED override reason enum")
    text: str | None = Field(None, description="the human's free-text note (optional — may be null)")
    overriddenAt: str = Field(..., description="ISO-8601 UTC ts of the override op")
    originalTitle: str = Field(
        ..., description="the note's title AT override time (snapshotted into the op — survives a delete)")
    overrideKind: OverrideKind = Field(..., description="edit | delete — which mutation carried the feedback")
