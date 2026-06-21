"""modules/tracing/router.py — Tracing REST + module registration (DAILY-TRACING-P1, #65).

Mounts at ``/tracing`` via the registry (``MODULE``). Locked envelope {success, data, warning?}.
Business logic + derivations live in service.py; this is HTTP shape + status codes only. Errors use
the flat agent_error shape (#46, the standard). No auth — single-user app. No routines in P1.

GET    /tracing                       → the board {date, activities[], heatmap12w[84], score}
POST   /tracing/{activity_id}/log     → log a session {val, dur_min?, note?, date?}; 404 unknown act
POST   /tracing/activities            → 201, create an activity def; 409 duplicate id
PUT    /tracing/activities/{id}       → update a def; 404 if absent
DELETE /tracing/activities/{id}       → archive (soft-delete); 404 if absent
"""

from __future__ import annotations

import logging
import sqlite3

from fastapi import APIRouter

from core.agent_errors import agent_error_response  # #46: flat REST error parity
from core.base import BaseModule
from core.responses import ok

from . import service
from .schema import ActivityInput, ActivityUpdate, LogInput

logger = logging.getLogger("life-os.tracing.router")

router = APIRouter(tags=["tracing"])


@router.get("")
def get_tracing():
    """The whole tracing board for today-VN. honest-mirror: no activities → [] + all-0 score +
    all-0 heatmap (raw-data-first, never fabricated)."""
    return ok(data=service.overview().model_dump())


@router.post("/{activity_id}/log")
def log_session(activity_id: str, body: LogInput):
    """Log one session against an activity (date defaults today-VN; same-day logs ACCUMULATE).
    Returns the activity's freshly-derived view (today/streak reflect the new session). 404 if the
    activity is unknown or archived. (val<0 is a 422 from the schema.)"""
    if service.get_activity(activity_id) is None:
        return agent_error_response("NOT_FOUND", f"activity {activity_id!r} not found",
                                    hint="GET /tracing for valid activity ids")
    view = service.log_session(activity_id, body)
    return ok(data=view.model_dump())


@router.post("/activities", status_code=201)
def create_activity(body: ActivityInput):
    """Create an activity def. 201 + the created def. 409 if the id already exists. (Blank id/name
    or goal<0 is a 422 from the schema.)"""
    try:
        activity = service.create_activity(body)
    except sqlite3.IntegrityError:
        return agent_error_response("CONFLICT", f"activity {body.id!r} already exists",
                                    hint="use PUT /tracing/activities/{id} to update, or a new id")
    return ok(data=activity.model_dump())


@router.put("/activities/{activity_id}")
def update_activity(activity_id: str, body: ActivityUpdate):
    """Update an activity def's supplied fields. 404 if absent. (goal<0 / blank name is a 422.)"""
    activity = service.update_activity(activity_id, body)
    if activity is None:
        return agent_error_response("NOT_FOUND", f"activity {activity_id!r} not found",
                                    hint="GET /tracing for valid activity ids")
    return ok(data=activity.model_dump())


@router.delete("/activities/{activity_id}")
def archive_activity(activity_id: str):
    """Archive (soft-delete) an activity def — its logs stay for history, it drops off the board.
    200 + {archived}. 404 if absent. (DELETE = archive, reversible; single-user.)"""
    if not service.archive_activity(activity_id):
        return agent_error_response("NOT_FOUND", f"activity {activity_id!r} not found",
                                    hint="GET /tracing for valid activity ids")
    return ok(data={"archived": activity_id})


# The registry discovers this MODULE (adding this folder is the only wiring needed). No routines P1.
MODULE = BaseModule(name="tracing", router=router)
