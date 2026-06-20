"""modules/settings/router.py — Settings REST endpoints (S12).

Mounts at ``/settings`` via the registry (``MODULE``). Returns the locked envelope
``{success, data, warning?}``. No routines — this module holds config the OTHER routines
read. Per-field validation lives in the AppConfigPatch schema → a bad PATCH field is a
422 echoing which field (FastAPI's validation error names the field + constraint).

  GET   /settings   the full resolved AppConfig (defaults if nothing persisted)
  PATCH /settings   partial update (only provided keys change) → the new full config
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter
from pydantic import BaseModel, Field

from core.base import BaseModule
from core.config import settings as app_settings
from core.responses import ok

from . import service
from .schema import AppConfigPatch

router = APIRouter(tags=["settings"])


class PrivacyVerify(BaseModel):
    """#74: the FE's privacy-reveal attempt. JSON field is ``pass`` (the natural name);
    the Python attr is ``passcode`` because ``pass`` is a keyword. populate_by_name lets
    either work. The stored pass NEVER goes to the FE — the FE sends the attempt, the BE
    compares + answers ok/not."""

    model_config = {"populate_by_name": True}

    passcode: str = Field(default="", alias="pass", description="the reveal-pass attempt")


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


@router.post("/privacy/verify")
def verify_privacy_pass(body: PrivacyVerify):
    """#74: compare the FE's reveal-pass attempt to the env-stored pass
    (LIFEOS_PRIVACY_PASS, default "0110") → ``{ok: bool}``. The pass NEVER leaves the BE
    (the FE sends the attempt, gets ok/not). Constant-time compare (hmac.compare_digest)
    so the answer time doesn't leak the pass. A simple display veil for single-user
    localhost — NOT access control.
    # public + unlimited because single-user localhost veil (no auth / no rate-limit)
    """
    ok_match = hmac.compare_digest(body.passcode, app_settings.privacy_pass)
    return ok(data={"ok": ok_match})


MODULE = BaseModule(name="settings", router=router)
