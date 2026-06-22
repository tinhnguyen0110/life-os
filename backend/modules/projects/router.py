"""modules/projects/router.py — Projects REST endpoints (Sprint 1, T2/T3).

Mounts at ``/projects`` via the registry (``MODULE`` below). Five endpoints, all
returning the locked envelope ``{success, data, warning?}`` via core.responses.
Business logic lives in service.py; this layer is HTTP shape + status codes only.

T3 also lives here: ``MODULE.routines()`` hands the scheduler the ``wiki-refresh``
routine (re-read git + persist lastAuto over all tracked projects, every 6h).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from core.agent_errors import ErrorCode, agent_error_response  # AGENT-ERROR-P4 (#46): flat REST error parity
from core.base import BaseModule, Routine
from core.responses import ok

# AGENT-ERROR-P4: map a ProjectError's HTTP code → the agent_error enum (400 bad-input, 409 conflict).
_PROJECT_ERR_CODE: dict[int, ErrorCode] = {400: "INVALID_INPUT", 409: "CONFLICT"}

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
        return agent_error_response(
            "NOT_FOUND", f"project {project_id!r} not found",
            hint="use the .id field from GET /projects (not .name); ids are matched "
                 "case-insensitively, so any case of a real id resolves")
    return ok(data=_attach_routines(status).model_dump())


@router.get("/{project_id}/context")
def get_project_context(project_id: str):
    """PROJECT-MEMORY (#42): a project's full context for an agent — its metadata + its accumulated
    wiki notes (tagged ``project:<id>``) as "project memory". ``{project, notes:[{id,title,status,
    updated,snippet}], noteCount}``. A project with zero tagged notes → ``notes: []`` (honest-empty);
    an untracked project → 404. Same ``service.get_context`` the MCP ``project_context`` tool calls →
    MCP≡REST byte-identical (#24). project_get stays lean; this is the 'everything about X' call."""
    ctx = service.get_context(project_id)
    if ctx is None:
        return agent_error_response(
            "NOT_FOUND", f"project {project_id!r} not found",
            hint="use the .id field from GET /projects (not .name); ids are matched "
                 "case-insensitively, so any case of a real id resolves")
    return ok(data=ctx)


@router.get("/{project_id}/dev-activity")
def get_project_dev_activity(project_id: str, days: int = 90):
    """PROJECTS-UNIFY T1 (#112): a project's dev-activity, JOINED by slug(dev_activity.repo)==project_id
    (projects use lowercase slugs; dev_activity stores raw basenames — the join normalizes at READ).
    ``{projectId, found, commits, locNet, lastActiveDay, days, activeDays, matches[], reason?, warning?}``.
    HONEST: a project whose repo is NOT in the dev_activity scan → found=false + commits=0 + reason
    (NOT a fabricated 0). A slug-collision (≥2 repos same basename) → found=true, summed, + matches[] +
    warning. 200 always (found=false is a valid honest answer, not a 404). Same service.dev_stat_for_project
    the MCP ``project_dev_activity`` tool calls → MCP≡REST byte-identical (#24). ``days`` clamped to ≥1."""
    stat = service.dev_stat_for_project(project_id, days=days)
    return ok(data=stat.model_dump())


@router.post("")
def register_project(body: ProjectRegisterInput):
    """Register a project: write its status.md (one commit) + return fresh status.

    400 if repo path is not an existing git repo; 409 if id already exists.
    """
    try:
        status = service.register_project(body)
    except service.ProjectError as exc:
        # #46-P4: map the ProjectError HTTP code → agent_error enum (400 not-git-repo→INVALID_INPUT,
        # 409 id-exists→CONFLICT). RETURN the flat error (not raise).
        return agent_error_response(_PROJECT_ERR_CODE.get(exc.code, "INVALID_INPUT"), str(exc),
                                    hint="check the repo path exists + is a git repo, and the id is unique")
    return ok(data=_attach_routines(status).model_dump())


@router.post("/{project_id}/refresh")
def refresh_project(project_id: str):
    """Re-read git, stamp lastAuto into status.md (one commit). 404 if unknown."""
    status = service.refresh_project(project_id)
    if status is None:
        return agent_error_response("NOT_FOUND", f"project {project_id!r} not found",
                                    hint="GET /projects for valid ids")
    return ok(data=_attach_routines(status).model_dump())


@router.post("/{project_id}/abandon")
def abandon_project(project_id: str, body: ProjectAbandonInput):
    """Flag a project abandoned (graveyard) in status.md, with optional lesson.
    404 if unknown. Orthogonal to health — the commit-age health field is untouched.
    """
    status = service.abandon_project(project_id, body)
    if status is None:
        return agent_error_response("NOT_FOUND", f"project {project_id!r} not found",
                                    hint="GET /projects for valid ids")
    return ok(data=_attach_routines(status).model_dump())


@router.post("/{project_id}/restore")
def restore_project(project_id: str):
    """Un-graveyard a project: clear abandoned* + lesson → rejoins list_projects.
    404 if unknown. Idempotent: restoring a non-abandoned project is a 200 no-op.
    """
    status = service.restore_project(project_id)
    if status is None:
        return agent_error_response("NOT_FOUND", f"project {project_id!r} not found",
                                    hint="GET /projects for valid ids")
    return ok(data=_attach_routines(status).model_dump())


# --------------------------------------------------------------------------- #
# T3 — the wiki-refresh routine (rule-based, no AI; read-only git + md_store).  #
# --------------------------------------------------------------------------- #
def _wiki_refresh_work() -> tuple[str, str]:
    """Re-read every tracked project's git + persist lastAuto. Returns (status, detail).

    Fail-open per project: one unreadable repo never aborts the sweep. NEVER pulls.

    WIKI-RECONCILE (#53): after the primary sweep, a FAIL-SOFT self-heal add-on runs reindex_all() —
    prunes orphan wiki cache rows (md gone) so the tree can't drift-lie over time. Per
    fail-closed-write-fail-soft-addon: the primary status is decided BEFORE the add-on, so a reindex
    error can NEVER fail the project sweep that already succeeded — it's noted in the detail only.
    """
    statuses, _ = service.list_projects()
    refreshed = 0
    for status in statuses:
        try:
            service.refresh_project(status.id)
            refreshed += 1
        except Exception as exc:  # per-project fail-open
            logger.error("wiki-refresh: project %r failed: %s", status.id, exc)
    # primary status decided HERE, before the add-on (the add-on can only ANNOTATE the detail).
    detail = f"wiki-refresh swept {refreshed} project(s)"
    try:
        from modules.wiki import reader as wiki_reader
        rec = wiki_reader.reindex_all()
        if rec["dropped"]:
            detail += f"; wiki-reconcile pruned {rec['dropped']} orphan note(s) {rec['droppedIds']}"
    except Exception as exc:  # noqa: BLE001 — fail-soft: a reconcile error must NOT fail the sweep
        logger.warning("wiki-refresh: reconcile add-on failed (sweep still OK): %s", exc)
        detail += "; wiki-reconcile ERR (skipped)"
    return "ok", detail


def wiki_refresh() -> None:
    """Scheduler entry point — runs the sweep via the unified run-record wrapper, gated on
    the master automation switch (S12; no-ops when off). S10A: shares the wrapper."""
    from modules.automation import service as auto
    auto.run_scheduled(WIKI_REFRESH_ID, _wiki_refresh_work)


_WIKI_REFRESH_ROUTINE = Routine(
    id=WIKI_REFRESH_ID,
    func=wiki_refresh,
    trigger="interval",
    trigger_args={"hours": 6},
    name="wiki-refresh (re-read project git every 6h)",
    enabled=True,
)


# --------------------------------------------------------------------------- #
# S10A — idle-hunter + pattern-check routines (owned by projects, the data home).
# The scheduler entry points wrap the decided algorithms (in automation.service)
# via record_routine_run so each timer fire records a run_log row. Lazy import of
# automation.service inside the func avoids a module-load import cycle.
# --------------------------------------------------------------------------- #
def _idle_hunter_job() -> None:
    # Gated on the master automation switch (S12) — no-ops when automation is off.
    from modules.automation import service as auto
    auto.run_scheduled("idle-hunter", auto.idle_hunter)


def _pattern_check_job() -> None:
    # Gated on BOTH the master switch AND the per-routine patternCheckEnabled (S12).
    from modules.automation import service as auto
    if not auto.pattern_check_on():
        logger.info("pattern-check disabled in settings — skipping")
        return
    auto.run_scheduled("pattern-check", auto.pattern_check)


_IDLE_HUNTER_ROUTINE = Routine(
    id="idle-hunter", func=_idle_hunter_job, trigger="cron",
    trigger_args={"hour": 22}, name="Idle Hunter", enabled=True,
)
_PATTERN_CHECK_ROUTINE = Routine(
    id="pattern-check", func=_pattern_check_job, trigger="cron",
    trigger_args={"hour": 9}, name="Pattern Check", enabled=True,
)


MODULE = BaseModule(
    name="projects", router=router,
    routines=[_WIKI_REFRESH_ROUTINE, _IDLE_HUNTER_ROUTINE, _PATTERN_CHECK_ROUTINE],
)
