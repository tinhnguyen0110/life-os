"""modules/code_insight/repo_memory.py — durable per-repo memory (REPO-MEMORY-P2, #64).

The Repos/<name> wiki note: a session-agent READS it for curated context (summary/stack/decisions/
lessons/in-progress) + PROPOSES updates to save what it learned. REUSES the wiki note store (read)
+ the wiki propose path (write) — does NOT fork the wiki engine. Pairs with code_insight: a cold
agent does code_insight(X) [fresh now] + repo_memory(X) [curated learned].

The convention: folder = ``Repos``, title = the repo name. READ finds that note (or honest
found:false). WRITE enqueues a wiki proposal (kind=note_create/note_edit) — per #80 a non-root MCP
write enqueues PENDING + won't auto-land until #80 is fixed; the READ + the ENQUEUE both work.
"""

from __future__ import annotations

import logging

from .schema import RepoMemory, RepoMemoryNote

logger = logging.getLogger("life-os.code_insight.repo_memory")

REPOS_FOLDER = "Repos"  # the wiki folder for per-repo memory notes (title = repo name)


def _find_repo_note_id(repo: str) -> int | None:
    """The wiki note id for Repos/<repo> (folder=='Repos', title==repo), or None. Reuses
    wiki_store.all_notes (the cache rows carry folder + title) — a deterministic folder+title match,
    not fuzzy FTS."""
    from modules.wiki import store as wiki_store
    name = (repo or "").strip()
    if not name:
        return None
    try:
        for row in wiki_store.all_notes():
            keys = row.keys()
            folder = row["folder"] if "folder" in keys else ""
            if folder == REPOS_FOLDER and row["title"] == name:
                return int(row["id"])
    except Exception as exc:  # noqa: BLE001 — wiki store unavailable → honest None (caller found:false)
        logger.warning("repo_memory: wiki note lookup failed for %s: %s", repo, exc)
    return None


def get_memory(repo: str) -> RepoMemory:
    """The durable Repos/<repo> memory note, or honest found:false if none written yet. Reads the
    full body via the wiki service get_note (the curated content). NEVER scans the repo (that's
    code_insight); this is the persisted curated half."""
    note_id = _find_repo_note_id(repo)
    if note_id is None:
        return RepoMemory(repo=repo, note=None, found=False)
    from modules.wiki import service as wiki_service
    note = wiki_service.get_note(note_id)
    if note is None:  # cache row but the md is gone (out-of-band) → honest found:false
        return RepoMemory(repo=repo, note=None, found=False)
    return RepoMemory(
        repo=repo,
        note=RepoMemoryNote(id=note.id, title=note.title, body=note.content, updated=note.updated),
        found=True,
    )


def propose_memory(repo: str, body: str, *, actor: str = "agent") -> dict:
    """An agent proposes saving/updating the Repos/<repo> memory note → enqueue a wiki proposal
    (REUSE the wiki propose path, don't fork). kind=note_edit if the note exists (update), else
    note_create (folder=Repos, title=repo). Returns the proposal result.

    #80: the MCP write-through auto-apply is broken for a non-root caller (root-owned data dir) →
    this ENQUEUES the proposal (recorded pending) but it won't auto-LAND until #80 is fixed. The
    enqueue itself is correct + testable; the land is #80-gated."""
    from modules.wiki import proposals_service as wiki_propose
    from modules.wiki.proposals_schema import ProposalCreateInput

    existing_id = _find_repo_note_id(repo)
    if existing_id is not None:
        inp = ProposalCreateInput(
            kind="note_edit", targetId=existing_id, actor=actor,
            payload={"content": body},
            rationale=f"repo_memory update for {repo}",
        )
    else:
        inp = ProposalCreateInput(
            kind="note_create", actor=actor,
            payload={"title": repo, "content": body, "folder": REPOS_FOLDER},
            rationale=f"repo_memory create for {repo}",
        )
    return wiki_propose.create_proposal(inp)
