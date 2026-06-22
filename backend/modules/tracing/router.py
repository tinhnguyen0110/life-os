"""modules/tracing/router.py — Tracing REST + module registration (DAILY-TRACING-P1, #65).

Mounts at ``/tracing`` via the registry (``MODULE``). Locked envelope {success, data, warning?}.
Business logic + derivations live in service.py; this is HTTP shape + status codes only. Errors use
the flat agent_error shape (#46, the standard). No auth — single-user app. No routines in P1.

GET    /tracing                       → the board {date, activities[], heatmap12w[84], score}
POST   /tracing/{activity_id}/log     → log a session {val, dur_min?, note?, date?}; 404 unknown act
POST   /tracing/activities            → 201, create an activity def; 409 duplicate id
PUT    /tracing/activities/{id}       → update a def; 404 if absent
DELETE /tracing/activities/{id}       → archive (soft-delete); 404 if absent

TRACING-UX T1 (#109) — task templates (prefill the "new activity" form; SEED ⊕ user override):
GET    /tracing/templates             → merged list [{id,name,goal,unit,emoji,color,source}]
PUT    /tracing/templates/{id}        → upsert a user override (override a seed / add new); 422 bad
DELETE /tracing/templates/{id}        → remove a user template / tombstone a seed; 200
POST   /tracing/templates/bulk-delete → {ids:[...]} bulk remove/hide; 200 {deleted}
POST   /tracing/templates/reset       → delete ALL overrides → pure seed; 200 {reset, count}
"""

from __future__ import annotations

import logging
import sqlite3

from fastapi import APIRouter
from pydantic import BaseModel

from core.agent_errors import agent_error_response  # #46: flat REST error parity
from core.base import BaseModule
from core.responses import ok

from . import service
from .schema import ActivityInput, ActivityUpdate, LogInput, NoteInput, NoteUpdate, TemplateInput

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


@router.delete("/{activity_id}/sessions")
def clear_sessions(activity_id: str, date: str | None = None):
    """#136 UN-TICK (the tick-toggle's un-complete half): delete an activity's session logs for
    ``date`` (default today-VN) → today.done flips FALSE, val→0. Returns
    ``{activityId, date, deletedSessions:N, view}`` (the freshly-derived view so the FE renders
    un-done immediately). 404 if the activity is unknown. 🔴 SCOPED to (activity_id, date) only —
    never another activity/day (#72). honest deletedSessions:0 if there were none."""
    if service.get_activity(activity_id) is None:
        return agent_error_response("NOT_FOUND", f"activity {activity_id!r} not found",
                                    hint="GET /tracing for valid activity ids")
    resolved_date, deleted, view = service.clear_sessions_for_day(activity_id, date)
    return ok(data={"activityId": activity_id, "date": resolved_date,
                    "deletedSessions": deleted, "view": view.model_dump()})


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


# --------------------------------------------------------------------------- #
# TRACING-UX T1 (#109): task templates (prefill the "new activity" form).        #
# Templates are PREFILL ONLY — they never create activities (the FE prefills the  #
# form → POST /tracing/activities does the create). All writes SCOPED to the      #
# tracing_template table (reset/delete NEVER touch real activities/logs).         #
# --------------------------------------------------------------------------- #
class _BulkDeleteBody(BaseModel):
    ids: list[str] = []  # empty → no-op 200


@router.get("/templates")
def list_templates():
    """The merged task-template list (SEED ⊕ user override), each tagged source='seed'|'user'.
    LEAN prefill suggestions {id,name,goal,unit,emoji,color,source}. Same reader.list_templates the
    MCP tracing_templates tool calls → MCP≡REST byte-identical (#24)."""
    templates = [t.model_dump() for t in service.list_templates()]
    return ok(data={"templates": templates})


@router.put("/templates/{template_id}")
def upsert_template(template_id: str, body: TemplateInput):
    """Upsert a user template override (override a seed with the same id, or add a new template).
    200 + the merged Template (source='user'). (Blank name / goal<0 / over-length id is a 422 — the
    path id is bounded below + the body by the schema.) Templates never create activities."""
    tid = (template_id or "").strip()
    if not tid or len(tid) > 64:
        return agent_error_response(
            "INVALID_INPUT", f"template id {template_id!r} invalid",
            hint="template id must be a non-empty slug ≤ 64 chars")
    template = service.upsert_template(tid, body)
    return ok(data=template.model_dump())


@router.delete("/templates/{template_id}")
def delete_template(template_id: str):
    """Delete a template: a USER template → remove its override; a SEED → tombstone it (hidden).
    200 + {deleted}. Idempotent — a non-existent non-seed id still returns 200 (nothing to hide).
    SCOPED to tracing_template (never touches real activities)."""
    changed = service.delete_template(template_id)
    return ok(data={"deleted": template_id, "changed": changed})


