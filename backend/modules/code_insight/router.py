"""modules/code_insight/router.py — code_insight REST + registration (REPO-MEMORY-P1, #64).

Mounts at ``/code_insight`` via the registry (``MODULE``). Locked envelope {success, data, warning?}.
The on-demand repo read lives in service.py; this is HTTP shape only. No auth (single-user). No
write/routine (P1 = a pure on-demand read). Reuses the dev_activity :ro mounts (no new mount).

GET /code_insight?repo=<name|path>  → the CodeInsight (structure/readme/recentCommits/stack/asOf).
                                       found:false + honest-empty + warning for a missing repo.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from core.base import BaseModule
from core.responses import ok

from . import reader

logger = logging.getLogger("life-os.code_insight.router")

router = APIRouter(tags=["code_insight"])


@router.get("")
def get_code_insight(repo: str = Query(..., min_length=1, description="repo name or path under the :ro roots")):
    """On-demand FRESH read of a repo (structure + README excerpt + recent git-log + stack + asOf)
    for a cold session-agent. honest: missing repo → found:false + honest-empty + warning. Each
    sub-read fail-soft; everything bounded (caps noted in warnings); asOf = the live read time."""
    insight = reader.get_insight(repo)
    warning = "; ".join(insight.warnings) if insight.warnings else None
    return ok(data=insight.model_dump(), warning=warning)


@router.get("/memory")
def get_repo_memory(repo: str = Query(..., min_length=1, description="repo name")):
    """REPO-MEMORY-P2 (#64): the DURABLE curated memory note (Repos/<repo>) a session-agent reads
    for context — summary/stack/decisions/lessons/in-progress. honest found:false if none written
    yet. The WRITE is a wiki propose (POST /wiki/proposals kind=note, folder=Repos) — not a route
    here (reuse the wiki propose tool). Pairs with code_insight (fresh-now + curated-learned)."""
    mem = reader.get_memory(repo)
    return ok(data=mem.model_dump())


# The registry discovers this MODULE (adding this folder is the only wiring — no core/main.py edit).
MODULE = BaseModule(name="code_insight", router=router)
