"""modules/career/schema.py — Career cockpit shapes (CAR-1). FROZEN on commit.

Three resources, each persisted as markdown-on-git via md_store:

  - CV         : one living markdown doc (`career/cv.md`) parsed into sections.
  - BlogPost   : `career/blog/<id>.md` — YAML front-matter + body (the dek/notes).
  - DemoItem   : `career/demo/<id>.md` — YAML front-matter + body (description).

frontend/lib/types.ts mirrors these field names + types exactly (FE contract).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

# --------------------------------------------------------------------------- #
# CV                                                                            #
# --------------------------------------------------------------------------- #
# A proof link attaches a CV section to evidence the user can show. `kind` says
# which surface it points at; `ref` is the id/url on that surface.
ProofKind = Literal["case-study", "blog", "demo", "repo", "url"]


class ProofLink(BaseModel):
    """A link from a CV section to a piece of proof (a case study / blog post /
    live demo / repo / external url). Rendered as a clickable chip on the section."""

    kind: ProofKind
    label: str = Field(..., min_length=1, max_length=200)
    ref: str = Field(..., min_length=1, max_length=500, description="id (blog/demo) or url")


class CvSection(BaseModel):
    """One parsed section of the CV (an H2 block from the markdown). `body` is the
    raw markdown under the heading; `proof` are the evidence chips attached to it."""

    id: str = Field(..., min_length=1, description="slug of the heading")
    heading: str = Field(..., min_length=1)
    level: int = Field(2, ge=1, le=6, description="markdown heading level")
    body: str = Field("", description="raw markdown under the heading")
    proof: list[ProofLink] = Field(default_factory=list)


class CvMeta(BaseModel):
    """CV header block — name/title/contact, parsed from the top of the doc."""

    name: str = ""
    title: str = ""
    contact: str = ""


class Cv(BaseModel):
    """The full living CV: header meta + ordered sections + bookkeeping."""

    meta: CvMeta = Field(default_factory=CvMeta)  # #57: removed stale type:ignore (was unused)
    sections: list[CvSection] = Field(default_factory=list)
    updatedAt: str | None = None
    seeded: bool = Field(False, description="True if seeded from the source CV (vs user-created)")


class CvUpdateInput(BaseModel):
    """PUT /career/cv body — replace the CV's raw markdown (the export/edit path)."""

    markdown: str = Field(..., min_length=1, max_length=200_000)


# --------------------------------------------------------------------------- #
# Blog                                                                          #
# --------------------------------------------------------------------------- #
BlogStatus = Literal["draft", "published"]


class BlogPost(BaseModel):
    """A blog post's metadata (the body holds the dek / notes, NOT the full article).

    Mirrors the shape of the user's blog/*.js drafts: title/subtitle/tags/date/
    readMinutes + a status (draft|published) and an optional public url.
    """

    id: str
    title: str
    subtitle: str = ""
    dek: str = ""
    status: BlogStatus = "draft"
    url: str | None = None
    tags: list[str] = Field(default_factory=list)
    publishedDate: str | None = None
    readMinutes: int | None = Field(None, ge=0)
    wordCount: int | None = Field(None, ge=0)
    createdAt: str
    updatedAt: str


class BlogInput(BaseModel):
    """POST/PUT body for a blog post. id + timestamps are server-set."""

    title: str = Field(..., min_length=1, max_length=300)
    subtitle: str = Field("", max_length=500)
    dek: str = Field("", max_length=2000)
    status: BlogStatus = "draft"
    url: str | None = Field(None, max_length=500)
    tags: list[str] = Field(default_factory=list)
    publishedDate: str | None = Field(None, max_length=64)
    readMinutes: int | None = Field(None, ge=0, le=1000)
    wordCount: int | None = Field(None, ge=0)

    @model_validator(mode="after")
    def _strip_title(self) -> "BlogInput":
        if not self.title.strip():
            raise ValueError("title must not be whitespace-only")
        return self


# --------------------------------------------------------------------------- #
# Demo / showcase                                                               #
# --------------------------------------------------------------------------- #
DemoStatus = Literal["live", "wip", "offline"]


class DemoItem(BaseModel):
    """A live demo / flagship project in the showcase."""

    id: str
    name: str
    tagline: str = ""
    desc: str = ""
    url: str | None = None
    repo: str | None = None
    status: DemoStatus = "live"
    tags: list[str] = Field(default_factory=list)
    loc: int | None = Field(None, ge=0, description="approx lines of code, if known")
    createdAt: str
    updatedAt: str


class DemoInput(BaseModel):
    """POST/PUT body for a demo item. id + timestamps are server-set."""

    name: str = Field(..., min_length=1, max_length=200)
    tagline: str = Field("", max_length=500)
    desc: str = Field("", max_length=4000)
    url: str | None = Field(None, max_length=500)
    repo: str | None = Field(None, max_length=500)
    status: DemoStatus = "live"
    tags: list[str] = Field(default_factory=list)
    loc: int | None = Field(None, ge=0)

    @model_validator(mode="after")
    def _strip_name(self) -> "DemoInput":
        if not self.name.strip():
            raise ValueError("name must not be whitespace-only")
        return self
