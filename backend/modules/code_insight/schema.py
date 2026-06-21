"""modules/code_insight/schema.py — code_insight shapes (REPO-MEMORY-P1, #64).

The FROZEN CodeInsight contract (MCP + FE mirror THIS). An on-demand repo read: bounded structure +
bounded README excerpt + bounded recent git-log + detected stack + asOf (the live read timestamp).
honest: missing repo → found:false + honest-empty; each sub-read fail-soft (its field empty + a
warning); asOf always set; everything bounded (capped + the cap noted in a warning). Agent-first —
lean, self-describing, asOf-tagged so a cold agent can act + trust the freshness.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RepoCommit(BaseModel):
    """One recent commit (bounded list)."""

    sha: str = Field(..., description="short commit sha")
    msg: str = Field(..., description="commit subject (first line)")
    date: str = Field(..., description="commit date (ISO or git's short date)")


class CodeInsight(BaseModel):
    """GET /code_insight + MCP code_insight — the on-demand repo read. honest-empty when found:false."""

    repo: str = Field(..., description="the requested repo (name or path)")
    root: str = Field(default="", description="the resolved absolute repo path ('' if not found)")
    found: bool = Field(..., description="whether the repo resolved to a readable git repo")
    structure: list[str] = Field(default_factory=list,
                                 description="top-level entries (bounded; dirs end with /), .git/node_modules/etc skipped")
    readme: str | None = Field(default=None, description="README excerpt (bounded), or None if no README")
    recentCommits: list[RepoCommit] = Field(default_factory=list,
                                            description="recent commits, newest-first (bounded)")
    stack: list[str] = Field(default_factory=list,
                             description="detected stack (node/python/go/rust/...) from manifest files")
    asOf: str = Field(..., description="ISO timestamp of THIS read (live, always-current — honest freshness)")
    warnings: list[str] = Field(default_factory=list,
                                description="honest non-fatal issues: not-found / sub-read failed / bounded-truncation")
