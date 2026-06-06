"""modules/projects/router.py — Projects REST endpoints (Sprint 1, T2/T3).

Mounts at ``/projects`` via the registry (``MODULE`` below). Five endpoints, all
returning the locked envelope ``{success, data, warning?}`` via core.responses.
Business logic lives in service.py; this layer is HTTP shape + status codes only.

T3 also lives here: ``MODULE.routines()`` hands the scheduler the ``wiki-refresh``
routine (re-read git + persist lastAuto over all tracked projects, every 6h).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from core.base import BaseModule, Routine
from core.responses import ok

from . import service
from .schema import ProjectAbandonInput, ProjectRegisterInput

logger = logging.getLogger("life-os.projects.router")

router = APIRouter(tags=["projects"])

# The routine this module contributes to the scheduler (T3).
WIKI_REFRESH_ID = "wiki-refresh"


def _summary(statuses: list) -> dict:
    """Counts by health for the S2 summary bar — computed server-side (raw-first)."""
    counts = {"act": 0, "slow": 0, "stall": 0, "dead": 0}
    for s in statuses:
        counts[s.health] = counts.get(s.health, 0) + 1
    counts["total"] = len(statuses)
    return counts


def _attach_routines(status):
    """Reflect the wiki-refresh routine on the returned status (shape accuracy)."""
    if WIKI_REFRESH_ID not in status.routines:
        return status.model_copy(update={"routines": [*status.routines, WIKI_REFRESH_ID]})
    return status


@router.get("")
def list_projects():
    """All tracked, non-abandoned projects + a health summary. EXCLUDES abandoned."""
    statuses, warnings = service.list_projects()
    statuses = [_attach_routines(s) for s in statuses]
    data = {
        "projects": [s.model_dump() for s in statuses],
        "summary": _summary(statuses),
    }
    warning = "; ".join(warnings) if warnings else None
    return ok(data=data, warning=warning)


@router.get("/{project_id}")
def get_project(project_id: str):
    """One project (INCLUDES abandoned). 404 if the id is not tracked."""
    status = service.get_project(project_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"project {project_id!r} not found")
    return ok(data=_attach_routines(status).model_dump())


@router.post("")
def register_project(body: ProjectRegisterInput):
    """Register a project: write its status.md (one commit) + return fresh status.

    400 if repo path is not an existing git repo; 409 if id already exists.
    """
    try:
        status = service.register_project(body)
    except service.ProjectError as exc:
        raise HTTPException(status_code=exc.code, detail=str(exc)) from exc
    return ok(data=_attach_routines(status).model_dump())


@router.post("/{project_id}/refresh")
def refresh_project(project_id: str):
    """Re-read git, stamp lastAuto into status.md (one commit). 404 if unknown."""
    status = service.refresh_project(project_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"project {project_id!r} not found")
    return ok(data=_attach_routines(status).model_dump())


@router.post("/{project_id}/abandon")
def abandon_project(project_id: str, body: ProjectAbandonInput):
    """Flag a project abandoned (graveyard) in status.md, with optional lesson.
    404 if unknown. Orthogonal to health — the commit-age health field is untouched.
    """
    status = service.abandon_project(project_id, body)
    if status is None:
        raise HTTPException(status_code=404, detail=f"project {project_id!r} not found")
    return ok(data=_attach_routines(status).model_dump())


@router.post("/{project_id}/restore")
def restore_project(project_id: str):
    """Un-graveyard a project: clear abandoned* + lesson → rejoins list_projects.
    404 if unknown. Idempotent: restoring a non-abandoned project is a 200 no-op.
    """
    status = service.restore_project(project_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"project {project_id!r} not found")
    return ok(data=_attach_routines(status).model_dump())


# --------------------------------------------------------------------------- #
# T3 — the wiki-refresh routine (rule-based, no AI; read-only git + md_store).  #
# --------------------------------------------------------------------------- #
def wiki_refresh() -> None:
    """Re-read every tracked project's git state + persist lastAuto. Idempotent.

    Fail-open per project: one unreadable repo never aborts the sweep. Cheap local
    git reads only — NEVER pulls. Same code path as POST /{id}/refresh.
    """
    statuses, _ = service.list_projects()
    refreshed = 0
    for status in statuses:
        try:
            service.refresh_project(status.id)
            refreshed += 1
        except Exception as exc:  # per-project fail-open — never crash the routine
            logger.error("wiki-refresh: project %r failed: %s", status.id, exc)
    logger.info("wiki-refresh swept %d project(s)", refreshed)


_WIKI_REFRESH_ROUTINE = Routine(
    id=WIKI_REFRESH_ID,
    func=wiki_refresh,
    trigger="interval",
    trigger_args={"hours": 6},
    name="wiki-refresh (re-read project git every 6h)",
    enabled=True,
)


MODULE = BaseModule(name="projects", router=router, routines=[_WIKI_REFRESH_ROUTINE])
