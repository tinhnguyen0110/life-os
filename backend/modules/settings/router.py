"""modules/settings/router.py — Settings REST endpoints (S12).

Mounts at ``/settings`` via the registry (``MODULE``). Returns the locked envelope
``{success, data, warning?}``. No routines — this module holds config the OTHER routines
read. Per-field validation lives in the AppConfigPatch schema → a bad PATCH field is a
422 echoing which field (FastAPI's validation error names the field + constraint).

  GET   /settings   the full resolved AppConfig (defaults if nothing persisted)
  PATCH /settings   partial update (only provided keys change) → the new full config
"""

from __future__ import annotations

from fastapi import APIRouter

from core.base import BaseModule
from core.responses import ok

from . import service
from .schema import AppConfigPatch

router = APIRouter(tags=["settings"])


@router.get("")
def get_settings():
    """The full resolved global config (defaults if nothing persisted yet). Never 500
    (fail-open read)."""
    return ok(data=service.get_config().model_dump())


@router.patch("")
def patch_settings(body: AppConfigPatch):
    """Partial update — only the provided keys change. A bad field value (e.g. briefHour
    25, idleThresholdDays 0) is a per-field 422 (FastAPI echoes the field + constraint);
    an unknown field is also 422 (extra=forbid). Returns the new full config."""
    return ok(data=service.set_config(body).model_dump())


MODULE = BaseModule(name="settings", router=router)
