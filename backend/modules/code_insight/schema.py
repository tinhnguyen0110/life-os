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


# --------------------------------------------------------------------------- #
# REPO-MEMORY-P2 (#64): the DURABLE per-repo memory — a curated Repos/<name>    #
# wiki note an agent READS for context + PROPOSES to update (via the wiki       #
# propose path). FROZEN.                                                         #
# --------------------------------------------------------------------------- #
class RepoMemoryNote(BaseModel):
    """The stored Repos/<name> wiki note (the curated memory)."""

    id: int = Field(..., description="the wiki note id")
    title: str = Field(..., description="the note title (= the repo name)")
    body: str = Field(..., description="the markdown body (summary/stack/decisions/lessons/in-progress)")
    updated: str = Field(..., description="ISO last-updated of the note")


class RepoMemory(BaseModel):
    """repo_memory(repo) read — the durable curated note for a repo, or honest found:false if none
    has been written yet. (The WRITE reuses the wiki propose path; per #80 a non-root MCP write
    enqueues pending and won't auto-land until #80 is fixed — the READ here is unaffected.)"""

    repo: str = Field(..., description="the requested repo")
    note: RepoMemoryNote | None = Field(default=None, description="the Repos/<repo> note, or None")
    found: bool = Field(..., description="whether a Repos/<repo> memory note exists")
