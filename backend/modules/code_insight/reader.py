"""modules/code_insight/reader.py — code_insight READ surface (REPO-MEMORY-P1, #64).

The read-only entrypoint the router + the MCP code_insight tool call. code_insight is an on-demand
LIVE read (the work is in service.code_insight); this reader is the thin, named read-surface (parity
with the other modules' reader.py). NO writes; NO recomputation outside service.
"""

from __future__ import annotations

from . import repo_memory, service
from .schema import CodeInsight, RepoMemory


def get_insight(repo: str) -> CodeInsight:
    """The on-demand insight for ``repo`` (name or path under the :ro roots). honest found:false on
    a missing repo. Delegates to the live service read (always-current, never indexed)."""
    return service.code_insight(repo)


def get_memory(repo: str) -> RepoMemory:
    """REPO-MEMORY-P2 (#64): the durable Repos/<repo> curated memory note, or honest found:false.
    Delegates to repo_memory (reuses the wiki note store — the read half; the write is a wiki
    propose)."""
    return repo_memory.get_memory(repo)