@router.post("/templates/bulk-delete")
def bulk_delete_templates(body: _BulkDeleteBody):
    """Bulk-delete templates (#109 bulk-action): each id → user-row-remove or seed-tombstone. 200 +
    {deleted: count}. Empty ids → no-op {deleted:0}; absent non-seed ids skipped (idempotent, no
    error). SCOPED to tracing_template."""
    count = service.bulk_delete_templates(body.ids)
    return ok(data={"deleted": count})


@router.post("/templates/reset")
def reset_templates():
    """RESET all templates to pure SEED: delete every user override row. 200 + {reset, count}.
    🔴 SCOPED — deletes ONLY tracing_template, NEVER the user's real activities/logs (the #72 lesson)."""
    count = service.reset_templates()
    return ok(data={"reset": True, "count": count})


# #124 NOTE: /templates/add-all is declared BEFORE /templates/{template_id}/add so the static path
# is matched first (FastAPI would also disambiguate, but explicit order is clearest).
@router.post("/templates/add-all")
def add_all_templates():
    """#124: add ALL non-hidden templates → today's activities in one call (the user's saved-todo
    list → today). 200 + {created:[Activity], skipped:[ids]}. An already-present id is SKIPPED (no
    dup, honest). honest-empty {created:[], skipped:[]} when there are no templates. SCOPED — reads
    tracing_template + writes tracing_activities only (NOT the rejected auto-seed-into-the-form)."""
    created, skipped = service.add_all_templates()
    return ok(data={"created": [a.model_dump() for a in created], "skipped": skipped})


@router.post("/templates/{template_id}/add")
def add_template_to_today(template_id: str):
    """#124: 1-click "add from my template" → create today's activity from the saved template.
    200 + {activity, added}. added=False when an activity with that id already exists (returns the
    EXISTING, no dup — idempotent). 404 if the template id is unknown. Explicit user action (the
    "+ Từ mẫu" button), NOT the rejected hard-code-chip auto-seed."""
    activity, added = service.add_template_to_today(template_id)
    if activity is None:
        return agent_error_response("NOT_FOUND", f"template {template_id!r} not found",
                                    hint="GET /tracing/templates for valid ids")
    return ok(data={"activity": activity.model_dump(), "added": added})


# --------------------------------------------------------------------------- #
# TRACING-UX2 T1 (#121): day-notes — text + optional remind (note→reminder link).#
# --------------------------------------------------------------------------- #
@router.get("/notes")
def list_notes():
    """All day-notes, newest-first. honest-empty {notes: []} when none (raw-data-first)."""
    return ok(data={"notes": [n.model_dump() for n in service.list_notes()]})


@router.post("/notes", status_code=201)
def create_note(body: NoteInput):
    """Create a day-note (text + optional remind). 201 + the Note. #125: remindDate+remindAt → a
    one-shot future reminder (repeat='once'); 🔴 a PAST one-shot → 422. A note with remindRepeat≠off
    (no date) → the #121 recurring reminder. 422 on blank text / bad HH:MM / bad date (validators)."""
    if service.note_remind_in_past(body.remindDate, body.remindAt):
        return agent_error_response(
            "INVALID_INPUT", f"remind {body.remindDate} {body.remindAt} is in the past",
            hint="a one-shot remindDate+remindAt must be in the FUTURE (VN time)")
    note = service.create_note(body)
    return ok(data=note.model_dump())


@router.put("/notes/{note_id}")
def update_note(note_id: str, body: NoteUpdate):
    """Partial update of a day-note + re-sync the linked reminder. 404 if absent. #125: a PAST
    one-shot remindDate+remindAt → 422. Pass remindRepeat='off' to CLEAR the remind (deletes the
    linked reminder, incl. a one-shot)."""
    # past-date check needs the EFFECTIVE values (merge supplied over current) — only when a one-shot
    # is actually being set (remindDate present in the body or already on the note + a remindAt).
    current = service.get_note(note_id)
    if current is not None:
        eff_date = body.remindDate if body.remindDate is not None else current.remindDate
        eff_at = body.remindAt if body.remindAt is not None else current.remindAt
        # an explicit clear (remindRepeat='off') drops the one-shot → not a past-remind error
        if body.remindRepeat != "off" and service.note_remind_in_past(eff_date, eff_at):
            return agent_error_response(
                "INVALID_INPUT", f"remind {eff_date} {eff_at} is in the past",
                hint="a one-shot remindDate+remindAt must be in the FUTURE (VN time)")
    note = service.update_note(note_id, body)
    if note is None:
        return agent_error_response("NOT_FOUND", f"note {note_id!r} not found",
                                    hint="GET /tracing/notes for valid ids")
    return ok(data=note.model_dump())


@router.delete("/notes/{note_id}")
def delete_note(note_id: str):
    """Delete a day-note + its linked reminder (no orphan). 404 if the note doesn't exist."""
    if not service.delete_note(note_id):
        return agent_error_response("NOT_FOUND", f"note {note_id!r} not found",
                                    hint="GET /tracing/notes for valid ids")
    return ok(data={"deleted": note_id})


# The registry discovers this MODULE (adding this folder is the only wiring needed). No routines P1.
MODULE = BaseModule(name="tracing", router=router)
